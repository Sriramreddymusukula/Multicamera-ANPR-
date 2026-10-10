"""
Operator routes (JWT required): ANPR detection, vehicle search,
multi-camera tracking, trajectories and evidence files.
"""

import os

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

from . import services, settings
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

    camera = services.camera_from_id(camera_id)

    if camera is None:

        raise HTTPException(status_code=400, detail="Unknown camera.")

    path = save_upload(
        file,
        settings.IMAGE_EXTENSIONS,
        settings.MAX_IMAGE_BYTES
    )

    try:

        result = process_images([str(path)], camera)

    finally:

        try:

            os.remove(path)

        except OSError:

            pass

    return {
        "detections": services.serialize_detections(
            result["detections"]
        ),
        "source_label": result["source_label"],
        "saved_count": result["saved_count"]
    }


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
