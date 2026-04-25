export type Provider = "zenmux" | "doubao" | "openai_compatible";
export type Quality = "standard" | "high";
export type OutputFormat = "png" | "jpg";
export type QueueStatus = "queued" | "uploading" | "running" | "done" | "failed";

export interface UploadedImage {
  id: string;
  file: File;
  url: string;
  width?: number;
  height?: number;
}

export interface GenerationRequest {
  files: File[];
  prompt: string;
  provider: Provider;
  model: string;
  size: string;
  quality: Quality;
  outputFormat: OutputFormat;
  realisticMode: boolean;
  watermarkCleanupEnabled: boolean;
  watermarkKeywords: string;
  qualityControlEnabled: boolean;
  qualityThreshold: number;
  qualityMaxRetries: number;
}

export interface GenerationResponseItem {
  sourceName?: string;
  status?: string;
  progress?: number;
  resultUrl?: string;
  resultDataUrl?: string;
  cleanupNote?: string;
  qualityScore?: number;
  qualityPassed?: boolean;
  qualityReasons?: string[];
  retryCount?: number;
  retried?: boolean;
  qualityRetryLimit?: number;
  iterationLogPath?: string;
  stageSummaryPath?: string;
  switchReviewPath?: string;
  switchWarning?: string;
  error?: string;
}

export interface GenerationResponse {
  jobId?: string;
  status?: string;
  items?: GenerationResponseItem[];
  providerCallCount?: number;
  providerCallLimit?: number;
}

export interface RuntimeConfig {
  providers: Provider[];
  defaultProvider: Provider;
  models: Record<Provider, string[]>;
  defaults: {
    provider: Provider;
    model: string;
    size: string;
    quality: Quality;
    outputFormat: OutputFormat;
  };
  apiConnected: boolean;
  apiConnections: Record<Provider, boolean>;
}

export interface QueueItem {
  id: string;
  jobId: string;
  sourceName: string;
  dimensions: string;
  thumbnailUrl?: string;
  status: QueueStatus;
  progress: number;
}

export interface ResultItem {
  id: string;
  jobId: string;
  title: string;
  imageUrl?: string;
  sourceImageUrl?: string;
  sourceName: string;
  prompt: string;
  size: string;
  createdAt: string;
  cleanupNote?: string;
  qualityScore?: number;
  qualityPassed?: boolean;
  qualityReasons?: string[];
  retryCount?: number;
  retried?: boolean;
  qualityRetryLimit?: number;
  iterationLogPath?: string;
  stageSummaryPath?: string;
  switchReviewPath?: string;
  switchWarning?: string;
}
