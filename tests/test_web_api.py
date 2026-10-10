"""
Web API tests: auth, .cop@ rule, privacy allowlist, trajectory.

Runs against FastAPI's TestClient with a throw-away database and
user store, so nothing touches the real project data.

Run from the project folder:

    .\\venv\\Scripts\\python.exe tests\\test_web_api.py
"""

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))

sys.path.insert(0, str(PROJECT_ROOT / "web" / "backend"))

import database
from app import settings as web_settings

_TMP = tempfile.TemporaryDirectory(prefix="anpr_web_test_")

web_settings.USERS_DB = Path(_TMP.name) / "web_users.db"
web_settings.SECRET_FILE = Path(_TMP.name) / ".secret"
web_settings.UPLOAD_DIR = Path(_TMP.name) / "uploads"

database.DATABASE_FILE = str(Path(_TMP.name) / "vehicle_database.csv")
database.OUTPUT_DIR = str(Path(_TMP.name) / "output")

from app import auth, services  # noqa: E402
from app.main import app  # noqa: E402

services.OUTPUT_DIR = database.OUTPUT_DIR

from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)

_SEEDED = {"done": False}


def _seed():

    if _SEEDED["done"]:

        return

    _SEEDED["done"] = True

    evidence_source = Path(_TMP.name) / "source_frame.jpg"

    evidence_source.write_bytes(b"\xff\xd8\xff\xe0jpegbytes")

    database.save_detections([
        {
            "plate_number": "TG257602",
            "image_path": str(evidence_source),
            "camera_id": "CAM-01",
            "location": "Suchitra Junction",
            "confidence": 0.91
        },
        {
            "plate_number": "TG257602",
            "image_path": "",
            "camera_id": "CAM-03",
            "location": "JNTU Road",
            "confidence": 0.83
        },
        {
            "plate_number": "MH12AB1234",
            "image_path": "",
            "camera_id": "CAM-02",
            "location": "Kukatpally",
            "confidence": 0.77
        }
    ])


def _operator_token():

    response = client.post(
        "/api/auth/register",
        json={
            "email": "sriram.cop@gmail.com",
            "password": "strongpass123"
        }
    )

    if response.status_code == 409:

        response = client.post(
            "/api/auth/login",
            json={
                "email": "sriram.cop@gmail.com",
                "password": "strongpass123"
            }
        )

    assert response.status_code in (200, 201), response.text

    return response.json()["token"]


def _walk_json(node):
    """Yield every string contained in a JSON structure."""

    if isinstance(node, dict):

        for key, value in node.items():

            yield str(key)

            yield from _walk_json(value)

    elif isinstance(node, list):

        for item in node:

            yield from _walk_json(item)

    else:

        yield str(node)


_seed()


# ============================================================
# EMAIL RULE
# ============================================================

def test_email_rule():

    assert auth.validate_email("sriram.cop@gmail.com") == (
        "sriram.cop@gmail.com"
    )

    assert auth.validate_email("ABC.COP@Outlook.in") == (
        "abc.cop@outlook.in"
    )

    for bad in (
        "sriram@gmail.com",
        "sriram.copgmail.com",
        "cop@x.com",
        "sriram.cop@nodot",
        "sriram@cop.com",
        "sriram..cop@gmail.com",
        "sriram.cop@gmail..com",
    ):

        try:

            auth.validate_email(bad)

            raise AssertionError(f"accepted invalid email: {bad}")

        except auth.AuthError:

            pass


def test_register_login_and_session():

    response = client.post(
        "/api/auth/register",
        json={
            "email": "teja.cop@gmail.com",
            "password": "operatorpass1"
        }
    )

    assert response.status_code == 201, response.text

    token = response.json()["token"]

    assert response.json()["email"] == "teja.cop@gmail.com"

    duplicate = client.post(
        "/api/auth/register",
        json={
            "email": "teja.cop@gmail.com",
            "password": "operatorpass1"
        }
    )

    assert duplicate.status_code == 409

    bad_format = client.post(
        "/api/auth/register",
        json={
            "email": "teja@gmail.com",
            "password": "operatorpass1"
        }
    )

    assert bad_format.status_code == 400

    wrong_password = client.post(
        "/api/auth/login",
        json={
            "email": "teja.cop@gmail.com",
            "password": "not-the-password"
        }
    )

    assert wrong_password.status_code == 401

    bad_login_format = client.post(
        "/api/auth/login",
        json={
            "email": "teja@gmail.com",
            "password": "operatorpass1"
        }
    )

    assert bad_login_format.status_code == 400

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert me.status_code == 200

    assert me.json()["email"] == "teja.cop@gmail.com"

    anonymous = client.get("/api/auth/me")

    assert anonymous.status_code == 401


