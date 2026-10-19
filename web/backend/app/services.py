"""
Service adapters between the web API and the existing modules.

Read paths reuse database.read_database(), analytics.* and
history.* exactly as the desktop app does (CSV rows are normalized
to the same dict shape the GUI keeps in memory). Detection paths
reuse processing.process_images / process_video, so web-triggered
uploads land in the same CSV and output/ folder as the GUI.

Privacy: public_* functions only ever return aggregates. Plate
numbers, per-vehicle records, trajectories and evidence filenames
are exposed exclusively through authenticated endpoints.
"""

import math
import logging
import os
from datetime import datetime
from pathlib import Path

from analytics import (
    active_camera_count,
    camera_statistics,
    traffic_activity,
    unique_plate_count,
    valid_detections,
)
from config import (
    CAMERA_BY_ID,
    CAMERA_LOCATION_BY_ID,
    OUTPUT_DIR,
)
from . import db as database, settings

logger = logging.getLogger(__name__)

_DATE_FORMAT = "%d-%m-%Y"
_TIME_FORMAT = "%I:%M:%S %p"


# ============================================================
# CAMERAS
# ============================================================

def cameras():
    """Camera network with verified marker coordinates."""

    return [
        {
            "id": camera["id"],
            "location": camera["location"],
            "label": f"{camera['id']} — {camera['location']}",
            "lat": camera["coordinates"]["lat"],
            "lon": camera["coordinates"]["lon"],
        }
        for camera in CAMERA_BY_ID.values()
    ]


def camera_from_id(camera_id):

    return CAMERA_BY_ID.get(camera_id)


# ============================================================
# SHARED LOADING
# ============================================================

def _clean(value):
    """Stringify a CSV cell, mapping missing/NaN to ""."""

    if value is None:

        return ""

    if isinstance(value, float) and math.isnan(value):

        return ""

    return str(value).strip()


def _confidence(value):

    try:

        number = float(value)

    except (TypeError, ValueError):

        return 0.0

    return number if math.isfinite(number) else 0.0


def _normalize_row(row):
    """Map CSV columns to the in-memory detection dict shape."""

    return {
        "plate_number": _clean(row.get("Plate Number")),
        "camera_id": _clean(row.get("Camera ID")) or "Unknown",
        "location": _clean(row.get("Location")) or "Unknown",
        "confidence": _confidence(row.get("Confidence")),
        "date": _clean(row.get("Date")),
        "time": _clean(row.get("Time")),
        "image_path": _clean(row.get("Image Path")),
    }


def _records():
    """Valid detection records as plain dicts (newest last)."""

    frame = database.read_detections()

    if frame.empty:

        return []

    rows = [_normalize_row(row) for row in frame.to_dict("records")]

    return valid_detections(rows)


def _parse_timestamp(date_value, time_value):

    try:

        return datetime.strptime(
            f"{date_value} {time_value}",
            f"{_DATE_FORMAT} {_TIME_FORMAT}"
        )

    except (TypeError, ValueError):

        return None


def _display_timestamp(parsed):

    if parsed is None:

        return ""

    return parsed.strftime("%d %b %Y · %H:%M")


def _plausible_route(events):
    """Return every timestamped, known-camera sighting in chronological order.

    Camera revisits remain separate route points, so trajectories such as
    CAM-02 -> CAM-03 -> CAM-02 -> CAM-01 are drawn in their recorded order.
    The map line visualizes recorded observations; it is not a verified road
    route or proof that the vehicle traveled between cameras.
    """
    timed = [
        event for event in events
        if event["parsed"] is not None and event["camera_id"] in CAMERA_BY_ID
    ]
    timed.sort(key=lambda event: event["parsed"])
    return {
        "events": timed,
        "camera_path": [event["camera_id"] for event in timed],
    }


def _multi_camera_routes(groups):
    """Return only plate histories with a plausible multi-camera chain."""
    routes = []
    for plate, events in groups.items():
        route = _plausible_route(events)
        if len(set(route["camera_path"])) > 1:
            routes.append({
                "plate": plate,
                "cameras": route["camera_path"],
                "events": events,
            })
    return routes


