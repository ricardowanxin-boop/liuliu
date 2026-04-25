"""Prompt assembly for ecommerce image generation."""

from __future__ import annotations


REALISTIC_ECOMMERCE_TEMPLATE = """
真实电商审美模式：
- 使用真实自然光，暖色调，柔和但有方向性的光线，保留自然阴影和接触阴影。
- 生活化陈列，构图自然，不要过度对称，不要商业棚拍感，不要冷白无菌背景。
- 材质要有真实纹理、细节层次和轻微使用痕迹，避免塑料感、过度磨皮、高饱和、AI 广告图质感。
- 画面像真实电商卖家拍摄、社媒分享或生活方式产品摄影，干净、可信、可直接用于商品展示。
""".strip()

HIGH_QUALITY_TEMPLATE = """
增强细节：保留商品主体结构和关键识别特征，边缘自然清晰，背景干净但不虚假，色彩准确不过饱和。
""".strip()


def compile_generation_prompt(
    *,
    prompt: str,
    realistic_mode: bool = False,
    style_template: str | None = None,
    quality: str | None = None,
) -> str:
    """Compose the user prompt, optional style guide, and ecommerce realism rules."""
    parts: list[str] = []

    user_prompt = (prompt or "").strip()
    if user_prompt:
        parts.append(user_prompt)

    style = (style_template or "").strip()
    if style:
        parts.append(f"参考风格要求：\n{style}")

    if realistic_mode:
        parts.append(REALISTIC_ECOMMERCE_TEMPLATE)

    if (quality or "").strip().lower() in {"high", "hd", "高", "高质量"}:
        parts.append(HIGH_QUALITY_TEMPLATE)

    compiled = "\n\n".join(parts).strip()
    if not compiled:
        raise ValueError("提示词不能为空。")
    return compiled
