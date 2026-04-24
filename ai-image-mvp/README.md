# ai-image-mvp

一个最小可交付的 Streamlit 图像编辑 MVP：支持批量上传图片，并在 OpenAI-compatible、Doubao Ark 与 ZenMux Vertex AI 图片通道之间切换，逐张处理图片、预览结果并下载单张 PNG 或整包 ZIP。

## 关键能力

- 批量上传多张图片并逐张处理
- 自定义提示词进行图像编辑
- 支持 OpenAI-compatible / DeepRouter、字节 Doubao Seedream / Ark、ZenMux / Vertex AI 三提供商切换
- ZenMux 预置 `openai/gpt-image-2` 与 `bytedance/doubao-seedream-5.0-lite`
- 支持结果预览、单张下载、批量 ZIP 下载
- 支持通过环境变量或 Streamlit secrets 注入 API Key
- 支持从本地 `style-references/` 读取 10-20 张风格样图并生成风格模板
- 支持 ZenMux/Gemini 对风格样图做一次 AI 分析，并缓存为可复用风格模板
- 可选的简单水印清理开关
- 所有结果统一导出为 PNG

## 项目目录结构

```text
ai-image-mvp/
├── app.py
├── README.md
├── requirements.txt
├── .gitignore
├── style-references/
│   └── .gitkeep
├── services/
│   ├── __init__.py
│   ├── doubao_seedream.py
│   ├── openai_compatible.py
│   ├── provider_base.py
│   ├── style_analyzer_base.py
│   ├── zenmux_style_analyzer.py
│   └── zenmux_vertex.py
└── utils/
    ├── __init__.py
    ├── image_utils.py
    ├── style_utils.py
    └── zip_utils.py
```

说明：

- `app.py`：Streamlit 单页入口，负责 UI、配置读取、任务执行与结果下载。
- `services/`：OpenAI-compatible、Doubao Seedream、ZenMux Vertex AI 的 provider，以及独立的 AI 风格分析器。
- `style-references/`：本地风格样图目录。真实样图会被 `.gitignore` 忽略，不会提交。
- `utils/`：图片标准化、风格模板、轻量去水印、文件命名和 ZIP 打包等工具函数。

## 本地运行

### 1. 准备 Python 环境

建议使用 Python 3.10 或 3.11。

