import type { GenerationRequest, GenerationResponse, RuntimeConfig } from "./types";

const DEFAULT_API_BASE = "http://localhost:8000";

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || DEFAULT_API_BASE;

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

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 310_000);

  try {
    const response = await fetch(`${apiBaseUrl}/api/generations`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return (await response.json()) as GenerationResponse;
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
