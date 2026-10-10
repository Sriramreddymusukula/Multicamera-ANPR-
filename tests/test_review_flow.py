"""Focused tests for uncertain observations and duplicate video reads."""

import sys
import base64
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from app import review, settings
from app.deps import require_user
from app.main import app
from fastapi.testclient import TestClient
import cv2
import numpy as np
from video import _finalize_groups, _merge_related_groups
from processing import process_images


def test_review_queue_and_confirmation():
    with TemporaryDirectory() as directory:
        with patch.object(settings, "REVIEW_DB", Path(directory) / "reviews.db"), \
             patch.object(review, "save_detections", return_value=1) as save:
            detection = {
                "plate_number": "TS08GH5405",
                "confidence": .72,
                "ocr_confidence": .29,
                "camera_id": "CAM-01",
                "location": "Hyderabad",
                "timestamp": "2026-10-10 12:00:00",
                "image_path": str(Path(directory) / "frame.jpg"),
                "cropped_plate": None,
            }
            result = review.ingest([detection])
            assert result["pending_count"] == 1
            assert result["saved_count"] == 0
            assert save.call_count == 0
            item = review.list_pending()[0]
            assert item["prediction"] == "TS08GH5405"
            confirmed = review.decide(item["id"], "confirm", "TS08GH5405", "operator.cop@example.com")
            assert confirmed["status"] == "confirmed"
            assert save.call_count == 1
            assert review.list_pending() == []
            try:
                review.decide(item["id"], "confirm", "TS08GH5405", "operator.cop@example.com")
            except ValueError:
                pass
            else:
                raise AssertionError("A reviewed observation was saved twice")


def test_matching_gemini_read_accepts_without_human_review():
    with TemporaryDirectory() as directory:
        detection = {
            "plate_number": "TS08GH5405", "confidence": .42,
            "ocr_confidence": .34, "camera_id": "CAM-01",
            "location": "Hyderabad", "timestamp": "2026-10-10 12:00:00",
            "image_path": str(Path(directory) / "frame.jpg"),
            "cropped_plate": str(Path(directory) / "crop.jpg"),
        }
        with patch.object(settings, "REVIEW_DB", Path(directory) / "reviews.db"), \
             patch.object(review, "_provider_read", return_value=("Gemini 3.8 Flash", "TS08GH5405")), \
             patch.object(review, "save_detections", return_value=1) as save:
            result = review.ingest([detection])
            assert result["pending_count"] == 0
            assert result["saved_count"] == 1
            assert result["detections"][0]["review_status"] == "accepted"
            assert review.list_pending() == []
            save.assert_called_once()


def test_disagreeing_gemini_read_stays_pending():
    with TemporaryDirectory() as directory:
        detection = {
            "plate_number": "TS08GH5405", "confidence": .42,
            "ocr_confidence": .34, "camera_id": "CAM-01",
            "location": "Hyderabad", "timestamp": "2026-10-10 12:00:00",
            "image_path": str(Path(directory) / "frame.jpg"),
            "cropped_plate": str(Path(directory) / "crop.jpg"),
        }
        with patch.object(settings, "REVIEW_DB", Path(directory) / "reviews.db"), \
             patch.object(review, "_provider_read", return_value=("Gemini 3.8 Flash", "TS08GH5406")), \
             patch.object(review, "save_detections", return_value=1) as save:
            result = review.ingest([detection])
            assert result["pending_count"] == 1
            assert result["saved_count"] == 0
            assert review.list_pending()[0]["provider_read"] == "TS08GH5406"
            save.assert_not_called()


