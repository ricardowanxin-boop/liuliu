"""Shared provider abstractions for image editing services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from PIL import Image


class ImageProviderError(RuntimeError):
    """Raised when a provider cannot complete an image editing request."""


@dataclass(slots=True)
class ProviderImageResult:
    """Structured result for callers that need metadata alongside the image."""

    image: Image.Image
    revised_prompt: str | None = None
    raw_response: dict[str, Any] | None = None


class BaseImageProvider(ABC):
    """Abstract contract implemented by all image editing providers."""

    @abstractmethod
    def edit_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        filename: str | None = None,
    ) -> Image.Image:
        """
        Edit a single image and return the generated result as a PIL image.

        Args:
            image_bytes: Source image payload for one uploaded file.
            prompt: The edit instruction sent to the provider.
            filename: Optional original filename used when sending multipart data.
        """
        raise NotImplementedError
