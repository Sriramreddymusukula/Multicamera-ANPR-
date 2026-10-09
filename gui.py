"""
City-Wide AI Traffic Engine - desktop dashboard.

The GUI owns session state (detections + trajectories), starts
detection work on background threads and renders results on the
Tk main thread. Workers communicate exclusively through a queue -
they never touch widgets.
"""

import logging
import os
import queue
import threading
from collections import defaultdict
from tkinter import filedialog, messagebox

import cv2
import customtkinter as ctk
from PIL import Image, ImageTk

from analytics import (
    INVALID_PLATES,
    active_camera_count,
    camera_statistics,
    multi_camera_vehicles,
    traffic_activity,
    unique_plate_count,
    valid_detections,
    vehicle_observation_statistics
)
from config import (
    CAMERA_LOCATION_BY_ID,
    CAMERAS,
    IMAGE_FILE_TYPES,
    LOG_LEVEL,
    OUTPUT_DIR,
    VIDEO_FILE_TYPES
)
from detector import check_dependencies
from history import get_history
from processing import process_images, process_video
from video import read_preview_frame

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

WINDOW_TITLE = "City-Wide AI Engine - Multi-Camera ANPR"
PREVIEW_SIZE = (760, 300)
POLL_INTERVAL_MS = 200


class ANPRApp:

    def __init__(self):

        self.selected_images = []
        self.selected_video = None
        self.all_detections = []
        self.trajectory_data = defaultdict(list)
        self.result_queue = queue.Queue()

        self.app = ctk.CTk()
        self.app.title(WINDOW_TITLE)
        self.app.geometry("1500x950")
        self.app.minsize(1200, 750)

        self._build_ui()

        self.update_camera_info()
        self.update_statistics()
        self.update_analytics_view()
        self._check_startup_dependencies()

        self.app.after(POLL_INTERVAL_MS, self.poll_results)

    def run(self):

        self.app.mainloop()

    # ========================================================
    # UI CONSTRUCTION
    # ========================================================

    def _build_ui(self):

        header_frame = ctk.CTkFrame(
            self.app,
            fg_color="transparent"
        )

        header_frame.pack(
            fill="x",
            padx=25,
            pady=(20, 5)
        )

        ctk.CTkLabel(
            header_frame,
            text="🚦 CITY-WIDE AI TRAFFIC ENGINE",
            font=("Arial", 30, "bold")
        ).pack()

        ctk.CTkLabel(
            header_frame,
            text=(
                "Multi-Camera ANPR • Vehicle Trajectory "
                "Tracking • Urban Traffic Analytics"
            ),
            font=("Arial", 15)
        ).pack(
            pady=(5, 0)
        )

        self._build_camera_bar()

        self._build_stat_cards()

        main_frame = ctk.CTkFrame(self.app)

        main_frame.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=15
        )

        self._build_left_panel(main_frame)

        self._build_right_panel(main_frame)

    def _build_camera_bar(self):

        camera_frame = ctk.CTkFrame(self.app)

        camera_frame.pack(
            fill="x",
            padx=25,
            pady=15
        )

        ctk.CTkLabel(
            camera_frame,
            text="📡 Camera / Location",
            font=("Arial", 17, "bold")
        ).pack(
            side="left",
            padx=20,
            pady=15
        )

        self.camera_dropdown = ctk.CTkComboBox(
            camera_frame,
            values=list(CAMERAS.keys()),
            width=320,
            height=40,
            command=self.update_camera_info
        )

        self.camera_dropdown.set(
            list(CAMERAS.keys())[0]
        )

        self.camera_dropdown.pack(
            side="left",
            padx=10
        )

        self.camera_info_label = ctk.CTkLabel(
            camera_frame,
            text=(
                "Camera ID: CAM-01\n"
                "Location: Suchitra Junction"
            ),
            font=("Arial", 14),
            justify="left"
        )

        self.camera_info_label.pack(
            side="left",
            padx=30
        )

    def _build_stat_cards(self):

        stats_frame = ctk.CTkFrame(
            self.app,
            fg_color="transparent"
        )

        stats_frame.pack(
            fill="x",
            padx=25,
            pady=5
        )

        self.total_label = self._make_stat_card(
            stats_frame,
            "TOTAL OBSERVATIONS"
        )

        self.unique_label = self._make_stat_card(
            stats_frame,
            "UNIQUE VEHICLES"
        )

        self.camera_count_label = self._make_stat_card(
            stats_frame,
            "ACTIVE CAMERAS"
        )

        self.trajectory_count_label = self._make_stat_card(
            stats_frame,
            "MULTI-CAMERA VEHICLES"
        )

    def _make_stat_card(self, parent, title):

        card = ctk.CTkFrame(parent)

        card.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5
        )

        ctk.CTkLabel(
            card,
            text=title,
            font=("Arial", 13, "bold")
        ).pack(
            pady=(12, 3)
        )

        value_label = ctk.CTkLabel(
            card,
            text="0",
            font=("Arial", 25, "bold")
        )

        value_label.pack(
            pady=(0, 12)
        )

        return value_label

    def _build_left_panel(self, main_frame):

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

        left_frame.pack_propagate(False)

        ctk.CTkButton(
            left_frame,
            text="📷 Upload Image",
            width=280,
            height=45,
            command=self.upload_image
        ).pack(
            pady=(25, 10)
        )

        ctk.CTkButton(
            left_frame,
            text="📂 Upload Multiple Images",
            width=280,
            height=45,
            command=self.upload_multiple_images
        ).pack(
            pady=10
        )

        ctk.CTkButton(
            left_frame,
            text="🎬 Upload Video",
            width=280,
            height=45,
            command=self.upload_video
        ).pack(
            pady=10
        )

        self.detect_btn = ctk.CTkButton(
            left_frame,
            text="🤖 Run AI Detection",
            width=280,
            height=50,
            command=self.detect_plate
        )

        self.detect_btn.pack(
            pady=20
        )

        ctk.CTkButton(
            left_frame,
            text="Clear Selection",
            width=280,
            height=40,
            command=self.clear_selection
        ).pack(
            pady=5
        )

        self.selected_files_label = ctk.CTkLabel(
            left_frame,
            text="Selected Images: 0",
            font=("Arial", 13),
            wraplength=280
        )

        self.selected_files_label.pack(
            pady=20
        )

        self.status_label = ctk.CTkLabel(
            left_frame,
            text="Ready.",
            font=("Arial", 13),
            wraplength=280
        )

        self.status_label.pack(
            pady=10
        )

        ctk.CTkButton(
            left_frame,
            text="📁 Open Output Folder",
            width=280,
            height=40,
            command=self.view_output_folder
        ).pack(
            pady=10
        )

        ctk.CTkButton(
            left_frame,
            text="View All Detection Events",
            width=280,
            height=40,
            command=self.show_all_detections
        ).pack(
            pady=10
        )

        ctk.CTkButton(
            left_frame,
            text="🗄️ View Detection History",
            width=280,
            height=40,
            command=self.show_history
        ).pack(
            pady=10
        )

        ctk.CTkButton(
            left_frame,
            text="Clear Session Data",
            width=280,
            height=40,
            command=self.clear_all_data
        ).pack(
            pady=10
        )

    def _build_right_panel(self, main_frame):

        right_frame = ctk.CTkScrollableFrame(main_frame)

        right_frame.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(10, 15),
            pady=15
        )

        ctk.CTkLabel(
            right_frame,
            text="Vehicle Image",
            font=("Arial", 18, "bold")
        ).pack(
            pady=(10, 5)
        )

        self.image_label = ctk.CTkLabel(
            right_frame,
            text="Image Preview Area",
            font=("Arial", 20),
            height=300
        )

        self.image_label.pack(
            fill="x",
            padx=20,
            pady=10
        )

        ctk.CTkLabel(
            right_frame,
            text="Detection Results",
            font=("Arial", 17, "bold")
        ).pack(
            pady=(5, 5)
        )

        self.result_textbox = ctk.CTkTextbox(
            right_frame,
            height=170,
            wrap="word",
            font=("Consolas", 13)
        )

        self.result_textbox.pack(
            fill="x",
            padx=20,
            pady=5
        )

        ctk.CTkLabel(
            right_frame,
            text="🚗 Multi-Camera Vehicle Trajectory",
            font=("Arial", 17, "bold")
        ).pack(
            pady=(15, 5)
        )

        self.trajectory_textbox = ctk.CTkTextbox(
            right_frame,
            height=230,
            wrap="word",
            font=("Consolas", 13)
        )

        self.trajectory_textbox.pack(
            fill="x",
            padx=20,
            pady=(5, 20)
        )

        self.trajectory_textbox.insert(
            "end",
            "No vehicle trajectories yet."
        )

        ctk.CTkLabel(
            right_frame,
            text="🚦 Urban Traffic Analytics",
            font=("Arial", 18, "bold")
        ).pack(
            pady=(5, 5)
        )

        self.analytics_textbox = ctk.CTkTextbox(
            right_frame,
            height=420,
            wrap="word",
            font=("Consolas", 13)
        )

        self.analytics_textbox.pack(
            fill="x",
            padx=20,
            pady=(5, 20)
        )

        self.analytics_textbox.insert(
            "end",
            "No traffic analytics available yet.\n\n"
            "Upload vehicle images and run AI Detection."
        )

        ctk.CTkLabel(
            right_frame,
            text="System Information",
            font=("Arial", 17, "bold")
        ).pack(
            pady=(5, 5)
        )

        self.info_textbox = ctk.CTkTextbox(
            right_frame,
            height=150,
            wrap="word",
            font=("Consolas", 12)
        )

        self.info_textbox.pack(
            fill="x",
            padx=20,
            pady=(5, 20)
        )

        self.info_textbox.insert(
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

    # ========================================================
    # SESSION HELPERS
    # ========================================================

    def get_selected_camera(self):

        camera_name = self.camera_dropdown.get()

        if camera_name not in CAMERAS:

            return None

        return CAMERAS[camera_name]

    def update_camera_info(self, choice=None):

        camera = self.get_selected_camera()

        if camera:

            self.camera_info_label.configure(
                text=(
                    f"Camera ID: {camera['id']}\n"
                    f"Location: {camera['location']}"
                )
            )

    def update_statistics(self):

        valid = valid_detections(self.all_detections)

        self.total_label.configure(
            text=str(len(valid))
        )

        self.unique_label.configure(
            text=str(unique_plate_count(valid))
        )

        self.camera_count_label.configure(
            text=str(active_camera_count(self.all_detections))
        )

        self.trajectory_count_label.configure(
            text=str(
                len(
                    multi_camera_vehicles(self.trajectory_data)
                )
            )
        )

    # ========================================================
    # ANALYTICS
    # ========================================================

    def update_analytics_view(self):

        valid = valid_detections(self.all_detections)

        self.analytics_textbox.delete("1.0", "end")

        if not valid:

            self.analytics_textbox.insert(
                "end",
                "No traffic analytics available yet.\n\n"
                "Upload vehicle images and run AI Detection."
            )

            return

        self.analytics_textbox.insert(
            "end",
            self._build_analytics_text(valid)
        )

        self.analytics_textbox.see("end")

    def _build_analytics_text(self, valid):

        activity_level = traffic_activity(valid)

        multi_camera = multi_camera_vehicles(self.trajectory_data)

        parts = [

            "URBAN TRAFFIC ANALYTICS\n",

            "============================================\n\n",

            "TRAFFIC SUMMARY\n",

            "--------------------------------------------\n",

            f"Vehicle Observations : {len(valid)}\n",

            f"Unique Vehicles      : "
            f"{unique_plate_count(valid)}\n",

            f"Active Cameras       : "
            f"{active_camera_count(valid)}\n",

            f"Multi-Camera Vehicles: {len(multi_camera)}\n",

            f"Traffic Activity     : {activity_level}\n\n",

            "CAMERA ACTIVITY\n",

            "--------------------------------------------\n"
        ]

        camera_stats = camera_statistics(valid)

        if not camera_stats:

            parts.append("No camera observations.\n\n")

        else:

            for camera_id, count in sorted(camera_stats.items()):

                location = CAMERA_LOCATION_BY_ID.get(
                    camera_id,
                    "Unknown"
                )

                parts.append(
                    f"{camera_id:<10} "
                    f"{location:<22} "
                    f"{count} observation(s)\n"
                )

            parts.append("\n")

        parts.append("VEHICLE OBSERVATION FREQUENCY\n")

        parts.append("--------------------------------------------\n")

        vehicle_stats = vehicle_observation_statistics(valid)

        sorted_vehicles = sorted(
            vehicle_stats.items(),
            key=lambda item: item[1],
            reverse=True
        )

        for plate, count in sorted_vehicles:

            parts.append(
                f"{plate:<15} "
                f"{count} observation(s)\n"
            )

        parts.append("\n")

        parts.append("MULTI-CAMERA VEHICLE MOVEMENT\n")

        parts.append("--------------------------------------------\n")

        if not multi_camera:

            parts.append("No multi-camera movement detected.\n\n")

        else:

            for vehicle in multi_camera:

                locations = list(
                    dict.fromkeys(
                        event["location"]
                        for event in vehicle["events"]
                    )
                )

                route = " → ".join(locations)

                parts.append(
                    f"Vehicle : {vehicle['plate']}\n"
                )

                parts.append(
                    f"Route   : {route}\n"
                )

                parts.append(
                    f"Cameras : "
                    f"{' → '.join(vehicle['cameras'])}\n\n"
                )

        parts.append("ANALYTICS INTERPRETATION\n")

        parts.append("--------------------------------------------\n")

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

        parts.append(f"{interpretation}\n\n")

        parts.append(
            "Note: Traffic Activity is calculated from "
            "ANPR observations in the current image-based "
            "demo session. It is not a real-time congestion "
            "measurement.\n"
        )

        return "".join(parts)

    # ========================================================
    # TRAJECTORY VIEW
    # ========================================================

    def update_trajectory_view(self):

        self.trajectory_textbox.delete("1.0", "end")

        if not self.trajectory_data:

            self.trajectory_textbox.insert(
                "end",
                "No vehicle trajectories yet."
            )

            return

        parts = [

            "VEHICLE TRAJECTORIES\n",

            "====================================\n\n"
        ]

        for plate, events in self.trajectory_data.items():

            parts.append(f"Vehicle: {plate}\n")

            parts.append("Path:\n")

            for event in events:

                parts.append(
                    f"  {event['camera_id']} "
                    f"→ {event['location']} "
                    f"at {event['timestamp']}\n"
                )

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

                path = " → ".join(unique_cameras)

                locations = " → ".join(unique_locations)

                parts.append(f"\nTrajectory: {path}\n")

                parts.append(f"Route: {locations}\n")

                parts.append("\nStatus: MULTI-CAMERA VEHICLE\n")

            else:

                parts.append(
                    "\nTrajectory: "
                    "Single camera observation\n"
                )

            parts.append("------------------------------------\n")

        self.trajectory_textbox.insert("end", "".join(parts))

        self.trajectory_textbox.see("end")

    # ========================================================
    # IMAGE PREVIEW
    # ========================================================

    def preview_image(self, image_path):

        try:

            with Image.open(image_path) as img:

                img.thumbnail(PREVIEW_SIZE)

                photo = ImageTk.PhotoImage(img)

            self.image_label.configure(
                image=photo,
                text=""
            )

            self.image_label.image = photo

        except Exception as error:

            logger.warning("Preview error: %s", error)

    def preview_frame(self, frame):

        try:

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            img = Image.fromarray(rgb)

            img.thumbnail(PREVIEW_SIZE)

            photo = ImageTk.PhotoImage(img)

            self.image_label.configure(
                image=photo,
                text=""
            )

            self.image_label.image = photo

        except Exception as error:

            logger.warning("Frame preview error: %s", error)

    # ========================================================
    # UPLOADS
    # ========================================================

    def upload_image(self):

        file_path = filedialog.askopenfilename(
            title="Select Vehicle Image",
            filetypes=[
                ("Image Files", IMAGE_FILE_TYPES)
            ]
        )

        if not file_path:

            return

        self.selected_video = None

        self.selected_images = [file_path]

        self.preview_image(file_path)

        self.selected_files_label.configure(
            text=(
                f"Selected Images: 1\n"
                f"{os.path.basename(file_path)}"
            )
        )

        self.status_label.configure(
            text="Image selected. Ready for detection."
        )

    def upload_multiple_images(self):

        file_paths = filedialog.askopenfilenames(
            title="Select Multiple Vehicle Images",
            filetypes=[
                ("Image Files", IMAGE_FILE_TYPES)
            ]
        )

        if not file_paths:

            return

        self.selected_video = None

        self.selected_images = list(file_paths)

        self.preview_image(self.selected_images[0])

        if len(self.selected_images) == 1:

            text = (
                "Selected Images: 1\n"
                f"{os.path.basename(self.selected_images[0])}"
            )

        else:

            text = (
                f"Selected Images: "
                f"{len(self.selected_images)}\n"
                f"First: "
                f"{os.path.basename(self.selected_images[0])}"
            )

        self.selected_files_label.configure(text=text)

        self.status_label.configure(
            text=(
                f"{len(self.selected_images)} images "
                "selected. Ready for processing."
            )
        )

    def upload_video(self):

        file_path = filedialog.askopenfilename(
            title="Select Vehicle Video",
            filetypes=[
                ("Video Files", VIDEO_FILE_TYPES)
            ]
        )

        if not file_path:

            return

        self.selected_video = file_path

        self.selected_images = []

        frame = read_preview_frame(file_path)

        if frame is not None:

            self.preview_frame(frame)

        else:

            self.image_label.configure(
                image="",
                text="Could not read video preview"
            )

            self.image_label.image = None

        self.selected_files_label.configure(
            text=(
                "Selected Video:\n"
                f"{os.path.basename(file_path)}"
            )
        )

        self.status_label.configure(
            text="Video selected. Ready for detection."
        )

    def clear_selection(self):

        self.selected_images = []

        self.selected_video = None

        self.image_label.configure(
            image="",
            text="Image Preview Area"
        )

        self.image_label.image = None

        self.selected_files_label.configure(
            text="Selected Images: 0"
        )

        self.result_textbox.delete("1.0", "end")

        self.status_label.configure(
            text="Selection cleared."
        )

    # ========================================================
    # DETECTION WORKFLOW
    # ========================================================

    def detect_plate(self):

        has_video = self.selected_video is not None

        if not self.selected_images and not has_video:

            messagebox.showwarning(
                "No Input",
                "Please upload one or more images "
                "or a video first."
            )

            return

        camera = self.get_selected_camera()

        if camera is None:

            messagebox.showwarning(
                "Camera Required",
                "Please select a camera location."
            )

            return

        self.result_textbox.delete("1.0", "end")

        self.detect_btn.configure(state="disabled")

        if has_video:

            self.result_textbox.insert(
                "end",
                f"Processing video: "
                f"{os.path.basename(self.selected_video)}\n"
            )

            self.status_label.configure(
                text="AI Engine analyzing video..."
            )

            self._start_detection_worker(
                process_video,
                self.selected_video,
                dict(camera),
                progress_callback=self._queue_video_progress
            )

        else:

            self.result_textbox.insert(
                "end",
                f"Processing {len(self.selected_images)} image(s) "
                "with the AI Engine...\n"
            )

            self.status_label.configure(
                text="AI Engine processing images..."
            )

            self._start_detection_worker(
                process_images,
                list(self.selected_images),
                dict(camera)
            )

    def _queue_video_progress(self, sampled_frames, seconds):

        self.result_queue.put(
            (
                "progress",
                f"Analyzing video... {sampled_frames} frame(s) "
                f"(~{seconds:.0f}s of footage)"
            )
        )

    def _start_detection_worker(self, worker, *args, **kwargs):

        def run():

            try:

                result = worker(*args, **kwargs)

            except Exception:

                logger.exception("Detection worker failed")

                result = {
                    "detections": [],
                    "source_label": "input",
                    "saved_count": 0
                }

            self.result_queue.put(
                (
                    "finished",
                    result["detections"],
                    result["source_label"],
                    result["saved_count"]
                )
            )

        threading.Thread(
            target=run,
            daemon=True
        ).start()

    def poll_results(self):

        try:

            while True:

                self._handle_worker_message(
                    self.result_queue.get_nowait()
                )

        except queue.Empty:

            pass

        self.app.after(POLL_INTERVAL_MS, self.poll_results)

    def _handle_worker_message(self, message):

        kind = message[0]

        if kind == "progress":

            self.status_label.configure(text=message[1])

        elif kind == "finished":

            self._detection_finished(
                message[1],
                message[2],
                message[3]
            )

    def _detection_finished(
        self,
        new_detections,
        source_label,
        saved_count
    ):

        self.all_detections.extend(new_detections)

        for detection in new_detections:

            plate = detection["plate_number"]

            if plate not in INVALID_PLATES:

                self.trajectory_data[plate].append(detection)

        self.result_textbox.delete("1.0", "end")

        if not new_detections:

            self.result_textbox.insert(
                "end",
                "No readable number plates detected.\n"
            )

        else:

            parts = [

                "CITY-WIDE AI DETECTION RESULTS\n",

                "====================================\n\n"
            ]

            for index, detection in enumerate(
                new_detections,
                start=1
            ):

                image_name = os.path.basename(
                    detection["image_path"]
                )

                parts.append(f"Detection {index}\n")

                parts.append(
                    f"Plate       : "
                    f"{detection['plate_number']}\n"
                )

                parts.append(
                    f"Confidence  : "
                    f"{detection['confidence']:.2f}\n"
                )

                parts.append(
                    f"Camera      : "
                    f"{detection['camera_id']}\n"
                )

                parts.append(
                    f"Location    : "
                    f"{detection['location']}\n"
                )

                parts.append(
                    f"Timestamp   : "
                    f"{detection['timestamp']}\n"
                )

                parts.append(f"Image       : {image_name}\n")

                parts.append(
                    "------------------------------------\n"
                )

            self.result_textbox.insert("end", "".join(parts))

        self.update_trajectory_view()

        self.update_statistics()

        self.update_analytics_view()

        if new_detections:

            self.preview_image(
                new_detections[0]["image_path"]
            )

        self.status_label.configure(
            text=(
                f"Processed {source_label} | "
                f"Detected {len(new_detections)} plate(s) | "
                f"Saved {saved_count} record(s)"
            )
        )

        self.detect_btn.configure(state="normal")

    # ========================================================
    # RESULT VIEWS
    # ========================================================

    def show_all_detections(self):

        self.result_textbox.delete("1.0", "end")

        if not self.all_detections:

            self.result_textbox.insert(
                "end",
                "No detections available."
            )

            return

        parts = [

            "ALL DETECTION EVENTS\n",

            "====================================\n\n"
        ]

        for index, detection in enumerate(
            self.all_detections,
            start=1
        ):

            parts.append(
                f"{index}. "
                f"{detection['plate_number']} | "
                f"{detection['camera_id']} | "
                f"{detection['location']} | "
                f"{detection['timestamp']}\n"
            )

        self.result_textbox.insert("end", "".join(parts))

        self.result_textbox.see("end")

    def show_history(self):

        self.result_textbox.delete("1.0", "end")

        self.result_textbox.insert(
            "end",
            "DETECTION HISTORY (vehicle_database.csv)\n"
        )

        self.result_textbox.insert(
            "end",
            "====================================\n\n"
        )

        self.result_textbox.insert(
            "end",
            get_history()
        )

        self.result_textbox.see("end")

    # ========================================================
    # SESSION CONTROL
    # ========================================================

    def clear_all_data(self):

        self.all_detections = []

        self.trajectory_data = defaultdict(list)

        self.result_textbox.delete("1.0", "end")

        self.trajectory_textbox.delete("1.0", "end")

        self.analytics_textbox.delete("1.0", "end")

        self.trajectory_textbox.insert(
            "end",
            "No vehicle trajectories yet."
        )

        self.analytics_textbox.insert(
            "end",
            "No traffic analytics available yet.\n\n"
            "Upload vehicle images and run AI Detection."
        )

        self.update_statistics()

        self.status_label.configure(
            text="All session data cleared."
        )

    def view_output_folder(self):

        if not os.path.exists(OUTPUT_DIR):

            messagebox.showwarning(
                "Output Folder",
                "Output folder not found."
            )

            return

        try:

            os.startfile(OUTPUT_DIR)

        except OSError as error:

            logger.warning("Could not open output folder: %s", error)

    # ========================================================
    # STARTUP
    # ========================================================

    def _check_startup_dependencies(self):

        problems = check_dependencies()

        if not problems:

            return

        for problem in problems:

            logger.warning("Startup: %s", problem)

        self.status_label.configure(
            text="Startup warning: " + problems[0]
        )


def main():

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ANPRApp().run()


if __name__ == "__main__":

    main()
