"""
Video ANPR support.

A video is processed by sampling frames at a fixed rate
(config.VIDEO_SAMPLE_FPS), running the standard plate detector on
each sampled frame, and aggregating the per-frame reads into one
detection per vehicle using temporal voting: a plate must be read
in at least config.VIDEO_MIN_HITS frames (or a single frame with
at least config.VIDEO_SINGLE_HIT_CONF confidence) to be accepted.

Only the best frame of each accepted vehicle is saved to output/.
"""

import contextlib
import io
import os
import uuid
from datetime import datetime

import cv2

from config import (
    OUTPUT_DIR,
    VIDEO_MIN_HITS,
    VIDEO_SAMPLE_FPS,
    VIDEO_SINGLE_HIT_CONF
)
from detector import detect_number_plates, preprocess_plate


def read_preview_frame(video_path):
    """Return the first readable frame of a video (BGR) or None."""

    cap = cv2.VideoCapture(video_path)

    try:

        ok, frame = cap.read()

        return frame if ok else None

    except Exception as error:

        print("Video preview error:", error)

        return None

    finally:

        cap.release()


def analyze_video(video_path, progress_callback=None):
    """
    Analyze a video file.

    Returns a dictionary:

        detections     : one detection per accepted vehicle
        sampled_frames : number of analyzed frames
        duration       : video duration in seconds (0 if unknown)
    """

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():

        raise RuntimeError(
            f"Could not open video: {video_path}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if not fps or fps <= 0:

        fps = 25.0

    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0

    duration = total_frames / fps if total_frames > 0 else 0.0

    step = max(1, int(round(fps / VIDEO_SAMPLE_FPS)))

    print(
        f"Video: {video_path}\n"
        f"  fps={fps:.1f} duration={duration:.1f}s "
        f"sampling every {step} frame(s)"
    )

    groups = {}

    frame_index = 0

    sampled_frames = 0

    try:

        while True:

            # grab() skips frames cheaply; retrieve() decodes
            # only the frames we actually analyze.
            if not cap.grab():

                break

            if frame_index % step == 0:

                ok, frame = cap.retrieve()

                if ok:

                    sampled_frames += 1

                    seconds = frame_index / fps

                    if (
                        progress_callback
                        and sampled_frames % 5 == 0
                    ):

                        progress_callback(
                            sampled_frames,
                            seconds
                        )

                    # Silence the per-frame detector chatter;
                    # real errors are still raised as exceptions.
                    with contextlib.redirect_stdout(io.StringIO()):

                        detections = detect_number_plates(
                            frame,
                            save_artifacts=False
                        )

                    for detection in detections:

                        _update_group(
                            groups,
                            detection,
                            frame,
                            frame_index,
                            seconds
                        )

            frame_index += 1

    finally:

        cap.release()

    detections = _finalize_groups(groups)

    print(
        f"Video analysis: {sampled_frames} frame(s) analyzed, "
        f"{len(detections)} vehicle(s) accepted"
    )

    return {
        "detections": detections,
        "sampled_frames": sampled_frames,
        "duration": duration
    }


def _update_group(groups, detection, frame, frame_index, seconds):
    """Fold one frame read into the per-plate aggregation."""

    plate = detection["plate_number"]

    group = groups.get(plate)

    if group is None:

        group = {
            "hits": 0,
            "best_confidence": 0.0,
            "first_frame": frame_index
        }

        groups[plate] = group

    group["hits"] += 1

    group["last_frame"] = frame_index

    confidence = detection["confidence"]

    if confidence > group["best_confidence"]:

        group["best_confidence"] = confidence

        group["best_detection"] = detection

        group["best_time"] = seconds

        group["best_frame_jpeg"] = _encode_jpeg(frame)


def _encode_jpeg(frame):
    """JPEG-encode a frame for compact evidence storage."""

    ok, buffer = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), 88]
    )

    return buffer.tobytes() if ok else None


def _finalize_groups(groups):
    """Apply acceptance rules and save evidence files."""

    accepted = []

    for plate, group in groups.items():

        if (
            group["hits"] < VIDEO_MIN_HITS
            and group["best_confidence"] < VIDEO_SINGLE_HIT_CONF
        ):

            print(
                f"  dropped '{plate}': "
                f"{group['hits']} hit(s), "
                f"conf {group['best_confidence']:.2f}"
            )

            continue

        detection = dict(group["best_detection"])

        frame_path, crop_path, pre_path = _save_evidence(
            plate,
            group
        )

        detection["cropped_plate"] = crop_path

        detection["preprocessed_plate"] = pre_path

        detection["image_path"] = frame_path or crop_path

        detection["hits"] = group["hits"]

        detection["video_time"] = round(
            group.get("best_time", 0.0),
            1
        )

        detection.pop("plate_image", None)

        accepted.append(detection)

    accepted.sort(
        key=lambda detection: detection["video_time"]
    )

    return accepted


def _save_evidence(plate, group):
    """Save the best frame, plate crop and preprocessed crop."""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    stamp = (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        + "_"
        + uuid.uuid4().hex[:6]
    )

    crop_path = None
    pre_path = None

    plate_image = group["best_detection"].get("plate_image")

    if plate_image is not None:

        crop_path = os.path.join(
            OUTPUT_DIR,
            f"video_plate_{plate}_{stamp}.jpg"
        )

        cv2.imwrite(crop_path, plate_image)

        pre_path = os.path.join(
            OUTPUT_DIR,
            f"video_preprocessed_{plate}_{stamp}.jpg"
        )

        cv2.imwrite(pre_path, preprocess_plate(plate_image))

    frame_path = None

    frame_jpeg = group.get("best_frame_jpeg")

    if frame_jpeg:

        frame_path = os.path.join(
            OUTPUT_DIR,
            f"video_frame_{plate}_{stamp}.jpg"
        )

        with open(frame_path, "wb") as file:

            file.write(frame_jpeg)

    return frame_path, crop_path, pre_path
