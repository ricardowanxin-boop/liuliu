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
from backend.services.config import get_image_edit_block_reason, resolve_provider_config


router = APIRouter(prefix="/api/generations", tags=["generations"])
MAX_FILES_PER_REQUEST = 5
MAX_PROVIDER_CALLS_PER_REQUEST = 10


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
    realistic_mode: Annotated[bool, Form()] = True,
    style_template: Annotated[str | None, Form()] = None,
    watermark_cleanup_enabled: Annotated[bool, Form()] = True,
    watermark_keywords: Annotated[str | None, Form()] = None,
    quality_control_enabled: Annotated[bool, Form()] = True,
    quality_threshold: Annotated[int, Form()] = 72,
    quality_max_retries: Annotated[int, Form()] = 1,
    subject_guard_enabled: Annotated[bool, Form()] = True,
    texture_preservation_enabled: Annotated[bool, Form()] = True,
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
    if len(uploads) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"单次最多上传 {MAX_FILES_PER_REQUEST} 张图片。")

    if not (prompt or "").strip():
        raise HTTPException(status_code=400, detail="提示词不能为空。")

    selected_provider = provider_type or provider or "zenmux"
    selected_model = (model or "").strip() or resolve_provider_config(selected_provider).model
    image_edit_block_reason = get_image_edit_block_reason(selected_provider, selected_model)
    if image_edit_block_reason:
        raise HTTPException(status_code=400, detail=image_edit_block_reason)

    normalized_retries = max(0, min(2, quality_max_retries))
    planned_calls = len(uploads) * (1 + normalized_retries)
    if planned_calls > MAX_PROVIDER_CALLS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"本次预计调用 {planned_calls} 次模型，超过单次预算 {MAX_PROVIDER_CALLS_PER_REQUEST} 次。",
        )

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
        provider_type=selected_provider,
        model=selected_model,
        size=size,
        quality=quality,
        output_format=output_format,
        realistic_mode=realistic_mode,
        style_template=style_template,
        watermark_cleanup_enabled=watermark_cleanup_enabled,
        watermark_keywords=watermark_keywords,
        quality_control_enabled=quality_control_enabled,
        quality_threshold=quality_threshold,
        quality_max_retries=normalized_retries,
        subject_guard_enabled=subject_guard_enabled,
        texture_preservation_enabled=texture_preservation_enabled,
    )
    return run_generation(files=payloads, options=options)
