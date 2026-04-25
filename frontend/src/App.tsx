import {
  Bell,
  BookOpen,
  ChevronDown,
  Clock3,
  Copy,
  Download,
  Files,
  FolderOpen,
  HelpCircle,
  History,
  ImagePlus,
  Layers3,
  Loader2,
  Maximize2,
  MoreHorizontal,
  PanelLeft,
  Pencil,
  Plus,
  Search,
  Settings,
  Sparkles,
  Trash2,
  UploadCloud,
  WandSparkles,
  X,
} from "lucide-react";
import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiBaseUrl, createGeneration, getRuntimeConfig } from "./api";
import type {
  GenerationResponse,
  OutputFormat,
  Provider,
  Quality,
  QueueItem,
  QueueStatus,
  ResultItem,
  RuntimeConfig,
  UploadedImage,
  GenerationResponseItem,
} from "./types";

const promptHints = [
  "产品图",
  "柔和日光",
  "真实阴影",
  "极简背景",
  "俯拍",
  "特写",
  "场景化",
  "高级质感",
];

const providerModels: Record<Provider, string[]> = {
  zenmux: ["openai/gpt-image-2", "bytedance/doubao-seedream-5.0-lite"],
  doubao: ["doubao-seedream-4-5-251128", "doubao-seedream-5-0-260128"],
  openai_compatible: ["openai/gpt-image-2"],
};

const samplePrompt =
  "去掉水印，更换背景，ins风，可以改变桌子颜色\n指甲改成通明带钻，全部一样的指甲样式，衣袖也全部更改，换成一样的样式";

const defaultWatermarkKeywords = "AI生成, 夸克, quark, watermark";
const maxUploadCount = 5;

