"""Image loading, provider normalization, and data URL helpers."""

from __future__ import annotations

import base64
import io
import re
import statistics
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, UnidentifiedImageError


MAX_IMAGE_PIXELS = 40_000_000
MAX_PROVIDER_IMAGE_EDGE = 2048
PROVIDER_JPEG_QUALITY = 90
OUTPUT_JPEG_QUALITY = 94
_OCR_READER = None


class ImagePreprocessError(RuntimeError):
    """Raised when the backend cannot read or normalize an image."""


def split_keywords(raw_value: str | None) -> list[str]:
    """Split comma/newline separated watermark keywords into a clean list."""
    if not raw_value:
        return []
    return [
        keyword.strip()
        for keyword in re.split(r"[,，\n\r]+", raw_value)
        if keyword.strip()
    ]


def sanitize_filename(value: str) -> str:
    """Remove unsafe filename characters while keeping the name readable."""
    cleaned = re.sub(r"[^\w.-]+", "-", value.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-.")
    return cleaned or "image"


def guess_image_mime_type(filename: str | None, image_bytes: bytes) -> str:
    """Guess image MIME type from bytes first, then filename."""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"

    lower_name = (filename or "").lower()
    if lower_name.endswith(".png"):
        return "image/png"
    if lower_name.endswith(".webp"):
        return "image/webp"
    if lower_name.endswith(".jpg") or lower_name.endswith(".jpeg"):
        return "image/jpeg"
    return "image/png"


def load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    """Load user-provided bytes as a PIL image with basic validation."""
    if not image_bytes:
        raise ImagePreprocessError("图片内容为空。")

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImagePreprocessError("上传的文件不是有效的图片。") from exc

    width, height = image.size
    if width * height > MAX_IMAGE_PIXELS:
        raise ImagePreprocessError("图片分辨率过大，请先压缩后再上传。")

    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA")
    else:
        image = image.copy()
    return image


def resize_image_for_provider(image: Image.Image, max_edge: int = MAX_PROVIDER_IMAGE_EDGE) -> Image.Image:
    """Keep provider requests compact while preserving source composition."""
    width, height = image.size
    longest_edge = max(width, height)
    if longest_edge <= max_edge:
        return image.copy()

    scale = max_edge / longest_edge
    target_size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    return image.resize(target_size, Image.Resampling.LANCZOS)


def prepare_provider_image_bytes(image_bytes: bytes) -> bytes:
    """
    Normalize uploads into provider-friendly bytes.

    Images are capped to a 2048px longest edge. Images without meaningful
    transparency are sent as JPEG to keep provider payloads compact.
    """
    image = load_image_from_bytes(image_bytes)
    normalized = resize_image_for_provider(image)

    if normalized.mode == "RGBA" and _has_meaningful_alpha(normalized):
        return pil_image_to_png_bytes(normalized)

    return pil_image_to_jpeg_bytes(normalized, quality=PROVIDER_JPEG_QUALITY)


def build_provider_input_filename(source_name: str, image_bytes: bytes) -> str:
    """Create a provider-facing filename that matches normalized bytes."""
    stem = sanitize_filename(Path(source_name).stem or "image")
    mime_type = guess_image_mime_type(source_name, image_bytes)
    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(mime_type, ".png")
    return f"{stem}{extension}"


def pil_image_to_png_bytes(image: Image.Image) -> bytes:
    """Serialize a PIL image to PNG bytes."""
    normalized = image.convert("RGBA") if image.mode not in {"RGB", "RGBA"} else image.copy()
    buffer = io.BytesIO()
    normalized.save(buffer, format="PNG")
    return buffer.getvalue()


def pil_image_to_jpeg_bytes(image: Image.Image, quality: int = PROVIDER_JPEG_QUALITY) -> bytes:
    """Serialize a PIL image to compact JPEG bytes."""
    normalized = image.convert("RGB") if image.mode != "RGB" else image.copy()
    buffer = io.BytesIO()
    normalized.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def image_to_data_url(image: Image.Image, output_format: str) -> str:
    """Serialize a PIL image result into a browser-ready data URL."""
    normalized_format = normalize_output_format(output_format)
    if normalized_format == "jpg":
        raw_bytes = pil_image_to_jpeg_bytes(image, quality=OUTPUT_JPEG_QUALITY)
        mime_type = "image/jpeg"
    else:
        raw_bytes = pil_image_to_png_bytes(image)
        mime_type = "image/png"

    encoded = base64.b64encode(raw_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def remove_watermark_if_needed(
    image: Image.Image,
    keywords: Sequence[str] | None = None,
) -> tuple[Image.Image, str]:
    """
    Best-effort watermark cleanup restored from the Streamlit MVP.

    This is intentionally non-blocking: if optional OCR dependencies are absent
    or detection is uncertain, generation still succeeds and returns the image.
    """
    cleaned = image.copy()
    normalized_keywords = [item.lower().strip() for item in (keywords or []) if item.strip()]

    try:
        if normalized_keywords:
            cleaned, removed_texts = _remove_watermark_by_text_ocr(cleaned, normalized_keywords)
            if removed_texts:
                unique_texts = list(dict.fromkeys(removed_texts))
                return cleaned, f"已按关键词去除水印：{', '.join(unique_texts)}"
    except Exception:
        cleaned = image.copy()

    try:
        heuristic_image, removed = _remove_bottom_right_light_watermark(cleaned)
        if removed:
            return heuristic_image, "已通过底部区域启发式方式清理疑似水印。"
    except Exception:
        pass

    return image, ""


def normalize_output_format(value: str | None) -> str:
    """Map frontend output format values to supported serializers."""
    cleaned = (value or "png").strip().lower()
    if cleaned in {"jpg", "jpeg"}:
        return "jpg"
    return "png"


def _get_ocr_reader():
    """Lazy-load EasyOCR only when the optional dependency is installed."""
    global _OCR_READER

    if _OCR_READER is not None:
        return _OCR_READER

    try:
        import easyocr  # type: ignore
    except ImportError:
        return None

    _OCR_READER = easyocr.Reader(["ch_sim", "en"], gpu=False)
    return _OCR_READER


def _remove_watermark_by_text_ocr(
    image: Image.Image,
    keywords: Sequence[str],
) -> tuple[Image.Image, list[str]]:
    """Use OCR keywords plus background sampling to erase detected watermark text."""
    try:
        import numpy as np
    except ImportError:
        return image, []

    reader = _get_ocr_reader()
    if reader is None:
        return image, []

    rgb_image = image.convert("RGB")
    image_array = np.array(rgb_image)
    results = reader.readtext(image_array, text_threshold=0.25, low_text=0.25)
    if not results:
        return image, []

    draw = ImageDraw.Draw(rgb_image)
    removed_texts: list[str] = []

    for bbox, text, _confidence in results:
        lowered = str(text).lower().replace(" ", "")
        if not any(keyword in lowered for keyword in keywords):
            continue

        x1, y1, x2, y2 = _bbox_rect(bbox)
        _erase_region_with_sampled_bg(draw, image_array, x1, y1, x2, y2, rgb_image.size)
        removed_texts.append(str(text).strip())

    return rgb_image if removed_texts else image, removed_texts


def _bbox_rect(bbox: Iterable[Iterable[float]]) -> tuple[int, int, int, int]:
    """Convert OCR bbox points into a rectangle."""
    points = list(bbox)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def _erase_region_with_sampled_bg(
    draw: ImageDraw.ImageDraw,
    image_array,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    image_size: tuple[int, int],
    expand: int = 18,
) -> None:
    """Fill a detected text region using a background color sampled from nearby pixels."""
    width, height = image_size
    fill_color = _sample_background_color(image_array, x1, y1, x2, y2)
    draw.rectangle(
        [
            max(0, x1 - expand),
            max(0, y1 - expand),
            min(width, x2 + expand),
            min(height, y2 + expand),
        ],
        fill=fill_color,
    )


def _sample_background_color(image_array, x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int]:
    """Sample a median background color from the left or upper strip of the bbox."""
    try:
        import numpy as np
    except ImportError:
        return (255, 255, 255)

    sx1 = max(0, x1 - 80)
    sx2 = max(0, x1 - 8)
    if sx2 > sx1 and y2 > y1:
        region = image_array[y1:y2, sx1:sx2]
        if region.size > 0:
            flat = region.reshape(-1, region.shape[-1])
            median = np.median(flat, axis=0)
            return tuple(int(channel) for channel in median[:3])

    top_y1 = max(0, y1 - 20)
    top_region = image_array[top_y1:y1, x1:x2]
    if top_region.size > 0:
        flat = top_region.reshape(-1, top_region.shape[-1])
        median = np.median(flat, axis=0)
        return tuple(int(channel) for channel in median[:3])

    return (255, 255, 255)


def _remove_bottom_right_light_watermark(image: Image.Image) -> tuple[Image.Image, bool]:
    """
    Detect a likely pale watermark in the bottom-right corner and cover it.

    The heuristic samples nearby background and fills only a small detected box,
    keeping it conservative enough for batch product images.
    """
    rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    crop_box = (
        int(width * 0.56),
        int(height * 0.72),
        width,
        height,
    )
    cropped = rgb_image.crop(crop_box)
    hsv = cropped.convert("HSV")

    points: list[tuple[int, int]] = []
    crop_width, crop_height = cropped.size

    for y in range(crop_height):
        for x in range(crop_width):
            _hue, saturation, value = hsv.getpixel((x, y))
            red, green, blue = cropped.getpixel((x, y))
            is_neutral = max(abs(red - green), abs(green - blue), abs(red - blue)) <= 18
            if saturation < 48 and 150 <= value <= 250 and is_neutral:
                points.append((x, y))

    if len(points) < 24:
        return image, False

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)

    bbox_width = x2 - x1 + 1
    bbox_height = y2 - y1 + 1
    area_ratio = (bbox_width * bbox_height) / max(1, crop_width * crop_height)
    if area_ratio > 0.35 or bbox_width < 24 or bbox_height < 10:
        return image, False

    full_x1 = crop_box[0] + x1
    full_x2 = crop_box[0] + x2
    full_y1 = crop_box[1] + y1
    full_y2 = crop_box[1] + y2

    fill_color = _sample_background_from_pil(rgb_image, full_x1, full_y1, full_x2, full_y2)
    draw = ImageDraw.Draw(rgb_image)
    padding = 12
    draw.rectangle(
        [
            max(0, full_x1 - padding),
            max(0, full_y1 - padding),
            min(width, full_x2 + padding),
            min(height, full_y2 + padding),
        ],
        fill=fill_color,
    )
    return rgb_image, True


def _sample_background_from_pil(
    image: Image.Image,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> tuple[int, int, int]:
    """Sample a reasonable fill color without requiring numpy."""
    samples: list[tuple[int, int, int]] = []

    left_start = max(0, x1 - 60)
    left_end = max(0, x1 - 5)
    for px in range(left_start, left_end):
        for py in range(y1, y2 + 1):
            samples.append(image.getpixel((px, py)))

    if not samples:
        top_start = max(0, y1 - 20)
        for px in range(x1, x2 + 1):
            for py in range(top_start, y1):
                samples.append(image.getpixel((px, py)))

    if not samples:
        return (255, 255, 255)

    red = int(statistics.median(pixel[0] for pixel in samples))
    green = int(statistics.median(pixel[1] for pixel in samples))
    blue = int(statistics.median(pixel[2] for pixel in samples))
    return (red, green, blue)


def _has_meaningful_alpha(image: Image.Image) -> bool:
    if image.mode != "RGBA":
        return False
    alpha = image.getchannel("A")
    return alpha.getextrema() != (255, 255)
