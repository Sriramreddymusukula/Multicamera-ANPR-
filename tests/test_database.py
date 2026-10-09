"""
Smoke tests for the CSV detection store.

Run from the project folder:

    .\\venv\\Scripts\\python.exe tests\\test_database.py
"""

import os
import sys
import tempfile

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

import pandas as pd

import database
from database import (
    COLUMN_ORDER,
    save_detections,
    save_to_database
)


class _TempDatabase:
    """Point the module at a throw-away database for one test."""

    def __enter__(self):

        self._tmp = tempfile.TemporaryDirectory()

        self._old_database = database.DATABASE_FILE
        self._old_output = database.OUTPUT_DIR

        database.DATABASE_FILE = os.path.join(
            self._tmp.name,
            "vehicle_database.csv"
        )

        database.OUTPUT_DIR = os.path.join(
            self._tmp.name,
            "output"
        )

        return self

    def __exit__(self, *exc_info):

        database.DATABASE_FILE = self._old_database
        database.OUTPUT_DIR = self._old_output

        self._tmp.cleanup()


def _detection(plate, confidence=0.9):

    return {
        "plate_number": plate,
        "image_path": "",
        "camera_id": "CAM-01",
        "location": "Suchitra Junction",
        "confidence": confidence
    }


def test_batch_append_and_single_wrapper():

    with _TempDatabase():

        assert save_detections([
            _detection("TG257602"),
            _detection("MH12AB1234", 0.8)
        ]) == 2

        assert save_to_database(
            "KA01AB1234",
            "",
            "CAM-02",
            "Kukatpally",
            0.7
        ) == 1

        frame = pd.read_csv(database.DATABASE_FILE)

        assert list(frame.columns) == COLUMN_ORDER

        assert frame["Plate Number"].tolist() == [
            "TG257602",
            "MH12AB1234",
            "KA01AB1234"
        ]

        assert frame["Camera ID"].tolist() == [
            "CAM-01",
            "CAM-01",
            "CAM-02"
        ]


def test_saving_nothing_is_a_noop():

    with _TempDatabase():

        assert save_detections([]) == 0

        assert not os.path.exists(database.DATABASE_FILE)


def test_legacy_schema_is_normalized_once():

    with _TempDatabase():

        legacy = pd.DataFrame([
            {
                "Date": "01-01-2026",
                "Time": "10:00:00 AM",
                "Plate Number": "TS08EU0079",
                "Image Path": ""
            }
        ])

        legacy.to_csv(database.DATABASE_FILE, index=False)

        save_detections([_detection("TG257602")])

        frame = pd.read_csv(database.DATABASE_FILE)

        assert list(frame.columns) == COLUMN_ORDER

        assert frame["Plate Number"].tolist() == [
            "TS08EU0079",
            "TG257602"
        ]

        assert frame.loc[0, "Camera ID"] == "CAM-01"

        assert frame.loc[0, "Location"] == "Unknown"


def test_unreadable_database_is_quarantined_not_lost():

    with _TempDatabase():

        with open(database.DATABASE_FILE, "wb") as file:

            file.write(b"\xff\xfe\x00binary garbage\x00\xff")

        save_detections([_detection("TG257602")])

        frame = pd.read_csv(database.DATABASE_FILE)

        assert frame["Plate Number"].tolist() == ["TG257602"]

        backups = [
            name
            for name in os.listdir(
                os.path.dirname(database.DATABASE_FILE)
            )
            if ".corrupt-" in name
        ]

        assert backups, "corrupt database was not preserved"


def test_read_database_reflects_writes_and_caches():

    with _TempDatabase():

        save_detections([_detection("TG257602")])

        first = database.read_database()

        assert first["Plate Number"].tolist() == ["TG257602"]

        second = database.read_database()

        assert second is first

        save_detections([_detection("MH12AB1234")])

        third = database.read_database()

        assert third["Plate Number"].tolist() == [
            "TG257602",
            "MH12AB1234"
        ]


if __name__ == "__main__":

    for name, function in sorted(globals().items()):

        if name.startswith("test_") and callable(function):

            function()

            print("PASS", name)

    print("All database tests passed.")