const statusLabel: Record<QueueStatus, string> = {
  queued: "排队中",
  uploading: "上传中",
  running: "生成中",
  done: "已完成",
  failed: "失败",
};

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function makeId(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function sanitizeDownloadName(value: string) {
  return value.trim().replace(/[\\/:*?"<>|]+/g, "-") || "生成结果";
}

function getStatus(progress: number): QueueStatus {
  if (progress >= 100) return "done";
  if (progress >= 40) return "running";
  if (progress >= 20) return "uploading";
  return "queued";
}

function isTrustedGenerationItem(item: GenerationResponseItem | undefined): item is GenerationResponseItem {
  return Boolean(item?.status === "done" && item.resultDataUrl && item.qualityPassed !== false);
}

function App() {
  const [prompt, setPrompt] = useState(samplePrompt);
  const [provider, setProvider] = useState<Provider>("zenmux");
  const [model, setModel] = useState(providerModels.zenmux[0]);
  const [size, setSize] = useState("1024x1365");
  const [quality, setQuality] = useState<Quality>("high");
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("png");
  const [realisticMode, setRealisticMode] = useState(true);
  const [watermarkCleanupEnabled, setWatermarkCleanupEnabled] = useState(true);
  const [watermarkKeywords, setWatermarkKeywords] = useState(defaultWatermarkKeywords);
  const [qualityControlEnabled, setQualityControlEnabled] = useState(true);
  const [uploads, setUploads] = useState<UploadedImage[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [results, setResults] = useState<ResultItem[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [notice, setNotice] = useState("生成模式已就绪");
  const [error, setError] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig | null>(null);
  const [previewResult, setPreviewResult] = useState<ResultItem | null>(null);
  const timersRef = useRef<number[]>([]);
  const uploadsRef = useRef<UploadedImage[]>([]);

  const activeJobs = queue.filter((item) => item.status !== "done" && item.status !== "failed").length;
  const completedJobs = queue.filter((item) => item.status === "done").length;
  const models = useMemo(
    () => runtimeConfig?.models?.[provider] || providerModels[provider],
    [provider, runtimeConfig],
  );
  const apiConnected = runtimeConfig?.apiConnections?.[provider] ?? false;

  useEffect(() => {
    if (!models.includes(model)) {
      setModel(models[0]);
    }
  }, [model, models]);

  useEffect(() => {
    void getRuntimeConfig()
      .then((config) => {
        setRuntimeConfig(config);
        setProvider(config.defaults.provider);
        setModel(config.defaults.model);
        setSize(config.defaults.size);
        setQuality(config.defaults.quality);
        setOutputFormat(config.defaults.outputFormat);
        setNotice(config.apiConnected ? "后端配置已同步" : "后端已连接，模型 Key 待配置");
      })
      .catch(() => {
        setNotice("正在使用本地演示配置");
      });
  }, []);

  useEffect(() => {
    uploadsRef.current = uploads;
  }, [uploads]);

  useEffect(() => {
    return () => {
      uploadsRef.current.forEach((upload) => URL.revokeObjectURL(upload.url));
      timersRef.current.forEach((timerId) => window.clearTimeout(timerId));
    };
  }, []);

  const canGenerate = prompt.trim().length > 0 && uploads.length > 0 && !isGenerating;

  const characterCount = useMemo(() => prompt.trim().length, [prompt]);

  const addFiles = async (fileList: FileList | File[]) => {
    const nextFiles = Array.from(fileList)
      .filter((file) => ["image/jpeg", "image/png", "image/webp"].includes(file.type))
      .slice(0, Math.max(0, maxUploadCount - uploads.length));

    if (nextFiles.length === 0) {
      setError(`请上传 JPG、PNG 或 WEBP 图片，单次最多 ${maxUploadCount} 张。`);
      return;
    }

    const nextUploads = await Promise.all(
      nextFiles.map(
        (file) =>
          new Promise<UploadedImage>((resolve) => {
            const url = URL.createObjectURL(file);
            const image = new Image();
            image.onload = () =>
              resolve({
                id: makeId("upload"),
                file,
                url,
                width: image.naturalWidth,
                height: image.naturalHeight,
              });
            image.onerror = () =>
              resolve({
                id: makeId("upload"),
                file,
                url,
              });
            image.src = url;
          }),
      ),
    );

    setUploads((current) => [...current, ...nextUploads]);
    setError("");
    setNotice(`已添加 ${nextUploads.length} 张参考图`);
  };

  const removeUpload = (id: string) => {
    setUploads((current) => {
      const target = current.find((upload) => upload.id === id);
      const isUsedByResult = target ? results.some((result) => result.sourceImageUrl === target.url) : false;
      if (target && !isUsedByResult) URL.revokeObjectURL(target.url);
      return current.filter((upload) => upload.id !== id);
    });
  };

  const triggerDownload = (url: string, filename: string) => {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  };

  const exportAllResults = () => {
    const downloadableResults = results.filter((result) => result.imageUrl);
    if (downloadableResults.length === 0) {
      setNotice("暂无可导出的结果图");
      return;
    }

    downloadableResults.forEach((result, index) => {
      window.setTimeout(() => {
        triggerDownload(
          result.imageUrl as string,
          `${sanitizeDownloadName(result.title)}.${outputFormat}`,
        );
      }, index * 180);
    });
    setNotice(`正在导出 ${downloadableResults.length} 张结果图`);
  };

  const deleteResult = (id: string) => {
    setResults((current) => current.filter((result) => result.id !== id));
    setPreviewResult((current) => (current?.id === id ? null : current));
    setNotice("已删除 1 组结果");
  };

  const clearResults = () => {
    if (results.length === 0) {
      setNotice("结果画廊已经是空的");
      return;
    }
    setResults([]);
    setPreviewResult(null);
    setNotice("已清空结果画廊");
  };

  const appendHint = (hint: string) => {
    setPrompt((current) => {
      const trimmed = current.trim();
      if (!trimmed) return hint;
      if (trimmed.includes(hint)) return current;
      return `${trimmed}，${hint}`;
    });
  };

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      void addFiles(event.target.files);
      event.target.value = "";
    }
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragActive(false);
    if (event.dataTransfer.files) {
      void addFiles(event.dataTransfer.files);
    }
  };

  const completeJob = (
    jobId: string,
    taskIds: string[],
    taskSources: UploadedImage[],
    serverResponse?: GenerationResponse,
  ) => {
    const responseItems = serverResponse?.items || [];
    const hasCompleteShape =
      serverResponse?.status === "completed" &&
      responseItems.length === taskIds.length &&
      taskIds.length > 0;
    const generatedAt = new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });

    setQueue((current) =>
      current.map((item) => {
        const responseItem = responseItems[taskIds.indexOf(item.id)];
        if (!taskIds.includes(item.id)) return item;
        const trusted = hasCompleteShape && isTrustedGenerationItem(responseItem);
        return {
          ...item,
          progress: 100,
          status: trusted ? "done" : "failed",
        };
      }),
    );

    setResults((current) => {
      const sourceItems =
        taskSources.length > 0
          ? taskSources
          : [
              {
                id: "text-only",
                file: new File([], "prompt-only"),
                url: undefined,
              } as unknown as UploadedImage,
            ];

      const nextResults = sourceItems.flatMap((source, index) => {
        const responseItem = responseItems[index];
        if (!hasCompleteShape || !isTrustedGenerationItem(responseItem)) {
          return [];
        }

        const resultUrl = responseItem.resultUrl
          ? `${apiBaseUrl}${responseItem.resultUrl.startsWith("/") ? "" : "/"}${responseItem.resultUrl}`
          : responseItem.resultDataUrl;

        if (!resultUrl) {
          return [];
        }

        return {
          id: makeId("result"),
          jobId,
          title: `结果 ${current.length + index + 1}`,
          imageUrl: resultUrl,
          sourceImageUrl: source.url,
          sourceName: source.file.name === "prompt-only" ? "提示词生成" : source.file.name,
          prompt,
          size,
          createdAt: generatedAt,
          cleanupNote: responseItem?.cleanupNote,
          qualityScore: responseItem?.qualityScore,
          qualityPassed: responseItem?.qualityPassed,
          qualityReasons: responseItem?.qualityReasons,
          retryCount: responseItem?.retryCount,
          retried: responseItem?.retried,
          qualityRetryLimit: responseItem?.qualityRetryLimit,
          iterationLogPath: responseItem?.iterationLogPath,
          stageSummaryPath: responseItem?.stageSummaryPath,
          switchReviewPath: responseItem?.switchReviewPath,
          switchWarning: responseItem?.switchWarning,
        };
      });
      return [...nextResults, ...current].slice(0, 12);
    });

    setIsGenerating(false);
    const trustedCount = responseItems.filter(isTrustedGenerationItem).length;
    const failedCount = Math.max(taskIds.length - trustedCount, 0);
    if (!hasCompleteShape || failedCount > 0) {
      const firstError = responseItems.find((item) => item.error)?.error;
      const callHint =
        typeof serverResponse?.providerCallCount === "number"
          ? `（本轮真实调用 ${serverResponse.providerCallCount} 次）`
          : "";
      setError(firstError || `${failedCount} 张图片未通过生成/质检流程，请检查模型、Key 或提示词。${callHint}`);
      setNotice(`生成未通过，${failedCount} 张未交付`);
      return;
    }
    setNotice(
      typeof serverResponse?.providerCallCount === "number"
        ? `生成完成，结果已加入右侧画廊，本轮调用 ${serverResponse.providerCallCount} 次`
        : "生成完成，结果已加入右侧画廊",
    );
  };

  const failJob = (taskIds: string[], message: string) => {
    setQueue((current) =>
      current.map((item) =>
        taskIds.includes(item.id)
          ? {
              ...item,
              progress: 100,
              status: "failed",
            }
          : item,
      ),
    );
    setIsGenerating(false);
    setError(message);
    setNotice("生成失败，请根据错误提示调整后重试");
  };

  const advanceJobWhileWaiting = (taskIds: string[]) => {
    const steps = [12, 26, 42, 68, 88];
    steps.forEach((progress, index) => {
      const timerId = window.setTimeout(() => {
        setQueue((current) =>
          current.map((item) => {
            if (!taskIds.includes(item.id) || item.status === "done" || item.status === "failed") {
              return item;
            }
            const nextProgress = Math.max(item.progress, progress);
            return {
              ...item,
              progress: nextProgress,
              status: getStatus(nextProgress),
            };
          }),
        );
      }, 900 * (index + 1));
      timersRef.current.push(timerId);
    });
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError("请输入提示词后再生成。");
      return;
    }

    if (uploads.length === 0) {
      setError("请先上传至少一张参考图，再开始生成。");
      return;
    }

    const jobId = makeId("job");
    const taskSources = uploads;

    const taskIds: string[] = [];
    const newTasks: QueueItem[] = taskSources.map((source) => {
      const id = makeId("task");
      taskIds.push(id);
      return {
        id,
        jobId,
        sourceName: source.file.name,
        dimensions: source.width && source.height ? `${source.width} x ${source.height}` : size.replace("x", " x "),
        thumbnailUrl: source.url,
        status: "queued",
        progress: 8,
      };
    });

    setQueue((current) => [...newTasks, ...current].slice(0, 16));
    setIsGenerating(true);
    setError("");
    setNotice("任务已进入底部队列");
    advanceJobWhileWaiting(taskIds);

    try {
      const response = await createGeneration({
        files: uploads.map((upload) => upload.file),
        prompt,
        provider,
        model,
        size,
        quality,
        outputFormat,
        realisticMode,
        watermarkCleanupEnabled,
        watermarkKeywords,
        qualityControlEnabled,
        qualityThreshold: 72,
        qualityMaxRetries: 1,
      });
      completeJob(response.jobId || jobId, taskIds, taskSources, response);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "生成请求失败，请检查后端服务、模型配置或网络。";
      failJob(taskIds, message);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <WandSparkles size={20} />
          </div>
          <div>
            <strong>图像工坊</strong>
            <span>电商视觉生产</span>
          </div>
        </div>

        <button className="new-project">
          <Plus size={18} />
          新建项目
        </button>

        <nav className="nav-groups" aria-label="主导航">
          <div className="nav-group">
            <span className="nav-title">工作台</span>
            <button className="nav-item active">
              <Sparkles size={18} />
              <span>生成</span>
            </button>
            <button className="nav-item" onClick={() => setNotice("编辑工作台即将开放")}>
              <Pencil size={18} />
              <span>编辑</span>
              <span className="nav-badge">即将开放</span>
            </button>
            <button className="nav-item" onClick={() => setNotice("批量工作台即将开放")}>
              <Layers3 size={18} />
              <span>批量</span>
              <span className="nav-badge">即将开放</span>
            </button>
          </div>

          <div className="nav-group">
            <span className="nav-title">预设</span>
            {["产品摄影", "生活方式", "社交媒体", "营销广告"].map((item) => (
              <button className="nav-item compact" key={item} onClick={() => appendHint(item)}>
                <Files size={17} />
                <span>{item}</span>
              </button>
            ))}
          </div>

          <div className="nav-group">
            <span className="nav-title">工具</span>
            <button className="nav-item" onClick={() => setNotice("历史记录即将开放")}>
              <History size={18} />
              <span>历史记录</span>
              <span className="nav-badge">即将开放</span>
            </button>
            <button className="nav-item" onClick={() => setNotice("素材库即将开放")}>
              <FolderOpen size={18} />
              <span>素材库</span>
              <span className="nav-badge">即将开放</span>
            </button>
            <button className="nav-item" onClick={() => setNotice("API 文档即将开放")}>
              <BookOpen size={18} />
              <span>API 文档</span>
              <span className="nav-badge">即将开放</span>
            </button>
          </div>
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button sidebar-toggle" aria-label="折叠导航">
              <PanelLeft size={19} />
            </button>
            <div>
              <h1>生成工作台</h1>
              <p>{notice}</p>
            </div>
          </div>
          <div className="topbar-right">
            <div className={`status-pill ${apiConnected ? "connected" : ""}`}>
              {apiConnected ? "API 已连接" : "API 待配置"}
            </div>
            <div className="status-pill">{provider} 通道</div>
            <div className="quota">
              <span>今日额度</span>
              <strong>72%</strong>
            </div>
            <button className="icon-button" aria-label="搜索">
              <Search size={18} />
            </button>
            <button className="icon-button" aria-label="帮助">
              <HelpCircle size={18} />
            </button>
            <button className="icon-button" aria-label="通知">
              <Bell size={18} />
            </button>
            <div className="avatar">柳</div>
          </div>
        </header>

          <section className="content-grid">
          <section className="generation-panel" aria-label="生成参数">
            <div className="generation-scroll">
              {error ? (
                <div className="inline-alert" role="alert">
                  {error}
                  <button onClick={() => setError("")} aria-label="关闭错误">
                    <X size={15} />
                  </button>
                </div>
              ) : null}

              <div className="panel-block">
              <div className="section-heading">
                <div>
                  <h2>提示词</h2>
                  <p>{characterCount} 字</p>
                </div>
                <button className="secondary-button small" onClick={() => setPrompt(samplePrompt)}>
                  <Copy size={15} />
                  示例
                </button>
              </div>
              <textarea
                className="prompt-input"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="输入商品图、场景、光线、材质和风格要求"
              />
              <div className="hint-row">
                {promptHints.map((hint) => (
                  <button key={hint} type="button" onClick={() => appendHint(hint)}>
                    {hint}
                  </button>
                ))}
              </div>
            </div>

              <div className="panel-block">
              <div className="section-heading">
                <div>
                  <h2>参考图</h2>
                  <p>{uploads.length}/{maxUploadCount} 张</p>
                </div>
                <label className="secondary-button small">
                  <ImagePlus size={15} />
                  添加
                  <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={onFileChange} />
                </label>
              </div>

              <label
                className={`upload-zone ${isDragActive ? "drag-active" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragActive(true);
                }}
                onDragLeave={() => setIsDragActive(false)}
                onDrop={onDrop}
              >
                <UploadCloud size={28} />
                <strong>拖拽或点击上传参考图</strong>
                <span>JPG / PNG / WEBP，单张建议 20MB 内，最多 {maxUploadCount} 张</span>
                <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={onFileChange} />
              </label>
              {uploads.length === 0 ? (
                <p className="field-hint attention">请先上传至少一张参考图，系统会基于参考图做电商场景重绘。</p>
              ) : null}

              {uploads.length > 0 ? (
                <div className="upload-grid">
                  {uploads.map((upload) => (
                    <article className="upload-card" key={upload.id}>
                      <img src={upload.url} alt={upload.file.name} />
                      <button onClick={() => removeUpload(upload.id)} aria-label={`删除 ${upload.file.name}`}>
                        <Trash2 size={15} />
                      </button>
                      <div>
                        <strong title={upload.file.name}>{upload.file.name}</strong>
                        <span>
                          {upload.width && upload.height ? `${upload.width} x ${upload.height}` : "读取尺寸中"} ·{" "}
                          {formatBytes(upload.file.size)}
                        </span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : null}
            </div>

              <div className="panel-block">
              <div className="section-heading">
                <div>
                  <h2>出图处理</h2>
                  <p>反 AI 棚拍、去水印与自动质检默认开启</p>
                </div>
              </div>

              <div className="processing-grid">
                <label className="switch-control">
                  <span>
                    真实电商审美模式
                    <small>自然光、真实阴影、生活化陈列</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={realisticMode}
                    onChange={(event) => setRealisticMode(event.target.checked)}
                  />
                </label>
                <label className="switch-control">
                  <span>
                    导出前自动去水印
                    <small>先提示词约束，再做轻量后处理</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={watermarkCleanupEnabled}
                    onChange={(event) => setWatermarkCleanupEnabled(event.target.checked)}
                  />
                </label>
                <label className="switch-control">
                  <span>
                    自动评分并重试
                    <small>低于 72 分会自动重试 1 次</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={qualityControlEnabled}
                    onChange={(event) => setQualityControlEnabled(event.target.checked)}
                  />
                </label>
                <label className="keyword-control">
                  <span>水印关键词</span>
                  <input
                    type="text"
                    value={watermarkKeywords}
                    disabled={!watermarkCleanupEnabled}
                    onChange={(event) => setWatermarkKeywords(event.target.value)}
                    placeholder="AI生成, 夸克, quark, watermark"
                  />
                </label>
              </div>
            </div>

              <div className="panel-block">
              <div className="section-heading">
                <div>
                  <h2>模型参数</h2>
                  <p>当前：{model}</p>
                </div>
                <button className="secondary-button small" onClick={() => setNotice("高级选项已使用默认配置")}>
                  <Settings size={15} />
                  高级
                </button>
              </div>

              <div className="control-grid">
                <label>
                  <span>模型通道</span>
                  <select value={provider} onChange={(event) => setProvider(event.target.value as Provider)}>
                    <option value="zenmux">ZenMux</option>
                    <option value="doubao">Doubao</option>
                    <option value="openai_compatible">OpenAI-compatible</option>
                  </select>
                </label>
                <label>
                  <span>模型</span>
                  <select value={model} onChange={(event) => setModel(event.target.value)}>
                    {models.map((item) => (
                      <option value={item} key={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>尺寸</span>
                  <select value={size} onChange={(event) => setSize(event.target.value)}>
                    <option value="1024x1024">1024 x 1024</option>
                    <option value="1024x1365">1024 x 1365</option>
                    <option value="1365x1024">1365 x 1024</option>
                    <option value="auto">自动</option>
                  </select>
                </label>
                <label>
                  <span>质量</span>
                  <select value={quality} onChange={(event) => setQuality(event.target.value as Quality)}>
                    <option value="standard">标准</option>
                    <option value="high">高</option>
                  </select>
                </label>
                <label>
                  <span>输出格式</span>
                  <select value={outputFormat} onChange={(event) => setOutputFormat(event.target.value as OutputFormat)}>
                    <option value="png">PNG</option>
                    <option value="jpg">JPG</option>
                  </select>
                </label>
              </div>
              </div>
            </div>

            <div className="action-bar">
              <button className="primary-button" disabled={!canGenerate} onClick={handleGenerate}>
                {isGenerating ? <Loader2 className="spin" size={18} /> : <Sparkles size={18} />}
                {isGenerating ? "生成中" : "生成图片"}
              </button>
              <button className="secondary-button" onClick={() => setNotice(`API Base：${apiBaseUrl}`)}>
                <ChevronDown size={17} />
                连接信息
              </button>
            </div>
          </section>

          <aside className="result-panel" aria-label="生成结果">
            <div className="result-toolbar">
              <div>
                <h2>结果画廊</h2>
                <p>{results.length} 张结果</p>
              </div>
              <div className="view-actions">
                <button
                  className="secondary-button small"
                  disabled={!results.some((result) => result.imageUrl)}
                  onClick={exportAllResults}
                >
                  <Download size={15} />
                  导出全部
                </button>
                <button className="secondary-button small" disabled={results.length === 0} onClick={clearResults}>
                  <Trash2 size={15} />
                  清空
                </button>
                <button className="icon-button" aria-label="更多操作">
                  <MoreHorizontal size={18} />
                </button>
              </div>
            </div>

            <div className="result-grid">
              {isGenerating
                ? [1, 2].map((item) => (
                    <div className="result-card skeleton" key={item}>
                      <div className="image-skeleton" />
                      <div className="result-card-footer">
                        <span>等待结果</span>
                        <span>{item}</span>
                      </div>
                    </div>
                  ))
                : null}

              {results.length === 0 && !isGenerating ? (
                <div className="empty-results">
                  <Sparkles size={26} />
                  <strong>生成结果会出现在这里</strong>
                  <span>上传商品参考图并点击生成后，可在这里预览、对比和下载结果。</span>
                </div>
              ) : null}

              {results.map((result) => (
                <article className="result-card" key={result.id}>
                  <label className="select-box" aria-label={`选择 ${result.title}`}>
                    <input type="checkbox" />
                  </label>
                  <div className="result-pair" aria-label={`${result.title} 原图和结果对比`}>
                    <button
                      type="button"
                      className="result-pair-cell"
                      onClick={() => setPreviewResult(result)}
                      disabled={!result.sourceImageUrl}
                      aria-label={`查看 ${result.title} 原图对比`}
                    >
                      <span className="pair-label">原图</span>
                      {result.sourceImageUrl ? (
                        <img src={result.sourceImageUrl} alt={`${result.sourceName} 原图`} />
                      ) : (
                        <span className="pair-placeholder">无原图</span>
                      )}
                    </button>
                    <button
                      type="button"
                      className="result-pair-cell result-pair-cell-output"
                      onClick={() => setPreviewResult(result)}
                      disabled={!result.imageUrl}
                      aria-label={`放大预览 ${result.title} 结果图`}
                    >
                      <span className="pair-label">结果</span>
                      {result.imageUrl ? (
                        <img src={result.imageUrl} alt={`${result.title} 结果图`} />
                      ) : (
                        <span className="pair-placeholder">无结果</span>
                      )}
                    </button>
                  </div>
                  <div className="result-meta">
                    <strong>{result.title}</strong>
                    <span>{result.size.replace("x", " x ")} · {result.createdAt}</span>
                    {typeof result.qualityScore === "number" ? (
                      <small className={result.qualityPassed ? "quality-note passed" : "quality-note failed"}>
                        质检 {result.qualityScore} 分{result.retried ? ` · 已自动重试 ${result.retryCount || 0} 次` : ""}
                      </small>
                    ) : null}
                    {result.iterationLogPath ? <small>已写入迭代日志</small> : null}
                    {result.stageSummaryPath ? <small>已生成阶段总结</small> : null}
                    {result.switchReviewPath ? <small className="quality-note failed">已生成换方案评估</small> : null}
                    {result.switchWarning ? <small className="quality-note failed">{result.switchWarning}</small> : null}
                    {result.cleanupNote ? <small>{result.cleanupNote}</small> : null}
                  </div>
                  <div className="result-actions">
                    <button
                      disabled={!result.imageUrl}
                      onClick={() => {
                        if (result.imageUrl) {
                          triggerDownload(result.imageUrl, `${sanitizeDownloadName(result.title)}.${outputFormat}`);
                        }
                      }}
                    >
                      <Download size={15} />
                      下载
                    </button>
                    <button onClick={() => setPreviewResult(result)} disabled={!result.imageUrl}>
                      <Maximize2 size={15} />
                      预览
                    </button>
                    <button className="danger-action" onClick={() => deleteResult(result.id)}>
                      <Trash2 size={15} />
                      删除
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </aside>
        </section>

        <section className="queue-dock" aria-label="底部批量队列">
          <div className="queue-summary">
            <div>
              <h2>批量队列</h2>
              <p>
                {activeJobs} 个进行中 · {completedJobs} 个已完成
              </p>
            </div>
            <button
              className="secondary-button small"
              onClick={() => setQueue((current) => current.filter((item) => item.status !== "done"))}
            >
              清空完成
            </button>
          </div>
          <div className="queue-list">
            {queue.length === 0 ? (
              <div className="empty-queue">
                <Clock3 size={22} />
                <span>暂无任务</span>
              </div>
            ) : (
              queue.map((item) => (
                <article className="queue-card" key={item.id}>
                  {item.thumbnailUrl ? <img src={item.thumbnailUrl} alt={item.sourceName} /> : <div className="queue-thumb"><Sparkles size={18} /></div>}
                  <div className="queue-card-body">
                    <div className="queue-card-title">
                      <strong title={item.sourceName}>{item.sourceName}</strong>
                      <MoreHorizontal size={16} />
                    </div>
                    <span>{item.dimensions}</span>
                    <div className="queue-progress-row">
                      <em className={`status-${item.status}`}>
                        {statusLabel[item.status]} {item.status === "running" ? `${item.progress}%` : ""}
                      </em>
                      <small>{item.progress}%</small>
                    </div>
                    <div className={`progress-track status-${item.status}`}>
                      <i style={{ width: `${item.progress}%` }} />
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </main>

      {previewResult ? (
        <div className="preview-modal" role="dialog" aria-modal="true" aria-label={`${previewResult.title} 大图预览`}>
          <button className="preview-backdrop" aria-label="关闭大图预览" onClick={() => setPreviewResult(null)} />
          <div className="preview-dialog">
            <div className="preview-header">
              <div>
                <strong>{previewResult.title}</strong>
                <span>{previewResult.size.replace("x", " x ")} · {previewResult.createdAt}</span>
              </div>
              <div className="preview-actions">
                {previewResult.imageUrl ? (
                  <a href={previewResult.imageUrl} download={`${previewResult.title}.${outputFormat}`}>
                    <Download size={16} />
                    下载结果图
                  </a>
                ) : null}
                <button onClick={() => setPreviewResult(null)} aria-label="关闭预览">
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="preview-compare">
              {previewResult.sourceImageUrl ? (
                <figure>
                  <figcaption>原图</figcaption>
                  <img src={previewResult.sourceImageUrl} alt={`${previewResult.sourceName} 原图`} />
                </figure>
              ) : null}
              {previewResult.imageUrl ? (
                <figure>
                  <figcaption>结果</figcaption>
                  <img src={previewResult.imageUrl} alt={`${previewResult.title} 结果图`} />
                </figure>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default App;
