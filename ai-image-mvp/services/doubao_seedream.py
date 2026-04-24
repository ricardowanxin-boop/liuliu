"""Volcengine Ark Doubao Seedream image generation provider."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import requests
from PIL import Image, UnidentifiedImageError

from services.provider_base import BaseImageProvider, ImageProviderError
from utils.image_utils import guess_image_mime_type


DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_SIZE = "2048x2048"


@dataclass(slots=True)
class DoubaoSeedreamProvider(BaseImageProvider):
    """Adapter for Volcengine Ark Seedream image generation APIs."""

    base_url: str
    model: str
    api_key: str
    size: str = DEFAULT_SIZE
    response_format: str = "b64_json"
    watermark: bool = False
    extra_payload: dict[str, Any] = field(default_factory=dict)
    timeout: int = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        sanitized_base_url = self.base_url.strip().rstrip("/")
        self.model = self.model.strip()
        self.api_key = self.api_key.strip()
        self.size = self.size.strip() or DEFAULT_SIZE
        self.response_format = self.response_format.strip() or "b64_json"

        if not sanitized_base_url:
            raise ImageProviderError("Doubao Base URL 不能为空。")
        if not self.model:
            raise ImageProviderError("Doubao 模型名称不能为空。")
        if not self.api_key:
            raise ImageProviderError("Doubao API Key 不能为空。")

        self.base_url = sanitized_base_url + "/"

    def edit_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        filename: str | None = None,
    ) -> Image.Image:
        """
        Generate or edit one image using Doubao Seedream.

        The API accepts a prompt and an optional reference image encoded as a
        data URL. For this MVP we always pass the uploaded image as a single
        reference image, so the behavior aligns with the existing image-to-image
        workflow in the app.
        """
        if not image_bytes:
            raise ImageProviderError("上传图片内容为空。")

        prompt_text = prompt.strip()
        if not prompt_text:
            raise ImageProviderError("图像编辑提示词不能为空。")

        endpoint = urljoin(self.base_url, "images/generations")
        payload = {
            "model": self.model,
            "prompt": prompt_text,
            "size": self.size,
            "response_format": self.response_format,
            "watermark": self.watermark,
            "image": self._to_data_url(image_bytes, filename),
        }
        payload.update(
            {
                key: value
                for key, value in self.extra_payload.items()
                if value is not None
            }
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise ImageProviderError("调用 Doubao Seedream 接口超时，请稍后重试。") from exc
        except requests.RequestException as exc:
            raise ImageProviderError(f"调用 Doubao Seedream 接口失败：{exc}") from exc

        if response.status_code >= 400:
            raise ImageProviderError(self._build_http_error(response))

        try:
            payload = response.json()
        except ValueError as exc:
            raise ImageProviderError("Doubao 服务返回了无法解析的 JSON 响应。") from exc

        return self._extract_image_from_payload(payload)

    def _to_data_url(self, image_bytes: bytes, filename: str | None) -> str:
        mime_type = self._guess_mime_type(filename or "image.png", image_bytes)
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _extract_image_from_payload(self, payload: dict[str, Any]) -> Image.Image:
        container = payload
        if isinstance(payload.get("data"), dict):
            container = payload["data"]
        elif isinstance(payload.get("data"), list):
            container = payload

        request_error = container.get("error")
        if isinstance(request_error, dict):
            message = request_error.get("message") or request_error.get("code") or "未知错误"
            raise ImageProviderError(f"Doubao 请求失败：{message}")

        items = container.get("data")
        if not isinstance(items, list) or not items:
            raise ImageProviderError("Doubao 服务返回成功，但未包含图像结果。")

        first_item = items[0]
        if not isinstance(first_item, dict):
            raise ImageProviderError("Doubao 服务返回的图像结果格式不正确。")

        item_error = first_item.get("error")
        if isinstance(item_error, dict):
            message = item_error.get("message") or item_error.get("code") or "未知错误"
            raise ImageProviderError(f"Doubao 图片生成失败：{message}")

        b64_data = first_item.get("b64_json")
        if isinstance(b64_data, str) and b64_data.strip():
            return self._load_image_from_bytes(self._decode_base64_image(b64_data))

        image_url = first_item.get("url")
        if isinstance(image_url, str) and image_url.strip():
            return self._download_image(image_url.strip())

        raise ImageProviderError("Doubao 服务未返回 `b64_json` 或 `url` 格式的图片结果。")

    def _download_image(self, image_url: str) -> Image.Image:
        try:
            response = requests.get(image_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.Timeout as exc:
            raise ImageProviderError("下载 Doubao 生成图片超时，请稍后重试。") from exc
        except requests.RequestException as exc:
            raise ImageProviderError(f"下载 Doubao 生成图片失败：{exc}") from exc

        return self._load_image_from_bytes(response.content)

    def _load_image_from_bytes(self, raw_bytes: bytes) -> Image.Image:
        try:
            image = Image.open(io.BytesIO(raw_bytes))
            image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise ImageProviderError("Doubao 返回的结果不是有效的图片文件。") from exc

        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA")
        else:
            image = image.copy()
        return image

    def _decode_base64_image(self, encoded: str) -> bytes:
        try:
            return base64.b64decode(encoded)
        except (ValueError, TypeError) as exc:
            raise ImageProviderError("Doubao 返回的 base64 图片数据无效。") from exc

    def _build_http_error(self, response: requests.Response) -> str:
        status_text = f"Doubao 图像请求失败（HTTP {response.status_code}）"
        try:
            payload = response.json()
        except ValueError:
            body = response.text.strip()
            return f"{status_text}：{body or '未知错误'}"

        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or "未知错误"
            return f"{status_text}：{message}"

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return f"{status_text}：{message.strip()}"

        code = payload.get("code")
        if code:
            return f"{status_text}：{code}"

        return status_text

    def _guess_mime_type(self, filename: str, image_bytes: bytes) -> str:
        return guess_image_mime_type(filename, image_bytes)
