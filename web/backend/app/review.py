"""Private, auditable operator review of uncertain ANPR observations."""

import base64
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from detector import find_plate_candidates

from . import settings
from . import db as database
from . import storage

_LOCK = threading.RLock()
logger = logging.getLogger(__name__)
VEHICLE_COLORS = {"Black", "White", "Silver", "Grey", "Blue", "Red", "Green", "Brown", "Yellow", "Other"}
LOCAL_OCR_AUTO_ACCEPT_THRESHOLD = 0.94
save_detections = database.save_detections


def _now():
    return datetime.now(timezone.utc).isoformat()


def _connect():
    return database.connect(settings.REVIEW_DB, timeout=15)


@contextmanager
def _db():
    with _LOCK:
        connection = _connect()
        with database.transaction(connection):
            yield connection


def init_db():
    if not database.postgres_enabled():
        settings.REVIEW_DB.parent.mkdir(parents=True, exist_ok=True)
    with _db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                prediction TEXT NOT NULL,
                final_plate TEXT,
                detector_score REAL NOT NULL,
                ocr_score REAL,
                match_score REAL,
                alternatives TEXT NOT NULL,
                reasons TEXT NOT NULL,
                provider TEXT,
                provider_read TEXT,
                camera_id TEXT NOT NULL,
                location TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                image_path TEXT NOT NULL,
                crop_path TEXT,
                source_name TEXT,
                hits INTEGER,
                video_time REAL,
                reviewer TEXT,
                reviewed_at TEXT,
                vehicle_color TEXT
            )
        """)
        if database.is_postgres(connection):
            connection.execute(
                "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vehicle_color TEXT"
            )
        else:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(reviews)")}
            if "vehicle_color" not in columns:
                connection.execute("ALTER TABLE reviews ADD COLUMN vehicle_color TEXT")


def _gemini_read(crop_path, key):
    """Second opinion on one crop. Never treat model output as verified."""
    try:
        encoded = base64.b64encode(Path(crop_path).read_bytes()).decode("ascii")
        payload = json.dumps({
            "contents": [{"parts": [
                {"text": (
                    "Read the vehicle registration printed on this number plate. "
                    "Return only the exact visible uppercase letters and digits, "
                    "without spaces or punctuation. If any character is unclear, "
                    "return UNREADABLE. Do not infer or complete missing characters."
                )},
                {"inline_data": {"mime_type": "image/jpeg", "data": encoded}},
            ]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 256},
        }).encode("utf-8")
        request = Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
            data=payload,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            data = json.load(response)
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        raw = "".join(part.get("text", "") for part in parts).strip().upper()
        if raw == "UNREADABLE":
            return "Gemini 3.8 Flash", None
        cleaned = "".join(char for char in raw if char.isalnum())
        if not 8 <= len(cleaned) <= 12:
            return "Gemini 3.8 Flash", None
        candidates = list(find_plate_candidates(cleaned))
        exact = [candidate for candidate, score in candidates if len(candidate) == len(cleaned) and score >= 7]
        return "Gemini 3.8 Flash", exact[0] if exact else None
    except HTTPError as error:
        try:
            response = json.loads(error.read().decode("utf-8", "replace"))
            message = str(response.get("error", {}).get("message", ""))
        except (ValueError, AttributeError):
            message = ""
        if "denied access" in message.lower():
            reason = "project access denied"
        elif error.code in {401, 403}:
            reason = "API key or project permission denied"
        else:
            reason = f"HTTP {error.code}"
        logger.warning("Gemini request rejected (%s): %s", reason, message[:240])
        return f"Gemini unavailable: {reason}", None
    except (OSError, ValueError, KeyError, IndexError, URLError, TimeoutError):
        logger.exception("Gemini request failed")
        return "Gemini 3.8 Flash (unavailable)", None


def _vision_read(crop_path, key):
    """Optional Cloud Vision OCR for operators with a separate Vision key."""
    try:
        encoded = base64.b64encode(Path(crop_path).read_bytes()).decode("ascii")
        payload = json.dumps({"requests": [{
            "image": {"content": encoded},
            "features": [{"type": "TEXT_DETECTION", "maxResults": 5}],
        }]}).encode("utf-8")
        request = Request(
            "https://vision.googleapis.com/v1/images:annotate",
            data=payload,
            headers={"Content-Type": "application/json", "X-goog-api-key": key},
            method="POST",
        )
        with urlopen(request, timeout=8) as response:
            data = json.load(response)
        annotations = data.get("responses", [{}])[0].get("textAnnotations", [])
        if annotations:
            cleaned = "".join(char for char in annotations[0].get("description", "").upper() if char.isalnum())
            candidates = list(find_plate_candidates(cleaned))
            if candidates:
                return "Google Cloud Vision", max(candidates, key=lambda item: item[1])[0]
        return "Google Cloud Vision", None
    except (OSError, ValueError, KeyError, URLError, TimeoutError):
        return "Google Cloud Vision (unavailable)", None


def _provider_read(crop_path):
    """Use only a saved plate crop with a configured server-side provider."""
    if not crop_path or not Path(crop_path).is_file():
        return None, None
    gemini_key = settings.get_gemini_key()
    if gemini_key:
        return _gemini_read(crop_path, gemini_key)
    vision_key = os.environ.get("ANPR_GOOGLE_VISION_API_KEY", "").strip()
    if vision_key:
        return _vision_read(crop_path, vision_key)
    return "Gemini not configured", None


def _safe_provider_read(crop_path):
    """Keep provider failures isolated to one observation."""
    try:
        return _provider_read(crop_path)
    except Exception:
        logger.exception("Second plate reader failed")
        return None, None


def _provider_read_for_detection(detection):
    """Skip Gemini only when the local OCR score exceeds the auto-save threshold."""
    try:
        ocr_score = float(detection.get("ocr_confidence"))
    except (TypeError, ValueError):
        ocr_score = 0.0

    if ocr_score > LOCAL_OCR_AUTO_ACCEPT_THRESHOLD:
        return "Skipped: local OCR >94%; Gemini not called", None

    return _safe_provider_read(detection.get("cropped_plate"))


def _row_dict(row):
    result = dict(row)
    result["alternatives"] = json.loads(result["alternatives"])
    result["reasons"] = json.loads(result["reasons"])
    result["evidence"] = Path(result["crop_path"]).name if result["crop_path"] else None
    result["frame"] = Path(result["image_path"]).name if result["image_path"] else None
    result.pop("crop_path")
    result.pop("image_path")
    return result


def ingest(detections):
    """Save clear or Gemini-corroborated reads; queue unresolved observations."""
    init_db()
    created = []
    saved_count = 0
    if detections:
        # Do provider I/O before taking the review database lock. Bounded
        # concurrency keeps video batches responsive without flooding APIs.
        with ThreadPoolExecutor(max_workers=min(4, len(detections))) as pool:
            provider_results = list(pool.map(
                _provider_read_for_detection,
                detections,
            ))
    else:
        provider_results = []

    if database.postgres_enabled():
        if not storage.configured():
            raise RuntimeError(
                "Supabase Storage is not configured; evidence cannot be persisted."
            )
        for detection in detections:
            for field in ("image_path", "cropped_plate"):
                local_path = detection.get(field)
                if local_path:
                    reference = storage.upload_file(local_path)
                    if reference:
                        detection[field] = reference

    with _db() as connection:
        for detection, (provider, provider_read) in zip(detections, provider_results):
            prediction = detection["plate_number"]
            detector_score = float(detection.get("confidence", 0))
            ocr_score = detection.get("ocr_confidence")
            local_ocr_auto_accept = (
                ocr_score is not None
                and float(ocr_score) > LOCAL_OCR_AUTO_ACCEPT_THRESHOLD
            )
            match_score = detection.get("match_confidence")
            reasons = list(detection.get("review_reasons", []))
            if detector_score < .5:
                reasons.append("Detector score below 50%")
            if ocr_score is None or float(ocr_score) < .5:
                reasons.append("OCR score below 50% or unavailable")
            if match_score is not None and float(match_score) < .5:
                reasons.append("Video correlation score below 50%")
            if detection.get("video_time") is not None and detection.get("hits", 0) < 2:
                reasons.append("Plate read in only one sampled video frame")

            if not local_ocr_auto_accept:
                gemini_configured = bool(settings.get_gemini_key())
                if not gemini_configured:
                    reasons.append("Gemini plate verification is not configured")
                elif provider != "Gemini 3.8 Flash" or not provider_read:
                    reasons.append("Gemini plate reading unavailable")

            # A local OCR quality score above 94% can bypass Gemini. Lower
            # scores require an agreeing Gemini read; disagreement or provider
            # failure keeps the observation in the operator review queue.
            if provider_read and provider_read != prediction:
                reasons.append("Gemini plate read disagrees")

            gemini_agrees = (
                provider == "Gemini 3.8 Flash"
                and provider_read == prediction
            )
            status = (
                "accepted"
                if local_ocr_auto_accept or gemini_agrees
                else "pending"
            )
            review_id = uuid.uuid4().hex
            if status == "accepted":
                saved_count += save_detections([detection])
            connection.execute("""
                INSERT INTO reviews (
                    id, created_at, status, prediction, final_plate,
                    detector_score, ocr_score, match_score, alternatives, reasons,
                    provider, provider_read, camera_id, location, observed_at,
                    image_path, crop_path, source_name, hits, video_time,
                    reviewer, reviewed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                review_id, _now(), status, prediction,
                prediction if status == "accepted" else None,
                detector_score, ocr_score, match_score,
                json.dumps(detection.get("alternatives", [prediction])),
                json.dumps(reasons), provider, provider_read,
                detection["camera_id"], detection["location"],
                detection["timestamp"], detection["image_path"],
                detection.get("cropped_plate"), detection.get("source_name"),
                detection.get("hits"), detection.get("video_time"),
                None, None,
            ))
            created.append({
                **detection,
                "review_id": review_id,
                "review_status": status,
                "review_reasons": reasons,
                "provider": provider,
                "provider_read": provider_read,
            })
    return {"detections": created, "saved_count": saved_count,
            "pending_count": sum(item["review_status"] == "pending" for item in created)}


