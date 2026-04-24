# 方案A：ComfyUI + LoRA 训练 - 技术实施方案

## 项目概述

**目标**：通过训练专属 LoRA 模型，实现批量生成具有一致暖色调、真实生活感的电商产品图

**适用场景**：需要完全控制风格，批量生成大量一致风格的产品图

**预期效果**：
- 暖色调（2800K-3200K 色温）
- 自然光线和方向性阴影
- 真实材质纹理
- 生活化场景氛围
- 手机实拍质感

---

## 技术架构

### 核心技术栈

```
ComfyUI (主工作流平台)
├── SDXL / Flux (基础模型)
├── LoRA Training Nodes (训练模块)
│   ├── ComfyUI-Realtime-Lora (实时训练)
│   ├── Lora-Training-in-Comfy (原生训练)
│   └── ComfyUI-FluxTrainer (Flux专用)
├── Image-Captioning (数据标注)
└── AI-Photography-Toolkit (摄影优化)
```

### 硬件要求

**最低配置**：
- GPU: NVIDIA RTX 3060 (12GB VRAM)
- RAM: 16GB
- 存储: 100GB SSD

**推荐配置**：
- GPU: NVIDIA RTX 4090 (24GB VRAM)
- RAM: 32GB
- 存储: 500GB NVMe SSD

---

## 实施步骤

### 阶段一：环境搭建（预计 1-2 天）

#### 1.1 安装 ComfyUI

```bash
# 克隆 ComfyUI 仓库
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 创建 Python 虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### 1.2 安装 LoRA 训练插件

```bash
cd ComfyUI/custom_nodes

# 方案1：实时训练插件（推荐）
git clone https://github.com/shootthesound/comfyUI-Realtime-Lora.git
cd comfyUI-Realtime-Lora
pip install -r requirements.txt

# 方案2：原生训练节点（备选）
cd ..
git clone https://github.com/LarryJane491/Lora-Training-in-Comfy.git
cd Lora-Training-in-Comfy
pip install -r requirements.txt

# 方案3：Flux 专用训练器（如使用 Flux 模型）
cd ..
git clone https://github.com/kijai/ComfyUI-FluxTrainer.git
cd ComfyUI-FluxTrainer
pip install -r requirements.txt
```

#### 1.3 安装辅助工具

```bash
cd ComfyUI/custom_nodes

# 图片标注工具
git clone https://github.com/LarryJane491/Image-Captioning-in-ComfyUI.git
cd Image-Captioning-in-ComfyUI
pip install -r requirements.txt

# AI 摄影工具包
cd ..
git clone https://github.com/slahiri/ComfyUI-AI-Photography-Toolkit.git
cd ComfyUI-AI-Photography-Toolkit
pip install -r requirements.txt
```

#### 1.4 下载基础模型

```bash
cd ComfyUI/models/checkpoints

# 下载 SDXL 基础模型（推荐）
wget https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors

# 或下载 Flux 模型（更好的真实感）
# wget https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors
```

#### 1.5 验证安装

```bash
cd ComfyUI
python main.py

# 访问 http://127.0.0.1:8188
# 确认所有节点正常加载
```

---

### 阶段二：数据准备（预计 2-3 天）

#### 2.1 收集训练数据

**数据要求**：
- 数量：50-100 张高质量图片
- 分辨率：至少 1024x1024
- 格式：JPG/PNG
- 内容：符合目标风格的真实产品照片

**数据来源**：
1. 自拍产品照片（最佳）
2. 小红书/Instagram 真实用户晒单
3. 淘宝买家秀（需筛选）
4. Unsplash/Pexels 生活化产品摄影

**风格标准**：
```
✅ 必须包含：
- 暖色调光线（黄昏/室内暖光）
- 自然阴影和高光
- 可见的材质纹理
- 生活化场景（桌面/手持/使用中）
- 非完美构图（略微倾斜/非居中）

❌ 避免：
- 纯白背景棚拍
- 冷白色调
- 过度修图
- 完美对称构图
```

#### 2.2 数据预处理

**文件组织**：
```
ComfyUI/
└── training_data/
    └── ecommerce_lifestyle/
        ├── images/
        │   ├── 001.jpg
        │   ├── 002.jpg
        │   └── ...
        └── captions/
            ├── 001.txt
            ├── 002.txt
            └── ...
