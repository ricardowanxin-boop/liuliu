"""ZenMux implementation for AI style-template extraction."""

from __future__ import annotations

from dataclasses import dataclass

from google import genai
from google.genai import types

from services.style_analyzer_base import BaseStyleAnalyzer, StyleAnalyzerError
from utils.image_utils import guess_image_mime_type


DEFAULT_STYLE_ANALYZER_MODEL = "google/gemini-2.5-pro"
STYLE_ANALYZER_FALLBACK_MODELS = ["google/gemini-2.5-pro"]
DEFAULT_STYLE_ANALYSIS_INSTRUCTION = """
你是一名资深电商视觉风格总监。请分析用户提供的一组品牌/电商风格参考图，
总结成一段可以直接用于图像生成模型的“风格模板提示词”。

请重点提取：
1. 色调与色温
2. 光线方向、光线软硬、阴影质感
3. 背景材质、背景干净程度
4. 构图、主体比例、镜头视角
5. 真实摄影感、商业电商感、质感关键词
6. 明确需要避免的画面问题

输出要求：
- 用中文输出
- 不要解释分析过程
- 不要编号太长
- 输出 1 段 300-600 字的可复用提示词
- 适合拼接到“新商品图生成/编辑”的提示词前面
""".strip()


@dataclass(slots=True)
class ZenMuxStyleAnalyzer(BaseStyleAnalyzer):
    """Analyze style reference images through ZenMux's Vertex AI endpoint."""

    base_url: str
    api_key: str
    model: str = DEFAULT_STYLE_ANALYZER_MODEL

    def __post_init__(self) -> None:
        self.base_url = self.base_url.strip().rstrip("/")
        self.api_key = self.api_key.strip()
        self.model = self._normalize_model(self.model)

        if not self.base_url:
            raise StyleAnalyzerError("ZenMux Base URL 不能为空。")
        if not self.api_key:
            raise StyleAnalyzerError("ZenMux API Key 不能为空。")
        if not self.model:
            raise StyleAnalyzerError("ZenMux 风格分析模型不能为空。")

        self._client = genai.Client(
            api_key=self.api_key,
            vertexai=True,
            http_options=types.HttpOptions(api_version="v1", base_url=self.base_url),
        )

    def analyze_images(
        self,
        *,
        images: list[tuple[str, bytes]],
        instruction: str = DEFAULT_STYLE_ANALYSIS_INSTRUCTION,
    ) -> str:
        """Summarize local style images into one reusable generation prompt."""
        if not images:
            raise StyleAnalyzerError("没有可分析的风格样图。")

        contents: list[object] = [
            "下面是一组电商/品牌风格参考图。请综合分析所有图片，而不是逐张罗列。",
        ]
        valid_image_count = 0
        for index, (filename, image_bytes) in enumerate(images, start=1):
            if not image_bytes:
                continue
            valid_image_count += 1
            contents.append(f"参考图 {index}：{filename}")
            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=guess_image_mime_type(filename, image_bytes),
                )
            )

        if valid_image_count == 0:
            raise StyleAnalyzerError("风格样图内容为空，无法分析。")

        contents.append((instruction or DEFAULT_STYLE_ANALYSIS_INSTRUCTION).strip())

        errors: list[str] = []
        for model in self._candidate_models():
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="text/plain",
                        temperature=0.2,
                    ),
                )
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                continue

            text = self._extract_text_response(response)
            if text:
                return text
            errors.append(f"{model}: 返回为空")

        raise StyleAnalyzerError("ZenMux 风格分析请求失败：" + "；".join(errors))

    def _candidate_models(self) -> list[str]:
        """Try the configured model first, then known vision-text fallbacks."""
        models = [self.model, *STYLE_ANALYZER_FALLBACK_MODELS]
        return list(dict.fromkeys(models))

    def _normalize_model(self, model: str) -> str:
        """Avoid routing image-to-text analysis to image-generation-only models."""
        cleaned = (model or "").strip()
        if not cleaned:
            return DEFAULT_STYLE_ANALYZER_MODEL
        if cleaned.endswith("-image") or cleaned.endswith("-image-preview"):
            return DEFAULT_STYLE_ANALYZER_MODEL
        return cleaned

    def _extract_text_response(self, response: object) -> str:
        """Read text from both high-level and candidate response shapes."""
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        chunks: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    chunks.append(part_text.strip())
        return "\n".join(chunks).strip()
