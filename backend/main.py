"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_assets import router as assets_router
from backend.api.routes_config import router as config_router
from backend.api.routes_generation import router as generation_router
from backend.services.config import resolve_allowed_origins


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    allowed_origins = resolve_allowed_origins()
    app = FastAPI(
        title="AI Image Ecommerce Backend",
        version="0.1.0",
        description="Minimal FastAPI backend for React-based ecommerce image generation.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials="*" not in allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(config_router)
    app.include_router(generation_router)
    app.include_router(assets_router)
    return app


app = create_app()
