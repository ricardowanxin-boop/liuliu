"""Local style reference helpers for brand-style prompt reuse."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from PIL import Image, ImageStat, UnidentifiedImageError

from utils.image_utils import guess_image_mime_type, prepare_input_image_bytes


STYLE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_STYLE_REFERENCES = 20
STYLE_TEMPLATE_CACHE_NAME = ".style-template-cache.txt"


class StyleUtilsError(RuntimeError):
    """Raised when local style references cannot be read."""


@dataclass(slots=True)
class StyleReferenceImage:
    """Normalized local style image payload."""

    path: Path
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    average_rgb: tuple[int, int, int]


def ensure_style_reference_dir(directory: Path) -> None:
    """Create the local style-reference folder if it does not exist."""
    directory.mkdir(parents=True, exist_ok=True)


def count_style_reference_paths(directory: Path) -> int:
    """Count supported local style images without loading image bytes."""
    if not directory.exists():
        return 0

    paths = [
        item
        for item in directory.rglob("*")
        if item.is_file() and item.suffix.lower() in STYLE_IMAGE_EXTENSIONS
    ]
    return len(paths)


def list_style_reference_paths(directory: Path, limit: int = MAX_STYLE_REFERENCES) -> list[Path]:
    """List local style images in a stable, evenly sampled order."""
    if limit <= 0 or not directory.exists():
        return []

    paths = sorted(
        [
            item
            for item in directory.rglob("*")
            if item.is_file() and item.suffix.lower() in STYLE_IMAGE_EXTENSIONS
        ],
        key=lambda item: str(item.relative_to(directory)).lower(),
    )
    if len(paths) <= limit:
        return paths

    # Large client libraries should not send hundreds of images to the AI model.
    # Even sampling gives the analyzer a broader style view than just the first N files.
    if limit == 1:
        return [paths[0]]

    step = (len(paths) - 1) / (limit - 1)
    selected_indexes: list[int] = []
    for index in range(limit):
        selected_index = round(index * step)
        if selected_indexes and selected_index <= selected_indexes[-1]:
            selected_index = selected_indexes[-1] + 1
        selected_indexes.append(min(selected_index, len(paths) - 1))

    return [paths[index] for index in selected_indexes]


def load_style_references(directory: Path, limit: int = MAX_STYLE_REFERENCES) -> list[StyleReferenceImage]:
    """Load and normalize local style references for analysis."""
    references: list[StyleReferenceImage] = []
    for path in list_style_reference_paths(directory, limit=limit):
        try:
            original_bytes = path.read_bytes()
            normalized_bytes = prepare_input_image_bytes(original_bytes)
            with Image.open(path) as image:
                image.load()
                rgb_image = image.convert("RGB")
                stat = ImageStat.Stat(rgb_image.resize((1, 1)))
                average_rgb = tuple(int(value) for value in stat.mean[:3])
                width, height = image.size
        except (OSError, UnidentifiedImageError) as exc:
            raise StyleUtilsError(f"无法读取风格样图 {path.name}：{exc}") from exc

        references.append(
            StyleReferenceImage(
                path=path,
                image_bytes=normalized_bytes,
                mime_type=guess_image_mime_type(path.name, normalized_bytes),
                width=width,
                height=height,
                average_rgb=average_rgb,
            )
        )
    return references


def read_style_template_cache(directory: Path) -> str:
    """Read the latest locally cached style template if it exists."""
    cache_path = directory / STYLE_TEMPLATE_CACHE_NAME
    if not cache_path.exists():
        return ""

    try:
        return cache_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise StyleUtilsError(f"无法读取风格模板缓存：{exc}") from exc


def write_style_template_cache(directory: Path, template: str) -> None:
    """Persist a generated style template so refreshes do not require a new AI call."""
    ensure_style_reference_dir(directory)
    cache_path = directory / STYLE_TEMPLATE_CACHE_NAME
    try:
        cache_path.write_text(template.strip(), encoding="utf-8")
    except OSError as exc:
        raise StyleUtilsError(f"无法写入风格模板缓存：{exc}") from exc


def build_heuristic_style_prompt(references: list[StyleReferenceImage]) -> str:
    """Create a free local fallback style prompt from simple image statistics."""
    if not references:
        return ""

    avg_r = int(mean(item.average_rgb[0] for item in references))
    avg_g = int(mean(item.average_rgb[1] for item in references))
    avg_b = int(mean(item.average_rgb[2] for item in references))
    portrait_count = sum(1 for item in references if item.height > item.width)
    landscape_count = sum(1 for item in references if item.width > item.height)
    square_count = len(references) - portrait_count - landscape_count

    orientation = max(
        [
            ("竖版构图", portrait_count),
            ("横版构图", landscape_count),
            ("方形构图", square_count),
        ],
        key=lambda item: item[1],
    )[0]
    warmth = "暖色调" if avg_r >= avg_b + 8 else "冷色调" if avg_b >= avg_r + 8 else "中性色调"
    brightness = (avg_r + avg_g + avg_b) / 3
    lightness = "明亮通透" if brightness >= 180 else "低调柔和" if brightness <= 105 else "自然均衡"

    return (
        "品牌视觉风格参考："
        f"整体保持{warmth}、{lightness}的电商摄影质感；"
        f"平均主色约为 RGB({avg_r}, {avg_g}, {avg_b})；"
        f"构图优先参考{orientation}；"
        "画面应保持真实摄影感、干净背景、柔和自然阴影、主体清晰、材质细节清楚；"
        "避免过度卡通化、过强锐化、脏乱背景、夸张滤镜和不真实反光。"
    )


def compose_prompt(user_prompt: str, style_template: str, *, enabled: bool = True) -> str:
    """Merge the user prompt with the current style template."""
    clean_user_prompt = user_prompt.strip()
    clean_style = style_template.strip()
    if not enabled or not clean_style:
        return clean_user_prompt
    return (
        f"{clean_style}\n\n"
        "本次图片任务：\n"
        f"{clean_user_prompt}\n\n"
        "请优先保证商品主体真实、可商用、构图清晰，并严格沿用上述品牌视觉风格。"
    )
