"""
Background video-analysis jobs.

Video ANPR is heavy (YOLO + multi-pass OCR per sampled frame), so
uploads run on a worker thread and the client polls for progress.
The job simply wraps the existing processing.process_video() - the
same function the desktop GUI calls.
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone

from processing import process_video

from . import review, services

logger = logging.getLogger(__name__)


class JobStore:

    def __init__(self):

        self._jobs = {}

        self._lock = threading.Lock()

    def create(self, video_path, camera):

        job_id = uuid.uuid4().hex

        with self._lock:

            self._jobs[job_id] = {
                "id": job_id,
                "status": "queued",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "progress": {
                    "frames": 0,
                    "seconds": 0.0,
                    "percent": 0
                },
                "result": None,
                "error": None
            }

        thread = threading.Thread(
            target=self._run,
            args=(job_id, video_path, camera),
            daemon=True
        )

        thread.start()

        return job_id

    def get(self, job_id):

        with self._lock:

            job = self._jobs.get(job_id)

            return dict(job) if job else None

    def _update(self, job_id, **fields):

        with self._lock:

            job = self._jobs.get(job_id)

            if job:

                job.update(fields)

    def _run(self, job_id, video_path, camera):

        duration = _probe_duration(video_path)

        self._update(job_id, status="running")

        last = {"frames": 0, "seconds": 0.0}

        def progress(sampled_frames, seconds):

            last["frames"] = sampled_frames
            last["seconds"] = round(seconds, 1)

            percent = 0

            if duration > 0:

                percent = min(99, int(seconds / duration * 100))

            self._update(
                job_id,
                progress={
                    "frames": sampled_frames,
                    "seconds": round(seconds, 1),
                    "percent": percent
                }
            )

        try:

            result = process_video(
                video_path,
                camera,
                progress_callback=progress,
                persist=False,
            )
            reviewed = review.ingest(result["detections"])

            self._update(
                job_id,
                status="completed",
                progress={
                    "frames": last["frames"],
                    "seconds": last["seconds"],
                    "percent": 100
                },
                result={
                    "detections": services.serialize_detections(
                        reviewed["detections"]
                    ),
                    "source_label": result["source_label"],
                    "saved_count": reviewed["saved_count"],
                    "pending_count": reviewed["pending_count"],
                }
            )

        except Exception:

            logger.exception("Video job %s failed", job_id)

            self._update(
                job_id,
                status="failed",
                error="Video analysis failed. Check the server log."
            )

        finally:

            try:

                if os.path.exists(video_path):

                    os.remove(video_path)

            except OSError:

                logger.warning("Could not remove upload %s", video_path)


def _probe_duration(video_path):

    try:

        import cv2

        capture = cv2.VideoCapture(video_path)

        fps = capture.get(cv2.CAP_PROP_FPS)

        frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)

        capture.release()

        if fps and fps > 0 and frames and frames > 0:

            return frames / fps

    except Exception:

        pass

    return 0.0


job_store = JobStore()
