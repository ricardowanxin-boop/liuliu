# 图像工坊：电商图片生成解决方案

这是一个面向电商视觉生产的图片生成与迭代验证项目。当前主线是 React 前端 + FastAPI 后端，通过 ZenMux、Doubao Seedream、OpenAI-compatible 等图片模型通道，对商品参考图进行批量图生图、提示词编译、水印清理、本地质检、失败重试和迭代日志沉淀。

仓库里同时保留了早期 Streamlit MVP、腾讯云函数部署适配、测试脚本、业务资料和阶段复盘文档，方便从原型验证继续推进到可演示、可部署、可复盘的产品化版本。

## 核心能力

- 上传 1-5 张商品参考图，按同一提示词批量生成结果图。
- 支持 ZenMux、Doubao Seedream、OpenAI-compatible 三类模型通道。
- 前端提供模型、尺寸、质量、输出格式、水印清理、真实商品图模式和本地质检开关。
- 后端统一处理提示词编译、图片预处理、模型调用、结果转码和错误返回。
- 内置轻量本地质检，检查过曝、过暗、AI 平滑、主体细节下降、背景棚拍感等问题。
- 质检失败时可自动追加修复提示词并重试，避免把明显不可交付结果直接进入画廊。
- 每轮生成写入迭代日志、阶段总结和切换复盘材料，便于持续沉淀失败原因。
- 提供 Vercel 静态前端 + 腾讯云函数 FastAPI 后端的部署路径。

## 目录结构

```text
.
├── frontend/                 # React + Vite 前端工作台
├── backend/                  # FastAPI 后端、模型 provider、质检和日志服务
├── scripts/                  # 控制变量测试、质量分析等辅助脚本
├── cloudbase/                # 腾讯云函数部署包装
├── ai-image-mvp/             # 早期 Streamlit MVP
├── 电商图片获取/             # 电商素材采集与过滤脚本
├── 业务资料/                 # PRD、提示词、素材与业务调研资料
├── 解决方案/                 # 产品化、部署、技术路线方案文档
├── 日志/                     # 生成迭代记录、测试结果和阶段总结
├── scf_index.py              # 云函数入口适配
└── vercel.json               # Vercel 前端构建配置
```

## 本地开发

### 1. 启动后端

建议使用 Python 3.10 或 3.11。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/config
```

### 2. 启动前端

```bash
cd frontend
npm ci
npm run dev
```

默认前端会请求 `http://localhost:8000`。如果后端部署在其他地址，可在 `frontend/.env` 中配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 3. 配置模型 Key

后端会从环境变量读取模型配置。至少配置一个可用通道。

ZenMux：

```env
DEFAULT_PROVIDER=zenmux
ZENMUX_API_KEY=your_zenmux_api_key
ZENMUX_BASE_URL=https://zenmux.ai/api/vertex-ai
ZENMUX_IMAGE_MODEL=openai/gpt-image-2
```

Doubao / Volcengine Ark：

```env
DEFAULT_PROVIDER=doubao
ARK_API_KEY=your_ark_api_key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_IMAGE_MODEL=doubao-seedream-5-0-260128
DOUBAO_IMAGE_SIZE=2K
```

OpenAI-compatible / DeepRouter：

```env
DEFAULT_PROVIDER=openai_compatible
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://deeprouter.top/v1
OPENAI_IMAGE_MODEL=gpt-image-2
```

不要把真实 API Key 写入代码、文档示例文件或提交到仓库。

## API 概览

- `GET /api/health`：后端健康检查。
- `GET /api/config`：返回前端可安全展示的 provider、模型、尺寸、质量和连接状态。
- `POST /api/generations`：上传参考图并同步执行一轮生成任务。
- `POST /api/logs/review`：手动触发迭代日志阶段总结生成。

`POST /api/generations` 使用 `multipart/form-data`，核心字段包括：

- `files[]`：参考图文件，支持 JPG、PNG、WEBP，单次最多 5 张。
- `prompt`：本轮生成提示词。
- `provider_type` / `provider`：模型通道，支持 `zenmux`、`doubao`、`openai_compatible`。
- `model`、`size`、`quality`、`output_format`：模型和输出参数。
- `realistic_mode`：是否追加真实电商图约束。
- `watermark_cleanup_enabled`、`watermark_keywords`：水印清理配置。
- `quality_control_enabled`、`quality_threshold`、`quality_max_retries`：本地质检和重试配置。

## 质检与迭代日志

后端会在生成过程中使用 `backend/services/quality_control.py` 对结果图做本地、确定性的质量检查。检查结果会随接口返回，并写入 `日志/迭代记录/` 和 `日志/generation_iteration_index.json`。

常用辅助脚本：

```bash
python scripts/run_controlled_gpt_image2_iteration.py --limit 1 --quality-max-retries 0
python scripts/analyze_generation_quality.py
```

这些脚本默认读取 `业务资料/提示词/原图/` 和 `日志/测试结果/`，用于控制变量测试、错题归因和质量知识库沉淀。

## 构建与部署

### 前端 Vercel

根目录已有 `vercel.json`，配置为：

- 安装命令：`cd frontend && npm ci`
- 构建命令：`cd frontend && npm run build`
- 输出目录：`frontend/dist`

部署前需要在 Vercel 环境变量里设置：

```env
VITE_API_BASE_URL=https://你的后端域名
```

### 后端腾讯云函数

后端可通过 `scf_index.py` 适配腾讯云函数 HTTP 触发器。更完整的部署说明见：

```text
backend/SCF_DEPLOY.md
```

推荐部署形态：

```text
Vercel React 静态前端
  -> 腾讯云函数 / API Gateway
  -> FastAPI 后端适配入口
  -> ZenMux / Doubao / OpenAI-compatible 图片模型
```

## 早期 MVP

`ai-image-mvp/` 是早期 Streamlit 版本，仍可独立运行和参考。它包含批量上传、provider 切换、风格样图模板和 ZIP 下载等能力。详细说明见：

```text
ai-image-mvp/README.md
```

## 开发注意事项

- 前端代码位于 `frontend/src/`，主要入口为 `App.tsx`、`api.ts`、`types.ts` 和 `styles.css`。
- 后端核心流程位于 `backend/services/generation_service.py`。
- provider 适配器位于 `backend/services/providers/`。
- 提示词增强逻辑位于 `backend/services/prompt_compiler.py`。
- 迭代日志逻辑位于 `backend/services/iteration_logger.py`。
- 真实模型调用会产生费用，批量测试前请确认 `quality_max_retries` 和单次上传数量。
- `日志/` 和 `业务资料/` 中包含大量实验材料，提交前应确认没有密钥、隐私信息或不应公开的客户素材。
