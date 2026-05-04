"""Prompt assembly for ecommerce image generation."""

from __future__ import annotations


REALISTIC_ECOMMERCE_TEMPLATE = """
真实电商审美模式：
- 使用真实自然光，暖色调，柔和但有方向性的光线，保留自然阴影和接触阴影。
- 生活化陈列，构图自然，不要过度对称，不要商业棚拍感，不要冷白无菌背景。
- 材质要有真实纹理、细节层次和轻微使用痕迹，避免塑料感、过度磨皮、高饱和、AI 广告图质感。
- 画面像真实电商卖家拍摄、社媒分享或生活方式产品摄影，干净、可信、可直接用于商品展示。
""".strip()

ANTI_AI_STUDIO_TEMPLATE = """
反 AI 棚拍编译规则：
- 默认拒绝 AI 棚拍审美：不要冷白棚拍、不要无影高亮、不要玻璃质感假背景、不要过度对称陈列。
- 优先真实电商场景：手机实拍、卖家秀、朋友圈分享、轻微生活痕迹、自然桌面或软装背景。
- 光线必须可信：有方向性的自然光、真实阴影、接触阴影、局部明暗变化，避免全画面均匀平光。
- 商品必须保持可售卖：主体结构、颜色、材质、佩戴方式和关键识别点要稳定，不要夸张重绘。
- 画面不出现 AI 生成感：不增加虚假品牌字样、乱码文字、漂浮饰品、塑料皮肤、过度锐化或过度磨皮。
""".strip()

REAL_PHOTO_FIDELITY_TEMPLATE = """
真实修图保真规则：
- 这是轻度真实修图，不是整体重绘；尽量继承原图构图、商品位置、手部姿态、透明托盘形状和现场光源方向。
- 不要把真实照片里的细微噪点、桌面纹理、布料纤维、皮肤纹理、甲面小反光当作瑕疵抹掉。
- 禁止全局磨皮、全局降噪、背景涂抹、桌面纯色化、边缘过度柔化；保留局部不完美和自然过渡。
- 商品优先增强：珠子更通透且保留内部颗粒，金属件更亮更清晰，珍珠更干净，主体边缘更锐利。
- 背景只能轻度整理，不能比商品更抢眼；桌面必须有真实纹理、反光渐变和微小噪点。
- 透明亚克力托盘必须保留厚度、折射、边缘高光、暗边、穿透感和接触阴影，不能变成扁平塑料片。
- 即使更换背景，也保持手机近距离实拍视角、真实透视、自然景深和轻微现场瑕疵，不要生成样板间式干净场景。
- 手部和指甲可以按要求统一风格，但必须保留真实手型、皮肤纹理、关节阴影、甲面真实反光，不要生成塑料皮肤或过长假甲。
- 首要目标是“商品更可卖”，不是“画面更干净”：链条、吊坠、珠子、金属镶边、珍珠和主体轮廓清晰度必须优先于背景美化。
- 商品主体在画面中的面积、清晰度和视觉权重不能变小；不要让花、杯子、托盘、桌面纹理或背景装饰抢过商品。
- 吊坠、链条和镶边钻位必须比原图更清楚：金属边缘有细小高光，链节独立可辨，宝石/珍珠有层次，不要变成一团亮片。
- 原图里的项链/吊坠/珠宝是交付主体，不允许更换为新的商品，不允许改变吊坠位置、链条走向、挂坠比例、金属镶边和宝石轮廓。
- 允许优化背景和桌面，但只允许做局部、轻量、真实照片级修饰；不要因为换背景而重画手、商品、袖口和首饰结构。
""".strip()

NAIL_ANATOMY_TEMPLATE = """
手部与美甲方向约束：
- 先判断手掌朝向：如果原图是手心朝上，必须保留手心朝上的姿态，不要把手背/手心逻辑画反。
- 人体结构常识：手心朝上时，掌纹和指腹面向镜头，指甲盖外侧属于手背侧；贴钻只能在手背侧的指甲盖外表面。
- 美甲贴钻只能贴在指甲盖外侧，也就是手背侧的甲面上；绝对不要把钻、亮片或装饰贴到指甲内侧、掌心侧、指腹侧、甲下或指甲背面。
- 手心朝上时，镜头通常看到的是指甲尖和部分侧边，透明甲面可以有边缘高光和折射，但贴钻不能像长在内侧一样朝向手心。
- 每根手指的透明带钻甲样式要一致，但钻的位置必须跟随真实甲面弧度和透视，贴在外甲面，不要漂浮、穿帮或反向贴钻。
- 如果因为手心朝上导致外侧甲面不可见或只露出边缘，宁可让贴钻可见度降低，也不要把钻移动到掌心侧来“展示”。
- 保持原图手势和手指朝向，不要为了展示美甲而翻转手掌、旋转手指、改变关节结构或生成不符合人体结构的指甲。
- 这张图如果是掌心面向镜头，不要把美甲改造成手背朝上视角；不要新增弯曲手指、握拳姿态或把手掌重构成另一张手部照片。
- 掌心侧是禁区：掌纹、指腹、手掌肉面和甲片内侧不能出现水钻、亮片、星点或金属装饰；这些装饰只能在真实可见的外甲面边缘少量出现。
- 美甲需求服从人体结构：当透明甲外表面不可见时，保持透明甲和自然高光即可，不要为了“展示钻”牺牲手心朝上的真实姿态。
""".strip()

SUBJECT_LOCK_TEMPLATE = """
商品主体锁定规则：
- 项链、吊坠、链条、金属镶边、珍珠/宝石、手部持物关系必须保留原图结构；不得重绘成另一件饰品。
- 去水印和换背景不能损伤商品边缘；商品区域应比背景更清楚，链节、镶边小钻和吊坠轮廓要可辨。
- 只在不破坏商品的前提下提升质感：增强金属高光、宝石通透度和吊坠清晰度，避免把主体磨成柔焦或糊成亮片团。
""".strip()

NAIL_ANATOMY_KEYWORDS = (
    "指甲",
    "美甲",
    "贴钻",
    "钻甲",
    "透明甲",
    "甲面",
    "甲片",
    "亮片",
    "水钻",
    "nail",
    "manicure",
)

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
        parts.append(ANTI_AI_STUDIO_TEMPLATE)
        parts.append(REAL_PHOTO_FIDELITY_TEMPLATE)
        parts.append(SUBJECT_LOCK_TEMPLATE)
        if _needs_nail_anatomy_lock(user_prompt, style):
            parts.append(NAIL_ANATOMY_TEMPLATE)
        parts.append(REALISTIC_ECOMMERCE_TEMPLATE)
    elif _needs_nail_anatomy_lock(user_prompt, style):
        parts.append(NAIL_ANATOMY_TEMPLATE)

    if (quality or "").strip().lower() in {"high", "hd", "高", "高质量"}:
        parts.append(HIGH_QUALITY_TEMPLATE)

    compiled = "\n\n".join(parts).strip()
    if not compiled:
        raise ValueError("提示词不能为空。")
    return compiled


def _needs_nail_anatomy_lock(*texts: str) -> bool:
    """Enable hand/nail structural constraints when the request touches manicure details."""
    combined = " ".join(text.lower() for text in texts if text)
    return any(keyword.lower() in combined for keyword in NAIL_ANATOMY_KEYWORDS)