def _evidence_name(image_path):
    """Return the evidence filename when it lives in output/."""

    if not image_path:

        return None

    if str(image_path).startswith("storage://"):

        return str(image_path)[len("storage://"):]

    absolute = os.path.abspath(str(image_path))

    output_root = os.path.abspath(OUTPUT_DIR)

    if not absolute.startswith(output_root + os.sep):

        return None

    return os.path.basename(absolute)


# ============================================================
# PUBLIC ANALYTICS (AGGREGATES ONLY - NO PLATES)
# ============================================================

def public_summary():

    records = _records()

    parsed = [
        _parse_timestamp(record["date"], record["time"])
        for record in records
    ]

    valid_dates = [value for value in parsed if value is not None]

    last_seen = max(valid_dates) if valid_dates else None

    first_seen = min(valid_dates) if valid_dates else None

    return {
        "total_observations": len(records),
        "unique_vehicles": unique_plate_count(records),
        "active_cameras": active_camera_count(records),
        "total_cameras": len(CAMERA_BY_ID),
        "multi_camera_vehicles": len(_multi_camera_routes(_trajectory_index(records))),
        "traffic_activity": traffic_activity(records),
        "first_seen": _display_timestamp(first_seen),
        "last_seen": _display_timestamp(last_seen),
    }


def public_camera_stats():

    records = _records()

    stats = camera_statistics(records)

    rows = [
        {
            "camera_id": camera_id,
            "location": CAMERA_LOCATION_BY_ID.get(camera_id, "Unknown"),
            "observations": count,
            "traffic_level": (
                "LOW" if count <= 2 else
                "MEDIUM" if count <= 5 else
                "HIGH"
            ),
        }
        for camera_id, count in stats.items()
    ]

    rows.sort(key=lambda row: row["observations"], reverse=True)

    for row in rows:

        camera = CAMERA_BY_ID.get(row["camera_id"])

        if camera:

            row["lat"] = camera["coordinates"]["lat"]
            row["lon"] = camera["coordinates"]["lon"]

    return rows


def public_trends():

    records = _records()

    hourly = {hour: 0 for hour in range(24)}

    daily = {}

    for record in records:

        parsed = _parse_timestamp(record["date"], record["time"])

        if parsed is None:

            continue

        hourly[parsed.hour] += 1

        key = parsed.strftime("%Y-%m-%d")

        daily[key] = daily.get(key, 0) + 1

    hourly_rows = [
        {"hour": hour, "observations": hourly[hour]}
        for hour in range(24)
    ]

    daily_rows = [
        {"date": day, "observations": count}
        for day, count in sorted(daily.items())
    ]

    peak_hour = None

    if records and any(hourly.values()):

        peak_hour = max(hourly, key=hourly.get)

    return {
        "hourly": hourly_rows,
        "daily": daily_rows,
        "peak_hour": peak_hour,
        "peak_hour_observations": hourly.get(peak_hour, 0)
        if peak_hour is not None else 0,
    }


def public_insights():

    records = _records()

    if not records:

        return {
            "insights": [
                "No observations recorded yet. Run ANPR detection "
                "from the operator console to populate analytics."
            ]
        }

    summary = public_summary()

    camera_rows = public_camera_stats()

    trends = public_trends()

    insights = []

    if camera_rows:

        busiest = camera_rows[0]

        insights.append(
            f"{busiest['camera_id']} ({busiest['location']}) logged "
            f"the most observations: {busiest['observations']}."
        )

    if trends["peak_hour"] is not None and trends["peak_hour_observations"]:

        insights.append(
            f"Peak recorded activity around "
            f"{trends['peak_hour']:02d}:00 with "
            f"{trends['peak_hour_observations']} observations."
        )

    if summary["multi_camera_vehicles"]:

        share = round(
            100 * summary["multi_camera_vehicles"]
            / max(1, summary["unique_vehicles"])
        )

        insights.append(
            f"{summary['multi_camera_vehicles']} vehicles ({share}%) "
            "were observed by more than one camera."
        )

    else:

        insights.append(
            "No multi-camera vehicle movement recorded so far."
        )

    insights.append(
        f"Current session activity level: "
        f"{summary['traffic_activity']}."
    )

    if summary["first_seen"] and summary["last_seen"]:

        insights.append(
            f"Observation window: {summary['first_seen']} → "
            f"{summary['last_seen']}."
        )

    return {"insights": insights}


