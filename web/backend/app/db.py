"""Small database compatibility layer for local SQLite and hosted Postgres."""

from contextlib import contextmanager
import os
import sqlite3
import uuid
from datetime import datetime

from . import settings


def postgres_enabled():
    return bool(os.environ.get("DATABASE_URL", "").strip())


class _PostgresConnection:
    """Keep the existing qmark SQL call sites portable to psycopg."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, parameters=()):
        return self._connection.execute(sql.replace("?", "%s"), parameters)

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._connection.__exit__(exc_type, exc, traceback)


def connect(sqlite_path, timeout=15):
    """Open the configured database; use the existing file locally."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        connection = sqlite3.connect(str(sqlite_path), timeout=timeout)
        connection.row_factory = sqlite3.Row
        return connection

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RuntimeError(
            "DATABASE_URL is configured but psycopg is missing; "
            "install web/backend/requirements-web.txt."
        ) from error

    # Supabase presents postgres:// or postgresql:// connection URLs.
    connection = psycopg.connect(url, row_factory=dict_row, connect_timeout=timeout)
    return _PostgresConnection(connection)


def is_postgres(connection):
    return isinstance(connection, _PostgresConnection)


@contextmanager
def transaction(connection):
    """Commit on success and roll back on failure for either driver."""
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def ensure_detection_schema(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id TEXT PRIMARY KEY,
            observed_at TEXT NOT NULL,
            plate_number TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            location TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
            image_path TEXT NOT NULL DEFAULT ''
        )
    """)


def save_detections(detections):
    """Persist web detections in Postgres; use CSV in local mode."""
    if not postgres_enabled():
        from database import save_detections as save_csv_detections
        return save_csv_detections(detections)
    if not detections:
        return 0

    from . import settings
    connection = connect(settings.REVIEW_DB)
    saved = 0
    try:
        with connection:
            ensure_detection_schema(connection)
            for item in detections:
                timestamp = str(item.get("timestamp") or item.get("observed_at") or "")
                try:
                    observed_at = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    observed_at = datetime.now()
                cursor = connection.execute("""
                    INSERT INTO detections
                        (id, observed_at, plate_number, camera_id, location, confidence, image_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING
                """, (
                    str(item.get("_migration_id") or uuid.uuid4().hex),
                    observed_at.isoformat(sep=" "),
                    str(item.get("plate_number") or ""),
                    str(item.get("camera_id") or "CAM-01"),
                    str(item.get("location") or "Unknown"),
                    float(item.get("confidence") or 0),
                    str(item.get("image_path") or ""),
                ))
                if cursor.rowcount > 0:
                    saved += 1
    finally:
        connection.close()
    return saved


def read_detections():
    """Return hosted detections using the legacy CSV column names."""
    if not postgres_enabled():
        from database import read_database
        return read_database()

    import pandas as pd
    from . import settings
    connection = connect(settings.REVIEW_DB)
    try:
        ensure_detection_schema(connection)
        rows = connection.execute("""
            SELECT observed_at, plate_number, camera_id, location, confidence, image_path
            FROM detections ORDER BY observed_at, id
        """).fetchall()
    finally:
        connection.close()
    records = []
    for row in rows:
        try:
            observed = datetime.fromisoformat(row["observed_at"])
        except (TypeError, ValueError):
            observed = datetime.now()
        records.append({
            "Date": observed.strftime("%d-%m-%Y"),
            "Time": observed.strftime("%I:%M:%S %p"),
            "Plate Number": row["plate_number"],
            "Camera ID": row["camera_id"],
            "Location": row["location"],
            "Confidence": row["confidence"],
            "Image Path": row["image_path"],
        })
    return pd.DataFrame(records)
