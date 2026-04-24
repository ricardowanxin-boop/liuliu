"""ZenMux Vertex AI compatible image provider."""

from __future__ import annotations

import io
from dataclasses import dataclass

from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError

from services.provider_base import BaseImageProvider, ImageProviderError
from utils.image_utils import guess_image_mime_type


DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_BASE_URL = "https://zenmux.ai/api/vertex-ai"


@dataclass(slots=True)
class ZenMuxVertexProvider(BaseImageProvider):
    """Adapter for ZenMux image models exposed through Vertex AI protocol."""

    base_url: str
    model: str
    api_key: str
    api_mode: str = "auto"
    timeout: int = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        self.base_url = (self.base_url or DEFAULT_BASE_URL).strip().rstrip("/")
        self.model = self.model.strip()
        self.api_key = self.api_key.strip()
        self.api_mode = (self.api_mode or "auto").strip().lower()

        if not self.base_url:
            raise ImageProviderError("ZenMux Base URL 不能为空。")
        if not self.model:
            raise ImageProviderError("ZenMux 模型名称不能为空。")
        if not self.api_key:
            raise ImageProviderError("ZenMux API Key 不能为空。")
        if self.api_mode not in {"auto", "imagen", "gemini"}:
            raise ImageProviderError("ZenMux API 模式只能是 auto、imagen 或 gemini。")

        self._client = genai.Client(
            api_key=self.api_key,
            vertexai=True,
            http_options=types.HttpOptions(api_version="v1", base_url=self.base_url),
        )

    def edit_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        filename: str | None = None,
    ) -> Image.Image:
        """Edit one uploaded image using ZenMux's Vertex AI image endpoint."""
        if not image_bytes:
            raise ImageProviderError("上传图片内容为空。")

        prompt_text = prompt.strip()
        if not prompt_text:
            raise ImageProviderError("图像编辑提示词不能为空。")

        if self._resolved_api_mode() == "gemini":
            return self._edit_image_with_gemini(
                image_bytes=image_bytes,
                prompt=prompt_text,
                filename=filename,
            )

        return self._edit_image_with_imagen(
            image_bytes=image_bytes,
            prompt=prompt_text,
            filename=filename,
        )

    def _edit_image_with_imagen(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        filename: str | None,
    ) -> Image.Image:
        """Use Vertex `edit_image` for ZenMux models whose suitable API is imagen."""
        reference = types.RawReferenceImage(
            reference_id=1,
            reference_image=types.Image(
                image_bytes=image_bytes,
                mime_type=self._guess_mime_type(filename or "image.png", image_bytes),
            ),
        )

        try:
            response = self._client.models.edit_image(
                model=self.model,
                prompt=prompt,
                reference_images=[reference],
                config=types.EditImageConfig(
                    number_of_images=1,
                    output_mime_type="image/png",
                    add_watermark=False,
                ),
            )
        except Exception as exc:
            raise ImageProviderError(f"ZenMux 图片编辑请求失败：{exc}") from exc

        return self._extract_imagen_response_image(response)

    def _edit_image_with_gemini(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        filename: str | None,
    ) -> Image.Image:
        """Use Vertex `generate_content` for Gemini image models."""
        image_part = types.Part(
            inline_data=types.Blob(
                data=image_bytes,
                mime_type=self._guess_mime_type(filename or "image.png", image_bytes),
            )
        )
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part(text=prompt),
                    image_part,
                ],
            )
        ]

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
        except Exception as exc:
            raise ImageProviderError(f"ZenMux Gemini 图片请求失败：{exc}") from exc

        return self._extract_gemini_response_image(response)

    def _extract_imagen_response_image(self, response: object) -> Image.Image:
        generated_images = getattr(response, "generated_images", None)
        if not generated_images:
            raise ImageProviderError("ZenMux 服务返回成功，但未包含图像结果。")

        first_image = getattr(generated_images[0], "image", None)
        raw_bytes = getattr(first_image, "image_bytes", None)
        if not raw_bytes:
            raise ImageProviderError("ZenMux 服务返回的图像结果为空。")

        return self._load_image_from_bytes(raw_bytes)

    def _extract_gemini_response_image(self, response: object) -> Image.Image:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            image = self._extract_image_from_parts(parts)
            if image is not None:
                return image

        parts = getattr(response, "parts", None) or []
        image = self._extract_image_from_parts(parts)
        if image is not None:
            return image

        raise ImageProviderError("ZenMux Gemini 服务返回成功，但未包含图片结果。")

    def _extract_image_from_parts(self, parts: list[object]) -> Image.Image | None:
        for part in parts:
            inline_data = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
            if inline_data is None:
                continue
            mime_type = (
                getattr(inline_data, "mime_type", None)
                or getattr(inline_data, "mimeType", None)
                or ""
            )
            raw_bytes = getattr(inline_data, "data", None)
            if raw_bytes and str(mime_type).startswith("image/"):
                return self._load_image_from_bytes(raw_bytes)
        return None

    def _resolved_api_mode(self) -> str:
        if self.api_mode in {"imagen", "gemini"}:
            return self.api_mode
        if self.model.startswith("google/gemini") or self.model.startswith("inclusionai/"):
            return "gemini"
        return "imagen"

    def _load_image_from_bytes(self, raw_bytes: bytes) -> Image.Image:
        try:
            image = Image.open(io.BytesIO(raw_bytes))
            image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise ImageProviderError("ZenMux 返回的结果不是有效的图片文件。") from exc

        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA")
        else:
            image = image.copy()
        return image

    def _guess_mime_type(self, filename: str, image_bytes: bytes) -> str:
        return guess_image_mime_type(filename, image_bytes)
