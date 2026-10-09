"""
End-to-end video ANPR smoke test.

Builds a short synthetic video from an existing plate crop in
output/ and checks that the video pipeline returns an aggregated
detection. Requires the YOLO model and Tesseract OCR.

Run from the project folder:

    .\\venv\\Scripts\\python.exe tests\\test_video_pipeline.py
"""

import os
import sys
import tempfile

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

import cv2

from config import OUTPUT_DIR
from video import analyze_video


def _find_sample_plate():

    if not os.path.isdir(OUTPUT_DIR):

        return None

    for name in sorted(os.listdir(OUTPUT_DIR)):

        if (
            name.startswith("cropped_plate_")
            and name.endswith(".jpg")
        ):

            return os.path.join(OUTPUT_DIR, name)

    return None


def test_video_pipeline():

    sample = _find_sample_plate()

    if sample is None:

        print("SKIP: no cropped plate sample found in output/")

        return

    frame = cv2.imread(sample)

    height, width = frame.shape[:2]

    width -= width % 2
    height -= height % 2

    frame = frame[:height, :width]

    video_path = os.path.join(
        tempfile.gettempdir(),
        "anpr_pipeline_test_video.avi"
    )

    writer = cv2.VideoWriter(
        video_path,
        cv2.VideoWriter_fourcc(*"MJPG"),
        10.0,
        (width, height)
    )

    for _ in range(40):

        writer.write(frame)

    writer.release()

    created_files = []

    try:

        result = analyze_video(video_path)

    finally:

        os.remove(video_path)

    detections = result["detections"]

    print("sampled frames:", result["sampled_frames"])

    for detection in detections:

        print(
            "  plate:", detection["plate_number"],
            "| hits:", detection["hits"],
            "| conf:", detection["confidence"],
            f"| t={detection['video_time']}s"
        )

        created_files.extend(
            path for path in (
                detection["image_path"],
                detection["cropped_plate"],
                detection["preprocessed_plate"]
            )
            if path
        )

    assert result["sampled_frames"] >= 4, result["sampled_frames"]

    assert detections, "no vehicle detected in the synthetic video"

    assert detections[0]["hits"] >= 2, detections[0]

    for path in created_files:

        if os.path.isfile(path):

            os.remove(path)

    print("Video pipeline test passed.")


if __name__ == "__main__":

    test_video_pipeline()