def test_gemini_appearance_masks_plate_and_stores_review_context():
    with TemporaryDirectory() as directory:
        frame_path = Path(directory) / "frame.jpg"
        cv2.imwrite(str(frame_path), np.full((100, 200, 3), 220, dtype=np.uint8))
        response = {"candidates": [{"content": {"parts": [
            {"text": json.dumps({"color": "blue", "body_style": "SUV"})}
        ]}}]}
        with patch.object(settings, "get_gemini_key", return_value="test-key"), \
             patch.object(review, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as send:
            attributes = review._gemini_vehicle_attributes(frame_path, (60, 40, 100, 60))
        assert attributes == ("Blue", "SUV")
        payload = json.loads(send.call_args.args[0].data)
        encoded = payload["contents"][0]["parts"][1]["inline_data"]["data"]
        masked = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), dtype=np.uint8), cv2.IMREAD_COLOR)
        assert masked[50, 80].max() < 10

        detection = {
            "plate_number": "TS08GH5405", "confidence": .4, "ocr_confidence": .3,
            "camera_id": "CAM-01", "location": "Hyderabad",
            "timestamp": "2026-10-10 12:00:00", "image_path": str(frame_path),
            "cropped_plate": None, "bbox": (60, 40, 100, 60),
        }
        with patch.object(settings, "REVIEW_DB", Path(directory) / "reviews.db"), \
             patch.object(review, "_gemini_vehicle_attributes", return_value=("Blue", "SUV")), \
             patch.object(review, "save_detections", return_value=1) as save:
            result = review.ingest([detection])
            assert result["pending_count"] == 1
            item = review.list_pending()[0]
            assert (item["suggested_color"], item["suggested_style"]) == ("Blue", "SUV")
            decided = review.decide(item["id"], "confirm", "TS08GH5405", "operator.cop@example.com", "Blue")
            assert decided["vehicle_color"] == "Blue"
            save.assert_called_once()


def test_video_variants_join_only_when_sightings_are_nearby():
    def group(plate, time, x):
        return {
            "hits": 2, "first_frame": int(time * 30),
            "best_confidence": .8,
            "best_detection": {"plate_number": plate},
            "sightings": [(time, (x, 20, x + 100, 60))],
        }

    groups = {
        "UK07BS4542": group("UK07BS4542", 1.0, 50),
        "UK07BS2542": group("UK07BS2542", 1.3, 70),
        "UK07BS4543": group("UK07BS4543", 1.3, 900),
    }
    merged = _merge_related_groups(groups)
    assert len(merged) == 2
    assert sorted(group["hits"] for _, group in merged) == [2, 4]


def test_authenticated_batch_upload_route():
    ok, buffer = cv2.imencode(".jpg", np.zeros((40, 80, 3), dtype=np.uint8))
    assert ok
    app.dependency_overrides[require_user] = lambda: "operator.cop@example.com"
    try:
        with patch("app.routes_ops.process_images", return_value={
            "detections": [], "source_label": "2 image(s)", "saved_count": 0,
        }) as process:
            response = TestClient(app).post(
                "/api/detect/images",
                data={"camera_id": "CAM-01"},
                files=[("files", (name, buffer.tobytes(), "image/jpeg")) for name in ("first.jpg", "second.jpg")],
            )
        assert response.status_code == 200, response.text
        assert response.json()["source_label"] == "2 image(s)"
        assert len(process.call_args.args[0]) == 2
    finally:
        app.dependency_overrides.clear()


def test_video_output_uses_canonical_plate():
    detection = {
        "plate_number": "UK07BS2542", "confidence": .8,
        "plate_image": None, "bbox": (10, 10, 110, 50),
    }
    group = {
        "hits": 2, "first_frame": 1, "best_confidence": .8,
        "best_detection": detection, "best_time": .2,
        "sightings": [(.2, detection["bbox"])],
    }
    with patch("video._merge_related_groups", return_value=[("UK07BS4542", group)]), \
         patch("video._save_evidence", return_value=("frame.jpg", "crop.jpg", None)):
        output = _finalize_groups({})
    assert output[0]["plate_number"] == "UK07BS4542"


def test_batch_processing_keeps_review_evidence():
    with TemporaryDirectory() as directory:
        images = []
        for name in ("one.jpg", "two.jpg"):
            path = Path(directory) / name
            path.write_bytes(b"test image bytes")
            images.append(str(path))
        fake_detection = {
            "plate_number": "TS08GH5405", "confidence": .8,
            "ocr_confidence": .4, "bbox": (0, 0, 10, 10),
            "cropped_plate": None, "preprocessed_plate": None,
        }
        import processing
        with patch.object(processing, "OUTPUT_DIR", str(Path(directory) / "output")), \
             patch.object(processing, "detect_number_plates", return_value=[fake_detection]):
            result = process_images(
                images, {"id": "CAM-01", "location": "Hyderabad"},
                retain_sources=True, source_names=["one.jpg", "two.jpg"],
                persist=False,
            )
        assert result["saved_count"] == 0
        assert [item["source_name"] for item in result["detections"]] == ["one.jpg", "two.jpg"]
        assert all(Path(item["image_path"]).is_file() for item in result["detections"])
