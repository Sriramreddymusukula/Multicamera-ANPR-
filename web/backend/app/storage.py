"""Private Supabase Storage adapter for ANPR evidence files."""

import json
import logging
import mimetypes
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

from . import settings

logger = logging.getLogger(__name__)
_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")


def configured():
    return bool(settings.get_supabase_url() and settings.get_supabase_service_key())


def _object_url(key):
    if not _SAFE_KEY.fullmatch(key):
        raise ValueError("Invalid evidence object name.")
    bucket = quote(settings.get_evidence_bucket(), safe="")
    return f"{settings.get_supabase_url()}/storage/v1/object/{bucket}/{quote(key, safe='')}"


def _headers(content_type="application/octet-stream"):
    key = settings.get_supabase_service_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
    }


def upload_file(path, object_name=None):
    """Upload one local evidence file; return a private storage reference."""
    if not configured():
        return None
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError("Evidence file is missing.")
    object_name = object_name or source.name
    content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    request = Request(
        _object_url(object_name),
        data=source.read_bytes(),
        headers={**_headers(content_type), "x-upsert": "true"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            response.read()
    except HTTPError as error:
        logger.error("Supabase Storage upload failed (HTTP %s).", error.code)
        raise RuntimeError("Could not upload evidence to Supabase Storage.") from None
    except (URLError, TimeoutError, OSError):
        logger.exception("Supabase Storage upload failed.")
        raise RuntimeError("Could not upload evidence to Supabase Storage.") from None
    return f"storage://{object_name}"


def read_object(object_name):
    """Read a private evidence object through the authenticated backend."""
    if not configured():
        return None
    request = Request(_object_url(object_name), headers=_headers(), method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            return response.read(), response.headers.get_content_type()
    except HTTPError as error:
        if error.code == 404:
            return None
        logger.error("Supabase Storage read failed (HTTP %s).", error.code)
        raise RuntimeError("Could not read evidence from Supabase Storage.") from None
    except (URLError, TimeoutError, OSError):
        logger.exception("Supabase Storage read failed.")
        raise RuntimeError("Could not read evidence from Supabase Storage.") from None


def delete_objects(object_names):
    """Delete a list of object names from the private evidence bucket."""
    names = [name for name in object_names if _SAFE_KEY.fullmatch(name)]
    if not names:
        return
    bucket = quote(settings.get_evidence_bucket(), safe="")
    request = Request(
        f"{settings.get_supabase_url()}/storage/v1/object/{bucket}",
        data=json.dumps({"prefixes": names}).encode("utf-8"),
        headers=_headers("application/json"),
        method="DELETE",
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except HTTPError as error:
        logger.error("Supabase Storage delete failed (HTTP %s).", error.code)
        raise RuntimeError("Could not delete evidence from Supabase Storage.") from None
    except (URLError, TimeoutError, OSError):
        logger.exception("Supabase Storage delete failed.")
        raise RuntimeError("Could not delete evidence from Supabase Storage.") from None


def check_bucket_access():
    """Verify configured service credentials can write and delete privately."""
    name = f"connection-check-{uuid.uuid4().hex}.txt"
    request = Request(
        _object_url(name),
        data=b"Meridian Supabase Storage connectivity check",
        headers={**_headers("text/plain"), "x-upsert": "false"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except HTTPError as error:
        logger.error("Supabase Storage check failed (HTTP %s).", error.code)
        raise RuntimeError("Storage access check failed. Check the bucket and server key.") from None
    except (URLError, TimeoutError, OSError):
        logger.exception("Supabase Storage check failed.")
        raise RuntimeError("Storage access check failed. Check the project URL and network.") from None
    delete_objects([name])
