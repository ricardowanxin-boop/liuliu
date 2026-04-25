"""Generation routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from backend.schemas.generation import GenerationJobResponse
from backend.services.generation_service import (
    GenerationOptions,
    UploadedImagePayload,
    run_generation,
)


router = APIRouter(prefix="/api/generations", tags=["generations"])


@router.post("", response_model=GenerationJobResponse)
async def create_generation(
    request: Request,
    prompt: Annotated[str, Form()],
    provider_type: Annotated[str | None, Form()] = None,
    provider: Annotated[str | None, Form()] = None,
    model: Annotated[str | None, Form()] = None,
    size: Annotated[str | None, Form()] = None,
    quality: Annotated[str | None, Form()] = "standard",
    output_format: Annotated[str | None, Form()] = "png",
    realistic_mode: Annotated[bool, Form()] = False,
    style_template: Annotated[str | None, Form()] = None,
    watermark_cleanup_enabled: Annotated[bool, Form()] = True,
    watermark_keywords: Annotated[str | None, Form()] = None,
) -> GenerationJobResponse:
    """Run a synchronous generation job for uploaded reference images."""
    form = await request.form()
    uploads: list[UploadFile] = []
    for field_name in ("files[]", "files", "file"):
        for value in form.getlist(field_name):
            if hasattr(value, "filename") and hasattr(value, "read"):
                uploads.append(value)

    if not uploads:
        raise HTTPException(status_code=400, detail="请至少上传一张图片。")

    if not (prompt or "").strip():
        raise HTTPException(status_code=400, detail="提示词不能为空。")

    payloads: list[UploadedImagePayload] = []
    for upload in uploads:
        content = await upload.read()
        payloads.append(
            UploadedImagePayload(
                source_name=upload.filename or "image.png",
                content=content,
            )
        )

    options = GenerationOptions(
        prompt=prompt,
        provider_type=provider_type or provider or "zenmux",
        model=model,
        size=size,
        quality=quality,
        output_format=output_format,
        realistic_mode=realistic_mode,
        style_template=style_template,
        watermark_cleanup_enabled=watermark_cleanup_enabled,
        watermark_keywords=watermark_keywords,
    )
    return run_generation(files=payloads, options=options)
