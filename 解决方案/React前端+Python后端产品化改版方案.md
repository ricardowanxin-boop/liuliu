# React 前端 + Python 后端产品化改版方案

更新时间：2026-04-24

## 1. 改版目标

当前项目已经验证了核心能力：上传商品图、输入提示词、调用 Doubao / ZenMux / OpenAI-compatible 等图片生成 API，并输出结果图。

但当前 Streamlit 版本更像技术验证 Demo，主要问题是：

- UI 观感偏简陋，不适合直接给客户展示。
- 页面层级不够产品化，上传、提示词、模型配置、结果预览、任务进度混在一起。
- 图片预览、生成进度、批量队列、结果卡片等交互不够直观。
- 后续如果要做登录、项目管理、历史记录、素材库、支付、额度、团队协作，Streamlit 扩展性有限。

本次改版目标：

> 使用 React 重做客户可见前端，保留现有 Python 生成能力作为后端 API，把项目从“技术 Demo”升级为“可给客户演示的电商图片工坊产品原型”。

## 2. 总体方案选择

选择方案：

```text
React 前端 + Python FastAPI 后端
```

不建议继续把主要客户界面堆在 Streamlit 上。Streamlit 可以保留为内部调试工具，但正式演示界面建议迁移到 React。

推荐架构：

```text
用户浏览器
  ↓
React 前端（Vercel 托管）
  ↓
Python FastAPI 后端（复用现有 provider 逻辑）
  ↓
Doubao / ZenMux / OpenAI-compatible 图片模型
  ↓
生成结果返回前端展示
```

## 3. 技术栈建议

### 3.1 前端

```text
React
Vite
TypeScript
Tailwind CSS
shadcn/ui 或 Radix UI
lucide-react 图标
TanStack Query 请求管理
Zustand 轻量状态管理
```

选择原因：

- React 更适合做复杂布局、拖拽上传、结果网格、底部任务队列。
- Tailwind + shadcn 可以快速做出接近 SaaS 产品的高级感。
- TanStack Query 适合管理生成任务、轮询任务状态、缓存结果。
- Zustand 适合管理当前项目、上传图片列表、选中结果、UI 面板状态。

### 3.2 后端

```text
Python
FastAPI
Uvicorn
Pydantic
Pillow
requests
google-genai
```

选择原因：

- 当前图片 provider 逻辑已经是 Python，可以低成本复用。
- FastAPI 适合提供清晰接口给 React 前端。
- 图片处理、压缩、格式转换、结果打包继续使用现有 Python 能力。

### 3.3 后续可选增强

```text
Redis：任务队列和状态缓存
Celery / RQ：长任务异步执行
阿里云 OSS：生成图片存储
PostgreSQL：项目、历史、用户、额度记录
```

第一版客户演示不强依赖这些，可以先用本地内存任务和临时文件。

## 4. UI 改版方向

参考图中的布局方式，但只保留当前业务真实需要的功能。

页面命名建议：

```text
图像工坊
```

整体布局：

```text
┌──────────────────────────────────────────────┐
│ 顶部状态栏：API 状态 / 额度 / 帮助 / 通知 / 用户 │
├──────────┬──────────────────────┬────────────┤
│ 左侧导航 │ 中间生成工作区          │ 右侧结果区  │
│          │                       │            │
├──────────┴──────────────────────┴────────────┤
│ 底部批量队列 / 生成进度条                      │
└──────────────────────────────────────────────┘
```

## 5. 前端页面模块设计

### 5.1 顶部状态栏

真实功能：

- 显示产品名：图像工坊
- API 密钥状态：已连接 / 未配置
- 当前模型通道：ZenMux / Doubao / OpenAI-compatible
- 当前额度展示：第一版可先做静态展示或配置项

占位功能：

- 帮助按钮
- 通知按钮
- 用户头像

第一版不做真实登录，也可以先显示默认头像。

### 5.2 左侧导航

真实功能：

- 生成
- 批量

占位功能：

- 编辑
- 历史记录
- 素材库
- 自动化
- API 文档

交互策略：

- 当前版本只有“生成”真实可用。
- 其他入口可以点击后显示“即将开放”，避免客户觉得功能缺失。

### 5.3 中间生成工作区

真实功能：

- 提示词输入框
- 提示词灵感标签
- 参考图上传
- 上传图片预览
- 模型选择
- 尺寸选择
- 质量选择
- 输出格式选择
- 真实电商审美模式开关
- 高级选项折叠面板
- 生成按钮

推荐提示词区域：

```text
提示词
一张干净的产品照片：薰衣草紫水晶珠与珍珠点缀的手链，放在透明亚克力托盘上。
柔和自然光，白色与浅粉色美学，优雅极简。
```

