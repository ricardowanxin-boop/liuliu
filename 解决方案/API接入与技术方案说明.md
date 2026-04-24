# API 接入与技术方案说明

更新时间：2026-04-24

本文档说明当前 `ai-image-mvp` 项目已经接入或预留的 API 类型、调用方式、模型配置、图片处理链路，以及当前本地配置中的真实 API Key。

> 注意：本文档包含真实密钥，只适合保存在私有仓库或本地受控环境中。

## 1. 当前已配置的真实 Key

配置文件位置：

```text
ai-image-mvp/.streamlit/secrets.toml
```

当前内容：

```toml
[doubao_provider]
api_key = "d947dc47-5257-4e19-9479-59f9c81745b9"
base_url = "https://ark.cn-beijing.volces.com/api/v3"
model = "doubao-seedream-5-0-260128"
size = "2048x2048"

[zenmux_provider]
api_key = "sk-ai-v1-050048c8a1c27722c19572757c956491636fb1b4192023b32190cfb402bcb253"
base_url = "https://zenmux.ai/api/vertex-ai"
model = "openai/gpt-image-2"
```

当前未在 secrets 中配置 OpenAI-compatible / DeepRouter 的真实 Key。如需启用该通道，可通过环境变量或 secrets 配置 `OPENAI_API_KEY`、`DEEPROUTER_API_KEY` 或 `AI_IMAGE_API_KEY`。

## 2. API 通道总览

| 通道 | 用途 | 当前状态 | 默认模型 | 调用协议 |
| --- | --- | --- | --- | --- |
| OpenAI-compatible / DeepRouter | 通用图片编辑兼容接口 | 代码已接入，当前未配置真实 key | `grok-4-image` | OpenAI 风格 `/images/edits` |
| 字节 Doubao Seedream / Ark | 火山方舟图片生成/参考图生成 | 已配置真实 key | `doubao-seedream-5-0-260128` | Ark `/images/generations` |
| ZenMux / Vertex AI | 多模型图片编辑/生成 | 已配置真实 key | `openai/gpt-image-2` | Google Vertex AI 兼容协议 |
| ZenMux Gemini 风格分析 | 本地风格样图分析成提示词模板 | 复用 ZenMux key | `google/gemini-2.5-pro` | Vertex `generate_content` |

## 3. OpenAI-compatible / DeepRouter 通道

代码位置：

```text
ai-image-mvp/services/openai_compatible.py
```

默认配置：

```text
DEFAULT_OPENAI_BASE_URL = "https://deeprouter.top/v1"
DEFAULT_OPENAI_MODEL = "grok-4-image"
```

Key 读取优先级：

```text
环境变量 OPENAI_API_KEY
环境变量 DEEPROUTER_API_KEY
环境变量 AI_IMAGE_API_KEY
Streamlit secrets.OPENAI_API_KEY
Streamlit secrets.DEEPROUTER_API_KEY
Streamlit secrets.AI_IMAGE_API_KEY
Streamlit secrets.provider.api_key
Streamlit secrets.openai_provider.api_key
```

Base URL 读取优先级：

```text
OPENAI_BASE_URL
DEEPROUTER_BASE_URL
secrets.OPENAI_BASE_URL
secrets.DEEPROUTER_BASE_URL
secrets.provider.base_url
secrets.openai_provider.base_url
默认 https://deeprouter.top/v1
```

接口方式：

```text
POST {base_url}/images/edits
Authorization: Bearer {api_key}
Content-Type: multipart/form-data
```

请求内容：

```text
image: 上传图片文件
model: 当前选择模型
prompt: 用户提示词
```

返回解析：

```text
优先读取 data[0].b64_json
如果没有 b64_json，则读取 data[0].url 并下载图片
最终统一转成 PIL Image，再导出 PNG
```

适用场景：

```text
当外部服务兼容 OpenAI 图片编辑接口时，可以直接填入 Base URL、模型名和 API Key 使用。
```

## 4. 字节 Doubao Seedream / Ark 通道

代码位置：

```text
ai-image-mvp/services/doubao_seedream.py
```

当前真实配置：

```text
API Key: d947dc47-5257-4e19-9479-59f9c81745b9
Base URL: https://ark.cn-beijing.volces.com/api/v3
当前模型: doubao-seedream-5-0-260128
当前 size: 2048x2048
```

代码默认值：

```text
DEFAULT_DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DOUBAO_MODEL = "doubao-seedream-5-0-260128"
DEFAULT_DOUBAO_SIZE = "2K"
DOUBAO_SIZE_OPTIONS = ["2K", "4K"]
```