# ============================================================
# AUTHENTICATED VEHICLE VIEWS
# ============================================================

def _trajectory_index(records=None):
    """Group records by plate with parsed timestamps (chronological)."""

    if records is None:

        records = _records()

    groups = {}

    for record in records:

        plate = record["plate_number"]

        if not plate:

            continue

        parsed = _parse_timestamp(record["date"], record["time"])

        groups.setdefault(plate, []).append(
            {
                "camera_id": record["camera_id"],
                "location": record["location"],
                "date": record["date"],
                "time": record["time"],
                "parsed": parsed,
                "confidence": record["confidence"],
                "evidence": _evidence_name(record["image_path"]),
            }
        )

    for plate, events in groups.items():

        events.sort(
            key=lambda event: (
                event["parsed"] is None,
                event["parsed"] or datetime.min
            )
        )

    return groups


def _serialize_event(event):

    return {
        "camera_id": event["camera_id"],
        "location": event["location"],
        "timestamp": _display_timestamp(event["parsed"]),
        "date": event["date"],
        "time": event["time"],
        "confidence": event["confidence"],
        "evidence": event["evidence"],
    }


def normalize_plate(plate):

    return str(plate or "").strip().upper().replace(" ", "")


def search_vehicle(plate):

    normalized = normalize_plate(plate)

    if not normalized:

        return {
            "plate": "",
            "found": False,
            "observations": [],
            "similar": []
        }

    groups = _trajectory_index()

    events = groups.get(normalized)

    if events:

        return {
            "plate": normalized,
            "found": True,
            "observations": [
                _serialize_event(event) for event in events
            ],
            "similar": []
        }

    similar = [
        {
            "plate": candidate,
            "observations": len(candidate_events)
        }
        for candidate, candidate_events in groups.items()
        if normalized in candidate
    ]

    similar.sort(key=lambda row: row["observations"], reverse=True)

    return {
        "plate": normalized,
        "found": False,
        "observations": [],
        "similar": similar[:8]
    }


def vehicle_trajectory(plate):

    normalized = normalize_plate(plate)

    groups = _trajectory_index()

    events = groups.get(normalized)

    if not events:

        return None

    route = _plausible_route(events)
    camera_path = route["camera_path"]
    polyline = [
        [
            CAMERA_BY_ID[camera_id]["coordinates"]["lat"],
            CAMERA_BY_ID[camera_id]["coordinates"]["lon"],
        ]
        for camera_id in camera_path
    ]

    parsed_events = [
        event for event in events if event["parsed"] is not None
    ]

    return {
        "plate": normalized,
        "observations": [
            _serialize_event(event) for event in events
        ],
        "polyline": polyline,
        "camera_path": camera_path,
        "multi_camera": len(camera_path) > 1,
        "route_established": len(camera_path) > 1,
        "summary": {
            "observations": len(events),
            "cameras": len(set(camera_path)),
            "first_seen": _display_timestamp(
                parsed_events[0]["parsed"]
            ) if parsed_events else "",
            "last_seen": _display_timestamp(
                parsed_events[-1]["parsed"]
            ) if parsed_events else "",
        }
    }


def multi_camera_list():

    groups = _trajectory_index()

    rows = []

    for plate, events in groups.items():
        route = _plausible_route(events)
        camera_path = route["camera_path"]
        camera_count = len(set(camera_path))
        if camera_count < 2:
            continue

        parsed = [
            event["parsed"] for event in events
            if event["parsed"] is not None
        ]
        last_seen_at = max(parsed) if parsed else datetime.min

        rows.append(
            {
                "plate": plate,
                "cameras": camera_path,
                "camera_count": camera_count,
                "observations": len(events),
                "last_seen": _display_timestamp(last_seen_at)
                if parsed else "",
                "_last_seen_at": last_seen_at,
            }
        )

    rows.sort(
        key=lambda row: (row["_last_seen_at"], row["observations"]),
        reverse=True,
    )
    for row in rows:
        row.pop("_last_seen_at", None)

    return rows


