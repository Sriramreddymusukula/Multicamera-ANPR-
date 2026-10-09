import os
import shutil
import uuid
from datetime import datetime

import pandas as pd

from config import (
    DATABASE_FILE,
    OUTPUT_DIR
)
from history import get_history_data


# ============================================================
# DATABASE SCHEMA
# ============================================================

COLUMN_ORDER = [
    "Date",
    "Time",
    "Plate Number",
    "Camera ID",
    "Location",
    "Confidence",
    "Image Path"
]


# ============================================================
# HELPERS
# ============================================================

def _prepare_dataframe(frame):
    """Normalize legacy CSVs to the current column layout."""

    if frame.empty:

        return pd.DataFrame(columns=COLUMN_ORDER)

    for column in COLUMN_ORDER:

        if column not in frame.columns:

            if column == "Camera ID":
                frame[column] = "CAM-01"

            elif column == "Location":
                frame[column] = "Unknown"

            elif column == "Confidence":
                frame[column] = 0.0

            else:
                frame[column] = ""

    return frame[COLUMN_ORDER]


def _copy_vehicle_image(image_path):
    """Copy the source vehicle image into output/."""

    if not image_path or not os.path.isfile(image_path):

        return image_path or ""

    # Images already stored in output/ (video evidence frames)
    # do not need to be copied again.
    if os.path.abspath(image_path).startswith(
        os.path.abspath(OUTPUT_DIR) + os.sep
    ):

        return image_path

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    saved_image_path = os.path.join(
        OUTPUT_DIR,
        f"detected_vehicle_{timestamp}_"
        f"{uuid.uuid4().hex[:6]}.jpg"
    )

    try:

        shutil.copy(image_path, saved_image_path)

        return saved_image_path

    except Exception as error:

        print("Could not save vehicle image:", error)

        return image_path


def _build_record(
    plate_number,
    image_path,
    camera_id,
    location,
    confidence
):

    now = datetime.now()

    return {

        "Date": now.strftime("%d-%m-%Y"),

        "Time": now.strftime("%I:%M:%S %p"),

        "Plate Number": plate_number,

        "Camera ID": camera_id,

        "Location": location,

        "Confidence": round(float(confidence), 4),

        "Image Path": _copy_vehicle_image(image_path)
    }


# ============================================================
# SAVE DETECTIONS (BATCH, SINGLE CSV WRITE)
# ============================================================

def save_detections(detections):
    """
    Persist a batch of detections to vehicle_database.csv.

    Each detection is a dict with the keys:
        plate_number, image_path, camera_id, location, confidence

    Returns the number of records saved.
    """

    if not detections:

        return 0

    rows = [
        _build_record(
            detection.get("plate_number", ""),
            detection.get("image_path", ""),
            detection.get("camera_id", "CAM-01"),
            detection.get("location", "Unknown"),
            detection.get("confidence", 0.0)
        )
        for detection in detections
    ]

    new_records = pd.DataFrame(
        rows,
        columns=COLUMN_ORDER
    )

    old_records = _prepare_dataframe(
        get_history_data()
    )

    combined = pd.concat(
        [old_records, new_records],
        ignore_index=True
    )

    combined.to_csv(
        DATABASE_FILE,
        index=False
    )

    print(
        f"Saved {len(rows)} record(s) to "
        f"{DATABASE_FILE}"
    )

    return len(rows)


# ============================================================
# SAVE ONE DETECTION (COMPATIBILITY WRAPPER)
# ============================================================

def save_to_database(
    plate_number,
    image_path,
    camera_id="CAM-01",
    location="Unknown",
    confidence=0.0
):

    return save_detections([
        {
            "plate_number": plate_number,
            "image_path": image_path,
            "camera_id": camera_id,
            "location": location,
            "confidence": confidence
        }
    ])