支持模型预设：

```text
doubao-seedream-5-0-260128
- 显示名：Doubao-Seedream-5.0
- response_format: b64_json
- watermark: false

doubao-seedream-4-5-251128
- 显示名：Doubao-Seedream-4.5
- response_format: url
- watermark: false
- extra_payload:
  sequential_image_generation = "disabled"
  stream = false
```

Key 读取优先级：

```text
环境变量 ARK_API_KEY
环境变量 DOUBAO_API_KEY
环境变量 VOLCENGINE_API_KEY
环境变量 LAS_API_KEY
环境变量 API_KEY
Streamlit secrets.ARK_API_KEY
Streamlit secrets.DOUBAO_API_KEY
Streamlit secrets.VOLCENGINE_API_KEY
Streamlit secrets.LAS_API_KEY
Streamlit secrets.API_KEY
Streamlit secrets.doubao_provider.api_key
Streamlit secrets.doubao.api_key
```

接口方式：

```text
POST {base_url}/images/generations
Authorization: Bearer {api_key}
Content-Type: application/json
```

请求 payload 核心字段：

```json
{
  "model": "doubao-seedream-5-0-260128",
  "prompt": "用户提示词",
  "size": "2K 或 4K",
  "response_format": "b64_json",
  "watermark": false,
  "image": "data:image/jpeg;base64,..."
}
```

技术特点：

```text
1. 项目把上传图片作为参考图，编码成 data URL 放入 image 字段。
2. Seedream 5.0 当前走 b64_json 返回，直接 base64 解码得到图片。
3. Seedream 4.5 当前走 url 返回，项目会下载 url 对应图片。
4. 结果统一转成 PIL Image，再按 PNG 导出。
```

## 5. ZenMux / Vertex AI 图片通道

代码位置：

```text
ai-image-mvp/services/zenmux_vertex.py
```

当前真实配置：

```text
API Key: sk-ai-v1-050048c8a1c27722c19572757c956491636fb1b4192023b32190cfb402bcb253
Base URL: https://zenmux.ai/api/vertex-ai
当前模型: openai/gpt-image-2
```

客户端创建方式：

```python
from google import genai
from google.genai import types

client = genai.Client(
    api_key="sk-ai-v1-050048c8a1c27722c19572757c956491636fb1b4192023b32190cfb402bcb253",
    vertexai=True,
    http_options=types.HttpOptions(
        api_version="v1",
        base_url="https://zenmux.ai/api/vertex-ai",
    ),
)
```

支持模型预设：

```text
openai/gpt-image-2                         imagen
sapiens-ai/agnes-image-1.2                 imagen
qwen/qwen-image-2.0-pro                    imagen
qwen/qwen-image-2.0                        imagen
bytedance/doubao-seedream-5.0-lite         imagen
google/gemini-3.1-flash-image-preview      gemini
inclusionai/ming-flash-omni-2.0            gemini
openai/gpt-image-1.5                       imagen
google/gemini-3-pro-image-preview          gemini
google/gemini-2.5-flash-image              gemini
tencent/hunyuan-image3                     imagen
klingai/kling-v2                           imagen
```

ZenMux 有两种调用模式：

### 5.1 imagen 模式

适用模型：

```text
openai/gpt-image-2
openai/gpt-image-1.5
qwen/qwen-image-2.0
qwen/qwen-image-2.0-pro
bytedance/doubao-seedream-5.0-lite
其他标记为 imagen 的模型
```

调用方式：

```python
response = client.models.edit_image(
    model=model,
    prompt=prompt,
    reference_images=[raw_reference_image],
    config=types.EditImageConfig(
        number_of_images=1,
        output_mime_type="image/png",
        add_watermark=False,
    ),
)
```

参考图封装方式：

```python
types.RawReferenceImage(
    reference_id=1,
    reference_image=types.Image(
        image_bytes=image_bytes,
        mime_type="image/jpeg 或 image/png",
    ),
)
```

返回解析：

```text
1. 读取 response.generated_images。
2. 优先读取 image.image_bytes。
3. 兼容 image_bytes 为 bytes、base64 字符串、data URL 的情况。
4. 如果返回 gcs_uri 且是 http/https，则下载图片。
5. 如果结果为空，尝试显示 rai_filtered_reason 或 safety_attributes。
```

### 5.2 gemini 模式

适用模型：

```text
google/gemini-3.1-flash-image-preview
google/gemini-3-pro-image-preview
google/gemini-2.5-flash-image
inclusionai/ming-flash-omni-2.0
```

