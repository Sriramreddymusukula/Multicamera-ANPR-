import os

import pandas as pd

from config import DATABASE_FILE


# ============================================================
# RAW RECORDS
# ============================================================

def get_history_data():

    if not os.path.exists(DATABASE_FILE):

        return pd.DataFrame()

    try:

        return pd.read_csv(DATABASE_FILE)

    except Exception as error:

        print("Database read error:", error)

        return pd.DataFrame()


# ============================================================
# FORMATTED HISTORY STRING (LATEST FIRST)
# ============================================================

def get_history():

    df = get_history_data()

    if df.empty:

        return "No History Available"

    history = ""

    df = df.iloc[::-1]

    for _, row in df.iterrows():

        plate = row.get(
            "Plate Number",
            "Unknown"
        )

        date = row.get(
            "Date",
            ""
        )

        time = row.get(
            "Time",
            ""
        )

        camera = row.get(
            "Camera ID",
            "Unknown Camera"
        )

        location = row.get(
            "Location",
            "Unknown Location"
        )

        confidence = row.get(
            "Confidence",
            0
        )

        history += (
            f"🚗 {plate}\n"
            f"📍 {camera} - {location}\n"
            f"🕒 {date}  {time}\n"
            f"🎯 Confidence: {confidence}\n\n"
        )

    return history


# ============================================================
# IMAGE PATH LOOKUP
# ============================================================

def get_image_path(plate_number):

    df = get_history_data()

    if df.empty:

        return None

    if "Plate Number" not in df.columns:

        return None

    rows = df[
        df["Plate Number"].astype(str)
        == str(plate_number)
    ]

    if len(rows) > 0:

        return rows.iloc[-1].get(
            "Image Path",
            None
        )

    return None


# ============================================================
# VEHICLE HISTORY (LATEST FIRST)
# ============================================================

def get_vehicle_history(plate_number):

    df = get_history_data()

    if df.empty:

        return df

    if "Plate Number" not in df.columns:

        return pd.DataFrame()

    rows = df[
        df["Plate Number"].astype(str)
        == str(plate_number)
    ]

    return rows.iloc[::-1]


# ============================================================
# CAMERA HISTORY (LATEST FIRST)
# ============================================================

def get_camera_history(camera_id):

    df = get_history_data()

    if df.empty:

        return df

    if "Camera ID" not in df.columns:

        return pd.DataFrame()

    rows = df[
        df["Camera ID"].astype(str)
        == str(camera_id)
    ]

    return rows.iloc[::-1]
