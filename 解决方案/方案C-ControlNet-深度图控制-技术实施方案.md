# 方案C：ControlNet + 深度图控制 - 技术实施方案

## 项目概述

**目标**：使用 ControlNet Depth 技术，在保持产品形态的前提下，改变背景、光线和材质风格

**适用场景**：已有产品图，需要保持产品结构，只改变风格和氛围

**预期效果**：
- 产品形态 100% 保持
- 暖色调自然光线
- 真实材质纹理
- 生活化背景场景
- 精确控制生成结果

---

## 技术架构

### 核心技术栈

```
ComfyUI / Stable Diffusion WebUI
├── SDXL / SD 1.5 基础模型
├── ControlNet Depth 模型
├── 深度估计模型
│   ├── MiDaS (通用深度估计)
│   └── ZoeDepth (高精度深度)
└── 后处理工具
```

### 技术原理

```
原始产品图
    ↓
深度估计 (MiDaS/ZoeDepth)
    ↓
深度图 (Depth Map)
    ↓
ControlNet Depth + 提示词
    ↓
新风格图片（保持结构）
```

### 硬件要求

**最低配置**：
- GPU: NVIDIA RTX 3060 (12GB VRAM)
- RAM: 16GB
- 存储: 50GB SSD

**推荐配置**：
- GPU: NVIDIA RTX 4070 (12GB VRAM)
- RAM: 32GB
- 存储: 100GB NVMe SSD

---

## 实施步骤

### 阶段一：环境搭建（预计 1 天）

#### 1.1 选择实现平台

**方案A：ComfyUI（推荐）**
```bash
# 克隆 ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 安装依赖
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**方案B：Stable Diffusion WebUI**
```bash
# 克隆 WebUI
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui

# 安装（自动）
./webui.sh  # Linux/Mac
# webui-user.bat  # Windows
```

#### 1.2 安装 ControlNet 扩展

**ComfyUI 安装**：
```bash
cd ComfyUI/custom_nodes

# 安装 ControlNet 节点
git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git
cd comfyui_controlnet_aux
pip install -r requirements.txt

# 返回主目录
cd ../..
```

**WebUI 安装**：
```bash
cd stable-diffusion-webui/extensions

# 安装 ControlNet 扩展
git clone https://github.com/Mikubill/sd-webui-controlnet.git
cd sd-webui-controlnet
pip install -r requirements.txt
```

#### 1.3 下载模型文件

**基础模型**：
```bash
cd ComfyUI/models/checkpoints

# SDXL 基础模型（推荐）
wget https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors

# 或 SD 1.5（更快）
# wget https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors
```

**ControlNet Depth 模型**：
```bash
cd ComfyUI/models/controlnet

# SDXL ControlNet Depth
wget https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors -O control_depth_sdxl.safetensors

# SD 1.5 ControlNet Depth（备选）
# wget https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11f1p_sd15_depth.pth
```

**深度估计模型**：
```bash
cd ComfyUI/models/annotators

# MiDaS 深度估计模型（自动下载）
# 首次使用时会自动下载
```

#### 1.4 验证安装

```bash
# 启动 ComfyUI
cd ComfyUI
python main.py

# 访问 http://127.0.0.1:8188
# 检查 ControlNet 节点是否可用
```

---

### 阶段二：深度图提取（预计 0.5 天）

#### 2.1 准备原始产品图

**图片要求**：
```
- 分辨率：至少 1024x1024
- 格式：JPG/PNG
- 内容：清晰的产品图，背景可以是任意
- 光线：不限（会被替换）
```

**文件组织**：
```
project/
├── input_images/          # 原始产品图
│   ├── product_001.jpg
│   ├── product_002.jpg
│   └── ...
├── depth_maps/            # 生成的深度图
└── output_images/         # 最终生成图
```

#### 2.2 ComfyUI 深度图提取工作流

**工作流节点配置**：
```
1. Load Image (加载原始图片)
   ├── image: input_images/product_001.jpg
   
2. MiDaS Depth Estimator (深度估计)
   ├── 连接 Load Image
   ├── model: "DPT_Large" (高质量) 或 "DPT_Hybrid" (平衡)
   
