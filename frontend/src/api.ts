import type { GenerationRequest, GenerationResponse, RuntimeConfig } from "./types";

const DEFAULT_API_BASE = "http://localhost:8000";

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || DEFAULT_API_BASE;

export class ApiError extends Error {
  status?: number;
  detail?: unknown;

  constructor(message: string, status?: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getErrorMessage(payload: unknown, status: number): string {
  if (!payload || typeof payload !== "object") {
    return `接口请求失败：HTTP ${status}`;
  }

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const first = detail[0] as { loc?: unknown[]; msg?: string } | undefined;
    const field = first?.loc?.slice(1).join(".");
    const suffix = field ? `（字段：${field}）` : "";
    return `${first?.msg || "请求参数校验失败"}${suffix}`;
  }

  return `接口请求失败：HTTP ${status}`;
}

export async function createGeneration(
  request: GenerationRequest,
): Promise<GenerationResponse> {
  const formData = new FormData();
  request.files.forEach((file) => formData.append("files[]", file));
  formData.append("prompt", request.prompt);
  formData.append("provider_type", request.provider);
  formData.append("provider", request.provider);
  formData.append("model", request.model);
  formData.append("size", request.size);
  formData.append("quality", request.quality);
  formData.append("output_format", request.outputFormat);
  formData.append("realistic_mode", String(request.realisticMode));
  formData.append("watermark_cleanup_enabled", String(request.watermarkCleanupEnabled));
  formData.append("watermark_keywords", request.watermarkKeywords);
  formData.append("quality_control_enabled", String(request.qualityControlEnabled));
  formData.append("quality_threshold", String(request.qualityThreshold));
  formData.append("quality_max_retries", String(request.qualityMaxRetries));
  formData.append("subject_guard_enabled", String(request.subjectGuardEnabled));
  formData.append("texture_preservation_enabled", String(request.texturePreservationEnabled));

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 310_000);

  try {
    const response = await fetch(`${apiBaseUrl}/api/generations`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      let payload: unknown = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      throw new ApiError(getErrorMessage(payload, response.status), response.status, payload);
    }

    return (await response.json()) as GenerationResponse;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("生成请求超时，请稍后重试。", 408);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  const response = await fetch(`${apiBaseUrl}/api/config`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as RuntimeConfig;
}