提示词灵感标签：

```text
产品图
柔和日光
真实阴影
暖色调
生活感
自然陈列
社媒风格
```

点击标签时，把对应短语追加到提示词中。

### 5.4 参考图上传区

真实功能：

- 支持拖拽上传
- 支持点击上传
- 显示缩略图
- 支持删除单张
- 显示文件大小和尺寸

第一版限制：

```text
格式：JPG / PNG / WEBP
单张大小：建议 20MB 内
上传数量：演示版可限制 1-8 张
```

上传后卡片样式：

```text
┌──────────────┐
│   缩略图      │
│ bracelet.jpg │
│ 1024 x 1365  │
└──────────────┘
```

### 5.5 模型配置区

真实功能：

- 模型通道选择
- 模型选择
- 尺寸选择
- 质量选择
- 输出格式选择

建议第一版展示：

```text
模型通道：
- ZenMux
- Doubao
- OpenAI-compatible

模型：
- openai/gpt-image-2
- doubao-seedream-5-0-260128
- bytedance/doubao-seedream-5.0-lite

尺寸：
- 1024 x 1024
- 1024 x 1365
- 1365 x 1024
- 自动

质量：
- 标准
- 高

输出格式：
- PNG
- JPG
```

注意：

真实 API 不一定每个模型都支持所有尺寸。前端可以先显示统一选项，后端根据模型做兼容映射。

### 5.6 真实电商审美模式

这是本次改版的核心能力之一。

UI 位置：

```text
提示词下方或高级选项里
```

建议文案：

```text
真实电商审美模式
避免 AI 棚拍感，强化自然光、真实阴影、生活化陈列和材质细节。
```

开启后，后端自动拼接一段真实电商审美提示词模板。

内置模板方向：

```text
真实自然光，暖色调，柔和但有方向性的光线，保留真实阴影。
生活化陈列，构图自然，不要过度对称，不要商业棚拍。
材质有真实纹理和轻微使用痕迹，避免塑料感、过度磨皮、冷白背景、高饱和、AI 广告图。
画面像真实电商卖家拍摄、社媒分享或生活方式产品摄影。
```

### 5.7 本地风格库的调整

当前“本地风格库”不建议作为主流程大模块展示。

建议改名：

```text
真实样图参考库 / 审美基准库
```

新定位：

- 不是主功能。
- 不是必须步骤。
- 是高级增强能力。

用途：

```text
1. 从真实样图中提取品牌风格提示词。
2. 作为生成后质检的审美参考。
3. 未来作为 LoRA / ControlNet / IP-Adapter 的训练素材库。
```

UI 策略：

- 默认折叠到高级选项。
- 没有样图时不展示大面积空面板。
- 有样图时显示“已读取 N 张参考图”。
- 不默认勾选“自动套用风格模板”。
- 用户点击“分析样图”后才生成模板。

### 5.8 右侧结果区

真实功能：

- 结果网格
- 每张图卡片
- 下载按钮
- 更多按钮
- 选择框
- 结果数量
- 缩放滑杆

卡片样式：

```text
┌────────────────┐
│ □              │
│    结果图片     │
│                │
├────────────────┤
│ 下载       ···  │
└────────────────┘
```

第一版可以只做：

- 下载
- 预览
- 复制图片地址占位

### 5.9 底部批量队列

这是客户感知“专业度”的重点。

真实功能：

- 每张上传图一个任务卡
- 显示缩略图
- 文件名
- 尺寸
- 状态
- 进度条

状态建议：

```text
排队中
上传中
生成中 30%
生成中 70%
已完成
失败
```

卡片样式：

```text
┌─────────────────────────┐
│ 缩略图  bracelet_01.png  · │
│       1024 x 1365        │
│       生成中 70%          │
│       ━━━━━━━───          │
└─────────────────────────┘
```

第一版后端如果无法提供真实百分比，可以用阶段式进度模拟：

```text
10% 读取图片
25% 压缩图片
40% 提交模型
70% 等待生成
90% 解析结果
100% 完成
```

## 6. 后端 API 设计

建议新增后端目录：

```text
backend/
├── main.py
├── api/
│   ├── routes_generation.py
│   ├── routes_config.py
│   └── routes_assets.py
├── services/
│   ├── providers/
│   │   ├── doubao_seedream.py
│   │   ├── openai_compatible.py
│   │   └── zenmux_vertex.py
│   ├── prompt_compiler.py
│   ├── image_preprocess.py
│   └── quality_review.py
├── storage/
│   └── local_store.py
├── schemas/
│   └── generation.py
└── requirements.txt
```

