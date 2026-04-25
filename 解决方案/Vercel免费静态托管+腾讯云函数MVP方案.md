# Vercel 免费静态托管 + 腾讯云函数 MVP 方案

更新时间：2026-04-25

## 1. 最终方案结论

当前第一版目标不是正式商用，而是：

```text
做一个可以发网址给内部小伙伴访问的真实可演示版本。
```

最终选择：

```text
React 前端：Vercel 免费静态托管
真实生成接口：腾讯云函数 Web Function
图片模型：继续使用现有 ZenMux / Doubao API Key
数据库：第一版不做
永久图片存储：第一版不做
登录系统：第一版不做
```

整体链路：

```text
用户浏览器
  ↓
Vercel 静态 React 页面
  ↓
腾讯云函数 HTTP API
  ↓
ZenMux / Doubao 图片生成 API
  ↓
腾讯云函数返回生成图片
  ↓
React 前端展示结果
```

这个方案的核心价值：

```text
1. 前端有正式产品 UI，客户和内部同事能直接打开网址体验。
2. API Key 不暴露在浏览器里。
3. 不需要买云服务器。
4. 不需要数据库、OSS、队列，第一版成本最低。
5. 后续如果要商用，可以平滑升级到云服务器 / 容器 / 对象存储。
```

## 2. 为什么不能只做纯静态 React

纯 React 可以做：

```text
上传预览
漂亮 UI
提示词输入
模型选择
结果占位
假进度条
Mock 结果图
```

但是只要要真实调用：

```text
ZenMux
Doubao
OpenAI-compatible
```

就必须有服务端代理。

原因：

```text
浏览器里的 React 代码无法安全保存 API Key。
前端 .env 里的 VITE_XXX 变量会被打包进浏览器代码。
用户打开开发者工具就能看到请求地址和密钥。
```

因此真实生成的最低限度架构是：

```text
React 静态页面
  ↓
云函数代理
  ↓
模型 API
```

## 3. 第一版功能范围

### 3.1 真实功能

第一版必须真实可用：

```text
1. 上传图片
2. 图片预览
3. 输入提示词
4. 选择模型通道
5. 选择模型
6. 开启真实电商审美模式
7. 点击生成
8. 展示生成进度
9. 展示生成结果
10. 下载结果图
```

### 3.2 视觉占位功能

可以先只做 UI，不做真实逻辑：

```text
编辑
批量高级队列
历史记录
素材库
自动化
通知
用户头像
额度明细
API 文档入口
```

点击后可以提示：

```text
该功能即将开放
```

### 3.3 第一版不做

明确不做：

```text
登录注册
数据库
团队管理
支付
额度扣费系统
永久图片存储
历史记录持久化
复杂任务队列
AI 自动质检
自动重试多轮优化
```

## 4. 前端方案

### 4.1 技术栈

```text
React
Vite
TypeScript
Tailwind CSS
shadcn/ui 或 Radix UI
lucide-react
TanStack Query
Zustand
```

### 4.2 前端部署

平台：

```text
Vercel Hobby / 免费静态托管
```

说明：

- Vercel 适合托管 React/Vite 静态前端。
- 第一版不在 Vercel 上跑图片生成函数，只放静态页面。
- Vercel 官方限制中，Hobby 项目有部署次数、静态文件上传大小、域名数量、构建时间等限制；第一版静态演示通常够用。
- Vercel 官方文档中，Hobby 的静态文件上传限制为 100MB，单日部署数为 100 次，构建时间为 45 分钟。

### 4.3 前端环境变量

只放公开配置：

```env
VITE_API_BASE_URL=https://你的腾讯云函数网关地址
VITE_APP_NAME=图像工坊
```

不要放：

```env
ZENMUX_API_KEY
DOUBAO_API_KEY
ARK_API_KEY
OPENAI_API_KEY
```

### 4.4 前端页面结构

```text
frontend/
├── package.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── AppShell.tsx
│   │   ├── Sidebar.tsx
│   │   ├── TopBar.tsx
│   │   ├── PromptPanel.tsx
│   │   ├── UploadPreview.tsx
│   │   ├── ModelSettings.tsx
│   │   ├── ResultsGrid.tsx
│   │   └── BatchQueue.tsx
│   ├── api/
│   │   └── client.ts
│   ├── store/
│   │   └── generationStore.ts
│   └── styles/
│       └── globals.css
```

### 4.5 UI 风格

参考方向：

```text
左侧导航
中间生成工作区
右侧结果网格
底部任务队列
顶部状态栏
```

页面名：

```text
图像工坊
```

视觉关键词：

```text
干净
专业
SaaS 工具感
浅灰背景
绿色主按钮
图片卡片
细进度条
真实电商工作台
```

## 5. 腾讯云函数方案

### 5.1 云函数定位

腾讯云函数不是完整后端系统，只做：

```text
1. 接收前端上传的图片和提示词
2. 读取服务端环境变量中的真实 API Key
3. 调用 ZenMux / Doubao
4. 返回生成结果
```

不做：

