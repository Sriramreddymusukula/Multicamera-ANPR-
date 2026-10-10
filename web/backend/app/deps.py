"""Shared FastAPI dependencies and upload helpers."""

import os
import uuid
from pathlib import Path

from fastapi import Header, HTTPException, UploadFile

from . import auth, settings


def require_user(authorization: str | None = Header(default=None)):
    """FastAPI dependency: valid operator JWT or 401."""

    if not authorization or not authorization.lower().startswith(
        "bearer "
    ):

        raise HTTPException(
            status_code=401,
            detail="Authentication required."
        )

    token = authorization.split(" ", 1)[1].strip()

    try:

        return auth.decode_token(token)

    except auth.AuthError as error:

        raise HTTPException(
            status_code=error.status,
            detail=str(error)
        )


def save_upload(upload: UploadFile, allowed_extensions, max_bytes):
    """Stream an upload to disk with extension and size limits."""

    suffix = Path(upload.filename or "").suffix.lower()

    if suffix not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. Allowed: "
                + ", ".join(sorted(allowed_extensions))
            )
        )

    directory = settings.ensure_upload_dir()

    path = directory / f"{uuid.uuid4().hex}{suffix}"

    total = 0

    try:

        with open(path, "wb") as output:

            while True:

                chunk = upload.file.read(1024 * 1024)

                if not chunk:

                    break

                total += len(chunk)

                if total > max_bytes:

                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "File too large. Limit: "
                            f"{max_bytes // (1024 * 1024)} MB"
                        )
                    )

                output.write(chunk)

    except HTTPException:

        _remove_quietly(path)

        raise

    except Exception:

        _remove_quietly(path)

        raise HTTPException(
            status_code=500,
            detail="Could not store the uploaded file."
        )

    return path


def _remove_quietly(path):

    try:

        if os.path.exists(path):

            os.remove(path)

    except OSError:

        pass
