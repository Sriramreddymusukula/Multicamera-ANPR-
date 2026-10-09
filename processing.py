"""
Detection workflows shared by the GUI and other front-ends.

These functions run on worker threads, never touch Tk widgets and
return plain result dictionaries. Both the image and the video
path build records through the same builder so a detection record
has one canonical shape.
"""

import logging
from datetime import datetime

from database import save_detections
from detector import detect_number_plates
from video import analyze_video

logger = logging.getLogger(__name__)


def build_detection_record(detection, camera, timestamp, image_path):

    return {

        "plate_number": detection["plate_number"],

        "confidence": detection["confidence"],

        "camera_id": camera["id"],

        "location": camera["location"],

        "timestamp": timestamp,

        "image_path": image_path,

        "bbox": detection["bbox"],

        "cropped_plate": detection["cropped_plate"],

        "preprocessed_plate": detection["preprocessed_plate"]
    }


def _persist(detections):
    """Save a batch without letting a storage error kill the worker."""

    if not detections:

        return 0

    try:

        return save_detections(detections)

    except Exception:

        logger.exception("Database save error")

        return 0


def process_images(image_paths, camera, should_cancel=None):
    """Run detection over uploaded images and persist the results."""

    new_detections = []

    processed_count = 0

    for image_path in image_paths:

        if should_cancel and should_cancel():

            break

        logger.info(
            "Processing image: %s | camera %s | location %s",
            image_path,
            camera["id"],
            camera["location"]
        )

        try:

            detections = detect_number_plates(
                image_path,
                verbose=False
            )

        except Exception:

            logger.exception("Detection error for %s", image_path)

            continue

        processed_count += 1

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        for detection in detections:

            new_detections.append(
                build_detection_record(
                    detection,
                    camera,
                    timestamp,
                    image_path
                )
            )

    return {
        "detections": new_detections,
        "source_label": f"{processed_count} image(s)",
        "saved_count": _persist(new_detections)
    }


def process_video(
    video_path,
    camera,
    progress_callback=None,
    should_cancel=None
):
    """Analyze a video file and persist one record per vehicle."""

    try:

        result = analyze_video(
            video_path,
            progress_callback=progress_callback,
            should_cancel=should_cancel
        )

        detections = result["detections"]

        source_label = (
            f"video ({result['sampled_frames']} frame(s))"
        )

    except Exception:

        logger.exception("Video analysis error")

        detections = []

        source_label = "video"

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    new_detections = [
        build_detection_record(
            detection,
            camera,
            timestamp,
            detection["image_path"]
        )
        for detection in detections
    ]

    return {
        "detections": new_detections,
        "source_label": source_label,
        "saved_count": _persist(new_detections)
    }