```

**图片处理脚本**：
```python
# resize_images.py
from PIL import Image
import os

input_dir = "raw_images"
output_dir = "training_data/ecommerce_lifestyle/images"
target_size = 1024

os.makedirs(output_dir, exist_ok=True)

for filename in os.listdir(input_dir):
    if filename.lower().endswith(('.jpg', '.png', '.jpeg')):
        img = Image.open(os.path.join(input_dir, filename))
        
        # 保持宽高比裁剪为正方形
        width, height = img.size
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        img_cropped = img.crop((left, top, left + min_dim, top + min_dim))
        
        # 调整大小
        img_resized = img_cropped.resize((target_size, target_size), Image.LANCZOS)
        
        # 保存
        output_path = os.path.join(output_dir, filename)
        img_resized.save(output_path, quality=95)
        print(f"Processed: {filename}")
```

#### 2.3 批量标注

**使用 ComfyUI 标注工具**：
1. 在 ComfyUI 中加载 Image-Captioning 节点
2. 批量导入训练图片
3. 自动生成基础描述

**标注模板**：
```
[产品类型], warm lighting, 2800K color temperature, 
natural window light from [方向], soft shadows, 
[材质] texture visible, lifestyle photography, 
shot on iPhone, candid moment, lived-in atmosphere,
[场景描述], shallow depth of field
```

**示例标注**：
```
# 001.txt
ceramic mug on wooden table, warm lighting, 2800K color temperature,
natural window light from left, soft shadows, ceramic glaze texture visible,
lifestyle photography, shot on iPhone, candid moment, lived-in atmosphere,
morning coffee scene, shallow depth of field

# 002.txt
cotton t-shirt hanging on chair, warm lighting, 3000K color temperature,
natural afternoon light from right, soft shadows, cotton fabric texture visible,
lifestyle photography, shot on iPhone, candid moment, lived-in atmosphere,
bedroom interior, shallow depth of field
```

#### 2.4 数据验证

**质量检查清单**：
- [ ] 所有图片分辨率一致（1024x1024）
- [ ] 每张图片都有对应的标注文件
- [ ] 标注包含关键词：warm lighting, texture, lifestyle, iPhone
- [ ] 风格一致性达到 80% 以上
- [ ] 无重复或低质量图片

---

### 阶段三：LoRA 训练（预计 1-2 天）

#### 3.1 训练参数配置

**推荐参数（SDXL 基础）**：
```json
{
  "base_model": "sd_xl_base_1.0.safetensors",
  "training_steps": 1500,
  "learning_rate": 0.0001,
  "batch_size": 1,
  "gradient_accumulation_steps": 4,
  "resolution": 1024,
  "lora_rank": 32,
  "lora_alpha": 32,
  "optimizer": "AdamW8bit",
  "lr_scheduler": "cosine",
  "warmup_steps": 100,
  "save_every_n_steps": 250,
  "mixed_precision": "fp16"
}
```

**推荐参数（Flux 模型）**：
```json
{
  "base_model": "flux1-dev.safetensors",
  "training_steps": 2000,
  "learning_rate": 0.0005,
  "batch_size": 1,
  "gradient_accumulation_steps": 4,
  "resolution": 1024,
  "lora_rank": 64,
  "lora_alpha": 64,
  "optimizer": "AdamW8bit",
  "lr_scheduler": "constant_with_warmup",
  "warmup_steps": 200,
  "save_every_n_steps": 500,
  "mixed_precision": "bf16"
}
```

#### 3.2 ComfyUI 训练工作流

**工作流节点配置**：
```
1. Load Checkpoint (加载基础模型)
   ├── ckpt_name: sd_xl_base_1.0.safetensors
   
2. Load Training Images (加载训练数据)
   ├── directory: training_data/ecommerce_lifestyle/images
   ├── caption_directory: training_data/ecommerce_lifestyle/captions
   
3. LoRA Training Node (训练节点)
   ├── 连接 Checkpoint 和 Images
   ├── 设置训练参数（见上方配置）
   
