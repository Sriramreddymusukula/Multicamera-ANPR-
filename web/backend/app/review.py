"""Private, auditable operator review of uncertain ANPR observations."""

import base64
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import cv2

from database import read_database, save_detections
from detector import find_plate_candidates

from . import settings

_LOCK = threading.RLock()
VEHICLE_COLORS = {"Black", "White", "Silver", "Grey", "Blue", "Red", "Green", "Brown", "Yellow", "Other"}
VEHICLE_STYLES = {"SUV", "Sedan", "Hatchback", "Van", "Truck", "Bus", "Motorcycle", "Other"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _connect():
    connection = sqlite3.connect(str(settings.REVIEW_DB), timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _db():
    with _LOCK:
        connection = _connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def init_db():
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
                reviewed_at TEXT
            )
        """)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(reviews)")}
        for column in ("vehicle_color", "suggested_color", "suggested_style"):
            if column not in columns:
                connection.execute(f"ALTER TABLE reviews ADD COLUMN {column} TEXT")


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
    except (OSError, ValueError, KeyError, IndexError, URLError, TimeoutError):
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
    return None, None


def _gemini_vehicle_attributes(frame_path, bbox):
    """Describe visible vehicle appearance in a frame with the plate masked."""
    key = settings.get_gemini_key()
    if not key or not frame_path or not bbox or len(bbox) != 4:
        return None, None
    try:
        frame = cv2.imread(str(frame_path))
        if frame is None:
            return None, None
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = [int(value) for value in bbox]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            return None, None
        pad_x, pad_y = max(8, (x2 - x1) // 5), max(8, (y2 - y1) // 2)
        cv2.rectangle(frame, (max(0, x1 - pad_x), max(0, y1 - pad_y)),
                      (min(width, x2 + pad_x), min(height, y2 + pad_y)), (0, 0, 0), -1)
        scale = min(1.0, 1024 / max(width, height))
        if scale < 1:
            frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        ok, encoded_frame = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if not ok:
            return None, None
        payload = json.dumps({
            "contents": [{"parts": [
                {"text": (
                    "Describe only the vehicle associated with the blacked-out number plate. "
                    "Return JSON with color and body_style. Use color from Black, White, Silver, Grey, "
                    "Blue, Red, Green, Brown, Yellow, Other, or Unknown. Use body_style from SUV, "
                    "Sedan, Hatchback, Van, Truck, Bus, Motorcycle, Other, or Unknown. "
                    "If the vehicle is not clearly visible, return Unknown. Do not infer registration, "
                    "make, model, route, or location."
                )},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(encoded_frame.tobytes()).decode("ascii")}},
            ]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "maxOutputTokens": 256},
        }).encode("utf-8")
        request = Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
            data=payload,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            method="POST",
        )
        with urlopen(request, timeout=15) as response:
            data = json.load(response)
        raw = "".join(part.get("text", "") for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []))
        attributes = json.loads(raw)
        color = str(attributes.get("color", "")).strip().title()
        if color == "Gray":
            color = "Grey"
        style_name = str(attributes.get("body_style", "")).strip().lower()
        style = "SUV" if style_name == "suv" else style_name.title()
        return color if color in VEHICLE_COLORS else None, style if style in VEHICLE_STYLES else None
    except (OSError, ValueError, TypeError, KeyError, IndexError, URLError, TimeoutError):
        return None, None


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
    with _db() as connection:
        for detection in detections:
            prediction = detection["plate_number"]
            detector_score = float(detection.get("confidence", 0))
            ocr_score = detection.get("ocr_confidence")
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

            provider, provider_read = (None, None)
            if reasons:
                provider, provider_read = _provider_read(detection.get("cropped_plate"))
                if provider_read and provider_read != prediction:
                    reasons.append("Second OCR reader disagrees")

            gemini_agrees = provider == "Gemini 3.8 Flash" and provider_read == prediction
            status = "accepted" if not reasons or gemini_agrees else "pending"
            suggested_color, suggested_style = (
                _gemini_vehicle_attributes(detection.get("image_path"), detection.get("bbox"))
                if status == "pending" else (None, None)
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
                    reviewer, reviewed_at, suggested_color, suggested_style
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                None, None, suggested_color, suggested_style,
            ))
            created.append({
                **detection,
                "review_id": review_id,
                "review_status": status,
                "review_reasons": reasons,
                "provider": provider,
                "provider_read": provider_read,
                "suggested_color": suggested_color,
                "suggested_style": suggested_style,
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
    history = read_database()
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
            if not 8 <= len(normalized) <= 12 or normalized != plate.strip().upper():
                raise ValueError("Enter a valid registration without spaces or symbols.")
            save_detections([{
                "plate_number": normalized,
                "image_path": row["image_path"],
                "camera_id": row["camera_id"],
                "location": row["location"],
                "confidence": row["detector_score"],
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
