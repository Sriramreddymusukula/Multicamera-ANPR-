"""
Smoke tests for the session analytics.

Run from the project folder:

    .\\venv\\Scripts\\python.exe tests\\test_analytics.py
"""

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from analytics import (
    active_camera_count,
    camera_statistics,
    multi_camera_vehicles,
    traffic_activity,
    unique_plate_count,
    valid_detections,
    vehicle_observation_statistics
)


def _detection(plate, camera_id, location, confidence=0.9):

    return {
        "plate_number": plate,
        "camera_id": camera_id,
        "location": location,
        "confidence": confidence
    }


def test_valid_detection_filtering():

    detections = [
        _detection("TG257602", "CAM-01", "Suchitra Junction"),
        _detection("No Plate Detected", "CAM-01", "Suchitra Junction"),
        _detection("OCR Failed", "CAM-02", "Kukatpally")
    ]

    assert len(valid_detections(detections)) == 1


def test_counts():

    detections = [
        _detection("TG257602", "CAM-01", "Suchitra Junction"),
        _detection("TG257602", "CAM-03", "JNTU Road"),
        _detection("MH12AB1234", "CAM-02", "Kukatpally")
    ]

    assert unique_plate_count(detections) == 2

    assert active_camera_count(detections) == 3

    assert camera_statistics(detections) == {
        "CAM-01": 1,
        "CAM-03": 1,
        "CAM-02": 1
    }

    assert vehicle_observation_statistics(detections) == {
        "TG257602": 2,
        "MH12AB1234": 1
    }


def test_traffic_activity_thresholds():

    assert traffic_activity([]) == "NO DATA"

    assert traffic_activity([1]) == "LOW"

    assert traffic_activity([1, 2]) == "LOW"

    assert traffic_activity([1, 2, 3]) == "MODERATE"

    assert traffic_activity([1, 2, 3, 4, 5]) == "MODERATE"

    assert traffic_activity([1, 2, 3, 4, 5, 6]) == "HIGH"


def test_multi_camera_vehicle_detection():

    trajectory_data = {

        "TG257602": [
            {"camera_id": "CAM-01", "location": "Suchitra Junction"},
            {"camera_id": "CAM-03", "location": "JNTU Road"},
            {"camera_id": "CAM-01", "location": "Suchitra Junction"}
        ],

        "MH12AB1234": [
            {"camera_id": "CAM-02", "location": "Kukatpally"}
        ]
    }

    multi = multi_camera_vehicles(trajectory_data)

    assert [vehicle["plate"] for vehicle in multi] == ["TG257602"]

    assert multi[0]["cameras"] == ["CAM-01", "CAM-03"]

    assert len(multi[0]["events"]) == 3


if __name__ == "__main__":

    for name, function in sorted(globals().items()):

        if name.startswith("test_") and callable(function):

            function()

            print("PASS", name)

    print("All analytics tests passed.")