现有 `ai-image-mvp/services/` 里的 provider 可以迁移到 `backend/services/providers/`。

### 6.1 获取配置

```text
GET /api/config
```

返回：

```json
{
  "providers": ["zenmux", "doubao", "openai_compatible"],
  "defaultProvider": "zenmux",
  "models": {
    "zenmux": ["openai/gpt-image-2", "bytedance/doubao-seedream-5.0-lite"],
    "doubao": ["doubao-seedream-5-0-260128"]
  },
  "apiConnected": true
}
```

### 6.2 创建生成任务

```text
POST /api/generations
Content-Type: multipart/form-data
```

请求字段：

```text
files[]: 上传图片
prompt: 用户提示词
provider: zenmux / doubao / openai_compatible
model: 模型名
size: 1024x1365 / auto
quality: standard / high
output_format: png / jpg
realistic_mode: true / false
style_template: 可选
```

返回：

```json
{
  "jobId": "job_20260424_xxx",
  "status": "queued"
}
```

### 6.3 查询任务状态

```text
GET /api/generations/{job_id}
```

返回：

```json
{
  "jobId": "job_20260424_xxx",
  "status": "running",
  "progress": 70,
  "items": [
    {
      "sourceName": "bracelet_01.png",
      "status": "done",
      "progress": 100,
      "resultUrl": "/api/assets/result_01.png"
    },
    {
      "sourceName": "bracelet_02.png",
      "status": "running",
      "progress": 70
    }
  ]
}
```

### 6.4 下载结果图

```text
GET /api/assets/{asset_id}
```

第一版可用本地临时文件返回。

后续正式上线建议改为阿里云 OSS URL。

### 6.5 下载 ZIP

```text
GET /api/generations/{job_id}/download.zip
```

复用当前 `utils/zip_utils.py` 的打包能力。

## 7. 生成质量优化方案

### 7.1 提示词编译器

后端新增：

```text
prompt_compiler.py
```

职责：

```text
用户原始提示词
  +
真实电商审美模板
  +
风格样图模板
  +
模型专用提示词兼容处理
  =
最终发送给模型的提示词
```

示例：

```text
用户提示词：
把手链放在透明亚克力托盘上，生成适合电商展示的图。

编译后：
把手链放在透明亚克力托盘上，生成适合电商展示的图。
画面需要像真实电商卖家实拍，不要 AI 棚拍广告感。
使用暖色自然光，有方向性的柔和阴影，背景生活化但干净。
材质保留真实纹理，避免塑料感、过度磨皮、冷白背景、过饱和、完美对称。
```

### 7.2 生成后质检

第一版可以先做“占位 UI”，第二版接入真实视觉模型质检。

质检维度：

```text
真实感
自然光
材质可信度
构图自然度
电商可用性
AI 棚拍感风险
商品主体是否变形
```

后续自动重试策略：

```text
生成 3 张
↓
AI 打分
↓
保留最高分
↓
低于阈值则自动重试一次
```

### 7.3 商品主体保护

后续可加入：

```text
前景分割
mask 编辑
ControlNet / IP-Adapter
```

第一版先不做复杂图像控制，只在提示词和输入压缩上优化。

## 8. 项目目录建议

推荐最终目录：

```text
刘刘电商解决方案/
├── frontend/
│   ├── package.json
│   ├── index.html
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   │   ├── AppShell.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── PromptPanel.tsx
│   │   │   ├── UploadPreview.tsx
│   │   │   ├── ModelSettings.tsx
│   │   │   ├── ResultsGrid.tsx
│   │   │   └── BatchQueue.tsx
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── store/
│   │   │   └── generationStore.ts
│   │   └── styles/
│   │       └── globals.css
│   └── vite.config.ts
│
├── backend/
│   ├── main.py
│   ├── api/
│   ├── services/
│   ├── schemas/
│   └── requirements.txt
│
├── ai-image-mvp/
│   └── 保留为内部 Streamlit 调试版
│
├── 电商图片获取/
├── 业务资料/
└── 解决方案/
```

## 9. 部署方案

### 9.1 演示版部署

推荐：

```text
前端：Vercel
后端：阿里云 ECS / Render / Railway / Fly.io 任选其一
域名：阿里云 DNS
```

访问链路：

```text
image.yourdomain.com
  ↓ CNAME
Vercel React 前端
  ↓ HTTPS API
api.yourdomain.com
  ↓
Python FastAPI 后端
  ↓
ZenMux / Doubao / OpenAI-compatible
```

### 9.2 阿里云 DNS 配置

前端域名：

```text
主机记录：image
记录类型：CNAME
记录值：Vercel 提供的 CNAME
```

后端域名：