4. Save LoRA (保存模型)
   ├── output_name: ecommerce_lifestyle_v1
   ├── save_path: models/loras/
```

#### 3.3 启动训练

```bash
# 在 ComfyUI 界面中
1. 加载训练工作流（workflow_lora_training.json）
2. 检查所有节点连接正确
3. 点击 "Queue Prompt" 开始训练
4. 监控训练进度和损失曲线
```

**预期训练时间**：
- RTX 3060 (12GB): 约 3-4 小时
- RTX 4070 (12GB): 约 2-3 小时
- RTX 4090 (24GB): 约 1-1.5 小时

#### 3.4 训练监控

**关键指标**：
```
- Loss (损失值): 应逐步下降，最终稳定在 0.1-0.3
- Learning Rate: 按调度器曲线变化
- VRAM Usage: 应保持在 GPU 容量的 80-90%
- Training Speed: 约 1-3 秒/步
```

**中间检查点**：
- 每 250 步保存一次模型
- 在步数 500、1000、1500 时生成测试图
- 对比不同检查点的效果

---

### 阶段四：测试与优化（预计 1-2 天）

#### 4.1 生成测试工作流

**ComfyUI 生成节点配置**：
```
1. Load Checkpoint
   ├── ckpt_name: sd_xl_base_1.0.safetensors
   
2. Load LoRA
   ├── lora_name: ecommerce_lifestyle_v1.safetensors
   ├── strength_model: 0.8
   ├── strength_clip: 0.8
   
3. CLIP Text Encode (Positive)
   ├── text: "ceramic coffee mug on wooden table, warm lighting, 
              2800K color temperature, natural window light, 
              soft shadows, lifestyle photography, shot on iPhone"
   
4. CLIP Text Encode (Negative)
   ├── text: "cold lighting, studio lighting, white background, 
              perfect symmetry, overexposed, artificial"
   
5. KSampler
   ├── seed: random
   ├── steps: 30
   ├── cfg: 7.0
   ├── sampler_name: dpmpp_2m
   ├── scheduler: karras
   
6. VAE Decode → Save Image
```

#### 4.2 测试用例

**测试提示词集**：
```python
test_prompts = [
    # 测试1：陶瓷产品
    "ceramic bowl on kitchen counter, warm morning light, 2800K, natural shadows, lifestyle shot",
    
    # 测试2：纺织品
    "cotton blanket on sofa, warm afternoon light, 3000K, soft texture visible, cozy atmosphere",
    
    # 测试3：木制品
    "wooden cutting board with vegetables, warm kitchen light, 2900K, natural grain texture",
    
    # 测试4：金属产品
    "stainless steel water bottle on desk, warm desk lamp light, 3200K, subtle reflections",
    
    # 测试5：复合场景
    "product flat lay on wooden table, warm natural light from window, 2800K, lifestyle photography"
]
```

**批量生成脚本**：
```python
# batch_generate.py
import json
import requests
import time

comfyui_url = "http://127.0.0.1:8188"

for i, prompt in enumerate(test_prompts):
    workflow = {
        # ... 工作流 JSON 配置
        "3": {"inputs": {"text": prompt}},  # Positive prompt
        "5": {"inputs": {"seed": i * 1000}}  # 不同种子
    }
    
    response = requests.post(f"{comfyui_url}/prompt", json={"prompt": workflow})
    print(f"Generated test image {i+1}/5")
    time.sleep(10)  # 等待生成完成
```

#### 4.3 效果评估

**评估维度**：
```
1. 色温准确性 (0-10分)
   - 是否呈现暖色调
   - 色温是否在 2800K-3200K 范围
   
2. 光线真实性 (0-10分)
   - 是否有方向性阴影
   - 高光是否自然
   
3. 材质细节 (0-10分)
   - 纹理是否清晰可见
   - 材质是否真实
   
4. 生活化氛围 (0-10分)
   - 是否有生活感
   - 构图是否自然
   
5. 整体质量 (0-10分)
   - 清晰度
   - 构图合理性
```

**对比测试**：
```
生成 3 组图片：
1. 不使用 LoRA（基础模型）
2. LoRA strength = 0.5
3. LoRA strength = 0.8
4. LoRA strength = 1.0

