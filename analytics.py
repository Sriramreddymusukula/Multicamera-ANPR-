"""
Pure session analytics over detection records.

All functions are side-effect free so the dashboard math can be
unit-tested without the GUI, the database or the ML stack.
"""

from collections import defaultdict


INVALID_PLATES = (
    "OCR Failed",
    "No Plate Detected"
)


def valid_detections(detections):

    return [
        detection
        for detection in detections
        if detection["plate_number"] not in INVALID_PLATES
    ]


def unique_plate_count(detections):

    return len(
        set(
            detection["plate_number"]
            for detection in detections
        )
    )


def active_camera_count(detections):

    return len(
        set(
            detection["camera_id"]
            for detection in detections
        )
    )


def camera_statistics(detections):

    stats = defaultdict(int)

    for detection in detections:

        stats[detection["camera_id"]] += 1

    return stats


def location_statistics(detections):

    stats = defaultdict(int)

    for detection in detections:

        stats[detection["location"]] += 1

    return stats


def vehicle_observation_statistics(detections):

    stats = defaultdict(int)

    for detection in detections:

        stats[detection["plate_number"]] += 1

    return stats


def multi_camera_vehicles(trajectory_data):
    """Vehicles observed by more than one camera, in first-seen order."""

    multi_camera = []

    for plate, events in trajectory_data.items():

        if plate in INVALID_PLATES:

            continue

        cameras = list(
            dict.fromkeys(
                event["camera_id"]
                for event in events
            )
        )

        if len(cameras) > 1:

            multi_camera.append(
                {
                    "plate": plate,
                    "cameras": cameras,
                    "events": events
                }
            )

    return multi_camera


def traffic_activity(detections):
    """Observation-count activity indicator (prototype metric)."""

    count = len(detections)

    if count == 0:

        return "NO DATA"

    if count <= 2:

        return "LOW"

    if count <= 5:

        return "MODERATE"

    return "HIGH"
