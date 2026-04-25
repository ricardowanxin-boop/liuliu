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
  Library,
  Loader2,
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
import { apiBaseUrl, createGeneration, getRuntimeConfig } from "./api";
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
  doubao: ["doubao-seedream-5-0-260128"],
  openai_compatible: ["openai/gpt-image-2"],
};

const samplePrompt =
  "一张干净的产品照片：薰衣草紫水晶珠与珍珠点缀的手链，放在透明亚克力托盘上。柔和自然光，白色与浅粉色美学，优雅极简。";

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

function getStatus(progress: number): QueueStatus {
  if (progress >= 100) return "done";
  if (progress >= 40) return "running";
  if (progress >= 20) return "uploading";
  return "queued";
}

function App() {
  const [prompt, setPrompt] = useState(samplePrompt);
  const [provider, setProvider] = useState<Provider>("zenmux");
  const [model, setModel] = useState(providerModels.zenmux[0]);
  const [size, setSize] = useState("1024x1365");
  const [quality, setQuality] = useState<Quality>("high");
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("png");
  const [realisticMode, setRealisticMode] = useState(true);
  const [uploads, setUploads] = useState<UploadedImage[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [results, setResults] = useState<ResultItem[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [notice, setNotice] = useState("生成模式已就绪");
  const [error, setError] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig | null>(null);
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

  const canGenerate = prompt.trim().length > 0 && !isGenerating;

  const characterCount = useMemo(() => prompt.trim().length, [prompt]);

  const addFiles = async (fileList: FileList | File[]) => {
    const nextFiles = Array.from(fileList)
      .filter((file) => ["image/jpeg", "image/png", "image/webp"].includes(file.type))
      .slice(0, Math.max(0, 8 - uploads.length));

    if (nextFiles.length === 0) {
      setError("请上传 JPG、PNG 或 WEBP 图片，演示版最多 8 张。");
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
      if (target) URL.revokeObjectURL(target.url);
      return current.filter((upload) => upload.id !== id);
    });
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
    serverResponse?: GenerationResponse,
  ) => {
    const responseItems = serverResponse?.items || [];
    const generatedAt = new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });

    setQueue((current) =>
      current.map((item) => {
        const responseItem = responseItems[taskIds.indexOf(item.id)];
        const failed = responseItem?.status === "failed";
        if (!taskIds.includes(item.id)) return item;
        return {
          ...item,
          progress: 100,
          status: failed ? "failed" : "done",
        };
      }),
    );

    setResults((current) => {
      const sourceItems =
        uploads.length > 0
          ? uploads
          : [
              {
                id: "text-only",
                file: new File([], "prompt-only"),
                url: undefined,
              } as unknown as UploadedImage,
            ];

      const nextResults = sourceItems.slice(0, 4).flatMap((source, index) => {
        const responseItem = responseItems[index];
        if (responseItem?.status === "failed") {
          return [];
        }

        const resultUrl = responseItem?.resultUrl
          ? `${apiBaseUrl}${responseItem.resultUrl.startsWith("/") ? "" : "/"}${responseItem.resultUrl}`
          : responseItem?.resultDataUrl || source.url;

        return {
          id: makeId("result"),
          jobId,
          title: `结果 ${current.length + index + 1}`,
          imageUrl: resultUrl,
          sourceName: source.file.name === "prompt-only" ? "提示词生成" : source.file.name,
          prompt,
          size,
          createdAt: generatedAt,
        };
      });
      return [...nextResults, ...current].slice(0, 12);
    });

    setIsGenerating(false);
    const failedCount = responseItems.filter((item) => item.status === "failed").length;
    if (failedCount > 0) {
      const firstError = responseItems.find((item) => item.error)?.error;
      setError(firstError || `${failedCount} 张图片生成失败，请检查模型、Key 或提示词。`);
      setNotice(`已完成，${failedCount} 张失败`);
      return;
    }
    setNotice("生成完成，结果已加入右侧画廊");
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

  const simulateProgress = (
    jobId: string,
    taskIds: string[],
    serverResponse?: GenerationResponse,
  ) => {
    const steps = [12, 26, 42, 68, 90, 100];
    steps.forEach((progress, index) => {
      const timerId = window.setTimeout(() => {
        if (progress < 100) {
          setQueue((current) =>
            current.map((item) =>
              taskIds.includes(item.id)
                ? {
                    ...item,
                    progress,
                    status: getStatus(progress),
                  }
                : item,
            ),
          );
        } else {
          completeJob(jobId, taskIds, serverResponse);
        }
      }, 520 * (index + 1));
      timersRef.current.push(timerId);
    });
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError("请输入提示词后再生成。");
      return;
    }

    const jobId = makeId("job");
    const sourceUploads = uploads.length > 0 ? uploads : [];
    const taskSources =
      sourceUploads.length > 0
        ? sourceUploads
        : [
            {
              id: "prompt-only",
              file: new File([], "提示词生成"),
              url: undefined,
            } as unknown as UploadedImage,
          ];

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
      });
      completeJob(response.jobId || jobId, taskIds, response);
    } catch {
      setNotice("后端暂不可用，已切换为本地演示进度");
      simulateProgress(jobId, taskIds);
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
              生成
            </button>
            <button className="nav-item" onClick={() => setNotice("编辑工作台即将开放")}>
              <Pencil size={18} />
              编辑
            </button>
            <button className="nav-item" onClick={() => setNotice("批量工作台即将开放")}>
              <Layers3 size={18} />
              批量
            </button>
          </div>

          <div className="nav-group">
            <span className="nav-title">预设</span>
            {["产品摄影", "生活方式", "社交媒体", "营销广告"].map((item) => (
              <button className="nav-item compact" key={item} onClick={() => appendHint(item)}>
                <Files size={17} />
                {item}
              </button>
            ))}
          </div>

          <div className="nav-group">
            <span className="nav-title">工具</span>
            <button className="nav-item" onClick={() => setNotice("历史记录即将开放")}>
              <History size={18} />
              历史记录
            </button>
            <button className="nav-item" onClick={() => setNotice("素材库即将开放")}>
              <FolderOpen size={18} />
              素材库
            </button>
            <button className="nav-item" onClick={() => setNotice("API 文档即将开放")}>
              <BookOpen size={18} />
              API 文档
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
                  <p>{uploads.length}/8 张</p>
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
                <span>JPG / PNG / WEBP，单张建议 20MB 内</span>
                <input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={onFileChange} />
              </label>

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
                <button className="icon-button" aria-label="素材库">
                  <Library size={18} />
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
                  <span>右侧保持两列网格，便于对比和下载。</span>
                </div>
              ) : null}

              {results.map((result) => (
                <article className="result-card" key={result.id}>
                  <label className="select-box" aria-label={`选择 ${result.title}`}>
                    <input type="checkbox" />
                  </label>
                  {result.imageUrl ? (
                    <img src={result.imageUrl} alt={result.title} />
                  ) : (
                    <div className="text-result">
                      <Sparkles size={24} />
                      <span>文本生成结果</span>
                    </div>
                  )}
                  <div className="result-meta">
                    <strong>{result.title}</strong>
                    <span>{result.size.replace("x", " x ")} · {result.createdAt}</span>
                  </div>
                  <div className="result-actions">
                    <a
                      className={result.imageUrl ? "" : "disabled"}
                      href={result.imageUrl}
                      download={`${result.title}.${outputFormat}`}
                      aria-disabled={!result.imageUrl}
                    >
                      <Download size={15} />
                      下载
                    </a>
                    <button onClick={() => setNotice(`已复制 ${result.sourceName} 的提示词`)}>
                      <MoreHorizontal size={16} />
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
    </div>
  );
}

export default App;
