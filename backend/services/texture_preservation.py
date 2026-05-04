"""Real-scene texture preservation for ecommerce image edits.

Generative image editors tend to interpret believable photo imperfections as
noise: book paper texture, desk grain, fabric fibers, acrylic tray refraction,
skin pores, and uneven live lighting. This module adds a conservative local
post-process that restores micro-detail without hallucinating new content.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps

from backend.services.subject_fidelity import build_product_protection_mask


@dataclass(frozen=True, slots=True)
class TexturePreservationResult:
    """A generated image plus a short user-facing operation note."""

    image: Image.Image
    note: str
    mask_coverage: float = 0.0
    detail_gain: float = 0.0


def preserve_real_scene_texture(
    result_image: Image.Image,
    *,
    source_image: Image.Image | None = None,
) -> TexturePreservationResult:
    """
    Reintroduce believable micro-texture where the model over-smoothed the scene.

    The pass is intentionally conservative:
    - copy back only high-frequency source detail, not full source pixels;
    - avoid product/hand structure rewrites;
    - add subtle deterministic photo grain to changed backgrounds so replaced
      desks do not become flat AI color blocks.
    """
    result = result_image.convert("RGB")
    if source_image is None:
        enhanced = _add_subtle_global_grain(result, amount=0.45)
        return TexturePreservationResult(
            image=enhanced,
            note="已启用真实纹理保护：无原图时仅补偿轻微自然颗粒，避免纯净 AI 平滑感。",
            mask_coverage=1.0,
            detail_gain=0.45,
        )

    source = _align_source_to_result(source_image, result.size)
    source_detail = _detail_energy(source)
    result_detail = _detail_energy(result)
    source_texture = _texture_candidate_mask(source_detail)
    lost_texture = result_detail < (source_detail * 0.76)
    same_region = _same_region_mask(source, result)
    non_subject = _non_subject_mask(source, result)
    scene_mask = source_texture & lost_texture & non_subject

    copy_mask = scene_mask & same_region
    grain_mask = scene_mask
    copy_coverage = float(copy_mask.sum() / copy_mask.size) if copy_mask.size else 0.0
    grain_coverage = float(grain_mask.sum() / grain_mask.size) if grain_mask.size else 0.0

    if grain_coverage < 0.006:
        enhanced = _add_subtle_global_grain(result, amount=0.32)
        return TexturePreservationResult(
            image=enhanced,
            note="已启用真实纹理保护：未检测到明显纹理丢失，仅补偿轻微自然颗粒。",
            mask_coverage=grain_coverage,
            detail_gain=0.32,
        )

    copy_mask_image = _soft_mask(copy_mask, result.size, strength=0.36)
    grain_mask_image = _soft_mask(grain_mask, result.size, strength=0.52)
    enhanced = _copy_back_micro_detail(
        source_image=source,
        result_image=result,
        copy_mask=copy_mask_image,
        grain_mask=grain_mask_image,
    )
    detail_gain = _mean_detail_delta(result, enhanced, grain_mask_image)
    note = (
        "已启用真实纹理保护：检测到背景/桌面/布料等区域被抹平，"
        f"已回填微纹理与自然颗粒（覆盖约 {grain_coverage:.1%}）。"
    )
    if copy_coverage < 0.01:
        note += " 背景变化较大，本次主要补颗粒，不强行恢复原背景纹理。"

    return TexturePreservationResult(
        image=enhanced,
        note=note,
        mask_coverage=grain_coverage,
        detail_gain=detail_gain,
    )


def _align_source_to_result(source_image: Image.Image, result_size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(
        source_image.convert("RGB"),
        result_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.52),
    )


def _detail_energy(image: Image.Image) -> np.ndarray:
    gray = ImageOps.grayscale(image)
    blur = gray.filter(ImageFilter.GaussianBlur(1.3))
    highpass = ImageChops.subtract(gray, blur, scale=1.0, offset=128)
    highpass_array = np.abs(np.asarray(highpass, dtype=np.float32) - 128.0)
    edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    return highpass_array * 0.62 + edges * 0.38


def _texture_candidate_mask(detail: np.ndarray) -> np.ndarray:
    if detail.size == 0:
        return np.zeros_like(detail, dtype=bool)
    threshold = max(float(np.percentile(detail, 58)), float(detail.mean() + detail.std() * 0.18), 4.0)
    return detail >= threshold


def _same_region_mask(source: Image.Image, result: Image.Image) -> np.ndarray:
    source_arr = np.asarray(source, dtype=np.int16)
    result_arr = np.asarray(result, dtype=np.int16)
    color_distance = np.abs(source_arr - result_arr).mean(axis=2)
    source_gray = np.asarray(ImageOps.grayscale(source), dtype=np.int16)
    result_gray = np.asarray(ImageOps.grayscale(result), dtype=np.int16)
    luma_distance = np.abs(source_gray - result_gray)
    return (color_distance < 52) | ((color_distance < 72) & (luma_distance < 44))


def _non_subject_mask(source: Image.Image, result: Image.Image) -> np.ndarray:
    product_mask = build_product_protection_mask(source, result)
    protected = np.asarray(product_mask.filter(ImageFilter.MaxFilter(11)), dtype=np.float32) / 255.0
    skin = _skin_like_mask(result)
    # Do not forbid all skin edges: sleeves and nearby texture are useful, but
    # avoid altering actual palm/finger areas where anatomy checks are strict.
    return (protected < 0.18) & (~skin)


def _skin_like_mask(image: Image.Image) -> np.ndarray:
    hsv = image.convert("HSV")
    hsv_array = np.asarray(hsv, dtype=np.uint8)
    hue = hsv_array[:, :, 0].astype(np.int16)
    saturation = hsv_array[:, :, 1].astype(np.int16)
    value = hsv_array[:, :, 2].astype(np.int16)
    warm_hue = (hue <= 30) | ((hue >= 235) & (hue <= 255))
    mask = warm_hue & (saturation >= 18) & (saturation <= 172) & (value >= 70)
    mask_image = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), mode="L")
    mask_image = mask_image.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(1.4))
    return np.asarray(mask_image, dtype=np.uint8) > 72


def _soft_mask(mask: np.ndarray, size: tuple[int, int], *, strength: float) -> Image.Image:
    mask_image = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), mode="L")
    mask_image = mask_image.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(3.0))
    mask_array = np.asarray(mask_image, dtype=np.float32) * strength
    return Image.fromarray(np.clip(mask_array, 0, 255).astype(np.uint8), mode="L").resize(
        size,
        Image.Resampling.BILINEAR,
    )


def _copy_back_micro_detail(
    *,
    source_image: Image.Image,
    result_image: Image.Image,
    copy_mask: Image.Image,
    grain_mask: Image.Image,
) -> Image.Image:
    source = source_image.convert("RGB")
    result = result_image.convert("RGB")
    source_arr = np.asarray(source, dtype=np.float32)
    result_arr = np.asarray(result, dtype=np.float32)
    source_blur = np.asarray(source.filter(ImageFilter.GaussianBlur(1.45)), dtype=np.float32)
    result_blur = np.asarray(result.filter(ImageFilter.GaussianBlur(1.45)), dtype=np.float32)
    source_highpass = source_arr - source_blur
    result_highpass = result_arr - result_blur
    detail_delta = np.clip(source_highpass - result_highpass, -28, 28)

    copy_weights = np.asarray(copy_mask, dtype=np.float32)[:, :, None] / 255.0
    grain_weights = np.asarray(grain_mask, dtype=np.float32)[:, :, None] / 255.0
    rng = np.random.default_rng(20260430)
    grain = rng.normal(0.0, 3.2, size=result_arr.shape).astype(np.float32)
    chroma_grain = grain * np.array([0.82, 0.92, 1.0], dtype=np.float32)

    transferred = result_arr + detail_delta * copy_weights + chroma_grain * grain_weights
    interim = Image.fromarray(np.clip(transferred, 0, 255).astype(np.uint8), mode="RGB")
    sharpened = interim.filter(ImageFilter.UnsharpMask(radius=0.9, percent=42, threshold=5))
    return Image.composite(sharpened, interim, grain_mask)


def _add_subtle_global_grain(image: Image.Image, *, amount: float) -> Image.Image:
    rgb = image.convert("RGB")
    arr = np.asarray(rgb, dtype=np.float32)
    rng = np.random.default_rng(20260430)
    grain = rng.normal(0.0, amount, size=arr.shape).astype(np.float32)
    return Image.fromarray(np.clip(arr + grain, 0, 255).astype(np.uint8), mode="RGB")


def _mean_detail_delta(before: Image.Image, after: Image.Image, mask: Image.Image) -> float:
    before_detail = _detail_energy(before)
    after_detail = _detail_energy(after)
    weights = np.asarray(mask, dtype=np.float32) / 255.0
    weight_sum = float(weights.sum())
    if weight_sum <= 0:
        return 0.0
    return float(((after_detail - before_detail) * weights).sum() / weight_sum)
