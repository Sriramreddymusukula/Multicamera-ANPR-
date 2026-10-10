"""
Operator accounts: registration, login, JWT sessions.

Rules:
  - Only emails containing ".cop@" (e.g. sriram.cop@gmail.com) may
    register or log in. The rule is enforced here on the backend,
    not only in the UI.
  - Passwords are stored as PBKDF2-HMAC-SHA256 hashes with a
    per-user salt (stdlib only).
  - Sessions are stateless HS256 JWTs signed with a local secret.
"""

import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import jwt

from . import settings

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+)*\.cop@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$"
)

PBKDF2_ITERATIONS = 210_000

MIN_PASSWORD_LENGTH = 8

_DB_LOCK = threading.Lock()


class AuthError(Exception):
    """Raised with a user-safe message and HTTP status."""

    def __init__(self, message, status=400):

        super().__init__(message)

        self.status = status


def validate_email(email):
    """Normalize and validate the operator email rule."""

    if not isinstance(email, str):

        raise AuthError("Email is required.")

    email = email.strip().lower()

    if (
        len(email) > 254
        or not EMAIL_PATTERN.fullmatch(email)
        or any(part.startswith("-") or part.endswith("-")
               for part in email.split("@")[1].split("."))
    ):

        raise AuthError(
            "Only operator emails in the format "
            "name.cop@domain (for example sriram.cop@gmail.com) "
            "can register or log in."
        )

    return email


def _connect():

    connection = sqlite3.connect(str(settings.USERS_DB))

    connection.row_factory = sqlite3.Row

    return connection


@contextmanager
def _db():
    """Serialized sqlite connection that always closes (Windows-safe)."""

    with _DB_LOCK:

        connection = _connect()

        try:

            with connection:

                yield connection

        finally:

            connection.close()


def init_db():

    settings.USERS_DB.parent.mkdir(parents=True, exist_ok=True)

    with _db() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def _hash_password(password, salt_hex):

    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        PBKDF2_ITERATIONS
    ).hex()


def _check_password(password, salt_hex, expected_hash):

    return hmac.compare_digest(
        _hash_password(password, salt_hex),
        expected_hash
    )


def register(email, password):
    """Create an operator account. Returns the user record."""

    email = validate_email(email)

    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:

        raise AuthError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} "
            "characters."
        )

    salt_hex = secrets.token_hex(16)

    password_hash = _hash_password(password, salt_hex)

    created_at = datetime.now(timezone.utc).isoformat()

    with _db() as connection:

        existing = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:

            raise AuthError(
                "This email is already registered.",
                status=409
            )

        connection.execute(
            """
            INSERT INTO users (email, password_hash, salt, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (email, password_hash, salt_hex, created_at)
        )

    return {"email": email, "created_at": created_at}


def authenticate(email, password):
    """Verify credentials. Returns the user record or raises."""

    email = validate_email(email)

    with _db() as connection:

        row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

    if row is None or not _check_password(
        password or "",
        row["salt"],
        row["password_hash"]
    ):

        raise AuthError("Invalid email or password.", status=401)

    return {"email": row["email"], "created_at": row["created_at"]}


def create_token(email):
    """Issue a signed JWT for an authenticated operator."""

    now = datetime.now(timezone.utc)

    expires = now + timedelta(seconds=settings.JWT_EXPIRE_SECONDS)

    token = jwt.encode(
        {
            "sub": email,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp())
        },
        settings.get_secret(),
        algorithm=settings.JWT_ALGORITHM
    )

    return token, settings.JWT_EXPIRE_SECONDS


def decode_token(token):
    """Return the operator email for a valid token."""

    try:

        payload = jwt.decode(
            token,
            settings.get_secret(),
            algorithms=[settings.JWT_ALGORITHM]
        )

    except jwt.ExpiredSignatureError:

        raise AuthError(
            "Session expired. Please log in again.",
            status=401
        )

    except jwt.InvalidTokenError:

        raise AuthError("Invalid session token.", status=401)

    email = payload.get("sub")

    if not email:

        raise AuthError("Invalid session token.", status=401)

    return email
