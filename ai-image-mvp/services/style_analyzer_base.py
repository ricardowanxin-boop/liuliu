"""Shared abstractions for AI-powered style analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod


class StyleAnalyzerError(RuntimeError):
    """Raised when a style analyzer cannot produce a reusable prompt."""


class BaseStyleAnalyzer(ABC):
    """Abstract contract for providers that summarize reference images."""

    @abstractmethod
    def analyze_images(
        self,
        *,
        images: list[tuple[str, bytes]],
        instruction: str,
    ) -> str:
        """
        Analyze reference images and return a reusable style prompt.

        Args:
            images: A list of ``(filename, image_bytes)`` tuples.
            instruction: The analysis brief sent to the AI model.
        """
        raise NotImplementedError
