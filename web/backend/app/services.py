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
import os
from datetime import datetime
from pathlib import Path

from analytics import (
    active_camera_count,
    camera_statistics,
    multi_camera_vehicles,
    traffic_activity,
    unique_plate_count,
    valid_detections,
)
from config import (
    CAMERA_BY_ID,
    CAMERA_LOCATION_BY_ID,
    OUTPUT_DIR,
)
from database import read_database

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

    frame = read_database()

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


def _evidence_name(image_path):
    """Return the evidence filename when it lives in output/."""

    if not image_path:

        return None

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
        "multi_camera_vehicles": len(
            multi_camera_vehicles(_trajectory_index(records))
        ),
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

    polyline = []

    camera_path = []

    for event in events:

        camera = CAMERA_BY_ID.get(event["camera_id"])

        if camera is None:

            continue

        point = [
            camera["coordinates"]["lat"],
            camera["coordinates"]["lon"]
        ]

        if not polyline or polyline[-1] != point:

            polyline.append(point)

        if not camera_path or camera_path[-1] != event["camera_id"]:

            camera_path.append(event["camera_id"])

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
        "summary": {
            "observations": len(events),
            "cameras": len(camera_path),
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

    vehicles = multi_camera_vehicles(groups)

    rows = []

    for vehicle in vehicles:

        events = vehicle["events"]

        parsed = [
            event["parsed"] for event in events
            if event["parsed"] is not None
        ]

        rows.append(
            {
                "plate": vehicle["plate"],
                "cameras": vehicle["cameras"],
                "camera_count": len(vehicle["cameras"]),
                "observations": len(events),
                "last_seen": _display_timestamp(max(parsed))
                if parsed else "",
            }
        )

    rows.sort(
        key=lambda row: row["observations"],
        reverse=True
    )

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
