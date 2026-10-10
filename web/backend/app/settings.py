"""
Web-layer settings: paths, JWT secret, upload limits, CORS.

Everything here is additive; the desktop app does not read it.
"""

import os
import secrets
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = WEB_DIR.parents[1]
FRONTEND_DIST = WEB_DIR.parent / "frontend" / "dist"

USERS_DB = WEB_DIR / "web_users.db"
SECRET_FILE = WEB_DIR / ".secret"
UPLOAD_DIR = WEB_DIR / ".uploads"

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_SECONDS = 12 * 60 * 60

MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_VIDEO_BYTES = 300 * 1024 * 1024

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".ogv"}

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]


def get_secret():
    """Return the JWT secret from env or a local generated file."""

    env_secret = os.environ.get("ANPR_WEB_SECRET")

    if env_secret:

        return env_secret

    if SECRET_FILE.exists():

        secret = SECRET_FILE.read_text(encoding="utf-8").strip()

        if secret:

            return secret

    secret = secrets.token_hex(32)

    SECRET_FILE.write_text(secret, encoding="utf-8")

    return secret


def ensure_upload_dir():

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    return UPLOAD_DIR