```text
数据库
登录
权限
历史存储
任务持久化
复杂队列
```

### 5.2 云函数类型

建议使用：

```text
腾讯云函数 SCF Web Function
Python Custom Runtime 或 Python Runtime + bootstrap
```

腾讯云官方 Web Function 文档说明：

- Web Function 可以通过 API Gateway 生成访问 URL。
- Web Function 需要配置 `scf_bootstrap` 启动文件。
- `scf_bootstrap` 用于启动 Web 服务。

### 5.3 后端技术栈

```text
FastAPI
Uvicorn
Pillow
requests
google-genai
python-multipart
pydantic
```

### 5.4 后端目录结构

```text
serverless-api/
├── main.py
├── requirements.txt
├── scf_bootstrap
├── services/
│   ├── doubao_seedream.py
│   ├── zenmux_vertex.py
│   ├── openai_compatible.py
│   └── prompt_compiler.py
├── utils/
│   ├── image_utils.py
│   └── response_utils.py
└── README.md
```

### 5.5 最小 API 设计

第一版只需要 3 个接口。

#### 健康检查

```text
GET /health
```

返回：

```json
{
  "ok": true,
  "service": "liuliu-image-api"
}
```

#### 模型配置

```text
GET /models
```

返回：

```json
{
  "defaultProvider": "zenmux",
  "providers": [
    {
      "id": "zenmux",
      "name": "ZenMux / Vertex AI",
      "models": ["openai/gpt-image-2", "bytedance/doubao-seedream-5.0-lite"]
    },
    {
      "id": "doubao",
      "name": "Doubao Seedream / Ark",
      "models": ["doubao-seedream-5-0-260128"]
    }
  ]
}
```

#### 图片生成

```text
POST /generate
Content-Type: multipart/form-data
```

请求字段：

```text
image: 上传图片
prompt: 用户提示词
provider: zenmux 或 doubao
model: 模型名
realistic_mode: true / false
output_format: png / jpg
```

返回方式：

第一版建议直接返回 JSON + base64：

```json
{
  "ok": true,
  "filename": "result.png",
  "mimeType": "image/png",
  "imageBase64": "iVBORw0KGgo..."
}
```

这样第一版不需要 COS/OSS，也不需要文件存储。

如果图片过大，第二版再改成：

```text
上传到 COS
返回 resultUrl
```

### 5.6 环境变量

腾讯云函数中配置：

```env
ZENMUX_API_KEY=sk-ai-v1-xxx
ZENMUX_BASE_URL=https://zenmux.ai/api/vertex-ai
ZENMUX_MODEL=openai/gpt-image-2

DOUBAO_API_KEY=d947dc47-xxx
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-seedream-5-0-260128

ALLOWED_ORIGINS=https://你的-vercel-域名.vercel.app
```

### 5.7 CORS

FastAPI 需要开启 CORS：

```text
允许 Vercel 前端域名访问腾讯云函数 API。
```

开发期可以临时允许：

```text
http://localhost:5173
https://你的-vercel-域名.vercel.app
```

不要长期使用：

```text
*
```

## 6. 真实电商审美模式

云函数后端要内置提示词编译器。

开关：

```text
realistic_mode = true
```

后端处理：

```text
最终提示词 = 用户提示词 + 真实电商审美模板 + 负面约束
```

内置模板：

```text
画面需要像真实电商卖家实拍，不要 AI 棚拍广告感。
使用暖色自然光，有方向性的柔和阴影，背景生活化但干净。
材质保留真实纹理和轻微使用痕迹，避免塑料感、过度磨皮、冷白背景、过饱和、完美对称。
构图自然，像真实手机拍摄、社媒分享或生活方式产品摄影。
```

这部分直接解决当前遇到的核心问题：

```text
AI 默认审美偏棚拍、冷白、高饱和、塑料感。
```

## 7. 图片处理策略

前端：

```text
1. 上传后先显示本地预览。
2. 限制单张图片大小，例如 20MB。
3. 显示图片文件名、格式、大小。
```

云函数：

```text
1. 用 PIL 校验图片是否有效。
2. 最长边压缩到 2048。
3. 无透明通道转 JPEG，quality=90。
4. 有透明通道保留 PNG。
5. 调用模型。
6. 返回 PNG 或 JPG base64。
```

这样做的原因：

```text
避免微信图片或大 JPG 转 PNG 后体积膨胀，导致云函数或模型 API 请求断开。
```

## 8. 成本判断

### 8.1 第一版成本结构

```text
Vercel 静态前端：免费额度内
腾讯云函数：使用免费/基础额度或极低量调用
图片生成 API：主要真实成本
数据库：无
对象存储：无
云服务器：无
```

### 8.2 主要花钱点

真正主要成本是：

```text
ZenMux / Doubao 图片生成调用
```

其次才是：

```text
腾讯云函数执行时间
公网出流量
```

### 8.3 腾讯云函数免费额度注意

腾讯云官方文档说明：