3. Save Image (保存深度图)
   ├── 连接 MiDaS 输出
   ├── filename_prefix: "depth_"
```

**工作流 JSON**：
```json
{
  "1": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "product_001.jpg"
    }
  },
  "2": {
    "class_type": "MiDaS-DepthMapPreprocessor",
    "inputs": {
      "image": ["1", 0],
      "a": 6.283185307179586,
      "bg_threshold": 0.1,
      "resolution": 1024
    }
  },
  "3": {
    "class_type": "SaveImage",
    "inputs": {
      "images": ["2", 0],
      "filename_prefix": "depth_"
    }
  }
}
```

#### 2.3 批量提取深度图

**Python 脚本**：
```python
# batch_extract_depth.py
import os
import json
import requests
import time
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"
INPUT_DIR = "input_images"
OUTPUT_DIR = "depth_maps"

# 加载工作流模板
with open("workflow_depth_extraction.json", "r") as f:
    workflow_template = json.load(f)

# 获取所有输入图片
input_images = list(Path(INPUT_DIR).glob("*.jpg")) + list(Path(INPUT_DIR).glob("*.png"))

print(f"找到 {len(input_images)} 张图片")

for i, img_path in enumerate(input_images):
    print(f"\n[{i+1}/{len(input_images)}] 处理: {img_path.name}")
    
    # 修改工作流
    workflow = workflow_template.copy()
    workflow["1"]["inputs"]["image"] = img_path.name
    workflow["3"]["inputs"]["filename_prefix"] = f"depth_{img_path.stem}_"
    
    # 提交任务
    response = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow}
    )
    
    if response.status_code == 200:
        print(f"✓ 提交成功")
        time.sleep(5)  # 等待处理
    else:
        print(f"✗ 提交失败: {response.text}")

print("\n深度图提取完成!")
```

#### 2.4 深度图质量检查

**检查要点**：
```python
quality_checklist = {
    "边缘清晰度": "产品边缘是否清晰可辨",
    "深度层次": "前景和背景是否有明显区分",
    "细节保留": "产品细节（如把手、纹理）是否保留",
    "噪点控制": "深度图是否平滑，无过多噪点"
}

# 如果深度图质量不佳
solutions = {
    "边缘模糊": "提高 resolution 参数到 2048",
    "细节丢失": "使用 ZoeDepth 替代 MiDaS",
    "噪点过多": "降低 bg_threshold 参数"
}
```

---

### 阶段三：风格化生成（预计 1 天）

#### 3.1 ComfyUI 生成工作流

**完整工作流节点**：
```
1. Load Checkpoint (加载基础模型)
   ├── ckpt_name: sd_xl_base_1.0.safetensors
   
2. Load Image (加载深度图)
   ├── image: depth_maps/depth_product_001.png
   
3. Load ControlNet Model (加载 ControlNet)
   ├── control_net_name: control_depth_sdxl.safetensors
   
4. Apply ControlNet (应用控制)
   ├── conditioning: [来自 CLIP Text Encode]
   ├── control_net: [来自 Load ControlNet]
   ├── image: [来自 Load Image - 深度图]
   ├── strength: 0.8
   
5. CLIP Text Encode (Positive) (正面提示词)
   ├── text: "ceramic mug on wooden table, warm lighting, 2800K..."
   
6. CLIP Text Encode (Negative) (负面提示词)
   ├── text: "cold lighting, studio lighting, white background..."
   
7. KSampler (采样器)
   ├── model: [来自 Load Checkpoint]
   ├── positive: [来自 Apply ControlNet]
   ├── negative: [来自 CLIP Text Encode Negative]
   ├── seed: random
   ├── steps: 30
   ├── cfg: 7.0
   ├── sampler_name: dpmpp_2m
   ├── scheduler: karras
   
8. VAE Decode (解码)
   ├── samples: [来自 KSampler]
   
9. Save Image (保存)
   ├── images: [来自 VAE Decode]
```

#### 3.2 提示词配置

**针对深度图的提示词模板**：
```python
# 基础模板
prompt_template = """
{product_description}, on {scene}, 
warm lighting, 2800K color temperature, 
natural window light from {direction}, soft shadows,
{material} texture visible, lifestyle photography,
shot on iPhone, candid moment, lived-in atmosphere,
shallow depth of field, {background_description}
"""

