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

import logging
import os
import uuid
from datetime import datetime

import cv2
import numpy as np

from config import (
    EVIDENCE_JPEG_QUALITY,
    OUTPUT_DIR,
    VIDEO_MIN_HITS,
    VIDEO_SAMPLE_FPS,
    VIDEO_SINGLE_HIT_CONF
)
from detector import detect_number_plates, preprocess_plate

logger = logging.getLogger(__name__)


def read_preview_frame(video_path):
    """Return the first readable frame of a video (BGR) or None."""

    cap = cv2.VideoCapture(video_path)

    try:

        ok, frame = cap.read()

        return frame if ok else None

    except Exception as error:

        logger.warning("Video preview error: %s", error)

        return None

    finally:

        cap.release()


def analyze_video(video_path, progress_callback=None, should_cancel=None):
    """
    Analyze a video file.

    Parameters:
        progress_callback : called as (sampled_frames, seconds)
        should_cancel     : optional () -> bool called between
                            frames; analysis stops early when True

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

    try:

        fps = cap.get(cv2.CAP_PROP_FPS)

        if not fps or fps <= 0:

            fps = 25.0

        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0

        duration = total_frames / fps if total_frames > 0 else 0.0

        step = max(1, int(round(fps / VIDEO_SAMPLE_FPS)))

        logger.info(
            "Video: %s | fps=%.1f duration=%.1fs "
            "sampling every %d frame(s)",
            video_path,
            fps,
            duration,
            step
        )

        groups = {}

        frame_index = 0

        sampled_frames = 0

        while True:

            if should_cancel and should_cancel():

                logger.info(
                    "Video analysis cancelled after %d frame(s)",
                    sampled_frames
                )

                break

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

                    detections = detect_number_plates(
                        frame,
                        save_artifacts=False,
                        verbose=False
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

    logger.info(
        "Video analysis: %d frame(s) analyzed, "
        "%d vehicle(s) accepted",
        sampled_frames,
        len(detections)
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
            "first_frame": frame_index,
            "sightings": [],
            "votes": {plate: 0},
        }

        groups[plate] = group

    group["hits"] += 1
    group["votes"][plate] += 1
    group["sightings"].append((seconds, detection["bbox"]))

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
        [int(cv2.IMWRITE_JPEG_QUALITY), EVIDENCE_JPEG_QUALITY]
    )

    return buffer.tobytes() if ok else None


def _finalize_groups(groups):
    """Apply acceptance rules and save evidence files."""

    accepted = []

    for plate, group in _merge_related_groups(groups):

        if (
            group["hits"] < VIDEO_MIN_HITS
            and group["best_confidence"] < VIDEO_SINGLE_HIT_CONF
        ):

            logger.info(
                "Dropped '%s': %d hit(s), conf %.2f",
                plate,
                group["hits"],
                group["best_confidence"]
            )

            continue

        detection = dict(group["best_detection"])
        detection["plate_number"] = plate

        frame_path, crop_path, pre_path = _save_evidence(
            plate,
            group
        )

        detection["cropped_plate"] = crop_path

        detection["preprocessed_plate"] = pre_path

        detection["image_path"] = frame_path or crop_path

        detection["hits"] = group["hits"]
        detection["alternatives"] = group.get("alternatives", [plate])
        detection["match_confidence"] = group.get("match_confidence", 1.0)
        detection["review_reasons"] = group.get("review_reasons", [])

        detection["video_time"] = round(
            group.get("best_time", 0.0),
            1
        )

        detection.pop("plate_image", None)
        detection.pop("raw_plate_image", None)

        accepted.append(detection)

    accepted.sort(
        key=lambda detection: detection["video_time"]
    )

    return accepted


def _plate_distance(left, right):
    """Count differing characters for equally sized registration reads."""
    if len(left) != len(right):
        return 99
    return sum(a != b for a, b in zip(left, right))


def _same_vehicle(left_plate, left, right_plate, right):
    """Require compatible text and nearby frame locations before merging."""
    if left_plate[:6] != right_plate[:6]:
        return False
    if _plate_distance(left_plate, right_plate) > 2:
        return False

    for left_time, left_box in left["sightings"]:
        for right_time, right_box in right["sightings"]:
            if abs(left_time - right_time) > 1.5:
                continue
            lx = (left_box[0] + left_box[2]) / 2
            ly = (left_box[1] + left_box[3]) / 2
            rx = (right_box[0] + right_box[2]) / 2
            ry = (right_box[1] + right_box[3]) / 2
            width = max(
                left_box[2] - left_box[0],
                right_box[2] - right_box[0],
            )
            height = max(
                left_box[3] - left_box[1],
                right_box[3] - right_box[1],
            )
            if abs(lx - rx) <= max(100, width * 2) and abs(ly - ry) <= max(60, height * 2):
                return True
    return False


def _merge_related_groups(groups):
    """Combine adjacent OCR variants of one observed vehicle."""
    merged = []
    for plate, group in sorted(
        groups.items(), key=lambda item: item[1]["first_frame"]
    ):
        target = next(
            (
                item for item in merged
                if any(
                    _same_vehicle(plate, group, member_plate, member)
                    for member_plate, member in item["members"]
                )
            ),
            None,
        )
        if target is None:
            merged.append({"members": [(plate, group)]})
        else:
            target["members"].append((plate, group))

    results = []
    for item in merged:
        members = item["members"]
        best_plate, best = max(
            members,
            key=lambda pair: (pair[1]["best_confidence"], pair[1]["hits"]),
        )
        votes = {plate: group["hits"] for plate, group in members}
        # Reread one evidence crop from *each* text variant. The most
        # confident YOLO box is not necessarily the most legible frame.
        # JPEG compression can also make a fine stroke readable again.
        from detector import ocr_plate_text
        rereads = {}
        for member_plate, member in members if len(members) > 1 else []:
            padded = member["best_detection"].get("plate_image")
            if padded is None or not padded.size:
                continue
            reread, _, confidence = ocr_plate_text(
                padded, return_confidence=True
            )
            if not reread:
                jpeg = _encode_jpeg(padded)
                crop = cv2.imdecode(
                    np.frombuffer(jpeg, dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                ) if jpeg else padded
                reread, _, confidence = ocr_plate_text(
                    crop, return_confidence=True
                )
            if reread and any(
                _plate_distance(reread, plate) <= 2 for plate in votes
            ):
                rereads[reread] = max(
                    rereads.get(reread, (0.0, None)),
                    (confidence, member_plate),
                )
                votes[reread] = votes.get(reread, 0) + 2
        canonical = max(
            votes,
            key=lambda value: (
                votes[value],
                rereads.get(value, (0.0, None))[0],
                value == best_plate,
            ),
        )
        if canonical in rereads:
            source_plate = rereads[canonical][1]
            best = next(group for plate, group in members if plate == source_plate)
        combined = dict(best)
        combined["hits"] = sum(group["hits"] for _, group in members)
        combined["first_frame"] = min(
            group["first_frame"] for _, group in members
        )
        combined["alternatives"] = sorted(votes, key=votes.get, reverse=True)
        combined["match_confidence"] = round(
            max(group["hits"] for _, group in members) / combined["hits"], 4
        )
        if len(members) > 1:
            combined["review_reasons"] = ["Conflicting plate reads across video frames"]
        results.append((canonical, combined))
    return results


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
