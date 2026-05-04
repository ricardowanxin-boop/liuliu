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
    load_image_from_bytes,
    prepare_provider_image_bytes,
    remove_watermark_if_needed,
    split_keywords,
)
from backend.services.hand_anatomy import build_source_hand_anatomy_prompt
from backend.services.iteration_logger import (
    IterationLogResult,
    write_generation_failure_log,
    write_generation_iteration_log,
)
from backend.services.prompt_compiler import compile_generation_prompt
from backend.services.quality_control import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_QUALITY_THRESHOLD,
    build_quality_retry_prompt,
    evaluate_generated_image,
    has_hard_quality_blocker,
)
from backend.services.subject_fidelity import (
    build_subject_fidelity_prompt,
    enhance_subject_non_generative,
)
from backend.services.texture_preservation import preserve_real_scene_texture
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
class ProcessFileResult:
    """One file response plus the actual number of provider calls used."""

    item: GenerationItemResponse
    provider_call_count: int


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    """Options accepted from the React generation form."""

    prompt: str
    provider_type: str
    model: str | None = None
    size: str | None = None
    quality: str | None = None
    output_format: str | None = None
    realistic_mode: bool = True
    style_template: str | None = None
    watermark_cleanup_enabled: bool = True
    watermark_keywords: str | None = None
    quality_control_enabled: bool = True
    quality_threshold: int = DEFAULT_QUALITY_THRESHOLD
    quality_max_retries: int = DEFAULT_MAX_RETRIES
    subject_guard_enabled: bool = True
    texture_preservation_enabled: bool = True


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
        watermark_cleanup_enabled=options.watermark_cleanup_enabled,
        watermark_keywords=split_keywords(options.watermark_keywords),
        texture_preservation_enabled=options.texture_preservation_enabled,
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
    provider_call_count = 0
    provider_call_limit = len(files) * (1 + max(0, min(2, options.quality_max_retries)))
    for index, file in enumerate(files, start=1):
        process_result = _process_single_file(
            job_id=job_id,
            file_index=index,
            provider=provider,
            file=file,
            user_prompt=options.prompt,
            compiled_prompt=compiled_prompt,
            provider_type=runtime_config.provider_type,
            model=runtime_config.model,
            output_format=options.output_format,
            watermark_cleanup_enabled=options.watermark_cleanup_enabled,
            watermark_keywords=options.watermark_keywords,
            quality_control_enabled=options.quality_control_enabled,
            quality_threshold=options.quality_threshold,
            quality_max_retries=options.quality_max_retries,
            subject_guard_enabled=options.subject_guard_enabled,
            texture_preservation_enabled=options.texture_preservation_enabled,
        )
        items.append(process_result.item)
        provider_call_count += process_result.provider_call_count

    return GenerationJobResponse(
        jobId=job_id,
        status=_summarize_job_status(items),
        items=items,
        providerCallCount=provider_call_count,
        providerCallLimit=provider_call_limit,
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
    job_id: str,
    file_index: int,
    provider: BaseImageProvider,
    file: UploadedImagePayload,
    user_prompt: str,
    compiled_prompt: str,
    provider_type: str,
    model: str,
    output_format: str | None,
    watermark_cleanup_enabled: bool,
    watermark_keywords: str | None,
    quality_control_enabled: bool,
    quality_threshold: int,
    quality_max_retries: int,
    subject_guard_enabled: bool,
    texture_preservation_enabled: bool,
) -> ProcessFileResult:
    retry_count = 0
    final_assessment = None
    cleanup_note = ""
    current_prompt = compiled_prompt
    max_retries = max(0, min(2, quality_max_retries))
    threshold = max(1, min(100, quality_threshold))
    last_log_path: str | None = None
    last_stage_summary_path: str | None = None
    last_switch_review_path: str | None = None
    last_switch_warning: str | None = None
    provider_call_count = 0

    try:
        provider_bytes = prepare_provider_image_bytes(file.content)
        provider_filename = build_provider_input_filename(file.source_name, provider_bytes)
        source_image = load_image_from_bytes(file.content)
        effective_quality_gate = quality_control_enabled or subject_guard_enabled or texture_preservation_enabled
        source_image_for_quality = source_image if effective_quality_gate else None
        hand_anatomy_prompt = build_source_hand_anatomy_prompt(source_image, prompt=compiled_prompt)
        if hand_anatomy_prompt:
            current_prompt = "\n\n".join([compiled_prompt, hand_anatomy_prompt]).strip()
        if subject_guard_enabled:
            current_prompt = "\n\n".join([current_prompt, build_subject_fidelity_prompt()]).strip()
        base_generation_prompt = current_prompt

        while True:
            provider_call_count += 1
            generated_image = provider.edit_image(
                image_bytes=provider_bytes,
                prompt=current_prompt,
                filename=provider_filename,
            )
            cleanup_note = ""
            if watermark_cleanup_enabled:
                generated_image, cleanup_note = remove_watermark_if_needed(
                    generated_image,
                    keywords=split_keywords(watermark_keywords),
                )
            if subject_guard_enabled:
                enhancement_result = enhance_subject_non_generative(
                    generated_image,
                    source_image=source_image,
                )
                generated_image = enhancement_result.image
                cleanup_note = "；".join(
                    item for item in (cleanup_note, enhancement_result.note) if item
                )
            if texture_preservation_enabled:
                texture_result = preserve_real_scene_texture(
                    generated_image,
                    source_image=source_image,
                )
                generated_image = texture_result.image
                cleanup_note = "；".join(
                    item for item in (cleanup_note, texture_result.note) if item
                )

            if not effective_quality_gate:
                log_result = write_generation_iteration_log(
                    source_name=file.source_name,
                    source_image_bytes=file.content,
                    generated_image=generated_image,
                    provider_type=provider_type,
                    model=model,
                    prompt=user_prompt,
                    compiled_prompt=current_prompt,
                    attempt=retry_count + 1,
                    status="done",
                    assessment=None,
                    cleanup_note=cleanup_note or None,
                    job_id=job_id,
                    file_index=file_index,
                )
                last_log_path = log_result.log_path
                last_stage_summary_path = log_result.stage_summary_path
                last_switch_review_path = log_result.switch_review_path
                last_switch_warning = log_result.switch_warning
                return ProcessFileResult(
                    item=GenerationItemResponse(
                        sourceName=file.source_name,
                        status="done",
                        progress=100,
                        resultDataUrl=image_to_data_url(generated_image, output_format or "png"),
                        cleanupNote=cleanup_note or None,
                        retryCount=retry_count,
                        retried=retry_count > 0,
                        qualityRetryLimit=max_retries,
                        iterationLogPath=last_log_path,
                        stageSummaryPath=last_stage_summary_path,
                        switchReviewPath=last_switch_review_path,
                        switchWarning=last_switch_warning,
                    ),
                    provider_call_count=provider_call_count,
                )

            final_assessment = evaluate_generated_image(
                generated_image,
                threshold=threshold,
                source_image=source_image_for_quality,
                prompt=current_prompt,
                subject_guard_enabled=subject_guard_enabled,
                texture_preservation_enabled=texture_preservation_enabled,
            )
            hard_blocker = has_hard_quality_blocker(final_assessment)
            will_retry = not final_assessment.passed and retry_count < max_retries and not hard_blocker
            status = "done" if final_assessment.passed else "quality_failed_retrying" if will_retry else "review_required"
            log_result = write_generation_iteration_log(
                source_name=file.source_name,
                source_image_bytes=file.content,
                generated_image=generated_image,
                provider_type=provider_type,
                model=model,
                prompt=user_prompt,
                compiled_prompt=current_prompt,
                attempt=retry_count + 1,
                status=status,
                assessment=final_assessment,
                cleanup_note=cleanup_note or None,
                error=None if final_assessment.passed else "自动质检需复核" if not will_retry else "自动质检未通过",
                job_id=job_id,
                file_index=file_index,
            )
            last_log_path = log_result.log_path
            last_stage_summary_path = log_result.stage_summary_path
            last_switch_review_path = log_result.switch_review_path
            last_switch_warning = log_result.switch_warning

            if final_assessment.passed:
                return ProcessFileResult(
                    item=GenerationItemResponse(
                        sourceName=file.source_name,
                        status="done",
                        progress=100,
                        resultDataUrl=image_to_data_url(generated_image, output_format or "png"),
                        cleanupNote=cleanup_note or None,
                        qualityScore=final_assessment.score,
                        qualityPassed=True,
                        qualityReasons=final_assessment.reasons,
                        retryCount=retry_count,
                        retried=retry_count > 0,
                        qualityRetryLimit=max_retries,
                        iterationLogPath=last_log_path,
                        stageSummaryPath=last_stage_summary_path,
                        switchReviewPath=last_switch_review_path,
                        switchWarning=last_switch_warning,
                    ),
                    provider_call_count=provider_call_count,
                )

            if not will_retry:
                return ProcessFileResult(
                    item=GenerationItemResponse(
                        sourceName=file.source_name,
                        status="review_required",
                        progress=100,
                        resultDataUrl=image_to_data_url(generated_image, output_format or "png"),
                        cleanupNote=cleanup_note or None,
                        qualityScore=final_assessment.score,
                        qualityPassed=False,
                        qualityReasons=final_assessment.reasons,
                        retryCount=retry_count,
                        retried=retry_count > 0,
                        qualityRetryLimit=max_retries,
                        iterationLogPath=last_log_path,
                        stageSummaryPath=last_stage_summary_path,
                        switchReviewPath=last_switch_review_path,
                        switchWarning=last_switch_warning,
                        error="自动质检未通过，结果仅供参考，不建议直接交付。",
                    ),
                    provider_call_count=provider_call_count,
                )

            retry_count += 1
            current_prompt = build_quality_retry_prompt(base_generation_prompt, final_assessment)

    except (ImagePreprocessError, ImageProviderError) as exc:
        failure_log = _try_write_failure_log(
            source_name=file.source_name,
            source_image_bytes=file.content,
            provider_type=provider_type,
            model=model,
            user_prompt=user_prompt,
            compiled_prompt=current_prompt,
            attempt=retry_count + 1,
            error=str(exc),
            job_id=job_id,
            file_index=file_index,
        )
        if failure_log:
            last_log_path = failure_log.log_path
            last_stage_summary_path = failure_log.stage_summary_path
            last_switch_review_path = failure_log.switch_review_path
            last_switch_warning = failure_log.switch_warning
        return ProcessFileResult(
            item=GenerationItemResponse(
                sourceName=file.source_name,
                status="failed",
                progress=100,
                qualityScore=final_assessment.score if final_assessment else None,
                qualityPassed=final_assessment.passed if final_assessment else None,
                qualityReasons=final_assessment.reasons if final_assessment else [],
                retryCount=retry_count,
                retried=retry_count > 0,
                qualityRetryLimit=max_retries,
                iterationLogPath=last_log_path,
                stageSummaryPath=last_stage_summary_path,
                switchReviewPath=last_switch_review_path,
                switchWarning=last_switch_warning,
                error=str(exc),
            ),
            provider_call_count=provider_call_count,
        )
    except Exception as exc:
        failure_log = _try_write_failure_log(
            source_name=file.source_name,
            source_image_bytes=file.content,
            provider_type=provider_type,
            model=model,
            user_prompt=user_prompt,
            compiled_prompt=current_prompt,
            attempt=retry_count + 1,
            error=f"处理图片时发生未知错误：{exc}",
            job_id=job_id,
            file_index=file_index,
        )
        if failure_log:
            last_log_path = failure_log.log_path
            last_stage_summary_path = failure_log.stage_summary_path
            last_switch_review_path = failure_log.switch_review_path
            last_switch_warning = failure_log.switch_warning
        return ProcessFileResult(
            item=GenerationItemResponse(
                sourceName=file.source_name,
                status="failed",
                progress=100,
                qualityScore=final_assessment.score if final_assessment else None,
                qualityPassed=final_assessment.passed if final_assessment else None,
                qualityReasons=final_assessment.reasons if final_assessment else [],
                retryCount=retry_count,
                retried=retry_count > 0,
                qualityRetryLimit=max_retries,
                iterationLogPath=last_log_path,
                stageSummaryPath=last_stage_summary_path,
                switchReviewPath=last_switch_review_path,
                switchWarning=last_switch_warning,
                error=f"处理图片时发生未知错误：{exc}",
            ),
            provider_call_count=provider_call_count,
        )


def _try_write_failure_log(
    *,
    source_name: str,
    source_image_bytes: bytes,
    provider_type: str,
    model: str,
    user_prompt: str,
    compiled_prompt: str,
    attempt: int,
    error: str,
    job_id: str,
    file_index: int,
) -> IterationLogResult | None:
    try:
        return write_generation_failure_log(
            source_name=source_name,
            source_image_bytes=source_image_bytes,
            provider_type=provider_type,
            model=model,
            prompt=user_prompt,
            compiled_prompt=compiled_prompt,
            attempt=attempt,
            error=error,
            job_id=job_id,
            file_index=file_index,
        )
    except Exception:
        return None


def _summarize_job_status(items: list[GenerationItemResponse]) -> str:
    if not items:
        return "failed"
    done_count = sum(1 for item in items if item.status == "done")
    deliverable_count = sum(1 for item in items if item.resultDataUrl)
    if done_count == len(items):
        return "completed"
    if deliverable_count == len(items):
        return "review_required"
    if deliverable_count == 0:
        return "failed"
    return "partial"


def _build_job_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"job_{timestamp}_{token_hex(4)}"