# 示例
prompt_ceramic_mug = """
ceramic coffee mug, on rustic wooden kitchen table,
warm lighting, 2800K color temperature,
natural morning light from left window, soft shadows,
ceramic glaze texture visible, lifestyle photography,
shot on iPhone, candid moment, lived-in atmosphere,
shallow depth of field, cozy kitchen background with plants
"""

# 负面提示词（重要）
negative_prompt = """
cold lighting, studio lighting, pure white background,
perfect symmetry, overexposed, artificial lighting,
sterile environment, harsh shadows, flat lighting,
no texture, plastic look, CGI, 3D render,
deformed, distorted, wrong proportions, extra objects
"""
```

**关键参数说明**：
```python
controlnet_params = {
    "strength": 0.8,  # 控制强度
    # 0.5-0.7: 较弱控制，允许更多变化
    # 0.8-0.9: 强控制，严格保持形态
    # 1.0: 最强控制，几乎完全保持
    
    "start_percent": 0.0,  # 开始应用的步数百分比
    "end_percent": 1.0     # 结束应用的步数百分比
}

sampler_params = {
    "steps": 30,      # 采样步数（20-40）
    "cfg": 7.0,       # 引导强度（5-10）
    "denoise": 1.0    # 去噪强度（0.8-1.0）
}
```

#### 3.3 批量生成脚本

```python
# batch_generate_controlnet.py
import pandas as pd
import json
import requests
import time
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"

# 读取产品列表
products = pd.read_csv("products.csv")

# 加载工作流模板
with open("workflow_controlnet_depth.json", "r") as f:
    workflow_template = json.load(f)

for index, product in products.iterrows():
    product_id = product['id']
    product_name = product['name']
    material = product['material']
    scene = product['scene']
    
    # 构建提示词
    prompt = f"""
    {material} {product_name}, on {scene},
    warm lighting, 2800K color temperature,
    natural window light, soft shadows,
    {material} texture visible, lifestyle photography,
    shot on iPhone, candid moment, lived-in atmosphere,
    shallow depth of field
    """
    
    # 修改工作流
    workflow = workflow_template.copy()
    workflow["2"]["inputs"]["image"] = f"depth_{product_id}.png"
    workflow["5"]["inputs"]["text"] = prompt
    workflow["4"]["inputs"]["strength"] = 0.8
    
    # 提交生成任务
    print(f"\n生成: {product_name}")
    response = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow}
    )
    
    if response.status_code == 200:
        print(f"✓ 提交成功")
        time.sleep(35)  # 等待生成
    else:
        print(f"✗ 失败: {response.text}")

print("\n批量生成完成!")
```

---

### 阶段四：效果优化（预计 1 天）

#### 4.1 ControlNet 强度调优

**测试不同强度**：
```python
# 对同一产品测试不同 ControlNet 强度
test_strengths = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

for strength in test_strengths:
    print(f"测试强度: {strength}")
    workflow["4"]["inputs"]["strength"] = strength
    # ... 生成并保存
```

**强度选择指南**：
```
0.5-0.6: 产品形态保留 60-70%，风格变化大
        适合：需要较大风格改变的场景
        
0.7-0.8: 产品形态保留 80-90%，风格适度变化
        适合：大多数电商场景（推荐）
        
0.9-1.0: 产品形态保留 95-100%，风格变化小
        适合：只需微调光线和背景的场景
```

#### 4.2 多阶段控制

**高级技巧：分阶段应用 ControlNet**：
```python
# 前期强控制，后期弱控制
controlnet_schedule = {
    "strength": 0.8,
    "start_percent": 0.0,   # 从第 0% 步开始
    "end_percent": 0.7      # 到第 70% 步结束
}

# 效果：前期严格保持形态，后期允许细节优化
```

#### 4.3 组合多个 ControlNet

**同时使用深度图和其他控制**：
```
ControlNet Depth (主控制)
    ├── strength: 0.8
    └── 保持产品形态

+ ControlNet Canny (边缘控制)
    ├── strength: 0.3
    └── 增强边缘清晰度

+ ControlNet Color (颜色控制)
    ├── strength: 0.4
    └── 保留原始色彩倾向
