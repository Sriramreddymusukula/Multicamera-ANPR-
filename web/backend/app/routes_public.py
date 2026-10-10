"""
Public routes: aggregates only.

Privacy contract: nothing in this module may return a plate
number, a per-vehicle record, a trajectory or an evidence file.
Only counts, camera metadata and derived insights leave here.
"""

from fastapi import APIRouter

from . import services

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health():

    summary = services.public_summary()

    return {
        "status": "ok",
        "records": summary["total_observations"]
    }


@router.get("/cameras")
def cameras():

    return {"cameras": services.cameras()}


@router.get("/analytics/summary")
def analytics_summary():

    return services.public_summary()


@router.get("/analytics/cameras")
def analytics_cameras():

    return {"cameras": services.public_camera_stats()}


@router.get("/analytics/trends")
def analytics_trends():

    return services.public_trends()


@router.get("/analytics/insights")
def analytics_insights():

    return services.public_insights()
