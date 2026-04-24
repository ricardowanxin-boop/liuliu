import hashlib
import os
from pathlib import Path
from typing import Any

import streamlit as st

from services.doubao_seedream import DoubaoSeedreamProvider
from services.openai_compatible import OpenAICompatibleProvider
from services.provider_base import BaseImageProvider, ImageProviderError
from services.style_analyzer_base import StyleAnalyzerError
from services.zenmux_vertex import ZenMuxVertexProvider
from services.zenmux_style_analyzer import (
    DEFAULT_STYLE_ANALYSIS_INSTRUCTION,
    DEFAULT_STYLE_ANALYZER_MODEL,
    ZenMuxStyleAnalyzer,
)
from utils.image_utils import (
    ImageUtilsError,
    build_output_filename,
    build_provider_input_filename,
    prepare_input_image_bytes,
    remove_watermark_if_needed,
    split_keywords,
)
from utils.style_utils import (
    StyleUtilsError,
    build_heuristic_style_prompt,
    compose_prompt,
    count_style_reference_paths,
    ensure_style_reference_dir,
    load_style_references,
    read_style_template_cache,
    write_style_template_cache,
)
from utils.zip_utils import build_results_zip


OPENAI_PROVIDER = "openai_compatible"
DOUBAO_PROVIDER = "doubao_seedream"
ZENMUX_PROVIDER = "zenmux_vertex"

PROVIDER_LABELS = {
    OPENAI_PROVIDER: "OpenAI-compatible / DeepRouter",
    DOUBAO_PROVIDER: "字节 Doubao Seedream / Ark",
    ZENMUX_PROVIDER: "ZenMux / Vertex AI",
}

DEFAULT_OPENAI_BASE_URL = "https://deeprouter.top/v1"
DEFAULT_OPENAI_MODEL = "grok-4-image"
DEFAULT_DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DOUBAO_MODEL = "doubao-seedream-5-0-260128"
DEFAULT_DOUBAO_SIZE = "2K"
DOUBAO_SIZE_OPTIONS = ["2K", "4K"]
DEFAULT_ZENMUX_BASE_URL = "https://zenmux.ai/api/vertex-ai"
DEFAULT_ZENMUX_MODEL = "openai/gpt-image-2"
ZENMUX_IMAGE_MODELS = [
    {"slug": "openai/gpt-image-2", "label": "OpenAI: GPT-Image-2", "api_mode": "imagen", "price_hint": "price_image=0.005"},
    {"slug": "sapiens-ai/agnes-image-1.2", "label": "Sapiens AI: Agnes-Image-1.2", "api_mode": "imagen", "price_hint": "price_image=0.008"},
    {"slug": "qwen/qwen-image-2.0-pro", "label": "Qwen-Image-2.0-Pro", "api_mode": "imagen", "price_hint": "price_image=0.073"},
    {"slug": "qwen/qwen-image-2.0", "label": "Qwen-Image-2.0", "api_mode": "imagen", "price_hint": "price_image=0.0289"},
    {"slug": "bytedance/doubao-seedream-5.0-lite", "label": "ByteDance: Doubao-Seedream-5.0-lite", "api_mode": "imagen", "price_hint": "price_image=0.032"},
    {"slug": "google/gemini-3.1-flash-image-preview", "label": "Google: Nano Banana 2 (Gemini 3.1 Flash Image Preview)", "api_mode": "gemini", "price_hint": "price_image=60"},
    {"slug": "inclusionai/ming-flash-omni-2.0", "label": "inclusionAI: Ming-flash-omni-2.0", "api_mode": "gemini", "price_hint": "price_image=0"},
    {"slug": "openai/gpt-image-1.5", "label": "OpenAI: GPT-Image-1.5", "api_mode": "imagen", "price_hint": "price_image=0.009"},
    {"slug": "google/gemini-3-pro-image-preview", "label": "Google: Nano Banana Pro (Gemini 3 Pro Image Preview)", "api_mode": "gemini", "price_hint": "price_image=120"},
    {"slug": "google/gemini-2.5-flash-image", "label": "Google: Gemini 2.5 Flash Image (Nano Banana)", "api_mode": "gemini", "price_hint": "price_image=0"},
    {"slug": "tencent/hunyuan-image3", "label": "Tencent: Hunyuan Image3", "api_mode": "imagen", "price_hint": "price_image=0.029"},
    {"slug": "klingai/kling-v2", "label": "KlingAI: Kling-v2", "api_mode": "imagen", "price_hint": "price_image=0.014"},
]
ZENMUX_MODEL_OPTIONS = [item["slug"] for item in ZENMUX_IMAGE_MODELS]
ZENMUX_MODEL_CONFIG = {item["slug"]: item for item in ZENMUX_IMAGE_MODELS}
DEFAULT_WATERMARK_KEYWORDS = "AI生成, 夸克, quark, watermark"
DEFAULT_STYLE_REFERENCES_DIR = Path(__file__).resolve().parent / "style-references"
LUMI_STYLE_REFERENCES_DIR = Path(
    "/Users/ricardo/文稿/创业/商业计划/刘刘电商解决方案/电商图片获取/downloads/lumi-products-only"
)
MAX_AI_STYLE_IMAGES = 12