```

#### 4.4 常见问题解决

**问题1：产品形态变形**
```python
solutions = {
    "原因": "ControlNet 强度太低",
    "解决": [
        "提高 strength 到 0.9",
        "提高 cfg 到 8-9",
        "使用更高质量的深度图"
    ]
}
```

**问题2：背景不够生活化**
```python
solutions = {
    "原因": "提示词不够具体",
    "解决": [
        "详细描述背景场景",
        "添加具体物品（plants, books, etc.）",
        "使用参考图（IP-Adapter）"
    ]
}
```

**问题3：材质不真实**
```python
solutions = {
    "原因": "深度图丢失了材质信息",
    "解决": [
        "在提示词中强化材质描述",
        "降低 ControlNet 强度到 0.7",
        "组合使用 ControlNet Tile（保留细节）"
    ]
}
```

**问题4：光线不够暖**
```python
solutions = {
    "原因": "提示词权重不足",
    "解决": [
        "使用权重语法: (warm lighting:1.4)",
        "在负面提示词中强化: (cold lighting:1.3)",
        "使用专门的暖色调 LoRA"
    ]
}
```

---

### 阶段五：高级功能（预计 1 天）

#### 5.1 结合 IP-Adapter 风格参考

**工作流增强**：
```
原始产品图 → 深度图 → ControlNet Depth
                            ↓
参考风格图 → IP-Adapter  →  组合控制
                            ↓
                        生成新图
```

**节点配置**：
```
1. Load IP-Adapter Model
   ├── model: ip-adapter_sdxl.safetensors
   
2. Load Reference Image (风格参考图)
   ├── image: reference_warm_lifestyle.jpg
   
3. Apply IP-Adapter
   ├── model: [来自 Load IP-Adapter]
   ├── image: [来自 Load Reference Image]
   ├── weight: 0.5
   
4. 连接到 KSampler
   ├── positive: [来自 Apply IP-Adapter + Apply ControlNet]
```

#### 5.2 自动化质量检查

**质量评分脚本**：
```python
# quality_check.py
from PIL import Image
import numpy as np
import cv2

def check_color_temperature(image_path):
    """检查色温是否偏暖"""
    img = Image.open(image_path)
    img_array = np.array(img)
    
    # 计算 R/B 比值
    r_mean = img_array[:,:,0].mean()
    b_mean = img_array[:,:,2].mean()
    rb_ratio = r_mean / b_mean
    
    # rb_ratio > 1.1 表示偏暖
    if rb_ratio > 1.1:
        return "✓ 暖色调", rb_ratio
    else:
        return "✗ 色调偏冷", rb_ratio

def check_texture_clarity(image_path):
    """检查纹理清晰度"""
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # 计算拉普拉斯方差（清晰度指标）
    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    
    if laplacian_var > 100:
        return "✓ 纹理清晰", laplacian_var
    else:
        return "✗ 纹理模糊", laplacian_var

def check_shape_preservation(original_depth, generated_depth):
    """检查形态保持度"""
    # 比较原始深度图和生成图的深度图
    orig = cv2.imread(original_depth, cv2.IMREAD_GRAYSCALE)
    gen = cv2.imread(generated_depth, cv2.IMREAD_GRAYSCALE)
    
    # 计算结构相似度 (SSIM)
    from skimage.metrics import structural_similarity as ssim
    similarity = ssim(orig, gen)
    
    if similarity > 0.85:
        return "✓ 形态保持良好", similarity
    else:
        return "✗ 形态变化较大", similarity

# 批量检查
output_images = Path("output_images").glob("*.png")

for img_path in output_images:
    print(f"\n检查: {img_path.name}")
    
    temp_result, temp_value = check_color_temperature(str(img_path))
    print(f"  色温: {temp_result} ({temp_value:.2f})")
    
    clarity_result, clarity_value = check_texture_clarity(str(img_path))
    print(f"  清晰度: {clarity_result} ({clarity_value:.2f})")
```

#### 5.3 A/B 测试框架

```python
# ab_test.py
import random

