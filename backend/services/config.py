"""Runtime configuration and Streamlit-compatible secret resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


OPENAI_PROVIDER = "openai_compatible"
DOUBAO_PROVIDER = "doubao"
DOUBAO_LEGACY_PROVIDER = "doubao_seedream"
ZENMUX_PROVIDER = "zenmux"
ZENMUX_LEGACY_PROVIDER = "zenmux_vertex"

DEFAULT_OPENAI_BASE_URL = "https://deeprouter.top/v1"
DEFAULT_OPENAI_MODEL = "gpt-image-2"
DEFAULT_DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DOUBAO_MODEL = "doubao-seedream-4-5-251128"
DEFAULT_DOUBAO_SIZE = "2K"
DEFAULT_ZENMUX_BASE_URL = "https://zenmux.ai/api/vertex-ai"
DEFAULT_ZENMUX_MODEL = "openai/gpt-image-2"

DOUBAO_IMAGE_MODELS = [
    {
        "slug": "doubao-seedream-4-5-251128",
        "label": "Doubao-Seedream-4.5",
        "response_format": "url",
        "watermark": False,
        "extra_payload": {
            "sequential_image_generation": "disabled",
            "stream": False,
        },
    },
    {
        "slug": "doubao-seedream-5-0-260128",
        "label": "Doubao-Seedream-5.0",
        "response_format": "b64_json",
        "watermark": False,
        "extra_payload": {},
    },
]
DOUBAO_MODEL_CONFIG = {item["slug"]: item for item in DOUBAO_IMAGE_MODELS}

ZENMUX_IMAGE_MODELS = [
    {"slug": "openai/gpt-image-2", "label": "OpenAI: GPT-Image-2", "api_mode": "imagen"},
    {"slug": "sapiens-ai/agnes-image-1.2", "label": "Sapiens AI: Agnes-Image-1.2", "api_mode": "imagen"},
    {"slug": "qwen/qwen-image-2.0-pro", "label": "Qwen-Image-2.0-Pro", "api_mode": "imagen"},
    {"slug": "qwen/qwen-image-2.0", "label": "Qwen-Image-2.0", "api_mode": "imagen"},
    {"slug": "bytedance/doubao-seedream-5.0-lite", "label": "ByteDance: Doubao-Seedream-5.0-lite", "api_mode": "imagen"},
    {"slug": "google/gemini-3.1-flash-image-preview", "label": "Google: Nano Banana 2", "api_mode": "gemini"},
    {"slug": "inclusionai/ming-flash-omni-2.0", "label": "inclusionAI: Ming-flash-omni-2.0", "api_mode": "gemini"},
    {"slug": "openai/gpt-image-1.5", "label": "OpenAI: GPT-Image-1.5", "api_mode": "imagen"},
    {"slug": "google/gemini-3-pro-image-preview", "label": "Google: Nano Banana Pro", "api_mode": "gemini"},
    {"slug": "google/gemini-2.5-flash-image", "label": "Google: Gemini 2.5 Flash Image", "api_mode": "gemini"},
    {"slug": "tencent/hunyuan-image3", "label": "Tencent: Hunyuan Image3", "api_mode": "imagen"},
    {"slug": "klingai/kling-v2", "label": "KlingAI: Kling-v2", "api_mode": "imagen"},
]
ZENMUX_MODEL_CONFIG = {item["slug"]: item for item in ZENMUX_IMAGE_MODELS}

SUPPORTED_SIZES = ["1024x1024", "1024x1365", "1365x1024", "auto"]
SUPPORTED_QUALITIES = ["standard", "high"]
SUPPORTED_OUTPUT_FORMATS = ["png", "jpg"]


@dataclass(frozen=True, slots=True)
class ProviderRuntimeConfig:
    """Resolved runtime settings for one provider request."""

    provider_type: str
    base_url: str
    model: str
    api_key: str
    api_key_source: str
    doubao_size: str = DEFAULT_DOUBAO_SIZE
    doubao_response_format: str = "b64_json"
    doubao_watermark: bool = False
    doubao_extra_payload: dict[str, Any] | None = None
    zenmux_api_mode: str = "auto"


def normalize_provider_type(provider_type: str | None) -> str:
    """Accept both frontend-friendly and legacy Streamlit provider names."""
    cleaned = (provider_type or ZENMUX_PROVIDER).strip().lower()
    if cleaned in {ZENMUX_PROVIDER, ZENMUX_LEGACY_PROVIDER}:
        return ZENMUX_PROVIDER
    if cleaned in {DOUBAO_PROVIDER, DOUBAO_LEGACY_PROVIDER}:
        return DOUBAO_PROVIDER
    if cleaned in {OPENAI_PROVIDER, "openai", "openai-compatible"}:
        return OPENAI_PROVIDER
    return cleaned


def resolve_provider_config(
    provider_type: str | None,
    *,
    model: str | None = None,
    size: str | None = None,
) -> ProviderRuntimeConfig:
    """Resolve provider endpoint, model, API key, and provider-specific options."""
    normalized_provider = normalize_provider_type(provider_type)
    if normalized_provider == ZENMUX_PROVIDER:
        configured_model = (model or "").strip() or resolve_zenmux_model()
        api_key, source = resolve_zenmux_api_key()
        return ProviderRuntimeConfig(
            provider_type=ZENMUX_PROVIDER,
            base_url=resolve_zenmux_base_url(),
            model=configured_model,
            api_key=api_key,
            api_key_source=source,
            zenmux_api_mode=get_zenmux_api_mode(configured_model),
        )

    if normalized_provider == DOUBAO_PROVIDER:
        configured_model = (model or "").strip() or resolve_doubao_model()
        api_key, source = resolve_doubao_api_key()
        return ProviderRuntimeConfig(
            provider_type=DOUBAO_PROVIDER,
            base_url=resolve_doubao_base_url(),
            model=configured_model,
            api_key=api_key,
            api_key_source=source,
            doubao_size=normalize_doubao_size(size or resolve_doubao_size()),
            doubao_response_format=get_doubao_response_format(configured_model),
            doubao_watermark=get_doubao_watermark(configured_model),
            doubao_extra_payload=get_doubao_extra_payload(configured_model),
        )

    if normalized_provider == OPENAI_PROVIDER:
        api_key, source = resolve_openai_api_key()
        return ProviderRuntimeConfig(
            provider_type=OPENAI_PROVIDER,
            base_url=resolve_openai_base_url(),
            model=(model or "").strip() or resolve_openai_model(),
            api_key=api_key,
            api_key_source=source,
        )

    raise ValueError(f"不支持的 provider_type：{provider_type}")


def build_public_config() -> dict[str, Any]:
    """Return frontend-safe runtime configuration without leaking secrets."""
    default_provider = normalize_provider_type(os.getenv("DEFAULT_PROVIDER", ZENMUX_PROVIDER))
    provider_configs = {
        ZENMUX_PROVIDER: resolve_provider_config(ZENMUX_PROVIDER),
        DOUBAO_PROVIDER: resolve_provider_config(DOUBAO_PROVIDER),
        OPENAI_PROVIDER: resolve_provider_config(OPENAI_PROVIDER),
    }
    api_connections = {
        provider: bool(config.api_key)
        for provider, config in provider_configs.items()
    }
    if default_provider not in provider_configs:
        default_provider = ZENMUX_PROVIDER

    default_model = provider_configs[default_provider].model
    if default_provider == DOUBAO_PROVIDER:
        default_model = DEFAULT_DOUBAO_MODEL
    elif default_provider == ZENMUX_PROVIDER:
        default_model = DEFAULT_ZENMUX_MODEL

    return {
        "providers": [ZENMUX_PROVIDER, DOUBAO_PROVIDER, OPENAI_PROVIDER],
        "defaultProvider": default_provider,
        "models": {
            ZENMUX_PROVIDER: [item["slug"] for item in ZENMUX_IMAGE_MODELS],
            DOUBAO_PROVIDER: [item["slug"] for item in DOUBAO_IMAGE_MODELS],
            OPENAI_PROVIDER: [resolve_openai_model()],
        },
        "defaults": {
            "provider": default_provider,
            "model": default_model,
            "size": "1024x1024",
            "quality": "standard",
            "outputFormat": "png",
        },
        "sizes": SUPPORTED_SIZES,
        "qualities": SUPPORTED_QUALITIES,
        "outputFormats": SUPPORTED_OUTPUT_FORMATS,
        "apiConnected": api_connections.get(default_provider, False),
        "apiConnections": api_connections,
    }


def resolve_allowed_origins() -> list[str]:
    """Resolve CORS origins from ALLOWED_ORIGINS plus local development defaults."""
    raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
    if raw_origins == "*":
        return ["*"]

    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    configured = [
        origin.strip()
        for origin in raw_origins.split(",")
        if origin.strip()
    ]
    return list(dict.fromkeys([*defaults, *configured]))


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


def get_secret_value(key: str, default: str = "") -> str:
    """Read a flat Streamlit secret from supported secrets.toml locations."""
    value = _load_streamlit_secrets().get(key, default)
    return str(value) if value else default


def get_nested_secret(section: str, key: str, default: str = "") -> str:
    """Support secrets.toml layouts like [provider]."""
    group = _load_streamlit_secrets().get(section, {})
    if isinstance(group, dict):
        value = group.get(key, default)
        return str(value) if value else default
    return default


def normalize_doubao_size(size: str | None) -> str:
    """Keep Doubao size values aligned with currently supported native options."""
    cleaned = (size or "").strip()
    if cleaned in {"2K", "4K"}:
        return cleaned
    if cleaned in {"1024x1024", "1024x1365", "1365x1024", "auto", "2048x2048"}:
        return DEFAULT_DOUBAO_SIZE
    return cleaned or DEFAULT_DOUBAO_SIZE


def get_zenmux_api_mode(model: str) -> str:
    """Choose the ZenMux Vertex API method for the selected image model."""
    configured = ZENMUX_MODEL_CONFIG.get(model, {})
    if configured.get("api_mode"):
        return str(configured["api_mode"])
    if model.startswith("google/gemini") or model.startswith("inclusionai/"):
        return "gemini"
    return "imagen"


def get_doubao_response_format(model: str) -> str:
    """Choose the Ark response format known to work for each native model."""
    configured = DOUBAO_MODEL_CONFIG.get(model, {})
    return str(configured.get("response_format") or "b64_json")


def get_doubao_watermark(model: str) -> bool:
    """Keep API-side watermarks off unless a model preset explicitly needs them."""
    configured = DOUBAO_MODEL_CONFIG.get(model, {})
    return bool(configured.get("watermark", False))


def get_doubao_extra_payload(model: str) -> dict[str, Any]:
    """Return optional Ark request fields for model-specific native APIs."""
    configured = DOUBAO_MODEL_CONFIG.get(model, {})
    extra_payload = configured.get("extra_payload")
    if isinstance(extra_payload, dict):
        return dict(extra_payload)
    return {}


_SECRETS_CACHE: dict[str, Any] | None = None


def _load_streamlit_secrets() -> dict[str, Any]:
    global _SECRETS_CACHE
    if _SECRETS_CACHE is not None:
        return _SECRETS_CACHE

    root_dir = Path(__file__).resolve().parents[2]
    candidates = [
        root_dir / ".streamlit" / "secrets.toml",
        root_dir / "backend" / ".streamlit" / "secrets.toml",
        root_dir / "ai-image-mvp" / ".streamlit" / "secrets.toml",
    ]
    merged: dict[str, Any] = {}
    for path in candidates:
        if not path.exists():
            continue
        try:
            with path.open("rb") as handle:
                payload = tomllib.load(handle)
        except Exception:
            continue
        _deep_merge(merged, payload)

    _SECRETS_CACHE = merged
    return merged


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
