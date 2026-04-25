"""Asset route placeholder for future local-file storage."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{asset_id}")
def get_asset(asset_id: str) -> None:
    """First version returns generated images as data URLs, so assets are absent."""
    raise HTTPException(status_code=404, detail=f"asset not found: {asset_id}")
