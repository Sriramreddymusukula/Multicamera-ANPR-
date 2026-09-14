
import pandas as pd
from datetime import datetime
import os
import shutil


# ============================================================
# DATABASE FILE
# ============================================================

DATABASE_FILE = "vehicle_database.csv"


# ============================================================
# SAVE DETECTION TO DATABASE
# ============================================================

def save_to_database(
    plate_number,
    image_path,
    camera_id="CAM-01",
    location="Unknown",
    confidence=0.0
):
    """
    Save a vehicle detection to the CSV database.

    Parameters:
        plate_number : Detected number plate
        image_path   : Original vehicle image
        camera_id    : Camera identifier
        location     : Camera location
        confidence   : YOLO detection confidence
    """

    now = datetime.now()

    date = now.strftime(
        "%d-%m-%Y"
    )

    time = now.strftime(
        "%I:%M:%S %p"
    )

    timestamp = now.strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    # ========================================================
    # CREATE OUTPUT DIRECTORY
    # ========================================================

    if not os.path.exists("output"):
        os.makedirs("output")

    # ========================================================
    # SAVE VEHICLE IMAGE
    # ========================================================

    saved_image_path = (
        f"output/"
        f"detected_vehicle_"
        f"{timestamp}.jpg"
    )

    try:

        shutil.copy(
            image_path,
            saved_image_path
        )

    except Exception as e:

        print(
            "Could not save vehicle image:",
            e
        )

        saved_image_path = image_path

    # ========================================================
    # CREATE NEW RECORD
    # ========================================================

    new_record = pd.DataFrame({

        "Date": [date],

        "Time": [time],

        "Plate Number": [plate_number],

        "Camera ID": [camera_id],

        "Location": [location],

        "Confidence": [round(
            float(confidence),
            4
        )],

        "Image Path": [saved_image_path]

    })

    # ========================================================
    # READ EXISTING DATABASE
    # ========================================================

    if os.path.exists(
        DATABASE_FILE
    ):

        try:

            old_records = pd.read_csv(
                DATABASE_FILE
            )

        except Exception as e:

            print(
                "Could not read existing database:",
                e
            )

            old_records = pd.DataFrame()

        # ----------------------------------------------------
        # Handle old database format
        # ----------------------------------------------------

        # If the existing CSV was created by your
        # previous version, add the new columns.

        required_columns = [
            "Date",
            "Time",
            "Plate Number",
            "Camera ID",
            "Location",
            "Confidence",
            "Image Path"
        ]

        for column in required_columns:

            if column not in old_records.columns:

                if column == "Camera ID":
                    old_records[column] = "CAM-01"

                elif column == "Location":
                    old_records[column] = "Unknown"

                elif column == "Confidence":
                    old_records[column] = 0.0

                else:
                    old_records[column] = ""

        # Make sure column order is correct
        old_records = old_records[
            required_columns
        ]

        updated_records = pd.concat(
            [
                old_records,
                new_record
            ],
            ignore_index=True
        )

    else:

        updated_records = new_record

    # ========================================================
    # SAVE DATABASE
    # ========================================================

    updated_records.to_csv(
        DATABASE_FILE,
        index=False
    )

    print(
        "Saved to Database Successfully"
    )

    print(
        f"Plate     : {plate_number}"
    )

    print(
        f"Camera    : {camera_id}"
    )

    print(
        f"Location  : {location}"
    )

    print(
        f"Confidence: {confidence}"
    )


# ============================================================
# GET ALL RECORDS
# ============================================================

def get_all_records():

    if not os.path.exists(
        DATABASE_FILE
    ):

        return pd.DataFrame()

    try:

        return pd.read_csv(
            DATABASE_FILE
        )

    except Exception as e:

        print(
            "Database read error:",
            e
        )

        return pd.DataFrame()


# ============================================================
# GET VEHICLE HISTORY
# ============================================================

def get_vehicle_history(
    plate_number
):

    records = get_all_records()

    if records.empty:
        return records

    return records[
        records["Plate Number"].astype(str)
        == str(plate_number)
    ]


# ============================================================
# GET CAMERA HISTORY
# ============================================================

def get_camera_history(
    camera_id
):

    records = get_all_records()

    if records.empty:
        return records

    if "Camera ID" not in records.columns:
        return pd.DataFrame()

    return records[
        records["Camera ID"].astype(str)
        == str(camera_id)
    ]

