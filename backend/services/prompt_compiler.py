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

WATERMARK_REMOVAL_TEMPLATE = """
水印处理要求：
- 去除原图或生成图中可见的平台水印、文字水印、Logo 标识、AI生成字样、夸克字样和 watermark 字样。
- 不要在最终图片中新增任何品牌水印、角标、字幕、签名或文字覆盖层。
- 去除水印时尽量保留商品主体、手部姿势、构图、材质和真实光影。
""".strip()


def compile_generation_prompt(
    *,
    prompt: str,
    realistic_mode: bool = False,
    style_template: str | None = None,
    quality: str | None = None,
    watermark_cleanup_enabled: bool = False,
    watermark_keywords: list[str] | None = None,
) -> str:
    """Compose the user prompt, optional style guide, and ecommerce realism rules."""
    parts: list[str] = []

    user_prompt = (prompt or "").strip()
    if user_prompt:
        parts.append(user_prompt)

    style = (style_template or "").strip()
    if style:
        parts.append(f"参考风格要求：\n{style}")

    if watermark_cleanup_enabled:
        keyword_text = "、".join(watermark_keywords or [])
        if keyword_text:
            parts.append(f"{WATERMARK_REMOVAL_TEMPLATE}\n重点关注这些水印关键词：{keyword_text}。")
        else:
            parts.append(WATERMARK_REMOVAL_TEMPLATE)

    if realistic_mode:
        parts.append(REALISTIC_ECOMMERCE_TEMPLATE)

    if (quality or "").strip().lower() in {"high", "hd", "高", "高质量"}:
        parts.append(HIGH_QUALITY_TEMPLATE)

    compiled = "\n\n".join(parts).strip()
    if not compiled:
        raise ValueError("提示词不能为空。")
    return compiled
