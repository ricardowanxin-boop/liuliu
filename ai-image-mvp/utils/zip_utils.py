"""ZIP helpers for batch download exports."""

from __future__ import annotations

import io
import zipfile
from typing import Iterable

from utils.image_utils import sanitize_filename


def build_results_zip(items: Iterable[tuple[str, bytes]]) -> bytes:
    """Create an in-memory ZIP archive for generated PNG files."""
    buffer = io.BytesIO()
    used_names: dict[str, int] = {}

    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, file_bytes in items:
            if not file_bytes:
                continue

            safe_name = sanitize_filename(filename.rsplit(".", 1)[0]) + ".png"
            final_name = _deduplicate_filename(safe_name, used_names)
            archive.writestr(final_name, file_bytes)

    buffer.seek(0)
    return buffer.getvalue()


def _deduplicate_filename(filename: str, used_names: dict[str, int]) -> str:
    """Avoid collisions when multiple results sanitize to the same filename."""
    counter = used_names.get(filename, 0)
    used_names[filename] = counter + 1

    if counter == 0:
        return filename

    stem, ext = filename.rsplit(".", 1)
    return f"{stem}-{counter + 1}.{ext}"
