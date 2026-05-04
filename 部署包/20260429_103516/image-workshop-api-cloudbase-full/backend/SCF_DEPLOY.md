# 图像工坊腾讯云函数部署说明

本文按你之前的腾讯云函数做法整理，目标是让 React 静态站点只调用自己的云函数，真实模型 Key 只放在腾讯云函数环境变量里。

## 1. 部署形态

```text
Vercel 静态 React 前端
  -> HTTPS 请求
  -> 腾讯云函数 HTTP 触发器 / API Gateway
  -> backend FastAPI 适配入口
  -> ZenMux / Doubao / OpenAI-compatible
```

前端需要配置：

```env
VITE_API_BASE_URL=https://你的腾讯云函数访问域名
```

云函数需要配置模型 Key，不需要把 Key 写进前端。

## 2. 云函数配置建议

```text
函数名称：image-workshop-api
运行环境：Python 3.10 或 Python 3.11
内存：1024MB 起步
超时时间：300 秒
触发方式：API Gateway / HTTP 触发器
请求方式：ANY 或 GET/POST/OPTIONS
执行方法：scf_index.main_handler
```

如果 API Gateway 路径前面带了固定前缀，例如 `/release`，通常不需要额外配置；适配器会自动截取 `/api/...`。如果你的网关路径比较特殊，可以在环境变量里配置：

```env
SCF_PATH_PREFIX=/release
```

## 3. 必填环境变量

至少配置一个真实图片模型通道。

```env
# 建议第一版只配置正式演示要用的通道
DEFAULT_PROVIDER=zenmux

# 前端域名，Vercel 部署后改成真实域名；开发阶段可不填
ALLOWED_ORIGINS=https://你的-vercel-域名.vercel.app

# ZenMux
ZENMUX_API_KEY=填腾讯云函数环境变量
ZENMUX_BASE_URL=https://zenmux.ai/api/vertex-ai
ZENMUX_IMAGE_MODEL=openai/gpt-image-2

# Doubao / Volcengine Ark
ARK_API_KEY=填腾讯云函数环境变量
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_IMAGE_MODEL=doubao-seedream-5-0-260128

# OpenAI-compatible / DeepRouter
OPENAI_API_KEY=填腾讯云函数环境变量
OPENAI_BASE_URL=https://deeprouter.top/v1
OPENAI_IMAGE_MODEL=grok-4-image
```

说明：

- `ALLOWED_ORIGINS` 可以填多个，用英文逗号分隔。
- 内部小范围演示阶段，若域名还没确定，可以临时设为 `*`。
- 不建议把模型 Key、腾讯云 SecretId、腾讯云 SecretKey 放进前端仓库。

## 4. 上传代码

推荐从项目根目录打包，确保压缩包根目录包含：

```text
backend/
scf_index.py
```

依赖可按 `backend/scf_requirements.txt` 安装或在云函数控制台依赖管理里配置。

本地验证入口：

```bash
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

云函数验证入口：

```bash
curl 'https://你的腾讯云函数域名/api/health'
curl 'https://你的腾讯云函数域名/api/config'
```

预期健康检查：

```json
{"ok":true,"service":"ai-image-backend","version":"0.1.0"}
```

## 5. 前端对接

Vercel 项目里配置环境变量：

```env
VITE_API_BASE_URL=https://你的腾讯云函数域名
```

然后重新部署前端。浏览器只会请求：

```text
GET  /api/config
POST /api/generations
```

## 6. 需要你后续提供或操作的内容

- 腾讯云函数控制台访问权限，或你自己按本文创建函数。
- 云函数 HTTP 触发器公网地址。
- Vercel 部署后的正式前端域名，用于回填 `ALLOWED_ORIGINS`。
- 最终要启用的模型通道和对应 Key。