- SCF 激活后的前三个月有每月免费额度。
- 免费额度包括调用次数、资源使用和公网出流量。
- 三个月后会进入基础套餐/计费规则。
- HTTP 触发函数响应流量不包含在部分免费额度内，需以腾讯云当前账单规则为准。

所以第一版可以低成本试，但要注意：

```text
不要让公开链接无限制传播。
不要被无关用户刷接口。
前端先加简单访问口令。
云函数后端也加一个简单 token。
```

## 9. 安全策略

第一版最小安全措施：

```text
1. API Key 只放腾讯云函数环境变量。
2. 前端永远不出现真实 API Key。
3. 云函数接口加一个简单访问 token。
4. CORS 只允许 Vercel 域名。
5. 限制单张图片大小。
6. 限制单次最多上传图片数量。
7. 每次请求最多生成 1-4 张。
8. 日志中不要打印 API Key 和完整 base64 图片。
```

前端请求头：

```text
X-Demo-Token: 自定义演示口令
```

云函数校验：

```text
如果 token 不匹配，返回 401。
```

## 10. 部署流程

### 10.1 前端部署到 Vercel

步骤：

```text
1. 创建 frontend/ React 项目。
2. 推送到 GitHub。
3. Vercel 导入 GitHub 仓库。
4. Framework 选择 Vite。
5. 设置环境变量 VITE_API_BASE_URL。
6. 部署。
```

Vercel Build 设置：

```text
Build Command: npm run build
Output Directory: dist
```

### 10.2 腾讯云函数部署

步骤：

```text
1. 创建 serverless-api/。
2. 写 main.py FastAPI 应用。
3. 写 scf_bootstrap 启动脚本。
4. 安装依赖到 third_party 或按腾讯云控制台方式打包。
5. 上传代码包到腾讯云函数。
6. 选择 Web Function。
7. 配置环境变量。
8. 配置 API Gateway 触发。
9. 拿到公网访问 URL。
10. 回填到 Vercel 的 VITE_API_BASE_URL。
```

`scf_bootstrap` 示例：

```bash
#!/bin/bash
export PYTHONPATH="./third_party:$PYTHONPATH"
python3 -m uvicorn main:app --host 0.0.0.0 --port 9000
```

注意：

```text
Web Function 的监听端口按腾讯云当前运行环境要求配置，常见为 9000。
```

### 10.3 域名

第一版可以先用：

```text
Vercel 默认域名
腾讯云函数默认网关域名
```

后续再绑定：

```text
前端：image.yourdomain.com
后端：api.yourdomain.com
```

如果域名在阿里云 DNS：

```text
image CNAME 到 Vercel
api CNAME 到腾讯云 API Gateway 自定义域名
```

## 11. 版本规划

### V0.1 静态 UI + 真实单图生成

目标：

```text
内部演示可用。
```

范围：

```text
React UI
Vercel 静态托管
腾讯云函数 /generate
ZenMux / Doubao 调用
上传预览
结果展示
下载结果
假进度条 + 真实完成状态
```

### V0.2 多图批量生成

范围：

```text
多图串行生成
底部任务队列
每张图状态
失败重试
ZIP 下载
```

### V0.3 轻量持久化

范围：

```text
腾讯云 COS 保存结果图
任务历史
简单访问口令
基础用量统计
```

### V1.0 商用准备

范围：

```text
登录
数据库
额度系统
正式对象存储
后端迁移到 CVM / 容器服务
日志监控
错误告警
```

## 12. 当前项目改造步骤

### 第一步：保留 Streamlit

当前 `ai-image-mvp/` 不删除，保留为：

```text
内部调试台
模型连通性验证
provider 逻辑来源
```

### 第二步：新增 frontend/

创建 React 产品界面：

```text
frontend/
```

先做 mock UI，再接真实接口。

### 第三步：新增 serverless-api/

从现有 Streamlit 项目迁移：

```text
services/doubao_seedream.py
services/zenmux_vertex.py
utils/image_utils.py
utils/zip_utils.py
```

只暴露：

```text
GET /health
GET /models
POST /generate
```

### 第四步：前后端联调

本地启动：

```bash
# 后端
cd serverless-api
uvicorn main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm run dev
```

前端本地环境变量：

```env
VITE_API_BASE_URL=http://localhost:8000
```

### 第五步：部署

```text
frontend -> Vercel
serverless-api -> 腾讯云函数
```

## 13. 官方依据

参考官方文档：

```text
Vercel Limits:
https://vercel.com/docs/limits

Tencent Cloud SCF Free Tier:
https://intl.cloud.tencent.com/document/product/583/12282

Tencent Cloud SCF Web Function:
https://www.tencentcloud.com/document/product/583/40689
```

## 14. 最终建议

当前就按这个路线做：

```text
Vercel 免费静态托管
+ 腾讯云函数最小 API 代理
+ 现有 ZenMux / Doubao 真实生成
+ 不接数据库
+ 不接对象存储
+ 不做登录
```

这就是目前最低成本、最少复杂度、又能真实生成图片的客户演示版方案。

后续如果内部反馈好，再升级到：

```text
腾讯云 COS
数据库
正式后端服务
商用部署
```