def inject_custom_css() -> None:
    """Apply the Streamlit page polish in one place."""
    st.markdown(
        """
        <style>
        :root {
            --app-bg: #f6f8fb;
            --card-bg: #ffffff;
            --card-border: #dbe4ef;
            --text-main: #172033;
            --text-muted: #65758b;
            --accent: #2563eb;
            --accent-2: #14b8a6;
            --shadow-sm: 0 10px 28px rgba(15, 23, 42, 0.08);
            --shadow-md: 0 18px 44px rgba(15, 23, 42, 0.13);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(37, 99, 235, 0.08), transparent 30rem),
                linear-gradient(180deg, #f8fafc 0%, var(--app-bg) 42%, #eef3f8 100%);
            color: var(--text-main);
        }

        .block-container {
            max-width: 1280px;
            padding-top: 2.2rem;
            padding-bottom: 3rem;
        }

        h1 {
            font-size: 2.3rem !important;
            line-height: 1.15 !important;
            letter-spacing: 0 !important;
            margin-bottom: 0.35rem !important;
        }

        h2, h3 {
            letter-spacing: 0 !important;
            color: var(--text-main);
        }

        p, label, .stMarkdown, .stCaption, [data-testid="stWidgetLabel"] {
            color: var(--text-main);
        }

        [data-testid="stCaptionContainer"] {
            color: var(--text-muted);
            font-size: 0.95rem;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid var(--card-border);
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.92);
            box-shadow: var(--shadow-sm);
            padding: 1.05rem 1.1rem;
        }

        [data-testid="stVerticalBlockBorderWrapper"] h3 {
            font-size: 1.12rem !important;
            margin-bottom: 0.8rem !important;
        }

        .upload-hint {
            border: 1.5px dashed #8fb4ff;
            border-radius: 16px;
            padding: 1rem;
            margin: 0.4rem 0 1rem;
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(20, 184, 166, 0.08));
            color: var(--text-main);
        }

        .upload-hint strong {
            display: block;
            font-size: 1rem;
            margin-bottom: 0.2rem;
        }

        .upload-hint span {
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        [data-testid="stFileUploader"] section {
            border: 1.5px dashed #8fb4ff;
            border-radius: 16px;
            background: #f8fbff;
            padding: 0.9rem;
            transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
        }

        [data-testid="stFileUploader"] section:hover {
            border-color: var(--accent);
            box-shadow: 0 12px 30px rgba(37, 99, 235, 0.12);
            transform: translateY(-1px);
        }

        .stTextInput input,
        .stTextArea textarea,
        [data-baseweb="select"] > div {
            border-radius: 12px !important;
            border-color: #cbd5e1 !important;
            background-color: #ffffff !important;
        }

        .stTextArea textarea {
            line-height: 1.58 !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            border: 0;
            border-radius: 13px;
            color: #ffffff;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            box-shadow: 0 12px 26px rgba(37, 99, 235, 0.22);
            transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            color: #ffffff;
            border: 0;
            filter: brightness(1.04);
            transform: translateY(-1px);
            box-shadow: 0 16px 34px rgba(37, 99, 235, 0.27);
        }

        .stButton > button:active,
        .stDownloadButton > button:active {
            transform: translateY(0);
        }

        [data-testid="stImage"] {
            display: flex;
            justify-content: center;
        }

        [data-testid="stImage"] img {
            max-width: 600px !important;
            width: 100%;
            height: auto;
            border-radius: 18px;
            box-shadow: var(--shadow-md);
            border: 1px solid rgba(148, 163, 184, 0.32);
            background: #ffffff;
        }

        @media (max-width: 760px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 1.2rem;
            }

            h1 {
                font-size: 1.75rem !important;
            }

            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }

            [data-testid="stVerticalBlockBorderWrapper"] {
                border-radius: 14px;
                padding: 0.85rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_secret_value(key: str, default: str = "") -> str:
    """Safely read Streamlit secrets without crashing when unset."""
    try:
        value = st.secrets.get(key, default)
        return str(value) if value else default
    except Exception:
        return default


def get_nested_secret(section: str, key: str, default: str = "") -> str:
    """Support secrets.toml layouts like [provider]."""
    try:
        group = st.secrets.get(section, {})
        if hasattr(group, "get"):
            value = group.get(key, default)
            return str(value) if value else default
    except Exception:
        pass
    return default


def resolve_env_or_secret(
    *,
    env_keys: list[str],
    secret_keys: list[str],
    nested_pairs: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """Resolve a value from environment variables or Streamlit secrets."""
    for key in env_keys:
        value = os.getenv(key, "").strip()
        if value:
            return value, f"环境变量 {key}"

    for key in secret_keys:
        value = get_secret_value(key).strip()
        if value:
            return value, f"Streamlit secrets.{key}"

    for section, key in (nested_pairs or []):
        nested_value = get_nested_secret(section, key).strip()
        if nested_value:
            return nested_value, f"Streamlit secrets.{section}.{key}"

    return "", ""


def resolve_openai_api_key() -> tuple[str, str]:
    return resolve_env_or_secret(
        env_keys=["OPENAI_API_KEY", "DEEPROUTER_API_KEY", "AI_IMAGE_API_KEY"],
        secret_keys=["OPENAI_API_KEY", "DEEPROUTER_API_KEY", "AI_IMAGE_API_KEY"],
        nested_pairs=[("provider", "api_key"), ("openai_provider", "api_key")],
    )


def resolve_doubao_api_key() -> tuple[str, str]:
    return resolve_env_or_secret(
        env_keys=["ARK_API_KEY", "DOUBAO_API_KEY", "VOLCENGINE_API_KEY", "LAS_API_KEY", "API_KEY"],
        secret_keys=["ARK_API_KEY", "DOUBAO_API_KEY", "VOLCENGINE_API_KEY", "LAS_API_KEY", "API_KEY"],
        nested_pairs=[("doubao_provider", "api_key"), ("doubao", "api_key")],
    )


def resolve_zenmux_api_key() -> tuple[str, str]:
    return resolve_env_or_secret(
        env_keys=["ZENMUX_API_KEY"],
        secret_keys=["ZENMUX_API_KEY"],
        nested_pairs=[("zenmux_provider", "api_key"), ("zenmux", "api_key")],
    )


def resolve_openai_base_url() -> str:
    return (
        os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("DEEPROUTER_BASE_URL", "").strip()
        or get_secret_value("OPENAI_BASE_URL").strip()
        or get_secret_value("DEEPROUTER_BASE_URL").strip()
        or get_nested_secret("provider", "base_url").strip()
        or get_nested_secret("openai_provider", "base_url").strip()
        or DEFAULT_OPENAI_BASE_URL
    )


def resolve_openai_model() -> str:
    return (
        os.getenv("OPENAI_IMAGE_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or get_secret_value("OPENAI_IMAGE_MODEL").strip()
        or get_secret_value("OPENAI_MODEL").strip()
        or get_nested_secret("provider", "model").strip()
        or get_nested_secret("openai_provider", "model").strip()
        or DEFAULT_OPENAI_MODEL
    )


def resolve_doubao_base_url() -> str:
    return (
        os.getenv("ARK_BASE_URL", "").strip()
        or os.getenv("LAS_BASE_URL", "").strip()
        or os.getenv("DOUBAO_BASE_URL", "").strip()
        or os.getenv("VOLCENGINE_LAS_BASE_URL", "").strip()
        or get_secret_value("ARK_BASE_URL").strip()
        or get_secret_value("LAS_BASE_URL").strip()
        or get_secret_value("DOUBAO_BASE_URL").strip()
        or get_secret_value("VOLCENGINE_LAS_BASE_URL").strip()
        or get_nested_secret("doubao_provider", "base_url").strip()
        or get_nested_secret("doubao", "base_url").strip()
        or DEFAULT_DOUBAO_BASE_URL
    )


def resolve_doubao_model() -> str:
    return (
        os.getenv("DOUBAO_IMAGE_MODEL", "").strip()
        or os.getenv("DOUBAO_MODEL", "").strip()
        or get_secret_value("DOUBAO_IMAGE_MODEL").strip()
        or get_secret_value("DOUBAO_MODEL").strip()
        or get_nested_secret("doubao_provider", "model").strip()
        or get_nested_secret("doubao", "model").strip()
        or DEFAULT_DOUBAO_MODEL
    )


def resolve_doubao_size() -> str:
    return (
        os.getenv("DOUBAO_IMAGE_SIZE", "").strip()
        or get_secret_value("DOUBAO_IMAGE_SIZE").strip()
        or get_nested_secret("doubao_provider", "size").strip()
        or get_nested_secret("doubao", "size").strip()
        or DEFAULT_DOUBAO_SIZE
    )


def resolve_zenmux_base_url() -> str:
    return (
        os.getenv("ZENMUX_VERTEX_BASE_URL", "").strip()
        or os.getenv("ZENMUX_BASE_URL", "").strip()
        or get_secret_value("ZENMUX_VERTEX_BASE_URL").strip()
        or get_secret_value("ZENMUX_BASE_URL").strip()
        or get_nested_secret("zenmux_provider", "base_url").strip()
        or get_nested_secret("zenmux", "base_url").strip()
        or DEFAULT_ZENMUX_BASE_URL
    )


def resolve_zenmux_model() -> str:
    return (
        os.getenv("ZENMUX_IMAGE_MODEL", "").strip()
        or os.getenv("ZENMUX_MODEL", "").strip()
        or get_secret_value("ZENMUX_IMAGE_MODEL").strip()
        or get_secret_value("ZENMUX_MODEL").strip()
        or get_nested_secret("zenmux_provider", "model").strip()
        or get_nested_secret("zenmux", "model").strip()
        or DEFAULT_ZENMUX_MODEL
    )


def resolve_zenmux_style_analyzer_model() -> str:
    """Resolve the dedicated ZenMux model used only for style analysis."""
    return (
        os.getenv("ZENMUX_STYLE_ANALYZER_MODEL", "").strip()
        or get_secret_value("ZENMUX_STYLE_ANALYZER_MODEL").strip()
        or get_nested_secret("zenmux_style_analyzer", "model").strip()
        or get_nested_secret("zenmux_provider", "style_analyzer_model").strip()
        or DEFAULT_STYLE_ANALYZER_MODEL
    )


def resolve_style_references_dir() -> Path:
    """Resolve the default local folder used as the style image library."""
    configured = (
        os.getenv("STYLE_REFERENCES_DIR", "").strip()
        or get_secret_value("STYLE_REFERENCES_DIR").strip()
        or get_nested_secret("style_references", "directory").strip()
        or get_nested_secret("style_reference_library", "directory").strip()
    )
    if configured:
        return Path(configured).expanduser()
    if LUMI_STYLE_REFERENCES_DIR.exists():
        return LUMI_STYLE_REFERENCES_DIR
    return DEFAULT_STYLE_REFERENCES_DIR


def get_style_template_cache_dir(style_references_dir: Path) -> Path:
    """Keep generated template caches in the app folder, not external image libraries."""
    try:
        if style_references_dir.resolve() == DEFAULT_STYLE_REFERENCES_DIR.resolve():
            return style_references_dir
    except OSError:
        pass

    digest = hashlib.sha256(str(style_references_dir).encode("utf-8")).hexdigest()[:16]
    return DEFAULT_STYLE_REFERENCES_DIR / ".cache" / digest


def normalize_style_analyzer_model(model: str) -> str:
    """Avoid using image-generation models for image-to-text style analysis."""
    cleaned = (model or "").strip()
    if not cleaned:
        return DEFAULT_STYLE_ANALYZER_MODEL
    if cleaned.endswith("-image") or cleaned.endswith("-image-preview"):
        return DEFAULT_STYLE_ANALYZER_MODEL
    return cleaned


def normalize_doubao_size(size: str) -> str:
    """Keep Doubao size values aligned with the currently supported options."""
    cleaned = (size or "").strip()
    if cleaned in DOUBAO_SIZE_OPTIONS:
        return cleaned
    if cleaned == "2048x2048":
        return "2K"
    return DEFAULT_DOUBAO_SIZE


def get_zenmux_api_mode(model: str) -> str:
    """Choose the ZenMux Vertex API method for the selected image model."""
    configured = ZENMUX_MODEL_CONFIG.get(model, {})
    if configured.get("api_mode"):
        return str(configured["api_mode"])
    if model.startswith("google/gemini") or model.startswith("inclusionai/"):
        return "gemini"
    return "imagen"


def format_zenmux_model(model: str) -> str:
    configured = ZENMUX_MODEL_CONFIG.get(model)
    if not configured:
        return model
    return (
        f"{configured['label']} · {configured['slug']} · "
        f"{configured['api_mode']} · {configured['price_hint']}"
    )


def build_generation_fingerprint(
    *,
    provider_type: str,
    base_url: str,
    model: str,
    uploaded_files: list[Any] | None,
    prompt: str,
    style_template: str,
    apply_style_template: bool,
    watermark_cleanup_enabled: bool,
    watermark_keywords: str,
) -> str:
    """Describe the visible inputs that make a generated result current."""
    file_parts = []
    for uploaded_file in uploaded_files or []:
        size = getattr(uploaded_file, "size", None)
        if size is None:
            try:
                size = len(uploaded_file.getvalue())
            except Exception:
                size = ""
        file_parts.append(f"{uploaded_file.name}:{size}")

    raw = "\n".join(
        [
            provider_type,
            base_url,
            model,
            "|".join(file_parts),
            prompt,
            style_template if apply_style_template else "",
            str(apply_style_template),
            str(watermark_cleanup_enabled),
            watermark_keywords,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_provider(
    *,
    provider_type: str,
    base_url: str,
    model: str,
    api_key: str,
    doubao_size: str,
    zenmux_api_mode: str = "auto",
) -> BaseImageProvider:
    """Build the requested provider adapter."""
    if provider_type == ZENMUX_PROVIDER:
        return ZenMuxVertexProvider(
            base_url=base_url,
            model=model,
            api_key=api_key,
            api_mode=zenmux_api_mode,
        )

    if provider_type == DOUBAO_PROVIDER:
        return DoubaoSeedreamProvider(
            base_url=base_url,
            model=model,
            api_key=api_key,
            size=doubao_size,
            watermark=False,
            response_format="b64_json",
        )

    return OpenAICompatibleProvider(
        base_url=base_url,
        model=model,
        api_key=api_key,
    )


def render_results(results: list[dict[str, Any]], *, disabled: bool = False) -> None:
    """Render image previews, download buttons, and error details."""
    if not results:
        return

    st.subheader("结果预览区")

    success_items = [item for item in results if item["ok"]]
    error_items = [item for item in results if not item["ok"]]

    if success_items:
        columns = st.columns(2)
        for index, item in enumerate(success_items):
            with columns[index % 2]:
                with st.container(border=True):
                    st.image(item["image_bytes"], caption=item["output_name"], use_column_width=True)
                    if item.get("cleanup_note"):
                        st.caption(f"后处理: {item['cleanup_note']}")
                    st.download_button(
                        label=f"下载 {item['output_name']}",
                        data=item["image_bytes"],
                        file_name=item["output_name"],
                        mime="image/png",
                        key=f"download-single-{index}",
                        use_container_width=True,
                        disabled=disabled,
                    )

        zip_bytes = build_results_zip(
            [(item["output_name"], item["image_bytes"]) for item in success_items]
        )
        st.download_button(
            label="下载全部结果 ZIP",
            data=zip_bytes,
            file_name="ai-image-mvp-results.zip",
            mime="application/zip",
            key="download-zip",
            use_container_width=True,
            disabled=disabled,
        )

    if error_items:
        with st.expander(f"查看失败项（{len(error_items)}）", expanded=False):
            for item in error_items:
                st.error(f"{item['source_name']}: {item['error']}")


def render_style_reference_section(*, disabled: bool) -> tuple[str, bool]:
    """Render local style-reference controls and return style settings."""
    default_style_dir = resolve_style_references_dir()
    if "style_references_dir" not in st.session_state:
        st.session_state["style_references_dir"] = str(default_style_dir)
    if "style_template" not in st.session_state:
        st.session_state["style_template"] = ""

    with st.container(border=True):
        st.subheader("本地风格库")
        style_dir_text = st.text_input(
            "风格样图目录",
            key="style_references_dir",
            help="可以直接指向包含大量客户真实图的本地目录；应用会自动均匀抽样，不会一次性加载全部给 AI。",
            disabled=disabled,
        ).strip()
        style_references_dir = Path(style_dir_text or str(default_style_dir)).expanduser()
        st.caption(f"当前风格库：`{style_references_dir}`")
        st.caption("推荐流程：AI 分析样图只调用一次，生成风格模板后会本地缓存；后续批量生成会复用模板，不会每张图重复分析。")

        if not style_references_dir.exists() and style_references_dir == DEFAULT_STYLE_REFERENCES_DIR:
            ensure_style_reference_dir(style_references_dir)

        template_cache_dir = get_style_template_cache_dir(style_references_dir)
        cache_error = ""
        style_dir_key = str(style_references_dir)
        if st.session_state.get("loaded_style_references_dir") != style_dir_key:
            try:
                st.session_state["style_template"] = read_style_template_cache(template_cache_dir)
            except StyleUtilsError as exc:
                st.session_state["style_template"] = ""
                cache_error = str(exc)
            st.session_state["loaded_style_references_dir"] = style_dir_key
        if cache_error:
            st.warning(cache_error)

        try:
            total_reference_count = count_style_reference_paths(style_references_dir)
            style_references = load_style_references(style_references_dir)
        except StyleUtilsError as exc:
            total_reference_count = 0
            style_references = []
            st.error(str(exc))

        if style_references:
            st.success(
                f"已发现 {total_reference_count} 张可用样图，当前均匀抽样读取 {len(style_references)} 张。"
            )
            preview_cols = st.columns(min(6, len(style_references)))
            for index, reference in enumerate(style_references[:6]):
                with preview_cols[index % len(preview_cols)]:
                    st.image(
                        reference.image_bytes,
                        caption=reference.path.name,
                        use_column_width=True,
                    )
        else:
            st.info("当前风格库为空或目录不存在。请检查目录中是否有 PNG/JPG/JPEG/WEBP 样图。")

        if "zenmux_style_analyzer_model" not in st.session_state:
            st.session_state["zenmux_style_analyzer_model"] = normalize_style_analyzer_model(
                resolve_zenmux_style_analyzer_model()
            )
        else:
            st.session_state["zenmux_style_analyzer_model"] = normalize_style_analyzer_model(
                st.session_state["zenmux_style_analyzer_model"]
            )

        with st.expander("AI 风格分析设置", expanded=False):
            analyzer_model = st.text_input(
                "ZenMux 风格分析模型",
                key="zenmux_style_analyzer_model",
                help="这个模型只用于看图输出文字风格模板，不参与最终图片生成；请使用视觉理解模型，不要使用 *-image 图片生成模型。",
                disabled=disabled,
            ).strip()

        button_col_1, button_col_2 = st.columns(2)
        with button_col_1:
            use_heuristic = st.button(
                "免费生成基础风格模板",
                disabled=disabled or not style_references,
                use_container_width=True,
            )
        with button_col_2:
            use_ai = st.button(
                "AI 生成风格模板",
                disabled=disabled or not style_references,
                use_container_width=True,
                help=f"会调用一次 ZenMux/Gemini，最多分析前 {MAX_AI_STYLE_IMAGES} 张样图。",
            )

        if use_heuristic:
            st.session_state["style_template"] = build_heuristic_style_prompt(style_references)
            try:
                write_style_template_cache(template_cache_dir, st.session_state["style_template"])
            except StyleUtilsError as exc:
                st.warning(str(exc))
            st.success("已用本地启发式方式生成基础风格模板，不消耗 API。")

        if use_ai:
            zenmux_key, zenmux_key_source = resolve_zenmux_api_key()
            if not zenmux_key:
                st.error("缺少 ZenMux API Key，无法进行 AI 风格分析。")
            elif not analyzer_model:
                st.error("请填写 ZenMux 风格分析模型。")
            else:
                try:
                    analyzer_model = normalize_style_analyzer_model(analyzer_model)
                    analyzer = ZenMuxStyleAnalyzer(
                        base_url=resolve_zenmux_base_url(),
                        api_key=zenmux_key,
                        model=analyzer_model,
                    )
                    image_items = [
                        (item.path.name, item.image_bytes)
                        for item in style_references[:MAX_AI_STYLE_IMAGES]
                    ]
                    with st.spinner(f"正在调用 ZenMux 分析风格样图，Key 来源：{zenmux_key_source}"):
                        st.session_state["style_template"] = analyzer.analyze_images(
                            images=image_items,
                            instruction=DEFAULT_STYLE_ANALYSIS_INSTRUCTION,
                        )
                    try:
                        write_style_template_cache(template_cache_dir, st.session_state["style_template"])
                    except StyleUtilsError as exc:
                        st.warning(str(exc))
                    st.success("AI 风格模板已生成。")
                except StyleAnalyzerError as exc:
                    fallback_template = build_heuristic_style_prompt(style_references)
                    if fallback_template:
                        st.session_state["style_template"] = fallback_template
                        try:
                            write_style_template_cache(template_cache_dir, fallback_template)
                        except StyleUtilsError as cache_exc:
                            st.warning(str(cache_exc))
                        st.warning(
                            f"{exc} 已自动改用本地免费基础风格模板，避免卡住后续生成。"
                        )
                    else:
                        st.error(str(exc))

        apply_style = st.checkbox(
            "生成时自动套用风格模板",
            value=True,
            disabled=disabled,
            key="apply_style_template",
        )
        style_template = st.text_area(
            "风格模板提示词",
            height=180,
            placeholder="这里会显示从本地风格样图提取出的品牌视觉风格。你也可以手动粘贴或修改。",
            disabled=disabled,
            key="style_template",
        )

    return style_template, apply_style


def main() -> None:
    st.set_page_config(page_title="ai-image-mvp", layout="wide")
    inject_custom_css()

    if "results" not in st.session_state:
        st.session_state["results"] = []
    if "generation_message" not in st.session_state:
        st.session_state["generation_message"] = None

    st.session_state.pop("is_generating", None)
    controls_disabled = False

    st.title("ai-image-mvp")
    st.caption("单页 Streamlit MVP：支持 OpenAI-compatible、字节 Doubao Ark 与 ZenMux Vertex AI 通道切换，批量处理图片并导出 PNG / ZIP。")

    config_col, upload_col = st.columns([1.12, 0.88], gap="large")

    with config_col:
        with st.container(border=True):
            st.subheader("模型配置区")
            provider_keys = [OPENAI_PROVIDER, DOUBAO_PROVIDER, ZENMUX_PROVIDER]
            provider_labels = [PROVIDER_LABELS[key] for key in provider_keys]
            provider_label_to_key = dict(zip(provider_labels, provider_keys, strict=True))
            previous_provider = st.session_state.get("provider_type", OPENAI_PROVIDER)
            if previous_provider not in provider_keys:
                previous_provider = OPENAI_PROVIDER
            provider_label = st.selectbox(
                "提供商",
                options=provider_labels,
                index=provider_keys.index(previous_provider),
                key="provider_label",
                disabled=controls_disabled,
            )
            provider_type = provider_label_to_key[provider_label]
            st.session_state["provider_type"] = provider_type

            if provider_type == ZENMUX_PROVIDER:
                api_key, api_key_source = resolve_zenmux_api_key()
                base_url = st.text_input(
                    "ZenMux Vertex Base URL",
                    value=resolve_zenmux_base_url(),
                    key="zenmux_base_url",
                    help="ZenMux 图片模型使用 Vertex AI 兼容接口，默认值来自 ZenMux 文档。",
                    disabled=controls_disabled,
                ).strip()
                current_model = resolve_zenmux_model()
                model_options = ZENMUX_MODEL_OPTIONS + (
                    [current_model] if current_model and current_model not in ZENMUX_MODEL_OPTIONS else []
                )
                model = st.selectbox(
                    "ZenMux Model",
                    options=model_options,
                    index=model_options.index(current_model) if current_model in model_options else 0,
                    format_func=format_zenmux_model,
                    key="zenmux_model",
                    help="已按 ZenMux 模型页筛选 input=image 且 output=image 的模型；如果 ZenMux 后台模型名变化，也可以通过 secrets/env 覆盖。",
                    disabled=controls_disabled,
                ).strip()
                zenmux_api_mode = get_zenmux_api_mode(model)
                st.caption(f"ZenMux 调用模式：`{zenmux_api_mode}`。价格字段来自 ZenMux 模型页，仅作试用前参考，请以控制台账单为准。")
                doubao_size = DEFAULT_DOUBAO_SIZE
            elif provider_type == DOUBAO_PROVIDER:
                api_key, api_key_source = resolve_doubao_api_key()
                base_url = st.text_input(
                    "Doubao Base URL",
                    value=resolve_doubao_base_url(),
                    key="doubao_base_url",
                    help="默认值为火山方舟 Ark 图片生成 API，北京地域可直接使用；如你用其他地域，请替换为对应地域的 Base URL。",
                    disabled=controls_disabled,
                ).strip()
                model = st.text_input(
                    "Doubao Model",
                    value=resolve_doubao_model(),
                    key="doubao_model",
                    help="推荐先用 doubao-seedream-5-0-260128。",
                    disabled=controls_disabled,
                ).strip()
                doubao_size = st.selectbox(
                    "Doubao 输出尺寸",
                    options=DOUBAO_SIZE_OPTIONS,
                    index=DOUBAO_SIZE_OPTIONS.index(normalize_doubao_size(resolve_doubao_size())),
                    key="doubao_size",
                    help="当前模型建议使用 2K 或 4K。1024x1024 会被 Ark 拒绝。",
                    disabled=controls_disabled,
                )
                zenmux_api_mode = "auto"
            else:
                api_key, api_key_source = resolve_openai_api_key()
                base_url = st.text_input(
                    "Base URL",
                    value=resolve_openai_base_url(),
                    key="openai_base_url",
                    help="默认填入 DeepRouter 的 OpenAI-compatible Base URL，可按需改成你自己的兼容网关。",
                    disabled=controls_disabled,
                ).strip()
                model = st.text_input(
                    "Model",
                    value=resolve_openai_model(),
                    key="openai_model",
                    help="当前通道建议先用 grok-4-image。",
                    disabled=controls_disabled,
                ).strip()
                doubao_size = DEFAULT_DOUBAO_SIZE
                zenmux_api_mode = "auto"

            if api_key:
                st.success(f"已检测到 {PROVIDER_LABELS[provider_type]} 的 API Key，来源：{api_key_source}")
            else:
                st.warning(f"未检测到 {PROVIDER_LABELS[provider_type]} 的 API Key。请通过环境变量或 Streamlit secrets 配置后再开始生成。")

    with upload_col:
        with st.container(border=True):
            st.subheader("批量图片上传区")
            st.markdown(
                """
                <div class="upload-hint">
                    <strong>上传商品图或素材图</strong>
                    <span>支持 PNG、JPG、JPEG、WEBP，可一次选择多张图片批量处理。</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            uploaded_files = st.file_uploader(
                "拖拽图片到这里，或点击选择文件",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
                disabled=controls_disabled,
            )
            if uploaded_files:
                st.info(f"当前已选择 {len(uploaded_files)} 张图片。")

    style_template, apply_style_template = render_style_reference_section(disabled=controls_disabled)

    with st.container(border=True):
        st.subheader("提示词输入区")
        prompt = st.text_area(
            "请输入图像编辑提示词",
            height=160,
            placeholder="例如：保留主体构图，把背景替换成极简电商棚拍风格，补充柔和打光与高质感阴影，整体输出为高端广告图。",
            disabled=controls_disabled,
        )
        with st.expander("高级选项", expanded=False):
            watermark_cleanup_enabled = st.checkbox(
                "导出前自动尝试去除常见水印",
                value=True,
                disabled=controls_disabled,
            )
            watermark_keywords = st.text_input(
                "水印关键词（逗号分隔，可留空）",
                value=DEFAULT_WATERMARK_KEYWORDS,
                help="用于轻量 OCR / 关键词策略的提示词，适合 AI生成、夸克、watermark 等常见字样。",
                disabled=controls_disabled,
            )

    current_generation_fingerprint = build_generation_fingerprint(
        provider_type=provider_type,
        base_url=base_url,
        model=model,
        uploaded_files=uploaded_files,
        prompt=prompt,
        style_template=style_template,
        apply_style_template=apply_style_template,
        watermark_cleanup_enabled=watermark_cleanup_enabled,
        watermark_keywords=watermark_keywords,
    )

    start_clicked = st.button(
        "开始生成",
        type="primary",
        use_container_width=True,
    )

    if start_clicked:
        if not api_key:
            st.error("缺少 API Key。请先在环境变量或 Streamlit secrets 中配置。")
        elif not base_url:
            st.error("请填写 Base URL。")
        elif not model:
            st.error("请填写模型名称。")
        elif not uploaded_files:
            st.error("请至少上传一张图片。")
        elif not prompt.strip():
            st.error("请输入提示词。")
        else:
            st.session_state["generation_message"] = None
            with st.status("正在生成图片...", expanded=True) as status:
                try:
                    provider = build_provider(
                        provider_type=provider_type,
                        base_url=base_url,
                        model=model,
                        api_key=api_key,
                        doubao_size=doubao_size,
                        zenmux_api_mode=zenmux_api_mode,
                    )
                except ImageProviderError as exc:
                    st.session_state["generation_message"] = ("error", str(exc))
                    status.update(label="生成前检查失败", state="error", expanded=True)
                    st.error(str(exc))
                    provider = None

                if provider is not None:
                    results: list[dict[str, Any]] = []
                    progress_bar = st.progress(0, text="准备开始...")
                    status_placeholder = st.empty()
                    keywords = split_keywords(watermark_keywords)
                    effective_prompt = compose_prompt(
                        prompt.strip(),
                        style_template,
                        enabled=apply_style_template,
                    )

                    total = len(uploaded_files)
                    for index, uploaded_file in enumerate(uploaded_files, start=1):
                        source_name = uploaded_file.name
                        try:
                            status_placeholder.write(f"正在处理第 {index}/{total} 张：`{source_name}`")
                            input_bytes = prepare_input_image_bytes(uploaded_file.getvalue())
                            provider_filename = build_provider_input_filename(source_name, input_bytes)
                            generated_image = provider.edit_image(
                                image_bytes=input_bytes,
                                prompt=effective_prompt,
                                filename=provider_filename,
                            )
                            cleanup_note = ""
                            if watermark_cleanup_enabled:
                                generated_image, cleanup_note = remove_watermark_if_needed(
                                    generated_image,
                                    keywords=keywords,
                                )

                            output_name = build_output_filename(source_name, suffix="result")
                            output_bytes = prepare_input_image_bytes(
                                image_bytes=None,
                                image=generated_image,
                            )
                            results.append(
                                {
                                    "ok": True,
                                    "source_name": source_name,
                                    "output_name": output_name,
                                    "image_bytes": output_bytes,
                                    "cleanup_note": cleanup_note,
                                }
                            )
                        except ImageProviderError as exc:
                            results.append(
                                {
                                    "ok": False,
                                    "source_name": source_name,
                                    "error": str(exc),
                                }
                            )
                        except ImageUtilsError as exc:
                            results.append(
                                {
                                    "ok": False,
                                    "source_name": source_name,
                                    "error": str(exc),
                                }
                            )
                        except Exception as exc:
                            results.append(
                                {
                                    "ok": False,
                                    "source_name": source_name,
                                    "error": f"处理失败：{exc}",
                                }
                            )

                        progress_bar.progress(index / total, text=f"已完成 {index}/{total}")

                    st.session_state["results"] = results
                    st.session_state["results_fingerprint"] = current_generation_fingerprint
                    success_count = sum(1 for item in results if item["ok"])
                    if success_count:
                        message = f"处理完成：成功 {success_count} 张，失败 {total - success_count} 张。"
                        st.session_state["generation_message"] = ("success", message)
                        status.update(label=message, state="complete", expanded=False)
                        st.success(message)
                    else:
                        message = "所有图片都处理失败了，请检查模型、Base URL、API Key 或提示词。"
                        st.session_state["generation_message"] = ("error", message)
                        status.update(label="生成失败", state="error", expanded=True)
                        st.error(message)

    generation_message = st.session_state.get("generation_message")
    if generation_message and not start_clicked:
        message_type, message_text = generation_message
        if message_type == "success":
            st.success(message_text)
        else:
            st.error(message_text)

    results_to_render = st.session_state.get("results", [])
    if results_to_render:
        if st.session_state.get("results_fingerprint") != current_generation_fingerprint:
            st.info("当前图片、提示词或生成设置已变化。下面展示的是上次生成结果，重新点击开始生成会按当前设置处理。")
        if st.button("清空上次结果", use_container_width=True):
            st.session_state["results"] = []
            st.session_state["results_fingerprint"] = None
            st.session_state["generation_message"] = None
            results_to_render = []

    render_results(results_to_render, disabled=False)


if __name__ == "__main__":
    main()