# ============================================================
# PUBLIC PRIVACY
# ============================================================

def test_public_endpoints_never_expose_plates():

    _seed()

    for path in (
        "/api/health",
        "/api/cameras",
        "/api/analytics/summary",
        "/api/analytics/cameras",
        "/api/analytics/trends",
        "/api/analytics/insights"
    ):

        response = client.get(path)

        assert response.status_code == 200, (path, response.text)

        strings = list(_walk_json(response.json()))

        for plate in ("TG257602", "MH12AB1234"):

            assert all(
                plate not in value for value in strings
            ), f"{path} leaked {plate}"

    summary = client.get("/api/analytics/summary").json()

    assert summary["total_observations"] == 3

    assert summary["unique_vehicles"] == 2

    assert summary["active_cameras"] == 3

    assert summary["multi_camera_vehicles"] == 1


def test_protected_endpoints_require_login():

    for path in (
        "/api/vehicles/search?plate=TG257602",
        "/api/vehicles/multi-camera",
        "/api/vehicles/TG257602/trajectory",
        "/api/evidence/whatever.jpg",
        "/api/jobs/whatever"
    ):

        response = client.get(path)

        assert response.status_code == 401, path


# ============================================================
# VEHICLE SEARCH + TRAJECTORY
# ============================================================

def test_search_and_trajectory():

    token = _operator_token()

    headers = {"Authorization": f"Bearer {token}"}

    search = client.get(
        "/api/vehicles/search?plate=tg 257602",
        headers=headers
    )

    assert search.status_code == 200

    payload = search.json()

    assert payload["found"] is True

    assert len(payload["observations"]) == 2

    trajectory = client.get(
        "/api/vehicles/TG257602/trajectory",
        headers=headers
    )

    assert trajectory.status_code == 200

    route = trajectory.json()

    assert route["multi_camera"] is True

    assert route["camera_path"] == ["CAM-01", "CAM-03"]

    assert len(route["polyline"]) == 2

    assert route["polyline"][0] == [17.4995, 78.4766]

    assert route["summary"]["observations"] == 2

    missing = client.get(
        "/api/vehicles/XX00XX0000/trajectory",
        headers=headers
    )

    assert missing.status_code == 404

    not_found = client.get(
        "/api/vehicles/search?plate=TG25",
        headers=headers
    )

    assert not_found.status_code == 200

    assert not_found.json()["found"] is False


def test_multi_camera_listing():

    token = _operator_token()

    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/vehicles/multi-camera",
        headers=headers
    )

    assert response.status_code == 200

    vehicles = response.json()["vehicles"]

    assert [row["plate"] for row in vehicles] == ["TG257602"]

    assert vehicles[0]["cameras"] == ["CAM-01", "CAM-03"]


# ============================================================
# EVIDENCE SECURITY
# ============================================================

def test_evidence_access_and_traversal():

    token = _operator_token()

    headers = {"Authorization": f"Bearer {token}"}

    output_files = [
        name
        for name in os.listdir(database.OUTPUT_DIR)
        if name.endswith(".jpg")
    ]

    assert output_files

    ok = client.get(
        f"/api/evidence/{output_files[0]}",
        headers=headers
    )

    assert ok.status_code == 200

    for attempt in (
        "..%2Fvehicle_database.csv",
        "..%5Cvehicle_database.csv",
        "%2e%2e%2fvehicle_database.csv"
    ):

        response = client.get(
            f"/api/evidence/{attempt}",
            headers=headers
        )

        assert response.status_code in (404, 400), attempt


def test_detect_upload_validation():

    token = _operator_token()

    headers = {"Authorization": f"Bearer {token}"}

    bad_type = client.post(
        "/api/detect/image",
        headers=headers,
        data={"camera_id": "CAM-01"},
        files={"file": ("notes.txt", b"hello", "text/plain")}
    )

    assert bad_type.status_code == 400

    bad_camera = client.post(
        "/api/detect/image",
        headers=headers,
        data={"camera_id": "CAM-99"},
        files={"file": ("plate.jpg", b"\xff\xd8jpeg", "image/jpeg")}
    )

    assert bad_camera.status_code == 400


if __name__ == "__main__":

    tests = [
        function
        for name, function in sorted(globals().items())
        if name.startswith("test_") and callable(function)
    ]

    for function in tests:

        function()

        print("PASS", function.__name__)

    print("All web API tests passed.")
