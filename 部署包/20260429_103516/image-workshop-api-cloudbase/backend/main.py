"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_assets import router as assets_router
from backend.api.routes_config import router as config_router
from backend.api.routes_generation import router as generation_router
from backend.api.routes_logs import router as logs_router
from backend.services.config import resolve_allowed_origins
from backend.services.iteration_logger import review_log_milestones


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
    app.include_router(logs_router)

    @app.on_event("startup")
    async def _start_log_reviewer() -> None:
        app.state.log_reviewer_task = asyncio.create_task(_periodic_log_review())

    @app.on_event("shutdown")
    async def _stop_log_reviewer() -> None:
        task = getattr(app.state, "log_reviewer_task", None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return app


app = create_app()


async def _periodic_log_review() -> None:
    """Periodically synthesize missing milestone summaries from iteration logs."""
    while True:
        await asyncio.sleep(900)
        await asyncio.to_thread(review_log_milestones)
