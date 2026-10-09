import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from detector import (
    detect_number_plates,
    check_dependencies
)
from database import save_detections
from history import get_history
from config import CAMERAS, OUTPUT_DIR, VIDEO_FILE_TYPES
from video import analyze_video, read_preview_frame

import os
import cv2
import queue
import threading
from datetime import datetime
from collections import defaultdict


# ============================================================
# THEME
# ============================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ============================================================
# MAIN WINDOW
# ============================================================

app = ctk.CTk()

app.title(
    "City-Wide AI Engine - Multi-Camera ANPR"
)

app.geometry("1500x950")
app.minsize(1200, 750)


# ============================================================
# CAMERA CONFIGURATION
# ============================================================
# The camera list is defined in config.py and imported above.


# ============================================================
# APPLICATION DATA
# ============================================================

selected_images = []

selected_video = None

current_camera = None

all_detections = []

trajectory_data = defaultdict(list)

result_queue = queue.Queue()


# ============================================================
# CONSTANTS
# ============================================================

INVALID_PLATES = [
    "OCR Failed",
    "No Plate Detected"
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_selected_camera():

    camera_name = camera_dropdown.get()

    if camera_name not in CAMERAS:
        return None

    return CAMERAS[camera_name]


def get_valid_detections():

    return [
        detection
        for detection in all_detections
        if detection["plate_number"]
        not in INVALID_PLATES
    ]


def update_camera_info(choice=None):

    camera = get_selected_camera()

    if camera:

        camera_info_label.configure(
            text=(
                f"Camera ID: {camera['id']}\n"
                f"Location: {camera['location']}"
            )
        )


def update_statistics():

    valid_detections = get_valid_detections()

    unique_plates = set(
        detection["plate_number"]
        for detection in valid_detections
    )

    active_cameras = len(
        set(
            detection["camera_id"]
            for detection in all_detections
        )
    )

    multi_camera_count = sum(
        1
        for plate, events in trajectory_data.items()
        if len(
            set(
                event["camera_id"]
                for event in events
            )
        ) > 1
    )

    total_label.configure(
        text=str(len(valid_detections))
    )

    unique_label.configure(
        text=str(len(unique_plates))
    )

    camera_count_label.configure(
        text=str(active_cameras)
    )

    trajectory_count_label.configure(
        text=str(multi_camera_count)
    )


# ============================================================
# TRAFFIC ANALYTICS
# ============================================================

def calculate_traffic_activity():

    valid_detections = get_valid_detections()

    count = len(valid_detections)

    if count == 0:
        return "NO DATA"

    if count <= 2:
        return "LOW"

    elif count <= 5:
        return "MODERATE"

    else:
        return "HIGH"


def get_camera_statistics():

    camera_stats = defaultdict(int)

    for detection in get_valid_detections():

        camera_id = detection["camera_id"]

        camera_stats[camera_id] += 1

    return camera_stats


def get_location_statistics():

    location_stats = defaultdict(int)

    for detection in get_valid_detections():

        location = detection["location"]

        location_stats[location] += 1

    return location_stats


def get_vehicle_observation_statistics():

    vehicle_stats = defaultdict(int)

    for detection in get_valid_detections():

        plate = detection["plate_number"]

        vehicle_stats[plate] += 1

    return vehicle_stats


def get_multi_camera_vehicles():

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


def update_analytics_view():

    analytics_textbox.delete(
        "1.0",
        "end"
    )

    valid_detections = get_valid_detections()

    if not valid_detections:

        analytics_textbox.insert(
            "end",
            "No traffic analytics available yet.\n\n"
            "Upload vehicle images and run AI Detection."
        )

        return

    # ========================================================
    # BASIC STATISTICS
    # ========================================================

    total_observations = len(
        valid_detections
    )

    unique_vehicles = len(
        set(
            detection["plate_number"]
            for detection in valid_detections
        )
    )

    active_cameras = len(
        set(
            detection["camera_id"]
            for detection in valid_detections
        )
    )

    multi_camera_vehicles = len(
        get_multi_camera_vehicles()
    )

    activity_level = calculate_traffic_activity()

    # ========================================================
    # HEADER
    # ========================================================

    analytics_textbox.insert(
        "end",
        "URBAN TRAFFIC ANALYTICS\n"
    )

    analytics_textbox.insert(
        "end",
        "============================================\n\n"
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    analytics_textbox.insert(
        "end",
        "TRAFFIC SUMMARY\n"
    )

    analytics_textbox.insert(
        "end",
        "--------------------------------------------\n"
    )

    analytics_textbox.insert(
        "end",
        f"Vehicle Observations : {total_observations}\n"
    )

    analytics_textbox.insert(
        "end",
        f"Unique Vehicles      : {unique_vehicles}\n"
    )

    analytics_textbox.insert(
        "end",
        f"Active Cameras       : {active_cameras}\n"
    )

    analytics_textbox.insert(
        "end",
        f"Multi-Camera Vehicles: {multi_camera_vehicles}\n"
    )

    analytics_textbox.insert(
        "end",
        f"Traffic Activity     : {activity_level}\n\n"
    )

    # ========================================================
    # CAMERA ACTIVITY
    # ========================================================

    analytics_textbox.insert(
        "end",
        "CAMERA ACTIVITY\n"
    )

    analytics_textbox.insert(
        "end",
        "--------------------------------------------\n"
    )

    camera_stats = get_camera_statistics()

    if not camera_stats:

        analytics_textbox.insert(
            "end",
            "No camera observations.\n\n"
        )

    else:

        for camera_id, count in sorted(
            camera_stats.items()
        ):

            location = "Unknown"

            for camera_name, camera_info in CAMERAS.items():

                if camera_info["id"] == camera_id:

                    location = camera_info[
                        "location"
                    ]

                    break

            analytics_textbox.insert(
                "end",
                f"{camera_id:<10} "
                f"{location:<22} "
                f"{count} observation(s)\n"
            )

        analytics_textbox.insert(
            "end",
            "\n"
        )

    # ========================================================
    # VEHICLE OBSERVATION FREQUENCY
    # ========================================================

    analytics_textbox.insert(
        "end",
        "VEHICLE OBSERVATION FREQUENCY\n"
    )

    analytics_textbox.insert(
        "end",
        "--------------------------------------------\n"
    )

    vehicle_stats = get_vehicle_observation_statistics()

    sorted_vehicles = sorted(
        vehicle_stats.items(),
        key=lambda item: item[1],
        reverse=True
    )

    for plate, count in sorted_vehicles:

        analytics_textbox.insert(
            "end",
            f"{plate:<15} "
            f"{count} observation(s)\n"
        )

    analytics_textbox.insert(
        "end",
        "\n"
    )

    # ========================================================
    # MULTI-CAMERA MOVEMENT
    # ========================================================

    analytics_textbox.insert(
        "end",
        "MULTI-CAMERA VEHICLE MOVEMENT\n"
    )

    analytics_textbox.insert(
        "end",
        "--------------------------------------------\n"
    )

    multi_camera = get_multi_camera_vehicles()

    if not multi_camera:

        analytics_textbox.insert(
            "end",
            "No multi-camera movement detected.\n\n"
        )

    else:

        for vehicle in multi_camera:

            plate = vehicle["plate"]

            locations = list(
                dict.fromkeys(
                    event["location"]
                    for event in vehicle["events"]
                )
            )

            route = " → ".join(
                locations
            )

            analytics_textbox.insert(
                "end",
                f"Vehicle : {plate}\n"
            )

            analytics_textbox.insert(
                "end",
                f"Route   : {route}\n"
            )

            analytics_textbox.insert(
                "end",
                f"Cameras : "
                f"{' → '.join(vehicle['cameras'])}\n\n"
            )

    # ========================================================
    # INTERPRETATION
    # ========================================================

    analytics_textbox.insert(
        "end",
        "ANALYTICS INTERPRETATION\n"
    )

    analytics_textbox.insert(
        "end",
        "--------------------------------------------\n"
    )

    if activity_level == "LOW":

        interpretation = (
            "Low vehicle observation activity "
            "in the current demo session."
        )

    elif activity_level == "MODERATE":

        interpretation = (
            "Moderate vehicle observation activity "
            "across the selected cameras."
        )

    else:

        interpretation = (
            "High vehicle observation activity "
            "in the current demo session."
        )

    analytics_textbox.insert(
        "end",
        f"{interpretation}\n\n"
    )

    analytics_textbox.insert(
        "end",
        "Note: Traffic Activity is calculated from "
        "ANPR observations in the current image-based "
        "demo session. It is not a real-time congestion "
        "measurement.\n"
    )

    analytics_textbox.see("end")


# ============================================================
# IMAGE PREVIEW
# ============================================================

def preview_image(image_path):

    try:

        img = Image.open(image_path)

        img.thumbnail(
            (760, 300)
        )

        photo = ImageTk.PhotoImage(img)

        image_label.configure(
            image=photo,
            text=""
        )

        image_label.image = photo

    except Exception as e:

        print(
            "Preview error:",
            e
        )


def preview_frame(frame):
    """Preview an OpenCV BGR frame in the image area."""

    try:

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        img = Image.fromarray(rgb)

        img.thumbnail(
            (760, 300)
        )

        photo = ImageTk.PhotoImage(img)

        image_label.configure(
            image=photo,
            text=""
        )

        image_label.image = photo

    except Exception as e:

        print(
            "Frame preview error:",
            e
        )


# ============================================================
# UPLOAD SINGLE IMAGE
# ============================================================

def upload_image():

    global selected_images
    global selected_video

    file_path = filedialog.askopenfilename(
        title="Select Vehicle Image",
        filetypes=[
            (
                "Image Files",
                "*.jpg *.jpeg *.png *.bmp"
            )
        ]
    )

    if not file_path:
        return

    selected_video = None

    selected_images = [
        file_path
    ]

    preview_image(
        file_path
    )

    selected_files_label.configure(
        text=(
            f"Selected Images: 1\n"
            f"{os.path.basename(file_path)}"
        )
    )

    status_label.configure(
        text="Image selected. Ready for detection."
    )


# ============================================================
# UPLOAD MULTIPLE IMAGES
# ============================================================

def upload_multiple_images():

    global selected_images
    global selected_video

    file_paths = filedialog.askopenfilenames(
        title="Select Multiple Vehicle Images",
        filetypes=[
            (
                "Image Files",
                "*.jpg *.jpeg *.png *.bmp"
            )
        ]
    )

    if not file_paths:
        return

    selected_video = None

    selected_images = list(
        file_paths
    )

    preview_image(
        selected_images[0]
    )

    if len(selected_images) == 1:

        text = (
            "Selected Images: 1\n"
            f"{os.path.basename(selected_images[0])}"
        )

    else:

        text = (
            f"Selected Images: "
            f"{len(selected_images)}\n"
            f"First: "
            f"{os.path.basename(selected_images[0])}"
        )

    selected_files_label.configure(
        text=text
    )

    status_label.configure(
        text=(
            f"{len(selected_images)} images "
            "selected. Ready for processing."
        )
    )


# ============================================================
# UPLOAD VIDEO
# ============================================================

def upload_video():

    global selected_images
    global selected_video

    file_path = filedialog.askopenfilename(
        title="Select Vehicle Video",
        filetypes=[
            (
                "Video Files",
                VIDEO_FILE_TYPES
            )
        ]
    )

    if not file_path:

        return

    selected_video = file_path

    selected_images = []

    frame = read_preview_frame(file_path)

    if frame is not None:

        preview_frame(frame)

    else:

        image_label.configure(
            image="",
            text="Could not read video preview"
        )

        image_label.image = None

    selected_files_label.configure(
        text=(
            "Selected Video:\n"
            f"{os.path.basename(file_path)}"
        )
    )

    status_label.configure(
        text="Video selected. Ready for detection."
    )


# ============================================================
# CLEAR CURRENT SELECTION
# ============================================================

def clear_selection():

    global selected_images
    global selected_video

    selected_images = []

    selected_video = None

    image_label.configure(
        image="",
        text="Image Preview Area"
    )

    image_label.image = None

    selected_files_label.configure(
        text="Selected Images: 0"
    )

    result_textbox.delete(
        "1.0",
        "end"
    )

    status_label.configure(
        text="Selection cleared."
    )


# ============================================================
# PROCESS IMAGES
# ============================================================

def detect_plate():
    """Validate the selection and start detection in a worker thread."""

    has_video = selected_video is not None

    if not selected_images and not has_video:

        messagebox.showwarning(
            "No Input",
            "Please upload one or more images "
            "or a video first."
        )

        return

    camera = get_selected_camera()

    if camera is None:

        messagebox.showwarning(
            "Camera Required",
            "Please select a camera location."
        )

        return

    result_textbox.delete(
        "1.0",
        "end"
    )

    detect_btn.configure(state="disabled")

    if has_video:

        result_textbox.insert(
            "end",
            f"Processing video: "
            f"{os.path.basename(selected_video)}\n"
        )

        status_label.configure(
            text="AI Engine analyzing video..."
        )

        worker = threading.Thread(
            target=_process_video,
            args=(selected_video, dict(camera)),
            daemon=True
        )

    else:

        result_textbox.insert(
            "end",
            f"Processing {len(selected_images)} image(s) "
            "with the AI Engine...\n"
        )

        status_label.configure(
            text="AI Engine processing images..."
        )

        worker = threading.Thread(
            target=_process_images,
            args=(list(selected_images), dict(camera)),
            daemon=True
        )

    worker.start()


def _process_images(image_paths, camera):
    """Background worker: run detection and persist records.

    This function must never touch Tk widgets. Results are
    handed back to the main thread through result_queue.
    """

    processed_count = 0

    new_detections = []

    # ========================================================
    # PROCESS EACH IMAGE
    # ========================================================

    for image_path in image_paths:

        print("\n====================================")
        print("Processing image:")
        print(image_path)
        print("Camera:")
        print(camera["id"])
        print("Location:")
        print(camera["location"])
        print("====================================")

        try:

            detections = detect_number_plates(
                image_path
            )

        except Exception as e:

            print(
                "Detection error:",
                e
            )

            continue

        processed_count += 1

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # ====================================================
        # STORE EVERY DETECTION
        # ====================================================

        for detection in detections:

            plate = detection[
                "plate_number"
            ]

            confidence = detection[
                "confidence"
            ]

            detection_record = {

                "plate_number": plate,

                "confidence": confidence,

                "camera_id": camera["id"],

                "location": camera["location"],

                "timestamp": timestamp,

                "image_path": image_path,

                "bbox": detection[
                    "bbox"
                ],

                "cropped_plate": detection[
                    "cropped_plate"
                ],

                "preprocessed_plate": detection[
                    "preprocessed_plate"
                ]
            }

            new_detections.append(
                detection_record
            )

    # ========================================================
    # PERSIST TO DATABASE (WORKER THREAD, NO UI CALLS)
    # ========================================================

    saved_count = 0

    if new_detections:

        try:

            saved_count = save_detections(
                new_detections
            )

        except Exception as e:

            print(
                "Database save error:",
                e
            )

    # ========================================================
    # HAND BACK TO THE MAIN THREAD
    # ========================================================

    result_queue.put(
        (
            "finished",
            new_detections,
            f"{processed_count} image(s)",
            saved_count
        )
    )


def _process_video(video_path, camera):
    """Background worker: analyze a video file (no Tk calls)."""

    def progress(sampled_frames, seconds):

        result_queue.put(
            (
                "progress",
                f"Analyzing video... {sampled_frames} frame(s) "
                f"(~{seconds:.0f}s of footage)"
            )
        )

    try:

        result = analyze_video(
            video_path,
            progress_callback=progress
        )

        detections = result["detections"]

        source_label = (
            f"video ({result['sampled_frames']} frame(s))"
        )

    except Exception as error:

        print("Video analysis error:", error)

        detections = []

        source_label = "video"

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    new_detections = []

    for detection in detections:

        new_detections.append({

            "plate_number": detection["plate_number"],

            "confidence": detection["confidence"],

            "camera_id": camera["id"],

            "location": camera["location"],

            "timestamp": timestamp,

            "image_path": detection["image_path"],

            "bbox": detection["bbox"],

            "cropped_plate": detection["cropped_plate"],

            "preprocessed_plate": detection["preprocessed_plate"]
        })

    saved_count = 0

    if new_detections:

        try:

            saved_count = save_detections(
                new_detections
            )

        except Exception as e:

            print(
                "Database save error:",
                e
            )

    result_queue.put(
        (
            "finished",
            new_detections,
            source_label,
            saved_count
        )
    )


def poll_results():
    """Main-thread queue consumer for worker messages."""

    try:

        while True:

            message = result_queue.get_nowait()

            _handle_worker_message(message)

    except queue.Empty:

        pass

    app.after(
        200,
        poll_results
    )


def _handle_worker_message(message):
    """Dispatch one worker message on the main thread."""

    kind = message[0]

    if kind == "progress":

        status_label.configure(text=message[1])

    elif kind == "finished":

        _detection_finished(
            message[1],
            message[2],
            message[3]
        )


def _detection_finished(
    new_detections,
    source_label,
    saved_count
):
    """Main-thread callback: refresh the dashboard."""

    global all_detections
    global trajectory_data

    # ========================================================
    # ADD TO GLOBAL DETECTIONS
    # ========================================================

    all_detections.extend(
        new_detections
    )

    # ========================================================
    # TRAJECTORY DATA
    # ========================================================

    for detection in new_detections:

        plate = detection["plate_number"]

        if plate not in INVALID_PLATES:

            trajectory_data[
                plate
            ].append(
                detection
            )

    # ========================================================
    # DISPLAY RESULTS
    # ========================================================

    result_textbox.delete(
        "1.0",
        "end"
    )

    if not new_detections:

        result_textbox.insert(
            "end",
            "No readable number plates detected.\n"
        )

    else:

        result_textbox.insert(
            "end",
            "CITY-WIDE AI DETECTION RESULTS\n"
        )

        result_textbox.insert(
            "end",
            "====================================\n\n"
        )

        for index, detection in enumerate(
            new_detections,
            start=1
        ):

            plate = detection[
                "plate_number"
            ]

            confidence = detection[
                "confidence"
            ]

            camera_id = detection[
                "camera_id"
            ]

            location = detection[
                "location"
            ]

            timestamp = detection[
                "timestamp"
            ]

            image_name = os.path.basename(
                detection[
                    "image_path"
                ]
            )

            result_textbox.insert(
                "end",
                f"Detection {index}\n"
            )

            result_textbox.insert(
                "end",
                f"Plate       : {plate}\n"
            )

            result_textbox.insert(
                "end",
                f"Confidence  : "
                f"{confidence:.2f}\n"
            )

            result_textbox.insert(
                "end",
                f"Camera      : {camera_id}\n"
            )

            result_textbox.insert(
                "end",
                f"Location    : {location}\n"
            )

            result_textbox.insert(
                "end",
                f"Timestamp   : {timestamp}\n"
            )

            result_textbox.insert(
                "end",
                f"Image       : {image_name}\n"
            )

            result_textbox.insert(
                "end",
                "------------------------------------\n"
            )

    # ========================================================
    # UPDATE TRAJECTORY
    # ========================================================

    update_trajectory_view()

    # ========================================================
    # UPDATE STATISTICS
    # ========================================================

    update_statistics()

    # ========================================================
    # UPDATE ANALYTICS
    # ========================================================

    update_analytics_view()

    # ========================================================
    # STATUS
    # ========================================================

    if new_detections:

        preview_image(
            new_detections[0]["image_path"]
        )

    status_label.configure(
        text=(
            f"Processed {source_label} | "
            f"Detected {len(new_detections)} plate(s) | "
            f"Saved {saved_count} record(s)"
        )
    )

    detect_btn.configure(state="normal")


# ============================================================
# TRAJECTORY VIEW
# ============================================================

def update_trajectory_view():

    trajectory_textbox.delete(
        "1.0",
        "end"
    )

    if not trajectory_data:

        trajectory_textbox.insert(
            "end",
            "No vehicle trajectories yet."
        )

        return

    trajectory_textbox.insert(
        "end",
        "VEHICLE TRAJECTORIES\n"
    )

    trajectory_textbox.insert(
        "end",
        "====================================\n\n"
    )

    for plate, events in trajectory_data.items():

        if plate in INVALID_PLATES:
            continue

        trajectory_textbox.insert(
            "end",
            f"Vehicle: {plate}\n"
        )

        trajectory_textbox.insert(
            "end",
            "Path:\n"
        )

        for event in events:

            trajectory_textbox.insert(
                "end",
                f"  {event['camera_id']} "
                f"→ {event['location']} "
                f"at {event['timestamp']}\n"
            )

        # ====================================================
        # SHOW MOVEMENT
        # ====================================================

        unique_cameras = list(
            dict.fromkeys(
                event["camera_id"]
                for event in events
            )
        )

        unique_locations = list(
            dict.fromkeys(
                event["location"]
                for event in events
            )
        )

        if len(unique_cameras) > 1:

            path = " → ".join(
                unique_cameras
            )

            locations = " → ".join(
                unique_locations
            )

            trajectory_textbox.insert(
                "end",
                f"\nTrajectory: {path}\n"
            )

            trajectory_textbox.insert(
                "end",
                f"Route: {locations}\n"
            )

            trajectory_textbox.insert(
                "end",
                "\nStatus: MULTI-CAMERA VEHICLE\n"
            )

        else:

            trajectory_textbox.insert(
                "end",
                "\nTrajectory: "
                "Single camera observation\n"
            )

        trajectory_textbox.insert(
            "end",
            "------------------------------------\n"
        )

    trajectory_textbox.see(
        "end"
    )


# ============================================================
# SHOW ALL DETECTIONS
# ============================================================

def show_all_detections():

    result_textbox.delete(
        "1.0",
        "end"
    )

    if not all_detections:

        result_textbox.insert(
            "end",
            "No detections available."
        )

        return

    result_textbox.insert(
        "end",
        "ALL DETECTION EVENTS\n"
    )

    result_textbox.insert(
        "end",
        "====================================\n\n"
    )

    for index, detection in enumerate(
        all_detections,
        start=1
    ):

        result_textbox.insert(
            "end",
            f"{index}. "
            f"{detection['plate_number']} | "
            f"{detection['camera_id']} | "
            f"{detection['location']} | "
            f"{detection['timestamp']}\n"
        )

    result_textbox.see(
        "end"
    )


# ============================================================
# SHOW DATABASE HISTORY
# ============================================================

def show_history():

    result_textbox.delete(
        "1.0",
        "end"
    )

    result_textbox.insert(
        "end",
        "DETECTION HISTORY (vehicle_database.csv)\n"
    )

    result_textbox.insert(
        "end",
        "====================================\n\n"
    )

    result_textbox.insert(
        "end",
        get_history()
    )

    result_textbox.see(
        "end"
    )


# ============================================================
# CLEAR ALL DATA
# ============================================================

def clear_all_data():

    global all_detections
    global trajectory_data

    all_detections = []

    trajectory_data = defaultdict(list)

    result_textbox.delete(
        "1.0",
        "end"
    )

    trajectory_textbox.delete(
        "1.0",
        "end"
    )

    analytics_textbox.delete(
        "1.0",
        "end"
    )

    trajectory_textbox.insert(
        "end",
        "No vehicle trajectories yet."
    )

    analytics_textbox.insert(
        "end",
        "No traffic analytics available yet.\n\n"
        "Upload vehicle images and run AI Detection."
    )

    update_statistics()

    status_label.configure(
        text="All session data cleared."
    )


# ============================================================
# OPEN OUTPUT FOLDER
# ============================================================

def view_output_folder():

    if os.path.exists(OUTPUT_DIR):

        os.startfile(
            OUTPUT_DIR
        )

    else:

        messagebox.showwarning(
            "Output Folder",
            "Output folder not found."
        )


# ============================================================
# HEADER
# ============================================================

header_frame = ctk.CTkFrame(
    app,
    fg_color="transparent"
)

header_frame.pack(
    fill="x",
    padx=25,
    pady=(20, 5)
)


title = ctk.CTkLabel(
    header_frame,
    text=(
        "🚦 CITY-WIDE AI TRAFFIC ENGINE"
    ),
    font=(
        "Arial",
        30,
        "bold"
    )
)

title.pack()


subtitle = ctk.CTkLabel(
    header_frame,
    text=(
        "Multi-Camera ANPR • Vehicle Trajectory "
        "Tracking • Urban Traffic Analytics"
    ),
    font=(
        "Arial",
        15
    )
)

subtitle.pack(
    pady=(5, 0)
)


# ============================================================
# CAMERA SELECTION
# ============================================================

camera_frame = ctk.CTkFrame(
    app
)

camera_frame.pack(
    fill="x",
    padx=25,
    pady=15
)


camera_title = ctk.CTkLabel(
    camera_frame,
    text="📡 Camera / Location",
    font=(
        "Arial",
        17,
        "bold"
    )
)

camera_title.pack(
    side="left",
    padx=20,
    pady=15
)


camera_dropdown = ctk.CTkComboBox(
    camera_frame,
    values=list(
        CAMERAS.keys()
    ),
    width=320,
    height=40,
    command=update_camera_info
)

camera_dropdown.set(
    list(CAMERAS.keys())[0]
)

camera_dropdown.pack(
    side="left",
    padx=10
)


camera_info_label = ctk.CTkLabel(
    camera_frame,
    text=(
        "Camera ID: CAM-01\n"
        "Location: Suchitra Junction"
    ),
    font=(
        "Arial",
        14
    ),
    justify="left"
)

camera_info_label.pack(
    side="left",
    padx=30
)


# ============================================================
# STATISTICS CARDS
# ============================================================

stats_frame = ctk.CTkFrame(
    app,
    fg_color="transparent"
)

stats_frame.pack(
    fill="x",
    padx=25,
    pady=5
)


# ============================================================
# TOTAL DETECTIONS
# ============================================================

total_card = ctk.CTkFrame(
    stats_frame
)

total_card.pack(
    side="left",
    fill="both",
    expand=True,
    padx=5
)


ctk.CTkLabel(
    total_card,
    text="TOTAL OBSERVATIONS",
    font=(
        "Arial",
        13,
        "bold"
    )
).pack(
    pady=(12, 3)
)


total_label = ctk.CTkLabel(
    total_card,
    text="0",
    font=(
        "Arial",
        25,
        "bold"
    )
)

total_label.pack(
    pady=(0, 12)
)


# ============================================================
# UNIQUE VEHICLES
# ============================================================

unique_card = ctk.CTkFrame(
    stats_frame
)

unique_card.pack(
    side="left",
    fill="both",
    expand=True,
    padx=5
)


ctk.CTkLabel(
    unique_card,
    text="UNIQUE VEHICLES",
    font=(
        "Arial",
        13,
        "bold"
    )
).pack(
    pady=(12, 3)
)


unique_label = ctk.CTkLabel(
    unique_card,
    text="0",
    font=(
        "Arial",
        25,
        "bold"
    )
)

unique_label.pack(
    pady=(0, 12)
)


# ============================================================
# ACTIVE CAMERAS
# ============================================================

camera_card = ctk.CTkFrame(
    stats_frame
)

camera_card.pack(
    side="left",
    fill="both",
    expand=True,
    padx=5
)


ctk.CTkLabel(
    camera_card,
    text="ACTIVE CAMERAS",
    font=(
        "Arial",
        13,
        "bold"
    )
).pack(
    pady=(12, 3)
)


camera_count_label = ctk.CTkLabel(
    camera_card,
    text="0",
    font=(
        "Arial",
        25,
        "bold"
    )
)

camera_count_label.pack(
    pady=(0, 12)
)


# ============================================================
# MULTI-CAMERA TRAJECTORIES
# ============================================================

trajectory_card = ctk.CTkFrame(
    stats_frame
)

trajectory_card.pack(
    side="left",
    fill="both",
    expand=True,
    padx=5
)


ctk.CTkLabel(
    trajectory_card,
    text="MULTI-CAMERA VEHICLES",
    font=(
        "Arial",
        13,
        "bold"
    )
).pack(
    pady=(12, 3)
)


trajectory_count_label = ctk.CTkLabel(
    trajectory_card,
    text="0",
    font=(
        "Arial",
        25,
        "bold"
    )
)

trajectory_count_label.pack(
    pady=(0, 12)
)


# ============================================================
# MAIN CONTENT
# ============================================================

main_frame = ctk.CTkFrame(
    app
)

main_frame.pack(
    fill="both",
    expand=True,
    padx=25,
    pady=15
)


# ============================================================
# LEFT PANEL
# ============================================================

left_frame = ctk.CTkFrame(
    main_frame,
    width=350
)

left_frame.pack(
    side="left",
    fill="y",
    padx=(15, 10),
    pady=15
)

left_frame.pack_propagate(
    False
)


# ============================================================
# UPLOAD SINGLE
# ============================================================

upload_btn = ctk.CTkButton(
    left_frame,
    text="📷 Upload Image",
    width=280,
    height=45,
    command=upload_image
)

upload_btn.pack(
    pady=(25, 10)
)


# ============================================================
# UPLOAD MULTIPLE
# ============================================================

multi_upload_btn = ctk.CTkButton(
    left_frame,
    text="📂 Upload Multiple Images",
    width=280,
    height=45,
    command=upload_multiple_images
)

multi_upload_btn.pack(
    pady=10
)


# ============================================================
# UPLOAD VIDEO
# ============================================================

video_btn = ctk.CTkButton(
    left_frame,
    text="🎬 Upload Video",
    width=280,
    height=45,
    command=upload_video
)

video_btn.pack(
    pady=10
)


# ============================================================
# DETECT
# ============================================================

detect_btn = ctk.CTkButton(
    left_frame,
    text="🤖 Run AI Detection",
    width=280,
    height=50,
    command=detect_plate
)

detect_btn.pack(
    pady=20
)


# ============================================================
# CLEAR SELECTION
# ============================================================

clear_btn = ctk.CTkButton(
    left_frame,
    text="Clear Selection",
    width=280,
    height=40,
    command=clear_selection
)

clear_btn.pack(
    pady=5
)


# ============================================================
# SELECTED IMAGES
# ============================================================

selected_files_label = ctk.CTkLabel(
    left_frame,
    text="Selected Images: 0",
    font=(
        "Arial",
        13
    ),
    wraplength=280
)

selected_files_label.pack(
    pady=20
)


# ============================================================
# STATUS
# ============================================================

status_label = ctk.CTkLabel(
    left_frame,
    text="Ready.",
    font=(
        "Arial",
        13
    ),
    wraplength=280
)

status_label.pack(
    pady=10
)


# ============================================================
# OPEN OUTPUT
# ============================================================

output_btn = ctk.CTkButton(
    left_frame,
    text="📁 Open Output Folder",
    width=280,
    height=40,
    command=view_output_folder
)

output_btn.pack(
    pady=10
)


# ============================================================
# SHOW ALL
# ============================================================

show_all_btn = ctk.CTkButton(
    left_frame,
    text="View All Detection Events",
    width=280,
    height=40,
    command=show_all_detections
)

show_all_btn.pack(
    pady=10
)


# ============================================================
# VIEW DATABASE HISTORY
# ============================================================

history_btn = ctk.CTkButton(
    left_frame,
    text="🗄️ View Detection History",
    width=280,
    height=40,
    command=show_history
)

history_btn.pack(
    pady=10
)


# ============================================================
# CLEAR SESSION
# ============================================================

clear_all_btn = ctk.CTkButton(
    left_frame,
    text="Clear Session Data",
    width=280,
    height=40,
    command=clear_all_data
)

clear_all_btn.pack(
    pady=10
)


# ============================================================
# RIGHT PANEL
# SCROLLABLE DASHBOARD
# ============================================================

right_frame = ctk.CTkScrollableFrame(
    main_frame
)

right_frame.pack(
    side="right",
    fill="both",
    expand=True,
    padx=(10, 15),
    pady=15
)


# ============================================================
# IMAGE PREVIEW
# ============================================================

preview_title = ctk.CTkLabel(
    right_frame,
    text="Vehicle Image",
    font=(
        "Arial",
        18,
        "bold"
    )
)

preview_title.pack(
    pady=(10, 5)
)


image_label = ctk.CTkLabel(
    right_frame,
    text="Image Preview Area",
    font=(
        "Arial",
        20
    ),
    height=300
)

image_label.pack(
    fill="x",
    padx=20,
    pady=10
)


# ============================================================
# RESULT AREA
# ============================================================

result_title = ctk.CTkLabel(
    right_frame,
    text="Detection Results",
    font=(
        "Arial",
        17,
        "bold"
    )
)

result_title.pack(
    pady=(5, 5)
)


result_textbox = ctk.CTkTextbox(
    right_frame,
    height=170,
    wrap="word",
    font=(
        "Consolas",
        13
    )
)

result_textbox.pack(
    fill="x",
    padx=20,
    pady=5
)


# ============================================================
# TRAJECTORY AREA
# ============================================================

trajectory_title = ctk.CTkLabel(
    right_frame,
    text="🚗 Multi-Camera Vehicle Trajectory",
    font=(
        "Arial",
        17,
        "bold"
    )
)

trajectory_title.pack(
    pady=(15, 5)
)


trajectory_textbox = ctk.CTkTextbox(
    right_frame,
    height=230,
    wrap="word",
    font=(
        "Consolas",
        13
    )
)

trajectory_textbox.pack(
    fill="x",
    padx=20,
    pady=(5, 20)
)


trajectory_textbox.insert(
    "end",
    "No vehicle trajectories yet."
)


# ============================================================
# URBAN TRAFFIC ANALYTICS
# ============================================================

analytics_title = ctk.CTkLabel(
    right_frame,
    text="🚦 Urban Traffic Analytics",
    font=(
        "Arial",
        18,
        "bold"
    )
)

analytics_title.pack(
    pady=(5, 5)
)


analytics_textbox = ctk.CTkTextbox(
    right_frame,
    height=420,
    wrap="word",
    font=(
        "Consolas",
        13
    )
)

analytics_textbox.pack(
    fill="x",
    padx=20,
    pady=(5, 20)
)


analytics_textbox.insert(
    "end",
    "No traffic analytics available yet.\n\n"
    "Upload vehicle images and run AI Detection."
)


# ============================================================
# SYSTEM INFORMATION
# ============================================================

info_title = ctk.CTkLabel(
    right_frame,
    text="System Information",
    font=(
        "Arial",
        17,
        "bold"
    )
)

info_title.pack(
    pady=(5, 5)
)


info_textbox = ctk.CTkTextbox(
    right_frame,
    height=150,
    wrap="word",
    font=(
        "Consolas",
        12
    )
)

info_textbox.pack(
    fill="x",
    padx=20,
    pady=(5, 20)
)


info_textbox.insert(
    "end",
    "CITY-WIDE AI TRAFFIC ENGINE\n"
    "--------------------------------------------\n"
    "AI Engine        : YOLOv8 + Tesseract OCR\n"
    "Input Mode       : Image + Video Upload\n"
    "Video Mode       : Frame Sampling + Temporal Voting\n"
    "Vehicle Identity : License Plate Number\n"
    "Camera Mode      : Multi-Camera Simulation\n"
    "Association       : Cross-Camera ANPR\n"
    "Trajectory        : Camera Route Reconstruction\n"
    "Analytics         : Session-Based Traffic Activity\n"
    "Database          : vehicle_database.csv (persistent)\n"
    "Processing        : Background Thread\n"
    "\n"
    "Current Prototype:\n"
    "Individual vehicle images are assigned to "
    "simulated camera locations to demonstrate "
    "city-wide ANPR, vehicle association, routes "
    "and traffic activity analytics.\n"
)


# ============================================================
# START APPLICATION
# ============================================================

update_camera_info()

update_statistics()

update_analytics_view()


# ============================================================
# STARTUP DEPENDENCY CHECK
# ============================================================

problems = check_dependencies()

if problems:

    print("\nSTARTUP WARNINGS:")

    for problem in problems:

        print(" -", problem)

    status_label.configure(
        text="Startup warning: " + problems[0]
    )


# ============================================================
# START RESULT POLLING + APPLICATION
# ============================================================

app.after(
    200,
    poll_results
)

app.mainloop()