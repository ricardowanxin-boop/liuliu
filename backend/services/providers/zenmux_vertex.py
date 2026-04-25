"""ZenMux Vertex AI compatible image provider."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any

import requests
from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError

from backend.services.image_preprocess import guess_image_mime_type
from backend.services.providers.provider_base import BaseImageProvider, ImageProviderError


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
                mime_type=guess_image_mime_type(filename or "image.png", image_bytes),
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
                mime_type=guess_image_mime_type(filename or "image.png", image_bytes),
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

        empty_reasons: list[str] = []
        for item in generated_images:
            filtered_reason = getattr(item, "rai_filtered_reason", None)
            if filtered_reason:
                empty_reasons.append(f"过滤原因：{filtered_reason}")

            image = getattr(item, "image", None)
            if image is None:
                continue

            raw_bytes = self._coerce_image_bytes(getattr(image, "image_bytes", None))
            if raw_bytes:
                return self._load_image_from_bytes(raw_bytes)

            gcs_uri = str(getattr(image, "gcs_uri", "") or "").strip()
            if gcs_uri:
                if gcs_uri.startswith(("http://", "https://")):
                    return self._download_image(gcs_uri)
                empty_reasons.append(f"服务返回了不可直接下载的图片 URI：{gcs_uri}")

            safety_reason = self._summarize_safety_attributes(
                getattr(item, "safety_attributes", None)
            )
            if safety_reason:
                empty_reasons.append(safety_reason)

        detail = "；".join(dict.fromkeys(empty_reasons))
        if detail:
            raise ImageProviderError(f"ZenMux 服务返回的图像结果为空：{detail}。")
        raise ImageProviderError("ZenMux 服务返回的图像结果为空，建议重试或切换模型。")

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
            normalized_bytes = self._coerce_image_bytes(raw_bytes)
            if normalized_bytes and str(mime_type).startswith("image/"):
                return self._load_image_from_bytes(normalized_bytes)
        return None

    def _resolved_api_mode(self) -> str:
        if self.api_mode in {"imagen", "gemini"}:
            return self.api_mode
        if self.model.startswith("google/gemini") or self.model.startswith("inclusionai/"):
            return "gemini"
        return "imagen"

    def _coerce_image_bytes(self, raw_value: object) -> bytes:
        if isinstance(raw_value, bytes):
            return raw_value
        if isinstance(raw_value, bytearray):
            return bytes(raw_value)
        if isinstance(raw_value, str):
            encoded = raw_value.strip()
            if not encoded:
                return b""
            if encoded.startswith("data:") and "," in encoded:
                encoded = encoded.split(",", 1)[1].strip()
            try:
                return base64.b64decode(encoded, validate=False)
            except (ValueError, TypeError) as exc:
                raise ImageProviderError("ZenMux 返回的 base64 图片数据无效。") from exc
        return b""

    def _download_image(self, image_url: str) -> Image.Image:
        try:
            response = requests.get(image_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.Timeout as exc:
            raise ImageProviderError("下载 ZenMux 生成图片超时，请稍后重试。") from exc
        except requests.RequestException as exc:
            raise ImageProviderError(f"下载 ZenMux 生成图片失败：{exc}") from exc

        return self._load_image_from_bytes(response.content)

    def _summarize_safety_attributes(self, safety_attributes: object) -> str:
        if safety_attributes is None:
            return ""

        payload: dict[str, Any]
        if hasattr(safety_attributes, "model_dump"):
            payload = safety_attributes.model_dump(exclude_none=True)
        elif isinstance(safety_attributes, dict):
            payload = safety_attributes
        else:
            return ""

        blocked = payload.get("blocked")
        categories = payload.get("categories") or payload.get("safety_categories")
        scores = payload.get("scores") or payload.get("safety_scores")
        parts = []
        if blocked is not None:
            parts.append(f"blocked={blocked}")
        if categories:
            parts.append(f"categories={categories}")
        if scores:
            parts.append(f"scores={scores}")
        if not parts:
            return ""
        return "安全属性：" + "，".join(str(part) for part in parts)

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
