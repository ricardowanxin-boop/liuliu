"""Configuration and health routes."""

from __future__ import annotations

from fastapi import APIRouter

from backend.schemas.generation import ConfigResponse, HealthResponse
from backend.services.config import build_public_config


router = APIRouter(prefix="/api", tags=["config"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Basic service health endpoint."""
    return HealthResponse(service="ai-image-backend", version="0.1.0")


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return frontend-safe provider/model/format configuration."""
    return ConfigResponse.model_validate(build_public_config())
