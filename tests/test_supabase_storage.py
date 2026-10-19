"""Supabase Storage adapter tests; all HTTP calls are mocked."""

from io import BytesIO
from email.message import Message
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "web" / "backend"))

from app import storage


def _configure(monkeypatch):
    monkeypatch.setattr(storage.settings, "get_supabase_url", lambda: "https://example.supabase.co")
    monkeypatch.setattr(storage.settings, "get_supabase_service_key", lambda: "test-server-key")
    monkeypatch.setattr(storage.settings, "get_evidence_bucket", lambda: "anpr-evidence")


def test_upload_returns_private_storage_reference(tmp_path, monkeypatch):
    _configure(monkeypatch)
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"jpeg-data")

    with patch.object(storage, "urlopen", return_value=BytesIO(b"{}")) as send:
        reference = storage.upload_file(image)

    assert reference == "storage://frame.jpg"
    request = send.call_args.args[0]
    assert request.full_url.endswith("/storage/v1/object/anpr-evidence/frame.jpg")
    assert request.get_header("X-upsert") == "true"
    assert request.get_header("Authorization") == "Bearer test-server-key"
    assert request.data == b"jpeg-data"


def test_private_evidence_can_be_read_through_backend(monkeypatch):
    _configure(monkeypatch)
    response = BytesIO(b"image-bytes")
    response.headers = Message()
    response.headers.add_header("Content-Type", "image/jpeg")

    with patch.object(storage, "urlopen", return_value=response):
        content, content_type = storage.read_object("frame.jpg")

    assert content == b"image-bytes"
    assert content_type == "image/jpeg"


@pytest.mark.parametrize("name", ["../secret.jpg", "nested/frame.jpg", "", ".", "x" * 256])
def test_storage_rejects_unsafe_object_names(name):
    with pytest.raises(ValueError, match="Invalid evidence object name"):
        storage._object_url(name)