def serialize_detections(detections):
    """Detection results for the operator console (authenticated)."""

    serialized = []

    for detection in detections:

        entry = {
            "plate_number": detection.get("plate_number", ""),
            "confidence": detection.get("confidence", 0.0),
            "camera_id": detection.get("camera_id", ""),
            "location": detection.get("location", ""),
            "timestamp": detection.get("timestamp", ""),
            "evidence": _evidence_name(detection.get("cropped_plate")),
            "frame": _evidence_name(detection.get("image_path")),
            "ocr_confidence": detection.get("ocr_confidence"),
            "match_confidence": detection.get("match_confidence"),
            "alternatives": detection.get("alternatives", []),
            "review_id": detection.get("review_id"),
            "review_status": detection.get("review_status", "accepted"),
            "review_reasons": detection.get("review_reasons", []),
            "provider": detection.get("provider"),
            "provider_read": detection.get("provider_read"),
            "source_name": detection.get("source_name"),
        }

        if "hits" in detection:

            entry["hits"] = detection["hits"]

        if "video_time" in detection:

            entry["video_time"] = detection["video_time"]

        serialized.append(entry)

    return serialized


# ============================================================
# EVIDENCE FILES
# ============================================================

def evidence_path(filename):
    """Resolve an evidence filename safely inside output/."""

    if not filename or filename != os.path.basename(filename):

        return None

    output_root = Path(OUTPUT_DIR).resolve()

    candidate = (output_root / filename).resolve()

    if candidate.parent != output_root or not candidate.is_file():

        return None

    return candidate


def clear_operational_data():
    """Clear detections and reviews, retaining operator accounts."""

    stored_objects = set()
    local_evidence = set()

    def collect_image(value):
        if not value:
            return
        value = str(value)
        if value.startswith("storage://"):
            stored_objects.add(value[len("storage://"):])
            return
        candidate = Path(value).resolve()
        output_root = Path(OUTPUT_DIR).resolve()
        if candidate.is_relative_to(output_root) and candidate.is_file():
            local_evidence.add(candidate)

    connection = database.connect(settings.REVIEW_DB)
    try:
        with connection:
            review_rows = connection.execute(
                "SELECT image_path, crop_path FROM reviews"
            ).fetchall()
            for row in review_rows:
                collect_image(row["image_path"])
                collect_image(row["crop_path"])

            if database.is_postgres(connection):
                detection_rows = connection.execute(
                    "SELECT image_path FROM detections"
                ).fetchall()
                detection_count = connection.execute(
                    "SELECT COUNT(*) AS count FROM detections"
                ).fetchone()["count"]
                review_count = connection.execute(
                    "SELECT COUNT(*) AS count FROM reviews"
                ).fetchone()["count"]
                for row in detection_rows:
                    collect_image(row["image_path"])
                connection.execute("DELETE FROM detections")
            else:
                import database as csv_database

                frame = csv_database.read_database()
                detection_count = len(frame.index)
                review_count = len(review_rows)
                if not frame.empty and "Image Path" in frame:
                    for value in frame["Image Path"].tolist():
                        collect_image(value)

            connection.execute("DELETE FROM reviews")
    finally:
        connection.close()

    if not database.postgres_enabled():
        import database as csv_database

        csv_database.clear_detections()

    evidence_deleted = 0
    evidence_cleanup_complete = True
    for path in local_evidence:
        try:
            path.unlink(missing_ok=True)
            evidence_deleted += 1
        except OSError:
            evidence_cleanup_complete = False

    if stored_objects:
        from . import storage

        if not storage.configured():
            evidence_cleanup_complete = False
        else:
            names = sorted(stored_objects)
            try:
                for start in range(0, len(names), 100):
                    storage.delete_objects(names[start:start + 100])
                    evidence_deleted += len(names[start:start + 100])
            except RuntimeError:
                logger.warning("Evidence cleanup was incomplete after records were cleared.")
                evidence_cleanup_complete = False

    return {
        "reviews_deleted": review_count,
        "detections_deleted": detection_count,
        "evidence_deleted": evidence_deleted,
        "evidence_cleanup_complete": evidence_cleanup_complete,
    }
