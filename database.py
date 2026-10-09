"""
Persistent detection storage.

Detections are stored in vehicle_database.csv with a fixed column
layout. Writes are append-based (O(1) per batch instead of a full
read-modify-rewrite), guarded by a process-wide lock, and the whole
file is never replaced in place - legacy normalizations are written
atomically through a temp file so a crash cannot destroy history.
An unreadable file is quarantined instead of being silently
overwritten.
"""

import logging
import os
import shutil
import threading
import uuid
from datetime import datetime

import pandas as pd

from config import (
    DATABASE_FILE,
    OUTPUT_DIR
)

logger = logging.getLogger(__name__)


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

_WRITE_LOCK = threading.RLock()

_CACHE = {
    "signature": None,
    "frame": None
}


# ============================================================
# HELPERS
# ============================================================

def _prepare_dataframe(frame):
    """Return a copy normalized to the current column layout."""

    if frame.empty:

        return pd.DataFrame(columns=COLUMN_ORDER)

    frame = frame.copy()

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

        logger.warning("Could not save vehicle image: %s", error)

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
# FILE SIGNATURE + READ CACHE
# ============================================================

def _file_signature():
    """A cheap change-detection signature for the CSV file."""

    try:

        stat = os.stat(DATABASE_FILE)

        return (stat.st_mtime_ns, stat.st_size)

    except OSError:

        return None


def _invalidate_cache():

    _CACHE["signature"] = None

    _CACHE["frame"] = None


def read_database():
    """
    Return the current detection records as a DataFrame.

    Legacy files are normalized to COLUMN_ORDER. Results are cached
    and re-read only when the file changed on disk.
    """

    signature = _file_signature()

    if signature is None:

        _invalidate_cache()

        return pd.DataFrame()

    with _WRITE_LOCK:

        signature = _file_signature()

        if (
            signature is not None
            and _CACHE["signature"] == signature
            and _CACHE["frame"] is not None
        ):

            return _CACHE["frame"]

        if signature is None:

            _invalidate_cache()

            return pd.DataFrame()

        try:

            frame = pd.read_csv(DATABASE_FILE)

        except Exception as error:

            logger.error(
                "Database read error (%s): %s",
                DATABASE_FILE,
                error
            )

            return pd.DataFrame()

        normalized = _prepare_dataframe(frame)

        _CACHE["signature"] = signature

        _CACHE["frame"] = normalized

        return normalized


# ============================================================
# WRITE SUPPORT
# ============================================================

def _atomic_write_csv(frame):
    """Replace the CSV through a temp file (crash-safe)."""

    temp_path = f"{DATABASE_FILE}.tmp"

    frame.to_csv(
        temp_path,
        index=False,
        encoding="utf-8"
    )

    os.replace(temp_path, DATABASE_FILE)


def _quarantine_corrupt_database(error):
    """
    Move an unreadable database aside so it is never silently
    destroyed. Raises when the file cannot be moved - callers must
    not append to a file they could not quarantine.
    """

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_path = f"{DATABASE_FILE}.corrupt-{stamp}"

    try:

        os.replace(DATABASE_FILE, backup_path)

    except OSError as move_error:

        raise RuntimeError(
            f"Database is unreadable and could not be quarantined: "
            f"{DATABASE_FILE}"
        ) from move_error

    logger.warning(
        "Unreadable database moved to %s (%s)",
        backup_path,
        error
    )


def _ensure_current_schema():
    """
    Guarantee the on-disk file is safe to append COLUMN_ORDER rows
    to. Normalizes legacy layouts once; quarantines unreadable files.
    """

    if (
        not os.path.exists(DATABASE_FILE)
        or os.path.getsize(DATABASE_FILE) == 0
    ):

        return

    try:

        columns = list(
            pd.read_csv(DATABASE_FILE, nrows=0).columns
        )

    except Exception as error:

        _quarantine_corrupt_database(error)

        return

    if columns == COLUMN_ORDER:

        return

    try:

        legacy = pd.read_csv(DATABASE_FILE)

    except Exception as error:

        _quarantine_corrupt_database(error)

        return

    _atomic_write_csv(_prepare_dataframe(legacy))

    logger.info(
        "Normalized legacy database to %d column(s)",
        len(COLUMN_ORDER)
    )


# ============================================================
# SAVE DETECTIONS (BATCH, APPEND, LOCKED)
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

    directory = os.path.dirname(DATABASE_FILE)

    if directory:

        os.makedirs(directory, exist_ok=True)

    with _WRITE_LOCK:

        _ensure_current_schema()

        needs_header = (
            not os.path.exists(DATABASE_FILE)
            or os.path.getsize(DATABASE_FILE) == 0
        )

        new_records.to_csv(
            DATABASE_FILE,
            mode="a",
            header=needs_header,
            index=False,
            encoding="utf-8"
        )

        _invalidate_cache()

    logger.info(
        "Saved %d record(s) to %s",
        len(rows),
        DATABASE_FILE
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