```bash
cd /Users/ricardo/文稿/创业/商业计划/刘刘电商解决方案/ai-image-mvp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 API Key

OpenAI-compatible 提供商优先级如下：

1. 环境变量 `OPENAI_API_KEY`
2. 环境变量 `DEEPROUTER_API_KEY`
3. 环境变量 `AI_IMAGE_API_KEY`
4. Streamlit secrets 中的同名字段
5. `st.secrets.provider.api_key`

Doubao Seedream / Ark 提供商优先级如下：

1. 环境变量 `ARK_API_KEY`
2. 环境变量 `DOUBAO_API_KEY`
3. 环境变量 `VOLCENGINE_API_KEY`
4. 环境变量 `LAS_API_KEY`
5. 环境变量 `API_KEY`
5. `st.secrets.doubao_provider.api_key`
6. `st.secrets.doubao.api_key`

ZenMux / Vertex AI 提供商优先级如下：

1. 环境变量 `ZENMUX_API_KEY`
2. Streamlit secrets 中的 `ZENMUX_API_KEY`
3. `st.secrets.zenmux_provider.api_key`
4. `st.secrets.zenmux.api_key`

ZenMux AI 风格分析模型可选配置如下，不配置时默认使用 `google/gemini-2.5-pro`：

1. 环境变量 `ZENMUX_STYLE_ANALYZER_MODEL`
2. Streamlit secrets 中的 `ZENMUX_STYLE_ANALYZER_MODEL`
3. `st.secrets.zenmux_style_analyzer.model`
4. `st.secrets.zenmux_provider.style_analyzer_model`

推荐本地使用环境变量：

```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_IMAGE_MODEL="gpt-image-1"
```

如果你使用 DeepRouter 这类 OpenAI-compatible provider，可改成：

```bash
export DEEPROUTER_API_KEY="your_deeprouter_key_here"
export DEEPROUTER_BASE_URL="https://deeprouter.top/v1"
export OPENAI_IMAGE_MODEL="gpt-image-1"
```

如果你使用字节 Doubao Seedream，可配置：

```bash
export ARK_API_KEY="your_ark_api_key_here"
export ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
export DOUBAO_MODEL="doubao-seedream-5-0-260128"
export DOUBAO_IMAGE_SIZE="2048x2048"
```

如果你使用 ZenMux 调用 `gpt-image-2` 或 `doubao-seedream-5.0-lite`，可配置：

```bash
export ZENMUX_API_KEY="your_zenmux_api_key_here"
export ZENMUX_VERTEX_BASE_URL="https://zenmux.ai/api/vertex-ai"
export ZENMUX_IMAGE_MODEL="openai/gpt-image-2"
export ZENMUX_STYLE_ANALYZER_MODEL="google/gemini-2.5-pro"
```

不要把真实 API Key 写进代码、README、`secrets.toml` 示例文件或提交到 Git 仓库。

### 3. 启动应用

```bash
streamlit run app.py
```

启动后在浏览器中打开 Streamlit 给出的本地地址即可。

### 4. 本地风格样图

把 10-20 张真实电商风格样图放到：

```text
ai-image-mvp/style-references/
```

应用会自动读取 `png`、`jpg`、`jpeg`、`webp` 文件。页面中的“本地风格库”支持两种方式：

- 免费生成基础风格模板：只用 PIL 做本地颜色和构图启发式分析，不调用 API。
- AI 生成风格模板：调用一次 ZenMux/Gemini 分析最多前 12 张样图，生成更细的品牌视觉提示词，并写入本地缓存。

生成图片时勾选“生成时自动套用风格模板”，系统会把风格模板和你的本次提示词自动合并。这个流程是“分析一次、复用多次”，不会在批量生成时对每张图重复分析风格样图。

如果你本地有一个很大的客户素材库，也可以直接在页面的“风格样图目录”里填入外部目录，例如：

```text
/Users/ricardo/文稿/创业/商业计划/刘刘电商解决方案/电商图片获取/downloads/lumi-products-only
```

应用会递归扫描支持的图片格式，并从全部图片里均匀抽样最多 20 张用于本地模板；AI 风格分析最多只发送前 12 张抽样图，避免一次性把几百张图片发给模型。

风格模板缓存文件位于：

```text
ai-image-mvp/style-references/.style-template-cache.txt
```

如果风格样图目录是外部路径，缓存会写入 `ai-image-mvp/style-references/.cache/`，不会修改外部客户素材目录。该目录默认被 `.gitignore` 忽略，避免把真实风格素材或缓存内容提交到仓库。

## Streamlit Cloud 部署

### 1. 推送代码到 Git 仓库

确保仓库中不要包含任何真实密钥，只提交代码和文档。

### 2. 在 Streamlit Cloud 创建应用

- Repository：选择你的仓库
- Branch：选择要部署的分支
- Main file path：填写 `ai-image-mvp/app.py`

### 3. 在 Streamlit Cloud 配置 Secrets

进入应用设置中的 `Secrets`，填入类似下面的内容。

基础 OpenAI-compatible 示例：

```toml
OPENAI_API_KEY = "your_api_key_here"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_IMAGE_MODEL = "gpt-image-1"
```

DeepRouter 兼容示例：

```toml
DEEPROUTER_API_KEY = "your_deeprouter_key_here"
DEEPROUTER_BASE_URL = "https://deeprouter.top/v1"
OPENAI_IMAGE_MODEL = "gpt-image-1"
```

也支持分组写法：

```toml
[provider]
api_key = "your_api_key_here"
base_url = "https://deeprouter.top/v1"
model = "grok-4-image"
```

Doubao Seedream 示例：

```toml
[doubao_provider]
api_key = "your_ark_api_key_here"
base_url = "https://ark.cn-beijing.volces.com/api/v3"
model = "doubao-seedream-5-0-260128"
size = "2048x2048"
```

ZenMux 示例：

```toml
[zenmux_provider]
api_key = "your_zenmux_api_key_here"
base_url = "https://zenmux.ai/api/vertex-ai"
model = "openai/gpt-image-2"
style_analyzer_model = "google/gemini-2.5-pro"
```

也可以单独配置风格分析模型：

```toml
[zenmux_style_analyzer]
model = "google/gemini-2.5-pro"
```

以上内容仅为格式示例，不要填写真实密钥到公开仓库。

## 配置说明

应用默认思路是“提供商切换 + 可配置 Base URL + 可配置模型名”：

- `OpenAI-compatible / DeepRouter`
  - 默认 `Base URL`：`https://deeprouter.top/v1`
  - 默认 `Model`：`grok-4-image`
  - `API Key`：建议使用 `OPENAI_API_KEY` / `DEEPROUTER_API_KEY`
