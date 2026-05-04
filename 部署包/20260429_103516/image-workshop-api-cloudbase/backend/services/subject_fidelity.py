"""Source-aware ecommerce subject protection checks.

The first production-safe layer should not try to "fix" the product by
hallucinating pixels. It should make small non-generative enhancements and
block results whose subject structure drifts too far from the source.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


COMPARE_SIZE = 512


@dataclass(frozen=True, slots=True)
class SubjectFidelityIssue:
    """One product/subject fidelity issue detected locally."""

    reason: str
    penalty: int
    retry_instruction: str
    blocker: bool = True


@dataclass(frozen=True, slots=True)
class SubjectEnhancementResult:
    """Non-generative subject enhancement result."""

    image: Image.Image
    note: str
    mask_coverage: float = 0.0


def build_subject_fidelity_prompt() -> str:
    """Return a source-lock instruction for the image model."""
    return "\n".join(
        [
            "商品主体保护硬约束：",
            "- 原图里的商品是唯一交付主体，必须保持原商品结构、颜色、材质、比例、边缘和关键识别点。",
            "- 不允许替换商品、不允许改变链条走向、吊坠外形、金属镶边、珠子/宝石数量和相对位置。",
            "- 背景、桌面、袖口和氛围可以优化，但不能牺牲商品清晰度；商品细节必须不低于原图。",
            "- 如果背景重绘和商品保真冲突，优先保留商品，不要为了画面风格重画商品。",
        ]
    )


def enhance_subject_non_generative(
    result_image: Image.Image,
    *,
    source_image: Image.Image | None = None,
) -> SubjectEnhancementResult:
    """
    Protect the source product with a conservative mask and copy-back.

    This is the first lightweight version of the "mask + background rewrite +
    copy-back" pipeline. The mask deliberately focuses on non-skin, high-detail
    product edges so it does not restore the whole hand, old background, or most
    text-like watermark pixels.
    """
    rgb = result_image.convert("RGB")
    if source_image is None:
        enhanced = _light_subject_enhance(rgb, _soft_center_subject_mask(rgb.size))
        return SubjectEnhancementResult(
            image=enhanced,
            note="已启用商品主体保护：无原图时仅做非生成式局部细节增强，并进入商品相似度硬质检。",
        )

    source_aligned = _align_source_to_result(source_image, rgb.size)
    protection_mask = build_product_protection_mask(source_aligned, rgb)
    mask_coverage = _mask_coverage(protection_mask)

    if mask_coverage < 0.006:
        enhanced = _light_subject_enhance(rgb, _soft_center_subject_mask(rgb.size))
        return SubjectEnhancementResult(
            image=enhanced,
            note="已启用商品主体保护：未能稳定提取商品保护 mask，已退回非生成式局部细节增强。",
            mask_coverage=mask_coverage,
        )

    recall, iou = _edge_similarity(
        _subject_roi(source_aligned),
        _subject_roi(rgb),
        _subject_roi(protection_mask),
    )
    if recall < 0.20 or iou < 0.10:
        enhanced = _light_subject_enhance(rgb, protection_mask)
        return SubjectEnhancementResult(
            image=enhanced,
            note=(
                "已启用商品主体保护：检测到商品/手部结构和原图未对齐，"
                f"跳过像素 copy-back 以避免错位脏点（边缘召回 {recall:.2f}，重合 {iou:.2f}）。"
            ),
            mask_coverage=mask_coverage,
        )

    copied_back = _copy_back_source_detail(
        source_image=source_aligned,
        result_image=rgb,
        mask=protection_mask,
    )
    final_image = _light_subject_enhance(copied_back, protection_mask)
    note = f"已启用商品保护 mask：已从原图 copy-back 商品纹理细节，保护覆盖约 {mask_coverage:.1%}，并进入商品相似度硬质检。"
    return SubjectEnhancementResult(image=final_image, note=note, mask_coverage=mask_coverage)


def build_product_protection_mask(source_image: Image.Image, result_image: Image.Image | None = None) -> Image.Image:
    """
    Build a conservative product mask from the source image.

    The mask uses high-frequency edges, non-skin filtering, center weighting, and
    bright text-like suppression. It is intentionally conservative until a SAM
    segmentation stage is added.
    """
    source = source_image.convert("RGB")
    gray = ImageOps.grayscale(source)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_array = np.asarray(edges, dtype=np.float32)
    edge_threshold = max(float(np.percentile(edge_array, 80)), float(edge_array.mean() + edge_array.std() * 0.68))

    hsv = source.convert("HSV")
    hsv_array = np.asarray(hsv, dtype=np.uint8)
    hue = hsv_array[:, :, 0].astype(np.int16)
    saturation = hsv_array[:, :, 1].astype(np.int16)
    value = hsv_array[:, :, 2].astype(np.int16)

    skin_like = _skin_like_mask(hue, saturation, value)
    text_like = _bright_text_like_mask(edge_array, saturation, value)
    focus = _center_focus_weight(source.size)

    base = (edge_array >= edge_threshold) & (~skin_like) & (~text_like) & (focus > 0.18)
    if result_image is not None:
        result = result_image.convert("RGB").resize(source.size, Image.Resampling.LANCZOS)
        base |= _changed_source_detail_mask(source, result, edge_array, edge_threshold, focus, skin_like, text_like)

    mask = Image.fromarray(np.where(base, 255, 0).astype(np.uint8), mode="L")
    mask = mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(2.2))
    mask = _apply_focus_to_mask(mask, focus)
    return mask


def evaluate_subject_fidelity(
    result_image: Image.Image,
    *,
    source_image: Image.Image | None,
) -> list[SubjectFidelityIssue]:
    """Compare likely product/hand subject region against the source image."""
    if source_image is None:
        return []

    source = _prepare_compare_image(source_image)
    result = _prepare_compare_image(result_image)
    source_roi = _subject_roi(source)
    result_roi = _subject_roi(result)
    mask = _build_source_edge_mask(source_roi)

    mask_coverage = _mask_coverage(mask)
    if mask_coverage < 0.018:
        return [
            SubjectFidelityIssue(
                reason=(
                    "未能稳定提取商品主体保护区域"
                    f"（mask 覆盖 {mask_coverage:.1%}），链条、吊坠、珠子或托盘边缘可能没有被锁定"
                ),
                penalty=18,
                retry_instruction=(
                    "减少整体重绘，保持原图商品主体位置、轮廓、链条和吊坠不变；"
                    "只允许背景和非主体区域轻微变化。"
                ),
                blocker=True,
            )
        ]

    edge_recall, edge_iou = _edge_similarity(source_roi, result_roi, mask)
    color_distance = _masked_color_hist_distance(source_roi, result_roi, mask)
    detail_ratio = _masked_edge_energy_ratio(source_roi, result_roi, mask)
    luma_delta = _masked_luma_delta(source_roi, result_roi, mask)

    issues: list[SubjectFidelityIssue] = []

    if edge_recall < 0.30 or edge_iou < 0.16:
        issues.append(
            SubjectFidelityIssue(
                reason=(
                    "商品/手部主体结构相对原图变化过大"
                    f"（边缘召回 {edge_recall:.2f}，边缘重合 {edge_iou:.2f}），"
                    "可能出现商品形状、链条走向、吊坠轮廓或持物关系被改坏"
                ),
                penalty=30,
                retry_instruction=(
                    "不要整体重绘商品区域；保留原图商品形状、链条走向、吊坠轮廓、金属镶边和手部持物关系，"
                    "只允许背景和非主体区域轻量变化。"
                ),
            )
        )

    if detail_ratio < 0.72:
        issues.append(
            SubjectFidelityIssue(
                reason=(
                    "商品主体高频细节低于原图"
                    f"（主体边缘能量比 {detail_ratio:.2f}），链条、镶边小钻、宝石或吊坠边缘可能变糊"
                ),
                penalty=20,
                retry_instruction=(
                    "商品细节必须不低于原图：链节独立可辨，金属镶边和宝石边缘清楚，背景不能抢走清晰度预算。"
                ),
            )
        )

    if color_distance > 0.28:
        issues.append(
            SubjectFidelityIssue(
                reason=(
                    "商品主体颜色分布相对原图偏移过大"
                    f"（颜色距离 {color_distance:.2f}），可能改色、偏色或材质失真"
                ),
                penalty=18,
                retry_instruction=(
                    "保持商品原始颜色和材质：金属、宝石、珍珠、链条和主体饰品不能被整体改色或换材质。"
                ),
            )
        )

    if abs(luma_delta) > 42:
        issues.append(
            SubjectFidelityIssue(
                reason=f"商品主体亮度相对原图偏移过大（{luma_delta:+.1f}），可能过曝、变暗或材质层次丢失",
                penalty=12,
                retry_instruction="保持商品主体曝光稳定，只做自然光感优化，不要让主体过曝或变成一团暗部。",
                blocker=False,
            )
        )

    return issues


def _prepare_compare_image(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    return ImageOps.fit(rgb, (COMPARE_SIZE, COMPARE_SIZE), method=Image.Resampling.LANCZOS, centering=(0.5, 0.52))


def _subject_roi(image: Image.Image) -> Image.Image:
    width, height = image.size
    return image.crop(
        (
            int(width * 0.12),
            int(height * 0.10),
            int(width * 0.90),
            int(height * 0.90),
        )
    )


def _soft_center_subject_mask(size: tuple[int, int]) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    inner = Image.new("L", (max(1, int(width * 0.78)), max(1, int(height * 0.78))), 255)
    x = int(width * 0.11)
    y = int(height * 0.12)
    mask.paste(inner, (x, y))
    blur_radius = max(18, int(min(size) * 0.035))
    return mask.filter(ImageFilter.GaussianBlur(blur_radius))


def _build_source_edge_mask(source_roi: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(source_roi)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_array = np.asarray(edges, dtype=np.float32)
    threshold = max(float(edge_array.mean() + edge_array.std() * 0.72), float(np.percentile(edge_array, 78)))
    mask = Image.fromarray(np.where(edge_array >= threshold, 255, 0).astype(np.uint8), mode="L")
    mask = mask.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(4))
    return mask


def _edge_similarity(source_roi: Image.Image, result_roi: Image.Image, source_mask: Image.Image) -> tuple[float, float]:
    source_edges = _binary_edges(source_roi)
    result_edges = _binary_edges(result_roi)
    mask = np.asarray(source_mask, dtype=np.uint8) > 24
    source_edges = np.logical_and(source_edges, mask)
    result_edges = np.logical_and(result_edges, mask)

    source_count = int(source_edges.sum())
    result_count = int(result_edges.sum())
    if source_count == 0 or result_count == 0:
        return 1.0, 1.0

    intersection = int(np.logical_and(source_edges, result_edges).sum())
    union = int(np.logical_or(source_edges, result_edges).sum())
    return intersection / source_count, intersection / union if union else 1.0


def _binary_edges(image: Image.Image) -> np.ndarray:
    gray = ImageOps.grayscale(image)
    edges = gray.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5))
    edge_array = np.asarray(edges, dtype=np.float32)
    threshold = max(float(edge_array.mean() + edge_array.std() * 0.62), float(np.percentile(edge_array, 76)))
    return edge_array >= threshold


def _masked_color_hist_distance(source_roi: Image.Image, result_roi: Image.Image, mask: Image.Image) -> float:
    source = np.asarray(source_roi.convert("RGB"), dtype=np.uint8)
    result = np.asarray(result_roi.convert("RGB"), dtype=np.uint8)
    weights = np.asarray(mask, dtype=np.float32) / 255.0
    keep = weights > 0.08
    if not np.any(keep):
        return 0.0

    distances: list[float] = []
    for channel in range(3):
        source_hist, _ = np.histogram(source[:, :, channel][keep], bins=24, range=(0, 255), density=True)
        result_hist, _ = np.histogram(result[:, :, channel][keep], bins=24, range=(0, 255), density=True)
        distances.append(float(np.abs(source_hist - result_hist).sum()) / 2.0)
    return sum(distances) / len(distances)


def _masked_edge_energy_ratio(source_roi: Image.Image, result_roi: Image.Image, mask: Image.Image) -> float:
    source_edges = np.asarray(ImageOps.grayscale(source_roi).filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    result_edges = np.asarray(ImageOps.grayscale(result_roi).filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    weights = np.asarray(mask, dtype=np.float32) / 255.0
    weight_sum = float(weights.sum())
    if weight_sum <= 0:
        return 1.0

    source_energy = float((source_edges * weights).sum() / weight_sum)
    result_energy = float((result_edges * weights).sum() / weight_sum)
    if source_energy <= 0.01:
        return 1.0
    return result_energy / source_energy


def _masked_luma_delta(source_roi: Image.Image, result_roi: Image.Image, mask: Image.Image) -> float:
    source = np.asarray(ImageOps.grayscale(source_roi), dtype=np.float32)
    result = np.asarray(ImageOps.grayscale(result_roi), dtype=np.float32)
    weights = np.asarray(mask, dtype=np.float32) / 255.0
    weight_sum = float(weights.sum())
    if weight_sum <= 0:
        return 0.0
    return float(((result - source) * weights).sum() / weight_sum)


def _mask_coverage(mask: Image.Image) -> float:
    array = np.asarray(mask, dtype=np.float32)
    if array.size == 0:
        return 0.0
    return float((array > 24).sum() / array.size)


def _align_source_to_result(source_image: Image.Image, result_size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(
        source_image.convert("RGB"),
        result_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.52),
    )


def _light_subject_enhance(image: Image.Image, mask: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    enhanced = rgb.filter(ImageFilter.UnsharpMask(radius=1.0, percent=70, threshold=4))
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.025)
    return Image.composite(enhanced, rgb, mask)


def _copy_back_source_detail(
    *,
    source_image: Image.Image,
    result_image: Image.Image,
    mask: Image.Image,
) -> Image.Image:
    """Transfer source high-frequency product detail without restoring full source pixels."""
    source = source_image.convert("RGB")
    result = result_image.convert("RGB")
    source_blur = source.filter(ImageFilter.GaussianBlur(1.8))
    result_blur = result.filter(ImageFilter.GaussianBlur(1.8))
    source_arr = np.asarray(source, dtype=np.float32)
    source_blur_arr = np.asarray(source_blur, dtype=np.float32)
    result_arr = np.asarray(result, dtype=np.float32)
    result_blur_arr = np.asarray(result_blur, dtype=np.float32)
    mask_arr = np.asarray(mask, dtype=np.float32)[:, :, None] / 255.0
    mask_arr = np.clip(mask_arr * 0.82, 0.0, 0.82)

    source_detail = source_arr - source_blur_arr
    result_detail = result_arr - result_blur_arr
    detail_delta = np.clip(source_detail - result_detail, -42, 42)
    low_frequency_delta = np.clip(source_blur_arr - result_blur_arr, -22, 22)
    transferred = result_arr + detail_delta * mask_arr + low_frequency_delta * mask_arr * 0.18
    return Image.fromarray(np.clip(transferred, 0, 255).astype(np.uint8), mode="RGB")


def _skin_like_mask(hue: np.ndarray, saturation: np.ndarray, value: np.ndarray) -> np.ndarray:
    warm_hue = (hue <= 30) | ((hue >= 235) & (hue <= 255))
    return warm_hue & (saturation >= 18) & (saturation <= 170) & (value >= 74)


def _bright_text_like_mask(edge_array: np.ndarray, saturation: np.ndarray, value: np.ndarray) -> np.ndarray:
    bright = (value >= 200) & (saturation <= 48)
    sharp = edge_array >= max(float(np.percentile(edge_array, 90)), float(edge_array.mean() + edge_array.std() * 1.0))
    text_like = bright & sharp
    mask = Image.fromarray(np.where(text_like, 255, 0).astype(np.uint8), mode="L")
    mask = mask.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(1.5))
    return np.asarray(mask, dtype=np.uint8) > 70


def _center_focus_weight(size: tuple[int, int]) -> np.ndarray:
    width, height = size
    yy, xx = np.mgrid[0:height, 0:width]
    cx = width * 0.52
    cy = height * 0.53
    rx = max(width * 0.46, 1)
    ry = max(height * 0.48, 1)
    distance = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    return np.clip(1.0 - distance, 0.0, 1.0)


def _changed_source_detail_mask(
    source: Image.Image,
    result: Image.Image,
    edge_array: np.ndarray,
    edge_threshold: float,
    focus: np.ndarray,
    skin_like: np.ndarray,
    text_like: np.ndarray,
) -> np.ndarray:
    source_gray = np.asarray(ImageOps.grayscale(source), dtype=np.float32)
    result_gray = np.asarray(ImageOps.grayscale(result), dtype=np.float32)
    color_delta = np.abs(np.asarray(source, dtype=np.int16) - np.asarray(result, dtype=np.int16)).mean(axis=2)
    luma_delta = np.abs(source_gray - result_gray)
    changed = (color_delta > 28) | (luma_delta > 32)
    detailed = edge_array >= max(edge_threshold * 0.82, float(np.percentile(edge_array, 72)))
    return changed & detailed & (~skin_like) & (~text_like) & (focus > 0.22)


def _apply_focus_to_mask(mask: Image.Image, focus: np.ndarray) -> Image.Image:
    mask_array = np.asarray(mask, dtype=np.float32)
    weighted = mask_array * np.clip(focus * 1.3, 0.0, 1.0)
    return Image.fromarray(np.clip(weighted, 0, 255).astype(np.uint8), mode="L")
