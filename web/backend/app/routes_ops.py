"""
Operator routes (JWT required): ANPR detection, vehicle search,
multi-camera tracking, trajectories and evidence files.
"""

import os
from pathlib import Path

import cv2
from pydantic import BaseModel

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse

from processing import process_images

from . import review, services, settings
from .deps import require_user, save_upload
from .jobs import job_store

router = APIRouter(prefix="/api", tags=["operator"])


# ============================================================
# ANPR DETECTION
# ============================================================

@router.post("/detect/image")
def detect_image(
    camera_id: str = Form(...),
    file: UploadFile = File(...),
    operator: str = Depends(require_user)
):

    return _detect_images(camera_id, [file])


@router.post("/detect/images")
def detect_images(
    camera_id: str = Form(...),
    files: list[UploadFile] = File(...),
    operator: str = Depends(require_user),
):
    return _detect_images(camera_id, files)


def _detect_images(camera_id, files):
    camera = services.camera_from_id(camera_id)
    if camera is None:
        raise HTTPException(status_code=400, detail="Unknown camera.")
    if not files or len(files) > settings.MAX_IMAGE_BATCH:
        raise HTTPException(status_code=400, detail="Choose up to 10 images per batch.")

    paths = []
    names = []
    total_bytes = 0
    try:
        for upload in files:
            path = save_upload(
                upload, settings.IMAGE_EXTENSIONS, settings.MAX_IMAGE_BYTES
            )
            paths.append(path)
            total_bytes += path.stat().st_size
            if total_bytes > settings.MAX_IMAGE_BATCH_BYTES:
                raise HTTPException(status_code=413, detail="Image batch exceeds 100 MB.")
            if cv2.imread(str(path)) is None:
                raise HTTPException(status_code=400, detail="An uploaded image could not be decoded.")
            names.append(Path(upload.filename or "image").name)

        result = process_images(
            [str(path) for path in paths], camera,
            retain_sources=True, source_names=names, persist=False,
        )
        reviewed = review.ingest(result["detections"])
        return {
            "detections": services.serialize_detections(reviewed["detections"]),
            "source_label": result["source_label"],
            "saved_count": reviewed["saved_count"],
            "pending_count": reviewed["pending_count"],
        }
    finally:
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                pass


class ReviewDecision(BaseModel):
    action: str
    plate: str = ""
    vehicle_color: str | None = None


@router.get("/reviews")
def pending_reviews(operator: str = Depends(require_user)):
    items = review.list_pending()
    return {"items": items, "count": len(items)}


@router.post("/reviews/{review_id}/decision")
def review_decision(
    review_id: str,
    payload: ReviewDecision,
    operator: str = Depends(require_user),
):
    try:
        return review.decide(review_id, payload.action, payload.plate, operator, payload.vehicle_color)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/detect/video", status_code=202)
def detect_video(
    camera_id: str = Form(...),
    file: UploadFile = File(...),
    operator: str = Depends(require_user)
):

    camera = services.camera_from_id(camera_id)

    if camera is None:

        raise HTTPException(status_code=400, detail="Unknown camera.")

    path = save_upload(
        file,
        settings.VIDEO_EXTENSIONS,
        settings.MAX_VIDEO_BYTES
    )

    job_id = job_store.create(str(path), camera)

    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def job_status(
    job_id: str,
    operator: str = Depends(require_user)
):

    job = job_store.get(job_id)

    if job is None:

        raise HTTPException(status_code=404, detail="Unknown job.")

    return job


# ============================================================
# VEHICLE SEARCH + TRACKING
# ============================================================

@router.get("/vehicles/search")
def vehicle_search(
    plate: str = Query(..., min_length=1, max_length=20),
    operator: str = Depends(require_user)
):

    return services.search_vehicle(plate)


@router.get("/vehicles/multi-camera")
def multi_camera(
    operator: str = Depends(require_user)
):

    return {"vehicles": services.multi_camera_list()}


@router.get("/vehicles/{plate}/trajectory")
def vehicle_trajectory(
    plate: str,
    operator: str = Depends(require_user)
):

    result = services.vehicle_trajectory(plate)

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="No observations recorded for this plate."
        )

    return result


# ============================================================
# EVIDENCE
# ============================================================

@router.get("/evidence/{filename}")
def evidence(
    filename: str,
    operator: str = Depends(require_user)
):

    path = services.evidence_path(filename)

    if path is None:

        raise HTTPException(
            status_code=404,
            detail="Evidence file not found."
        )

    return FileResponse(path)