- `Doubao Seedream`
  - 默认 `Base URL`：`https://ark.cn-beijing.volces.com/api/v3`
  - 默认 `Model`：`doubao-seedream-5-0-260128`
  - `API Key`：建议使用 `ARK_API_KEY`
  - Doubao 请求默认会关闭接口侧 `watermark`
- `ZenMux / Vertex AI`
  - 默认 `Base URL`：`https://zenmux.ai/api/vertex-ai`
  - 默认 `Model`：`openai/gpt-image-2`
  - 可切换模型：ZenMux 当前筛选出的 `input=image` 且 `output=image` 模型
  - `API Key`：建议使用 `ZENMUX_API_KEY`

部署到不同 provider 时，只需要切换对应的 API Key、Base URL 和模型名。

## ZenMux 接入说明

ZenMux 图片模型使用 Vertex AI 兼容协议，代码中通过 `google-genai` 创建客户端：

```python
genai.Client(
    api_key="your_zenmux_api_key_here",
    vertexai=True,
    http_options=types.HttpOptions(api_version="v1", base_url="https://zenmux.ai/api/vertex-ai"),
)
```

当前应用对 ZenMux 做了双通道适配：

- `imagen` 类模型：把上传图片作为 `RawReferenceImage`，调用 `client.models.edit_image(...)`。
- `gemini` 类模型：通过 `client.models.generate_content(...)` 传入图片和提示词，并解析返回图片。
- 风格分析器：通过 `services/zenmux_style_analyzer.py` 单独调用 Gemini 图像理解模型，把 `style-references/` 中的样图总结成风格模板。

如果 ZenMux 后台新增或调整模型名，可以在页面输入框、环境变量或 Streamlit secrets 中覆盖 `ZENMUX_IMAGE_MODEL`。

## Doubao 接入说明

如果你要接 `doubao-seedream-5-0-260128`，建议准备这几项：

1. 火山引擎账号，并开通火山方舟对应的图片生成能力。
2. 一个可调用 Ark 图像生成 API 的 `ARK_API_KEY`。
3. 对应地域的 Base URL。北京地域常见值是 `https://ark.cn-beijing.volces.com/api/v3`。
4. 在 Ark Console 中激活你要用的模型服务，例如 `doubao-seedream-5-0-260128`。如果没有激活，接口通常会返回 “has not activated the model ...”。

官方文档参考：
- [火山引擎图片生成 API](https://www.volcengine.com/docs/6492/2172373?lang=zh)
- [火山引擎 Seedream 5.0 发布记录](https://www.volcengine.com/docs/6492/2165228)
- [火山方舟获取 API Key 并配置](https://www.volcengine.com/docs/82379/1541594?lang=zh)
- [火山方舟 Base URL 及鉴权](https://www.volcengine.com/docs/82379/1298459?lang=zh)

## 安全建议

- 不要提交 `.env`、`.streamlit/secrets.toml` 或任何含真实密钥的文件
- 不要提交 `style-references/` 里的真实商业素材图
- 不要把真实 API Key 直接写在 `app.py` 中
- 在共享截图、录屏、日志前，先确认没有暴露密钥

## 当前交付边界

这个 MVP 文档默认面向最小上线版本，重点覆盖：

- 本地快速运行
- Streamlit Cloud 快速部署
- OpenAI-compatible provider 配置方式
- 密钥注入与安全边界

当前交付已经包含 `services/openai_compatible.py`、`services/doubao_seedream.py`、`services/zenmux_vertex.py`、`services/style_analyzer_base.py`、`services/zenmux_style_analyzer.py`、`services/provider_base.py`、`utils/image_utils.py`、`utils/style_utils.py`、`utils/zip_utils.py`，可直接本地运行或部署到 Streamlit Community Cloud。
