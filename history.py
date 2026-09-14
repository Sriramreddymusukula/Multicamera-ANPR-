
import pandas as pd
import os


# ============================================================
# DATABASE FILE
# ============================================================

DATABASE_FILE = "vehicle_database.csv"


# ============================================================
# GET DETECTION HISTORY
# ============================================================

def get_history():

    if not os.path.exists(DATABASE_FILE):

        return "No History Available"

    try:

        df = pd.read_csv(
            DATABASE_FILE
        )

    except Exception as e:

        print(
            "History read error:",
            e
        )

        return "No History Available"

    if df.empty:

        return "No History Available"

    history = ""

    # Latest detection first
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
# GET HISTORY DATA
# ============================================================

def get_history_data():

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
# GET IMAGE PATH FOR A PLATE
# ============================================================

def get_image_path(
    plate_number
):

    if not os.path.exists(
        DATABASE_FILE
    ):

        return None

    try:

        df = pd.read_csv(
            DATABASE_FILE
        )

    except Exception as e:

        print(
            "Could not read database:",
            e
        )

        return None

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
# GET VEHICLE HISTORY
# ============================================================

def get_vehicle_history(
    plate_number
):

    df = get_history_data()

    if df.empty:

        return pd.DataFrame()

    if "Plate Number" not in df.columns:

        return pd.DataFrame()

    rows = df[
        df["Plate Number"].astype(str)
        == str(plate_number)
    ]

    return rows.iloc[::-1]


# ============================================================
# GET CAMERA HISTORY
# ============================================================

def get_camera_history(
    camera_id
):

    df = get_history_data()

    if df.empty:

        return pd.DataFrame()

    if "Camera ID" not in df.columns:

        return pd.DataFrame()

    rows = df[
        df["Camera ID"].astype(str)
        == str(camera_id)
    ]

    return rows.iloc[::-1]


# ============================================================

