"""Idempotently migrate local Meridian data and image evidence to Supabase."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import sqlite3
from datetime import datetime

from app import auth, db, review, settings, storage
from config import OUTPUT_DIR

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_MAX_STORAGE_OBJECT_BYTES = 50 * 1024 * 1024


def _sqlite_rows(path, query):
    if not path.is_file():
        return []
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(query).fetchall()]
    finally:
        connection.close()


def _existing_image_path(value):
    if not value or str(value).startswith("storage://"):
        return None
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return path if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES else None


def _object_name(path):
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    return f"legacy-{digest}-{path.name}"


def _storage_reference(value, path_to_object):
    if not value:
        return ""
    if str(value).startswith("storage://"):
        return str(value)
    path = _existing_image_path(value)
    object_name = path_to_object.get(path) if path else None
    return f"storage://{object_name}" if object_name else ""


def _read_local_sources():
    from database import read_database

    users = _sqlite_rows(settings.USERS_DB, "SELECT * FROM users")
    reviews = _sqlite_rows(settings.REVIEW_DB, "SELECT * FROM reviews")
    detections = read_database()
    detection_rows = detections.to_dict("records") if not detections.empty else []

    candidates = set()
    for path in Path(OUTPUT_DIR).glob("*"):
        if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES:
            candidates.add(path.resolve())
    for row in reviews:
        for field in ("image_path", "crop_path"):
            path = _existing_image_path(row.get(field))
            if path:
                candidates.add(path)
    for row in detection_rows:
        path = _existing_image_path(row.get("Image Path"))
        if path:
            candidates.add(path)

    return users, reviews, detection_rows, sorted(candidates)


def _upload_images(paths):
    oversized = [path for path in paths if path.stat().st_size > _MAX_STORAGE_OBJECT_BYTES]
    if oversized:
        raise RuntimeError(
            f"{len(oversized)} evidence file(s) exceed the bucket's 50 MB object limit."
        )

    object_names = {path: _object_name(path) for path in paths}
    # Uploads are idempotent (upsert) and bounded so the migration doesn't
    # overwhelm the free project or the local machine.
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [
            pool.submit(storage.upload_file, path, object_names[path])
            for path in paths
        ]
        for future in futures:
            future.result()
    return object_names


def _counts(connection):
    return {
        table: connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        for table in ("users", "reviews", "detections")
    }


def main():
    if not db.postgres_enabled():
        raise SystemExit("DATABASE_URL is missing. Configure web/backend/.env first.")
    if not storage.configured():
        raise SystemExit(
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in web/backend/.env first."
        )

    users, reviews, source_detections, image_paths = _read_local_sources()
    print(
        f"Local source inventory: {len(users)} account(s), {len(reviews)} review(s), "
        f"{len(source_detections)} observation(s), {len(image_paths)} available image file(s)."
    )

    # Confirm this key can write and delete in the existing private bucket
    # before uploading evidence or changing the relational database.
    storage.check_bucket_access()
    object_names = _upload_images(image_paths)
    print(f"Uploaded or refreshed {len(object_names)} image file(s) in private Storage.")

    auth.init_db()
    review.init_db()
    connection = db.connect(settings.REVIEW_DB)
    try:
        with connection:
            db.ensure_detection_schema(connection)

            for row in users:
                connection.execute("""
                    INSERT INTO users (email, password_hash, salt, created_at)
                    VALUES (?, ?, ?, ?) ON CONFLICT (email) DO NOTHING
                """, (row["email"], row["password_hash"], row["salt"], row["created_at"]))

            columns = [
                "id", "created_at", "status", "prediction", "final_plate",
                "detector_score", "ocr_score", "match_score", "alternatives",
                "reasons", "provider", "provider_read", "camera_id", "location",
                "observed_at", "image_path", "crop_path", "source_name", "hits",
                "video_time", "reviewer", "reviewed_at", "vehicle_color",
            ]
            placeholders = ", ".join("?" for _ in columns)
            selected = ", ".join(columns)
            for row in reviews:
                values = [row.get(column) for column in columns]
                values[columns.index("image_path")] = _storage_reference(
                    row.get("image_path"), object_names
                )
                values[columns.index("crop_path")] = _storage_reference(
                    row.get("crop_path"), object_names
                ) or None
                connection.execute(
                    f"INSERT INTO reviews ({selected}) VALUES ({placeholders}) "
                    "ON CONFLICT (id) DO NOTHING",
                    values,
                )
    finally:
        connection.close()

    migrated_detections = []
    for index, row in enumerate(source_detections):
        try:
            observed_at = datetime.strptime(
                f"{row.get('Date', '')} {row.get('Time', '')}",
                "%d-%m-%Y %I:%M:%S %p",
            ).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            continue
        identity = "|".join(str(row.get(key, "")) for key in (
            "Date", "Time", "Plate Number", "Camera ID", "Location", "Image Path"
        ))
        migrated_detections.append({
            "_migration_id": hashlib.sha256(f"{index}|{identity}".encode("utf-8")).hexdigest(),
            "plate_number": str(row.get("Plate Number", "")),
            "camera_id": str(row.get("Camera ID", "CAM-01")),
            "location": str(row.get("Location", "Unknown")),
            "confidence": row.get("Confidence", 0),
            "image_path": _storage_reference(row.get("Image Path"), object_names),
            "timestamp": observed_at,
        })

    new_detections = db.save_detections(migrated_detections)
    connection = db.connect(settings.REVIEW_DB)
    try:
        final_counts = _counts(connection)
    finally:
        connection.close()

    if (
        final_counts["users"] < len(users)
        or final_counts["reviews"] < len(reviews)
        or final_counts["detections"] < len(migrated_detections)
    ):
        raise RuntimeError("Migration count verification failed; keep local data unchanged.")

    missing_review_images = sum(
        1 for row in reviews
        if row.get("image_path") and not _storage_reference(row.get("image_path"), object_names)
    )
    missing_detection_images = sum(
        1 for row in source_detections
        if row.get("Image Path") and not _storage_reference(row.get("Image Path"), object_names)
    )
    print(
        f"Verified hosted totals: users={final_counts['users']}, "
        f"reviews={final_counts['reviews']}, detections={final_counts['detections']}."
    )
    print(f"New detection rows inserted: {new_detections}.")
    if missing_review_images or missing_detection_images:
        print(
            f"Warning: {missing_review_images} review and {missing_detection_images} "
            "observation image reference(s) had no local file; their text records were preserved."
        )
    print("Migration complete. Local SQLite, CSV, and image files were left unchanged.")


if __name__ == "__main__":
    main()
