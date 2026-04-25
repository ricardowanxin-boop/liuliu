"""Pydantic schemas for generation APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool = True
    service: str
    version: str


class ConfigResponse(BaseModel):
    providers: list[str]
    defaultProvider: str
    models: dict[str, list[str]]
    defaults: dict[str, str]
    sizes: list[str]
    qualities: list[str]
    outputFormats: list[str]
    apiConnected: bool
    apiConnections: dict[str, bool]


class GenerationItemResponse(BaseModel):
    sourceName: str
    status: str
    progress: int = Field(ge=0, le=100)
    resultDataUrl: str | None = None
    cleanupNote: str | None = None
    error: str | None = None


class GenerationJobResponse(BaseModel):
    jobId: str
    status: str
    items: list[GenerationItemResponse]
