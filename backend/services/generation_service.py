"""Synchronous image generation workflow for the first FastAPI version."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from secrets import token_hex

from backend.schemas.generation import GenerationItemResponse, GenerationJobResponse
from backend.services.config import (
    DOUBAO_PROVIDER,
    OPENAI_PROVIDER,
    ZENMUX_PROVIDER,
    ProviderRuntimeConfig,
    resolve_provider_config,
)
from backend.services.image_preprocess import (
    ImagePreprocessError,
    build_provider_input_filename,
    image_to_data_url,
    prepare_provider_image_bytes,
)
from backend.services.prompt_compiler import compile_generation_prompt
from backend.services.providers.doubao_seedream import DoubaoSeedreamProvider
from backend.services.providers.openai_compatible import OpenAICompatibleProvider
from backend.services.providers.provider_base import BaseImageProvider, ImageProviderError
from backend.services.providers.zenmux_vertex import ZenMuxVertexProvider


@dataclass(frozen=True, slots=True)
class UploadedImagePayload:
    """One uploaded image with source metadata already read from multipart."""

    source_name: str
    content: bytes


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    """Options accepted from the React generation form."""

    prompt: str
    provider_type: str
    model: str | None = None
    size: str | None = None
    quality: str | None = None
    output_format: str | None = None
    realistic_mode: bool = False
    style_template: str | None = None


def run_generation(
    *,
    files: list[UploadedImagePayload],
    options: GenerationOptions,
) -> GenerationJobResponse:
    """Run a synchronous, serial generation job and return per-file results."""
    job_id = _build_job_id()
    compiled_prompt = compile_generation_prompt(
        prompt=options.prompt,
        realistic_mode=options.realistic_mode,
        style_template=options.style_template,
        quality=options.quality,
    )

    try:
        runtime_config = resolve_provider_config(
            options.provider_type,
            model=options.model,
            size=options.size,
        )
        provider = build_provider(runtime_config)
    except (ValueError, ImageProviderError) as exc:
        return GenerationJobResponse(
            jobId=job_id,
            status="failed",
            items=[
                GenerationItemResponse(
                    sourceName=file.source_name,
                    status="failed",
                    progress=100,
                    error=str(exc),
                )
                for file in files
            ],
        )

    items: list[GenerationItemResponse] = []
    for file in files:
        items.append(
            _process_single_file(
                provider=provider,
                file=file,
                prompt=compiled_prompt,
                output_format=options.output_format,
            )
        )

    return GenerationJobResponse(
        jobId=job_id,
        status=_summarize_job_status(items),
        items=items,
    )


def build_provider(config: ProviderRuntimeConfig) -> BaseImageProvider:
    """Build the requested provider adapter from resolved runtime config."""
    if not config.api_key:
        raise ImageProviderError(f"缺少 {config.provider_type} API Key，请配置环境变量或 Streamlit secrets。")

    if config.provider_type == ZENMUX_PROVIDER:
        return ZenMuxVertexProvider(
            base_url=config.base_url,
            model=config.model,
            api_key=config.api_key,
            api_mode=config.zenmux_api_mode,
        )

    if config.provider_type == DOUBAO_PROVIDER:
        return DoubaoSeedreamProvider(
            base_url=config.base_url,
            model=config.model,
            api_key=config.api_key,
            size=config.doubao_size,
            watermark=config.doubao_watermark,
            response_format=config.doubao_response_format,
            extra_payload=config.doubao_extra_payload or {},
        )

    if config.provider_type == OPENAI_PROVIDER:
        return OpenAICompatibleProvider(
            base_url=config.base_url,
            model=config.model,
            api_key=config.api_key,
        )

    raise ImageProviderError(f"不支持的 provider_type：{config.provider_type}")


def _process_single_file(
    *,
    provider: BaseImageProvider,
    file: UploadedImagePayload,
    prompt: str,
    output_format: str | None,
) -> GenerationItemResponse:
    try:
        provider_bytes = prepare_provider_image_bytes(file.content)
        provider_filename = build_provider_input_filename(file.source_name, provider_bytes)
        generated_image = provider.edit_image(
            image_bytes=provider_bytes,
            prompt=prompt,
            filename=provider_filename,
        )
        return GenerationItemResponse(
            sourceName=file.source_name,
            status="done",
            progress=100,
            resultDataUrl=image_to_data_url(generated_image, output_format or "png"),
        )
    except (ImagePreprocessError, ImageProviderError) as exc:
        return GenerationItemResponse(
            sourceName=file.source_name,
            status="failed",
            progress=100,
            error=str(exc),
        )
    except Exception as exc:
        return GenerationItemResponse(
            sourceName=file.source_name,
            status="failed",
            progress=100,
            error=f"处理图片时发生未知错误：{exc}",
        )


def _summarize_job_status(items: list[GenerationItemResponse]) -> str:
    if not items:
        return "failed"
    done_count = sum(1 for item in items if item.status == "done")
    if done_count == len(items):
        return "completed"
    if done_count == 0:
        return "failed"
    return "partial"


def _build_job_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"job_{timestamp}_{token_hex(4)}"