对比选出最佳 strength 值
```

#### 4.4 迭代优化

**如果效果不理想**：

**问题1：色温不够暖**
```
解决方案：
- 增加训练数据中暖色调图片比例
- 在标注中强化 "warm lighting, 2800K" 关键词
- 提高 LoRA strength 到 0.9-1.0
```

**问题2：材质不够真实**
```
解决方案：
- 添加更多特写纹理图片
- 在标注中详细描述材质（"visible grain", "rough texture"）
- 增加训练步数到 2000-2500
```

**问题3：风格不一致**
```
解决方案：
- 清理训练数据，移除风格差异大的图片
- 降低 learning rate 到 0.00005
- 增加训练数据量到 100+ 张
```

**问题4：过拟合**
```
解决方案：
- 减少训练步数到 1000
- 降低 LoRA rank 到 16
- 增加数据多样性
```

---

### 阶段五：生产部署（预计 1 天）

#### 5.1 API 封装

**FastAPI 服务**：
```python
# comfyui_api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import json
import uuid
import os

app = FastAPI()

COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = "outputs"

class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = "cold lighting, studio lighting, white background"
    lora_strength: float = 0.8
    steps: int = 30
    cfg: float = 7.0
    seed: int = -1

@app.post("/generate")
async def generate_image(req: GenerateRequest):
    # 加载工作流模板
    with open("workflow_template.json", "r") as f:
        workflow = json.load(f)
    
    # 设置参数
    workflow["3"]["inputs"]["text"] = req.prompt
    workflow["4"]["inputs"]["text"] = req.negative_prompt
    workflow["2"]["inputs"]["strength_model"] = req.lora_strength
    workflow["5"]["inputs"]["steps"] = req.steps
    workflow["5"]["inputs"]["cfg"] = req.cfg
    workflow["5"]["inputs"]["seed"] = req.seed if req.seed > 0 else random.randint(0, 2**32)
    
    # 提交任务
    response = requests.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="ComfyUI generation failed")
    
    prompt_id = response.json()["prompt_id"]
    
    # 等待生成完成（简化版，生产环境需要改进）
    import time
    time.sleep(30)
    
    # 获取生成的图片
    # ... 实现图片获取逻辑
    
    return {"prompt_id": prompt_id, "status": "completed"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### 5.2 批量生产脚本

```python
# batch_production.py
import pandas as pd
import requests
import time

# 读取产品列表
products = pd.read_csv("products.csv")

api_url = "http://localhost:8000/generate"

for index, row in products.iterrows():
    product_name = row['name']
    product_category = row['category']
    
    # 构建提示词
    prompt = f"{product_category} {product_name}, warm lighting, 2800K color temperature, natural window light, soft shadows, lifestyle photography, shot on iPhone, candid moment"
    
    # 调用 API
    response = requests.post(api_url, json={
        "prompt": prompt,
        "lora_strength": 0.8,
        "steps": 30,
        "seed": -1
    })
    
    if response.status_code == 200:
        print(f"Generated image for {product_name}")
    else:
        print(f"Failed to generate image for {product_name}")
    
    time.sleep(35)  # 避免过载
```

#### 5.3 Docker 部署

**Dockerfile**：
```dockerfile
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# 安装 Python 和依赖
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 克隆 ComfyUI
WORKDIR /app
RUN git clone https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /app/ComfyUI

# 安装 Python 依赖
RUN pip3 install -r requirements.txt
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 复制模型和 LoRA
COPY models/checkpoints/* /app/ComfyUI/models/checkpoints/
COPY models/loras/* /app/ComfyUI/models/loras/

# 暴露端口
EXPOSE 8188

# 启动 ComfyUI
CMD ["python3", "main.py", "--listen", "0.0.0.0"]
```

**docker-compose.yml**：
```yaml
version: '3.8'

services:
  comfyui:
    build: .
    ports:
      - "8188:8188"
    volumes:
      - ./outputs:/app/ComfyUI/output
      - ./workflows:/app/ComfyUI/workflows
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  api:
    build: ./api
    ports:
      - "8000:8000"
    depends_on:
      - comfyui
    environment:
      - COMFYUI_URL=http://comfyui:8188
    restart: unless-stopped
```

---

## 成本估算

### 一次性成本

| 项目 | 成本 | 说明 |
|------|------|------|
| GPU 硬件 | ¥5,000 - ¥15,000 | RTX 3060/4070（或云 GPU） |
| 开发时间 | ¥0 | 开源工具，无授权费 |
| 数据收集 | ¥500 - ¥2,000 | 购买/拍摄训练图片 |
| **总计** | **¥5,500 - ¥17,000** | |

### 运营成本

| 项目 | 成本 | 说明 |
|------|------|------|
| 电费 | ¥50 - ¥200/月 | 取决于使用频率 |
| 云 GPU（可选） | ¥2 - ¥10/小时 | AWS/阿里云 GPU 实例 |
| 维护时间 | ¥0 - ¥1,000/月 | 模型更新和优化 |

---

## 风险与应对

### 技术风险

**风险1：训练效果不理想**
- 概率：中
- 影响：高
- 应对：准备多组训练数据，迭代优化参数

**风险2：GPU 资源不足**
- 概率：中
- 影响：中
- 应对：使用云 GPU 或降低分辨率

**风险3：生成速度慢**
- 概率：低
- 影响：中
- 应对：优化工作流，使用批量生成

### 业务风险

**风险4：风格一致性问题**
- 概率：中
- 影响：高
- 应对：严格控制训练数据质量，定期重新训练

**风险5：版权问题**
- 概率：低
- 影响：高
- 应对：使用自拍或授权图片作为训练数据

---

## 成功指标

### 技术指标

- [ ] LoRA 训练损失 < 0.3
- [ ] 生成图片色温在 2800K-3200K 范围
- [ ] 材质纹理清晰可见
- [ ] 生成速度 < 30 秒/张
- [ ] 批量生成风格一致性 > 85%

### 业务指标

- [ ] 用户满意度 > 80%
- [ ] 图片采用率 > 70%
- [ ] 相比 DALL-E 3 成本降低 > 90%
- [ ] 每日可生成 > 100 张图片

---

## 时间线

| 阶段 | 任务 | 工期 | 负责人 |
|------|------|------|--------|
| Week 1 | 环境搭建 + 数据收集 | 3 天 | 技术团队 |
| Week 1-2 | 数据标注 + 预处理 | 2 天 | 数据团队 |
| Week 2 | LoRA 训练 | 2 天 | 技术团队 |
| Week 2-3 | 测试与优化 | 2 天 | 技术+产品 |
| Week 3 | API 开发 + 部署 | 1 天 | 技术团队 |
| **总计** | | **10 天** | |

---

## 下一步行动

### 立即执行（本周）

1. [ ] 采购或租用 GPU 硬件
2. [ ] 搭建 ComfyUI 环境
3. [ ] 开始收集训练数据（目标 50 张）

### 短期计划（2 周内）

4. [ ] 完成数据标注
5. [ ] 完成首次 LoRA 训练
6. [ ] 生成测试图片并评估

### 中期计划（1 个月内）

7. [ ] 优化模型到生产可用
8. [ ] 开发 API 接口
9. [ ] 批量生成测试

---

## 附录

### A. 推荐学习资源

- [ComfyUI 官方文档](https://docs.comfy.org/)
- [LoRA 训练完整教程](https://civitai.com/articles/2000)
- [SDXL 最佳实践](https://stable-diffusion-art.com/sdxl/)

### B. 常见问题

**Q: 训练需要多少张图片？**
A: 最少 50 张，推荐 100+ 张。质量比数量更重要。

**Q: 可以使用 CPU 训练吗？**
A: 理论可行，但速度极慢（可能需要数天）。强烈建议使用 GPU。

**Q: LoRA 模型可以商用吗？**
A: 取决于基础模型的许可证。SDXL 允许商用，Flux 需要查看具体许可。

**Q: 如何更新 LoRA 模型？**
A: 添加新的训练数据，重新训练即可。可以基于旧模型继续训练。

### C. 联系方式

- 技术支持：[技术团队邮箱]
- 项目负责人：[负责人姓名]
- 文档版本：v1.0
- 最后更新：2026-04-24