调用方式：

```python
response = client.models.generate_content(
    model=model,
    contents=[
        types.Content(
            role="user",
            parts=[
                types.Part(text=prompt),
                types.Part(
                    inline_data=types.Blob(
                        data=image_bytes,
                        mime_type="image/jpeg 或 image/png",
                    )
                ),
            ],
        )
    ],
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    ),
)
```

返回解析：

```text
遍历 candidates[].content.parts[]，读取 inline_data.data 中的图片结果。
```

## 6. ZenMux 风格分析通道

代码位置：

```text
ai-image-mvp/services/zenmux_style_analyzer.py
```

用途：

```text
读取本地风格参考图，把 10-20 张电商图片总结成一段可复用的风格提示词模板。
生成图片时可自动把风格模板拼接到用户提示词前面。
```

当前使用的 Key：

```text
复用 ZenMux API Key:
sk-ai-v1-050048c8a1c27722c19572757c956491636fb1b4192023b32190cfb402bcb253
```

默认模型：

```text
google/gemini-2.5-pro
```

模型读取优先级：

```text
环境变量 ZENMUX_STYLE_ANALYZER_MODEL
Streamlit secrets.ZENMUX_STYLE_ANALYZER_MODEL
Streamlit secrets.zenmux_style_analyzer.model
Streamlit secrets.zenmux_provider.style_analyzer_model
默认 google/gemini-2.5-pro
```

调用方式：

```python
response = client.models.generate_content(
    model="google/gemini-2.5-pro",
    contents=[
        "下面是一组电商/品牌风格参考图...",
        "参考图 1：xxx.jpg",
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        "...",
        "分析指令文本",
    ],
    config=types.GenerateContentConfig(
        response_mime_type="text/plain",
        temperature=0.2,
    ),
)
```

输出：

```text
300-600 字中文风格模板提示词。
缓存到 ai-image-mvp/style-references/ 或其 .cache 子目录，后续批量生成可复用。
```

## 7. 图片预处理技术方案

上传图片进入模型前，当前项目会做一次 provider 友好的压缩与标准化。

代码位置：

```text
ai-image-mvp/utils/image_utils.py
```

核心规则：

```text
1. 先用 PIL 读取图片，验证是否为有效图片。
2. 单图像素上限：40,000,000 像素。
3. 发给 provider 前，最长边限制到 2048。
4. 如果图片没有有效透明通道，转成 JPEG，quality=90，降低请求体积。
5. 如果图片有透明通道，保留 PNG。
6. 模型返回结果统一转成 PNG 供页面预览和下载。
```

这一步是为了解决大图或微信图片被转成 PNG 后体积变大，导致接口请求体过大或服务端连接断开的问题。

## 8. 批量处理流程

整体流程：

```text
1. 用户在 Streamlit 页面选择 provider、模型、Base URL。
2. 上传一张或多张商品图。
3. 输入提示词。
4. 可选：读取本地风格样图并生成风格模板。
5. 点击开始生成。
6. 每张图依次处理：
   - 本地校验图片
   - 压缩成 provider 友好格式
   - 构建 provider 输入文件名和 MIME type
   - 调用对应 API
   - 解析 base64 / url / Vertex image bytes
   - 可选执行轻量水印清理
   - 转成 PNG
7. 页面展示成功项和失败项。
8. 支持单张 PNG 下载或 ZIP 打包下载。
```

## 9. 当前建议优先级

当前推荐优先使用：

```text
1. ZenMux / Vertex AI：openai/gpt-image-2
   - 已配置真实 key。
   - 当前 smoke test 可正常返回图片。
   - 支持多模型切换。

2. Doubao Seedream / Ark：doubao-seedream-5-0-260128
   - 已配置真实 key。
   - 返回 b64_json，链路简单稳定。

3. OpenAI-compatible / DeepRouter
   - 代码已接好。
   - 当前未配置真实 key，适合后续接其他兼容服务。
```

## 10. 主要风险与注意事项

```text
1. 文档和 secrets.toml 均包含真实 API Key，只适合私有仓库。
2. 私有仓库仍然可能因为协作者、CI 日志、部署平台配置或未来权限变化暴露密钥。
3. 如果后续部署到 Streamlit Cloud，建议把 key 放到平台 secrets，而不是写死到代码或文档。
4. 大图请求容易触发 provider 超时或断连，因此当前已加入 2048 最长边压缩策略。
5. ZenMux 的模型列表和价格字段可能随平台变化，需要以后按控制台实际信息更新。
```
