"""Image loading, provider normalization, and data URL helpers."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_PIXELS = 40_000_000
MAX_PROVIDER_IMAGE_EDGE = 2048
PROVIDER_JPEG_QUALITY = 90
OUTPUT_JPEG_QUALITY = 94


class ImagePreprocessError(RuntimeError):
    """Raised when the backend cannot read or normalize an image."""


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


def normalize_output_format(value: str | None) -> str:
    """Map frontend output format values to supported serializers."""
    cleaned = (value or "png").strip().lower()
    if cleaned in {"jpg", "jpeg"}:
        return "jpg"
    return "png"


def _has_meaningful_alpha(image: Image.Image) -> bool:
    if image.mode != "RGBA":
        return False
    alpha = image.getchannel("A")
    return alpha.getextrema() != (255, 255)
