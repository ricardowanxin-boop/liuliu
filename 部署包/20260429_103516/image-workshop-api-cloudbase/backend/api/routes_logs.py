"""Iteration log review routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.services.iteration_logger import review_log_milestones


router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.post("/review")
def review_logs() -> dict[str, object]:
    """Manually trigger milestone summary generation from existing logs."""
    created = review_log_milestones()
    return {
        "ok": True,
        "created": created,
    }
