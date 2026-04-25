"""Local image quality gate for generated ecommerce assets."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageOps, ImageStat


DEFAULT_QUALITY_THRESHOLD = 72
DEFAULT_MAX_RETRIES = 1


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    """A lightweight, deterministic quality report for one generated image."""

    score: int
    passed: bool
    reasons: list[str]
    retry_instruction: str


def evaluate_generated_image(
    image: Image.Image,
    *,
    threshold: int = DEFAULT_QUALITY_THRESHOLD,
    source_image: Image.Image | None = None,
) -> QualityAssessment:
    """
    Score a generated image without calling another model.

    The scoring intentionally checks objective failure signals that matter for
    ecommerce demos: blank/flat output, overexposure, underexposure, harsh AI
    saturation, low detail, and sterile white studio backgrounds.
    """
    sample = _prepare_sample(image)
    gray = ImageOps.grayscale(sample)
    hsv = sample.convert("HSV")

    luminance = ImageStat.Stat(gray)
    hue_stat = ImageStat.Stat(hsv)
    mean_luma = float(luminance.mean[0])
    luma_std = float(luminance.stddev[0])
    mean_saturation = float(hue_stat.mean[1])
    edge_mean = float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0])
    background_edge_mean, background_luma_std = _background_texture_metrics(gray)
    center_edge_mean = _center_detail_score(gray)
    white_ratio = _white_or_near_white_ratio(hsv)
    dark_ratio = _dark_ratio(gray)
    source_comparison = _compare_with_source(source_image, sample) if source_image is not None else None

    score = 100
    reasons: list[str] = []

    if min(image.size) < 512:
        score -= 14
        reasons.append("分辨率偏低，不适合交付展示")

    if mean_luma > 222:
        score -= 18
        reasons.append("整体过亮，容易像棚拍白底图")
    elif mean_luma < 38:
        score -= 18
        reasons.append("整体过暗，商品细节不足")

    if luma_std < 24:
        score -= 18
        reasons.append("光影层次过平，缺少真实阴影")

    if edge_mean < 5.2:
        score -= 15
        reasons.append("边缘和材质细节偏弱")

    if background_edge_mean < 2.7 and background_luma_std < 14 and white_ratio < 0.58:
        score -= 14
        reasons.append("桌面/背景纹理过度平滑，像被 AI 涂抹成均匀色块")

    if center_edge_mean < 7.4:
        score -= 14
        reasons.append("商品主体细节和边缘增强不足，珠子、金属或珍珠不够抓人")

    if background_edge_mean < 3.2 and center_edge_mean < 8.8:
        score -= 8
        reasons.append("画面存在全局降噪或柔化痕迹，真实照片微纹理不足")

    if mean_saturation > 118:
        score -= 12
        reasons.append("颜色饱和度偏高，存在 AI 广告图质感")

    if white_ratio > 0.68:
        score -= 16
        reasons.append("大面积冷白背景，偏 AI 棚拍")
    elif white_ratio > 0.52 and luma_std < 32:
        score -= 10
        reasons.append("背景过干净，生活化场景不足")

    if dark_ratio > 0.48:
        score -= 10
        reasons.append("暗部占比过高，商品可读性不足")

    if source_comparison:
        edge_delta = source_comparison["edge_delta"]
        background_texture_delta = source_comparison["background_texture_delta"]
        center_detail_delta = source_comparison["center_detail_delta"]
        luma_delta = source_comparison["luma_delta"]
        saturation_delta = source_comparison["saturation_delta"]

        if background_texture_delta < -2.5:
            score -= 14
            reasons.append("相对原图桌面/背景纹理下降，真实微纹理被抹平")
        if center_detail_delta < -1.6:
            score -= 18
            reasons.append("相对原图商品主体细节下降，链条、吊坠、金属或珠宝边缘不够抓人")
        if edge_delta < -2.2:
            score -= 12
            reasons.append("相对原图全局边缘细节下降，存在整体降噪或柔化倾向")
        if luma_delta > 30:
            score -= 8
            reasons.append("相对原图明显变亮，容易出现过曝或 AI 棚拍感")
        if saturation_delta > 28:
            score -= 8
            reasons.append("相对原图饱和度提升过大，容易像 AI 广告图")
        if min(image.size) < min(source_image.size) * 0.82:
            score -= 6
            reasons.append("结果尺寸明显小于原图，交付清晰度有损失")

    if not reasons:
        reasons.append("通过本地质检：亮度、细节、色彩和背景自然度达标")

    normalized_score = max(0, min(100, round(score)))
    passed = normalized_score >= threshold
    return QualityAssessment(
        score=normalized_score,
        passed=passed,
        reasons=reasons,
        retry_instruction=_build_retry_instruction(reasons),
    )


def build_quality_retry_prompt(base_prompt: str, assessment: QualityAssessment) -> str:
    """Append focused repair instructions for one retry attempt."""
    return "\n\n".join(
        [
            base_prompt.strip(),
            "自动质检未通过，请基于同一张原图重新生成，并重点修正以下问题：",
            "\n".join(f"- {reason}" for reason in assessment.reasons),
            assessment.retry_instruction,
        ]
    ).strip()


def _prepare_sample(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    rgb.thumbnail((420, 420), Image.Resampling.LANCZOS)
    return rgb


def _white_or_near_white_ratio(hsv: Image.Image) -> float:
    pixels = list(hsv.getdata())
    if not pixels:
        return 0
    white_pixels = sum(1 for _hue, saturation, value in pixels if saturation < 34 and value > 224)
    return white_pixels / len(pixels)


def _dark_ratio(gray: Image.Image) -> float:
    pixels = list(gray.getdata())
    if not pixels:
        return 0
    dark_pixels = sum(1 for value in pixels if value < 38)
    return dark_pixels / len(pixels)


def _background_texture_metrics(gray: Image.Image) -> tuple[float, float]:
    """Estimate whether border background areas were over-smoothed."""
    width, height = gray.size
    boxes = [
        (0, 0, int(width * 0.28), int(height * 0.28)),
        (int(width * 0.72), 0, width, int(height * 0.28)),
        (0, int(height * 0.72), int(width * 0.28), height),
        (int(width * 0.72), int(height * 0.72), width, height),
    ]
    edge_values: list[float] = []
    std_values: list[float] = []

    for box in boxes:
        patch = gray.crop(box)
        if patch.size[0] < 12 or patch.size[1] < 12:
            continue
        edge_values.append(float(ImageStat.Stat(patch.filter(ImageFilter.FIND_EDGES)).mean[0]))
        std_values.append(float(ImageStat.Stat(patch).stddev[0]))

    if not edge_values:
        return 0, 0
    return sum(edge_values) / len(edge_values), sum(std_values) / len(std_values)


def _center_detail_score(gray: Image.Image) -> float:
    """Estimate detail in the likely product area."""
    width, height = gray.size
    center = gray.crop(
        (
            int(width * 0.22),
            int(height * 0.20),
            int(width * 0.78),
            int(height * 0.82),
        )
    )
    return float(ImageStat.Stat(center.filter(ImageFilter.FIND_EDGES)).mean[0])


def _compare_with_source(source_image: Image.Image, result_sample: Image.Image) -> dict[str, float]:
    source_sample = _prepare_sample(source_image)
    source_gray = ImageOps.grayscale(source_sample)
    result_gray = ImageOps.grayscale(result_sample)
    source_hsv = source_sample.convert("HSV")
    result_hsv = result_sample.convert("HSV")

    source_background_edge, _source_background_luma_std = _background_texture_metrics(source_gray)
    result_background_edge, _result_background_luma_std = _background_texture_metrics(result_gray)

    return {
        "luma_delta": float(ImageStat.Stat(result_gray).mean[0] - ImageStat.Stat(source_gray).mean[0]),
        "saturation_delta": float(ImageStat.Stat(result_hsv).mean[1] - ImageStat.Stat(source_hsv).mean[1]),
        "edge_delta": float(
            ImageStat.Stat(result_gray.filter(ImageFilter.FIND_EDGES)).mean[0]
            - ImageStat.Stat(source_gray.filter(ImageFilter.FIND_EDGES)).mean[0]
        ),
        "background_texture_delta": float(result_background_edge - source_background_edge),
        "center_detail_delta": float(_center_detail_score(result_gray) - _center_detail_score(source_gray)),
    }


def _build_retry_instruction(reasons: list[str]) -> str:
    if any("纹理过度平滑" in reason or "柔化" in reason or "微纹理" in reason for reason in reasons):
        return "降低重绘强度：保留桌面纹理、自然噪点、皮肤纹理、甲面反光和局部瑕疵，禁止全局降噪和背景涂抹。"
    if any("商品主体" in reason or "珠子" in reason or "金属" in reason or "珍珠" in reason for reason in reasons):
        return "把商品作为第一优先级：增强珠子通透度、金属高光、珍珠洁净度和主体边缘清晰度，背景只做轻微整理。"
    if any("棚拍" in reason or "背景" in reason for reason in reasons):
        return "改为真实卖家拍摄感：自然桌面、布料、托盘或生活化背景，保留接触阴影，避免纯白棚拍。"
    if any("过亮" in reason or "过暗" in reason or "光影" in reason for reason in reasons):
        return "调整为柔和自然光，保留真实阴影和层次，避免冷白曝光或死黑暗部。"
    if any("饱和" in reason for reason in reasons):
        return "降低饱和度和磨皮感，使用自然色彩、真实材质纹理和轻微生活痕迹。"
    return "提高商品边缘清晰度、材质细节和生活化真实感，避免 AI 质感。"