```text
主机记录：api
记录类型：A 或 CNAME
记录值：后端服务器 IP 或服务商域名
```

### 9.3 Vercel 注意事项

适合放：

```text
React 前端
静态资源
客户演示页面
轻量 API 代理
```

不建议放：

```text
长时间图片生成任务
大文件上传处理
真实批量生成队列
大量生成图临时存储
```

所以后端建议独立部署。

### 9.4 国内正式商用注意事项

如果客户主要在中国大陆：

```text
1. Vercel 访问速度和稳定性可能不如国内云。
2. 正式商用建议备案域名。
3. 图片存储建议上阿里云 OSS。
4. 前端可后续迁移到阿里云 OSS + CDN。
5. 后端建议部署到阿里云 ECS / 函数计算 / 容器服务。
```

## 10. 版本规划

### V0.1 客户演示版

目标：

```text
做出图像工坊式 UI，核心生成链路可用，适合给客户看。
```

范围：

- React 前端主界面
- 左侧导航
- 顶部状态栏
- 提示词输入
- 标签灵感
- 参考图上传和预览
- 模型设置
- 真实电商审美模式
- 右侧结果网格
- 底部批量队列
- FastAPI 调用现有 provider
- 单任务生成
- 多图串行生成

不做：

- 登录
- 付费
- 真实额度系统
- 多租户
- 历史记录持久化
- OSS 存储
- AI 自动质检

### V0.2 产品增强版

范围：

- 历史记录
- 本地任务缓存
- ZIP 下载
- 样图参考库优化
- 生成后评分
- 自动重试
- 批量任务状态轮询优化

### V0.3 商用试点版

范围：

- 用户登录
- 项目管理
- 阿里云 OSS
- 数据库
- 额度系统
- 管理后台
- 域名和 HTTPS
- 部署监控

## 11. 实施步骤

### 第一步：搭建 React 前端骨架

```text
创建 frontend/
安装 Vite + React + TypeScript + Tailwind
搭建 AppShell、Sidebar、TopBar、主工作区、结果区、底部队列
先用 mock 数据做完整 UI
```

产出：

```text
一个静态但完整的客户演示界面
```

### 第二步：拆出 Python FastAPI 后端

```text
创建 backend/
迁移现有 provider 代码
封装 /api/config
封装 /api/generations
封装 /api/generations/{job_id}
封装 /api/assets/{asset_id}
```

产出：

```text
React 可以真实调用 Python 后端生成图片
```

### 第三步：接入真实电商审美模式

```text
新增 prompt_compiler.py
内置真实电商审美模板
前端增加开关
后端根据开关拼接提示词
```

产出：

```text
生成结果不再完全依赖模型默认审美
```

### 第四步：结果区和队列体验优化

```text
完善任务状态
完善进度条
完善失败提示
完善结果卡片
支持下载单张
支持下载 ZIP
```

产出：

```text
客户能清楚看到每张图的生成状态和结果
```

### 第五步：部署演示版

```text
前端部署 Vercel
后端部署阿里云 ECS 或其他 Python 服务
阿里云 DNS 绑定域名
配置跨域 CORS
配置 API Key 环境变量
```

产出：

```text
可公网访问的客户演示版本
```

## 12. 风险与处理策略

### 风险 1：生成结果仍然有 AI 棚拍感

处理：

```text
加入真实电商审美提示词模板
加入负面提示词
加入样图风格模板
后续加入 AI 质检和自动重试
```

### 风险 2：大图上传导致接口断连

处理：

```text
前端限制大小
后端最长边压缩到 2048
无透明通道转 JPEG
超时重试
任务失败提示更明确
```

### 风险 3：Vercel 不适合长任务

处理：

```text
Vercel 只放前端
Python 生成服务单独部署
长任务由后端处理
```

### 风险 4：国内访问 Vercel 不稳定

处理：

```text
演示期先用 Vercel
正式商用可迁移到阿里云 OSS + CDN
```

### 风险 5：API Key 泄露

处理：

```text
前端不保存任何真实 key
key 只放后端环境变量
生产环境不把 secrets.toml 提交到公网
限制协作者权限
定期轮换 key
```

## 13. 最终建议

建议立即启动 V0.1：

```text
React 前端先做完整视觉模板
Python 后端复用现有生成逻辑
真实功能只做上传、提示词、模型选择、生成、结果展示、队列进度
其他入口全部做占位
```

这样能最快得到一个“客户能看懂、愿意继续聊”的产品版本。

当前 Streamlit 版本不要删除，可以保留为：

```text
内部调试台
API 测试工具
模型连通性验证页面
```

客户演示和未来产品主线则切到：

```text
React + FastAPI
```