def list_pending():
    init_db()
    with _db() as connection:
        rows = connection.execute(
            "SELECT * FROM reviews WHERE status = 'pending' ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    items = [_row_dict(row) for row in rows]
    if not settings.get_gemini_key():
        for item in items:
            if item.get("provider") is None:
                item["provider"] = "Gemini not configured"
    history = database.read_detections()
    if history.empty:
        return items
    # These are context suggestions, never automatic identity matches.
    recent = history.tail(2000)
    for item in items:
        related = []
        observed_at = datetime.strptime(item["observed_at"], "%Y-%m-%d %H:%M:%S")
        for _, observation in recent.iloc[::-1].iterrows():
            seen = str(observation.get("Plate Number", ""))
            if seen[:6] != item["prediction"][:6]:
                continue
            if len(seen) != len(item["prediction"]):
                continue
            if sum(a != b for a, b in zip(seen, item["prediction"])) > 2:
                continue
            try:
                recorded_at = datetime.strptime(
                    f"{observation['Date']} {observation['Time']}",
                    "%d-%m-%Y %I:%M:%S %p",
                )
            except (ValueError, KeyError):
                continue
            if abs((observed_at - recorded_at).total_seconds()) > 24 * 3600:
                continue
            related.append({
                "plate": seen,
                "camera_id": str(observation.get("Camera ID", "")),
                "location": str(observation.get("Location", "")),
                "recorded": f"{observation.get('Date', '')} {observation.get('Time', '')}",
                "character_matches": sum(a == b for a, b in zip(seen, item["prediction"])),
                "minutes_apart": round(abs((observed_at - recorded_at).total_seconds()) / 60),
                "time_relation": "before" if recorded_at <= observed_at else "after",
            })
            if len(related) == 3:
                break
        item["related_observations"] = related
    return items


def decide(review_id, action, plate, reviewer, vehicle_color=None):
    """Confirm a corrected plate or reject an observation exactly once."""
    if action not in {"confirm", "reject"}:
        raise ValueError("Action must be confirm or reject.")
    if vehicle_color and vehicle_color not in VEHICLE_COLORS:
        raise ValueError("Choose a supported vehicle colour.")
    init_db()
    with _db() as connection:
        row = connection.execute(
            "SELECT * FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
        if row is None:
            raise LookupError("Review item not found.")
        if row["status"] != "pending":
            raise ValueError("This observation has already been reviewed.")
        if action == "confirm":
            normalized = "".join(char for char in plate.upper() if char.isalnum())
            valid_plate = any(
                candidate == normalized and score >= 5
                for candidate, score in find_plate_candidates(normalized)
            )
            if (
                not 8 <= len(normalized) <= 11
                or normalized != plate.strip().upper()
                or not valid_plate
            ):
                raise ValueError("Enter a valid Indian registration without spaces or symbols.")
            save_detections([{
                "plate_number": normalized,
                "image_path": row["image_path"],
                "camera_id": row["camera_id"],
                "location": row["location"],
                "confidence": row["detector_score"],
                "timestamp": row["observed_at"],
            }])
            status = "confirmed"
        else:
            normalized = None
            status = "rejected"
        connection.execute("""
            UPDATE reviews SET status = ?, final_plate = ?, reviewer = ?, reviewed_at = ?, vehicle_color = ?
            WHERE id = ?
        """, (status, normalized, reviewer, _now(), vehicle_color, review_id))
        updated = connection.execute(
            "SELECT * FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
    return _row_dict(updated)