# 定义测试变量
test_variants = {
    "A_baseline": {
        "controlnet_strength": 0.8,
        "cfg": 7.0,
        "prompt_weight": 1.0
    },
    "B_strong_control": {
        "controlnet_strength": 0.9,
        "cfg": 8.0,
        "prompt_weight": 1.0
    },
    "C_warm_enhanced": {
        "controlnet_strength": 0.8,
        "cfg": 7.0,
        "prompt_weight": 1.3  # 增强暖色关键词
    },
    "D_texture_focus": {
        "controlnet_strength": 0.7,
        "cfg": 7.5,
        "prompt_weight": 1.0,
        "additional_prompt": "(texture:1.3), (material detail:1.2)"
    }
}

# 为每个产品生成所有变体
for product in products:
    for variant_name, params in test_variants.items():
        print(f"生成 {product['name']} - {variant_name}")
        # ... 使用对应参数生成
        
# 收集用户反馈
# 分析哪个变体效果最好
```

---

## 生产部署

### Docker 部署

**Dockerfile**：
```dockerfile
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# 安装依赖
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip git wget \
    && rm -rf /var/lib/apt/lists/*

# 安装 ComfyUI
WORKDIR /app
RUN git clone https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /app/ComfyUI
RUN pip3 install -r requirements.txt
RUN pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 安装 ControlNet
WORKDIR /app/ComfyUI/custom_nodes
RUN git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git
WORKDIR /app/ComfyUI/custom_nodes/comfyui_controlnet_aux
RUN pip3 install -r requirements.txt

# 复制模型
COPY models/ /app/ComfyUI/models/

WORKDIR /app/ComfyUI
EXPOSE 8188
CMD ["python3", "main.py", "--listen", "0.0.0.0"]
```

### API 服务

```python
# api_server.py
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import requests
import json
import uuid
import os

app = FastAPI()

COMFYUI_URL = "http://localhost:8188"

@app.post("/generate")
async def generate_with_depth(
    image: UploadFile = File(...),
    prompt: str = "",
    controlnet_strength: float = 0.8
):
    # 保存上传的图片
    image_id = str(uuid.uuid4())
    input_path = f"temp/{image_id}_input.png"
    
    with open(input_path, "wb") as f:
        f.write(await image.read())
    
    # 1. 提取深度图
    depth_workflow = load_workflow("depth_extraction.json")
    depth_workflow["1"]["inputs"]["image"] = input_path
    
    response = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": depth_workflow})
    # ... 等待完成
    
    # 2. 生成新图
    gen_workflow = load_workflow("controlnet_generation.json")
    gen_workflow["2"]["inputs"]["image"] = f"depth_{image_id}.png"
    gen_workflow["5"]["inputs"]["text"] = prompt
    gen_workflow["4"]["inputs"]["strength"] = controlnet_strength
    
    response = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": gen_workflow})
    # ... 等待完成
    
    output_path = f"outputs/{image_id}_output.png"
    return FileResponse(output_path)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 成本估算

### 一次性成本

| 项目 | 成本 | 说明 |
|------|------|------|
| GPU 硬件 | ¥3,000 - ¥8,000 | RTX 3060/4070 |
| 开发时间 | ¥0 | 开源工具 |
| **总计** | **¥3,000 - ¥8,000** | |

### 运营成本

| 项目 | 成本 | 说明 |
|------|------|------|
| 电费 | ¥40 - ¥150/月 | 取决于使用频率 |
| 云 GPU | ¥2 - ¥8/小时 | 按需使用 |

---

## 成功指标

- [ ] 产品形态保持度 > 90%
- [ ] 色温满意度 > 80%
- [ ] 生成速度 < 40 秒/张
- [ ] 批量一致性 > 85%

---

## 时间线

| 阶段 | 工期 |
|------|------|
| 环境搭建 | 1 天 |
| 深度图提取 | 0.5 天 |
| 风格化生成 | 1 天 |
| 效果优化 | 1 天 |
| 高级功能 | 1 天 |
| **总计** | **4.5 天** |

---

## 下一步行动

1. [ ] 搭建 ComfyUI + ControlNet 环境
2. [ ] 准备 10 张测试产品图
3. [ ] 提取深度图并验证质量
4. [ ] 生成首批测试图片
5. [ ] 优化参数并批量生产

---

**文档版本**：v1.0  
**创建日期**：2026-04-24  
**适用场景**：需要精确控制产品形态的电商图片生成
