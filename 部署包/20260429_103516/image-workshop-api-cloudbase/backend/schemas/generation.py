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
    modelCapabilities: dict[str, dict[str, dict[str, object]]] = Field(default_factory=dict)
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
    qualityScore: int | None = Field(default=None, ge=0, le=100)
    qualityPassed: bool | None = None
    qualityReasons: list[str] = Field(default_factory=list)
    retryCount: int = Field(default=0, ge=0)
    retried: bool = False
    qualityRetryLimit: int = Field(default=0, ge=0)
    iterationLogPath: str | None = None
    stageSummaryPath: str | None = None
    switchReviewPath: str | None = None
    switchWarning: str | None = None
    error: str | None = None


class GenerationJobResponse(BaseModel):
    jobId: str
    status: str
    items: list[GenerationItemResponse]
    providerCallCount: int = Field(default=0, ge=0)
    providerCallLimit: int = Field(default=0, ge=0)
