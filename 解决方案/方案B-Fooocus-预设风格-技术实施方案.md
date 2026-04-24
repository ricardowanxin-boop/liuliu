# 方案B：Fooocus + 预设风格 - 技术实施方案

## 项目概述

**目标**：使用 Fooocus 的内置风格预设，快速生成暖色调、真实生活感的电商产品图

**适用场景**：快速上手，不需要训练模型，适合小规模测试和快速迭代

**预期效果**：
- 暖色调自然光线
- 真实摄影质感
- 生活化场景氛围
- 快速生成（30-60秒/张）

---

## 技术架构

### 核心技术栈

```
Fooocus (简化版 Stable Diffusion)
├── SDXL 基础模型
├── 184+ 内置风格预设
├── 自动参数优化
└── 一键生成界面
```

### 硬件要求

**最低配置**：
- GPU: NVIDIA GTX 1660 (6GB VRAM)
- RAM: 8GB
- 存储: 20GB SSD

**推荐配置**：
- GPU: NVIDIA RTX 3060 (12GB VRAM)
- RAM: 16GB
- 存储: 50GB SSD

---

## 实施步骤

### 阶段一：环境搭建（预计 0.5 天）

#### 1.1 安装 Fooocus

**Windows 安装**：
```bash
# 下载预编译版本（推荐）
# 访问 https://github.com/lllyasviel/Fooocus/releases
# 下载最新的 Fooocus_win64.7z

# 解压后直接运行
run.bat
```

**Linux/Mac 安装**：
```bash
# 克隆仓库
git clone https://github.com/lllyasviel/Fooocus.git
cd Fooocus

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 启动
python launch.py
```

#### 1.2 首次启动

```bash
# 首次启动会自动下载模型（约 6GB）
# 下载内容：
# - SDXL 基础模型
# - VAE 模型
# - ControlNet 模型（可选）

# 启动后访问
http://127.0.0.1:7865
```

#### 1.3 验证安装

```
1. 打开浏览器访问 http://127.0.0.1:7865
2. 输入简单提示词："a coffee mug on table"
3. 点击 Generate
4. 等待 30-60 秒
5. 确认图片正常生成
```

---

### 阶段二：风格预设配置（预计 0.5 天）

#### 2.1 推荐风格预设

**针对电商产品的最佳预设**：

```python
# 按优先级排序
recommended_styles = [
    # 1. 暖色调摄影风格
    "MRE Warm Film",           # 暖色调胶片感 ⭐⭐⭐⭐⭐
    "MRE Photographic",        # 真实摄影风格 ⭐⭐⭐⭐⭐
    "Artstyle Warm Box",       # 温暖氛围 ⭐⭐⭐⭐
    
    # 2. 电影感光线
    "MRE Cinematic Dynamic",   # 电影感自然光 ⭐⭐⭐⭐
    "SAI Cinematic",           # 电影级光影 ⭐⭐⭐⭐
    
    # 3. 生活化场景
    "MRE Lifestyle",           # 生活方式摄影 ⭐⭐⭐⭐
    "Artstyle Cozy Interior",  # 温馨室内 ⭐⭐⭐
    
    # 4. 自然光线
    "MRE Natural Light",       # 自然光摄影 ⭐⭐⭐⭐
    "Artstyle Golden Hour",    # 黄金时段光线 ⭐⭐⭐⭐
]
```

#### 2.2 风格预设测试

**测试脚本**：
```python
# test_styles.py
import requests
import json
import time

fooocus_url = "http://127.0.0.1:7865"

test_prompt = "ceramic coffee mug on wooden table, warm lighting, lifestyle photography"

styles_to_test = [
    "MRE Warm Film",
    "MRE Photographic",
    "MRE Cinematic Dynamic",
    "Artstyle Warm Box",
    "SAI Cinematic"
]

for style in styles_to_test:
    print(f"Testing style: {style}")
    
    # 构建请求
    payload = {
        "prompt": test_prompt,
        "styles": [style],
        "performance": "Quality",
        "aspect_ratio": "1:1"
    }
    
    # 发送请求（需要根据 Fooocus API 调整）
    # response = requests.post(f"{fooocus_url}/api/generate", json=payload)
    
    # 手动测试：在界面中选择风格并生成
    print(f"Please manually test style: {style}")
    input("Press Enter when done...")
```

#### 2.3 创建自定义预设组合

**最佳组合配置**：
```json
{
  "preset_name": "Ecommerce Lifestyle",
  "styles": [
    "MRE Warm Film",
    "MRE Photographic"
  ],
  "performance": "Quality",
  "aspect_ratio": "1:1",
  "image_number": 2,
  "negative_prompt": "cold lighting, studio lighting, white background, perfect symmetry, overexposed, artificial, sterile",
  "guidance_scale": 7.0,
  "sharpness": 2.0,
  "advanced_params": {
    "adm_guidance": 1.5,
    "refiner_switch": 0.8,
    "base_model_name": "juggernautXL_v9Rundiffusionphoto2.safetensors"
  }
}
```

---

### 阶段三：提示词工程（预计 1 天）

#### 3.1 提示词模板

**基础模板**：
```
[产品类型] on [场景], warm lighting, 2800K color temperature, 
natural window light, soft shadows, [材质] texture visible, 
lifestyle photography, shot on iPhone, candid moment, 
lived-in atmosphere, shallow depth of field
```

**具体示例**：

```python
# 陶瓷产品
prompt_ceramic = """
ceramic coffee mug on wooden kitchen table, warm lighting, 
2800K color temperature, natural morning light from window, 
soft shadows, ceramic glaze texture visible, steam rising, 
lifestyle photography, shot on iPhone, candid moment, 
cozy breakfast scene, shallow depth of field
"""

# 纺织品
prompt_textile = """
cotton throw blanket on linen sofa, warm afternoon lighting, 
3000K color temperature, natural side light, soft shadows, 
visible fabric weave texture, cozy living room, 
lifestyle photography, shot on iPhone, lived-in atmosphere, 
shallow depth of field
"""

# 木制品
prompt_wood = """
wooden cutting board with fresh vegetables, warm kitchen lighting, 
2900K color temperature, natural overhead light, soft shadows, 
visible wood grain texture, cooking preparation scene, 
lifestyle photography, shot on iPhone, candid cooking moment, 
shallow depth of field
```

#### 3.2 负面提示词

**通用负面提示词**：
```
cold lighting, studio lighting, pure white background, 
perfect symmetry, overexposed, underexposed, artificial lighting, 
sterile environment, clinical look, harsh shadows, 
flat lighting, no texture, plastic look, CGI, 
3D render, cartoon, illustration
```

**针对特定问题的负面提示词**：
```python
# 如果色调太冷
negative_cold = "cold lighting, blue tint, 5000K+, daylight white, cool tone"

# 如果太像棚拍
negative_studio = "studio lighting, white background, softbox, professional setup, catalog photo"

# 如果材质不真实
negative_texture = "smooth surface, plastic look, no texture, artificial material, CGI"

# 如果构图太完美
negative_perfect = "perfect symmetry, centered composition, professional staging, catalog shot"
```

#### 3.3 提示词优化技巧

**权重调整**：
```
# Fooocus 支持权重语法
(warm lighting:1.3)  # 增强暖光效果
(texture:1.2)        # 增强纹理
(lifestyle:1.1)      # 增强生活感
(studio lighting:0.5) # 在负面提示词中降低权重
```

**分层提示词**：
```
# 主体层
ceramic mug, wooden table

# 光线层
warm lighting, 2800K, natural window light, soft shadows

# 材质层
ceramic glaze texture, wood grain visible

# 氛围层
lifestyle photography, cozy atmosphere, lived-in feel

# 技术层
shot on iPhone, shallow depth of field, candid moment
```

---

### 阶段四：批量生成工作流（预计 1 天）

#### 4.1 产品列表准备

**products.csv**：
```csv
id,name,category,material,scene
1,咖啡杯,陶瓷,ceramic,kitchen table
2,毛毯,纺织品,cotton,sofa
3,砧板,木制品,wood,kitchen counter
4,水杯,玻璃,glass,desk
5,托盘,竹制品,bamboo,dining table
```

#### 4.2 批量生成脚本

```python
# batch_generate_fooocus.py
import pandas as pd
import time
import os
from datetime import datetime

# 读取产品列表
products = pd.read_csv("products.csv")

# 配置
STYLE_PRESET = "MRE Warm Film"
OUTPUT_DIR = "generated_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 提示词模板
def build_prompt(product):
    material = product['material']
    scene = product['scene']
    name = product['name']
    
    prompt = f"""
    {material} {name} on {scene}, warm lighting, 2800K color temperature,
    natural window light, soft shadows, {material} texture visible,
    lifestyle photography, shot on iPhone, candid moment,
    lived-in atmosphere, shallow depth of field
    """
    
    return prompt.strip()

# 负面提示词
NEGATIVE_PROMPT = """
cold lighting, studio lighting, white background, perfect symmetry,
overexposed, artificial, sterile, harsh shadows, flat lighting
"""

# 生成日志
log_file = f"generation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

print("开始批量生成...")
print(f"总计 {len(products)} 个产品")
print(f"风格预设: {STYLE_PRESET}")
print("-" * 50)

for index, product in products.iterrows():
    product_id = product['id']
    product_name = product['name']
    
    prompt = build_prompt(product)
    
    print(f"\n[{index+1}/{len(products)}] 生成: {product_name}")
    print(f"提示词: {prompt[:100]}...")
    
    # 记录到日志
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"产品ID: {product_id}\n")
        f.write(f"产品名称: {product_name}\n")
        f.write(f"提示词: {prompt}\n")
        f.write(f"风格: {STYLE_PRESET}\n")
        f.write(f"时间: {datetime.now()}\n")
    
    # 手动操作说明（因为 Fooocus 没有官方 API）
    print("\n请在 Fooocus 界面中:")
    print(f"1. 粘贴提示词")
    print(f"2. 选择风格: {STYLE_PRESET}")
    print(f"3. 点击 Generate")
    print(f"4. 保存图片为: {OUTPUT_DIR}/{product_id}_{product_name}.png")
    
    input("\n按 Enter 继续下一个产品...")

print("\n" + "="*50)
print("批量生成完成!")
print(f"日志文件: {log_file}")
```

#### 4.3 自动化方案（使用 Selenium）

```python
# auto_generate_fooocus.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd

# 初始化浏览器
driver = webdriver.Chrome()
driver.get("http://127.0.0.1:7865")

# 等待页面加载
time.sleep(5)

# 读取产品列表
products = pd.read_csv("products.csv")

for index, product in products.iterrows():
    try:
        # 构建提示词
        prompt = build_prompt(product)
        
        # 找到提示词输入框
        prompt_box = driver.find_element(By.CSS_SELECTOR, "textarea[placeholder*='prompt']")
        prompt_box.clear()
        prompt_box.send_keys(prompt)
        
        # 选择风格（需要根据实际页面结构调整）
        style_dropdown = driver.find_element(By.ID, "style_select")
        style_dropdown.click()
        style_option = driver.find_element(By.XPATH, f"//option[text()='MRE Warm Film']")
        style_option.click()
        
        # 点击生成按钮
        generate_btn = driver.find_element(By.ID, "generate_button")
        generate_btn.click()
        
        # 等待生成完成（监控进度条）
        WebDriverWait(driver, 120).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".output-image"))
        )
        
        # 下载图片
        # ... 实现下载逻辑
        
        print(f"✓ 完成: {product['name']}")
        time.sleep(5)
        
    except Exception as e:
        print(f"✗ 失败: {product['name']} - {str(e)}")
        continue

driver.quit()
```

---

### 阶段五：质量控制与优化（预计 1 天）

#### 5.1 质量评估标准

**评分表**：
```python
quality_checklist = {
    "色温": {
        "优秀 (9-10分)": "明显暖色调，2800K-3000K",
        "良好 (7-8分)": "偏暖色调，3000K-3500K",
        "及格 (5-6分)": "中性色调，3500K-4000K",
        "不及格 (<5分)": "冷色调，>4000K"
    },
    "光线": {
        "优秀": "自然方向性光线，柔和阴影",
        "良好": "有方向性，阴影略硬",
        "及格": "光线较平，阴影不明显",
        "不及格": "完全平光或过硬阴影"
    },
    "材质": {
        "优秀": "纹理清晰可见，真实感强",
        "良好": "纹理可见，略显平滑",
        "及格": "纹理模糊，真实感一般",
        "不及格": "无纹理，塑料感"
    },
    "氛围": {
        "优秀": "强烈生活感，自然随意",
        "良好": "有生活感，略显刻意",
        "及格": "中性场景，无明显氛围",
        "不及格": "棚拍感，过于完美"
    }
}
```

#### 5.2 A/B 测试

**测试方案**：
```python
# 对同一产品生成多个版本
test_configs = [
    {
        "name": "版本A - 单一风格",
        "styles": ["MRE Warm Film"],
        "guidance_scale": 7.0
    },
    {
        "name": "版本B - 组合风格",
        "styles": ["MRE Warm Film", "MRE Photographic"],
        "guidance_scale": 7.0
    },
    {
        "name": "版本C - 高引导",
        "styles": ["MRE Warm Film"],
        "guidance_scale": 9.0
    },
    {
        "name": "版本D - 低引导",
        "styles": ["MRE Warm Film"],
        "guidance_scale": 5.0
    }
]

# 生成并对比
for config in test_configs:
    print(f"生成 {config['name']}")
    # ... 生成逻辑
    # 保存到对应文件夹
```

#### 5.3 参数优化

**关键参数调优**：
```python
optimization_params = {
    # 如果色调不够暖
    "too_cold": {
        "action": "增强暖色关键词",
        "prompt_addition": "(warm lighting:1.4), (golden hour:1.2)",
        "negative_addition": "(cold lighting:1.3), (blue tint:1.2)"
    },
    
    # 如果材质不够真实
    "texture_lacking": {
        "action": "增强纹理关键词",
        "prompt_addition": "(visible texture:1.3), (material detail:1.2)",
        "sharpness": 3.0  # 提高锐度
    },
    
    # 如果太像棚拍
    "too_studio": {
        "action": "增强生活感",
        "prompt_addition": "(candid:1.3), (lived-in:1.2), (imperfect:1.1)",
        "negative_addition": "(studio:1.4), (professional setup:1.3)"
    },
    
    # 如果构图太完美
    "too_perfect": {
        "action": "增加随意感",
        "prompt_addition": "(casual composition:1.2), (off-center:1.1)",
        "negative_addition": "(perfect symmetry:1.3), (centered:1.2)"
    }
}
```

---

### 阶段六：生产部署（预计 0.5 天）

#### 6.1 标准操作流程（SOP）

**生成流程文档**：
```markdown
# Fooocus 电商图片生成 SOP

## 准备工作
1. 启动 Fooocus: 运行 run.bat 或 python launch.py
2. 等待模型加载完成（约 30 秒）
3. 打开浏览器访问 http://127.0.0.1:7865

## 生成步骤
1. 在 Prompt 框中输入提示词（使用模板）
2. 在 Negative Prompt 框中输入负面提示词
3. 在 Style 下拉菜单中选择 "MRE Warm Film"
4. 设置 Performance 为 "Quality"
5. 设置 Aspect Ratio 为 "1:1" (1024x1024)
6. 设置 Image Number 为 2（生成2张备选）
7. 点击 "Generate" 按钮
8. 等待 30-60 秒
9. 查看生成结果，选择最佳图片
10. 点击图片下载

## 质量检查
- [ ] 色温是否偏暖（黄色调）
- [ ] 是否有自然阴影
- [ ] 材质纹理是否清晰
- [ ] 是否有生活感
- [ ] 构图是否自然

## 如果效果不理想
- 色调太冷 → 在提示词中增加 (warm:1.3)
- 材质不真实 → 在提示词中增加 (texture:1.2)
- 太像棚拍 → 在负面提示词中增加 (studio:1.3)
```

#### 6.2 团队协作配置

**多人使用方案**：
```bash
# 方案1：本地多实例
# 在不同端口启动多个 Fooocus 实例
python launch.py --port 7865  # 用户A
python launch.py --port 7866  # 用户B
python launch.py --port 7867  # 用户C

# 方案2：局域网共享
python launch.py --listen 0.0.0.0 --port 7865
# 团队成员通过 http://[服务器IP]:7865 访问
```

#### 6.3 备份与版本管理

```bash
# 备份生成的图片
backup_dir="backups/$(date +%Y%m%d)"
mkdir -p $backup_dir
cp outputs/*.png $backup_dir/

# 备份配置
cp config.txt $backup_dir/
cp styles.json $backup_dir/

# 版本标记
echo "Generated on $(date)" > $backup_dir/metadata.txt
echo "Style: MRE Warm Film" >> $backup_dir/metadata.txt
```

---

## 成本估算

### 一次性成本

| 项目 | 成本 | 说明 |
|------|------|------|
| GPU 硬件 | ¥2,000 - ¥5,000 | GTX 1660 / RTX 3060（或云GPU） |
| 软件授权 | ¥0 | 完全开源免费 |
| 培训时间 | ¥500 | 1天培训 |
| **总计** | **¥2,500 - ¥5,500** | |

### 运营成本

| 项目 | 成本 | 说明 |
|------|------|------|
| 电费 | ¥30 - ¥100/月 | 取决于使用频率 |
| 云 GPU（可选） | ¥1 - ¥5/小时 | 按需使用 |
| 维护时间 | ¥0 | 几乎无需维护 |

---

## 风险与应对

### 技术风险

**风险1：风格一致性不足**
- 概率：中
- 影响：中
- 应对：使用固定的风格预设和提示词模板

**风险2：无法精确控制**
- 概率：高
- 影响：低
- 应对：通过多次生成选择最佳结果

### 业务风险

**风险3：批量生成效率低**
- 概率：中
- 影响：中
- 应对：使用自动化脚本或多实例并行

---

## 成功指标

### 技术指标

- [ ] 单张图片生成时间 < 60 秒
- [ ] 色温满意度 > 70%
- [ ] 材质清晰度 > 75%
- [ ] 首次通过率 > 60%

### 业务指标

- [ ] 用户满意度 > 75%
- [ ] 图片采用率 > 60%
- [ ] 每日可生成 > 50 张
- [ ] 成本 < ¥0.5/张

---

## 时间线

| 阶段 | 任务 | 工期 |
|------|------|------|
| Day 1 上午 | 环境搭建 | 0.5 天 |
| Day 1 下午 | 风格测试 | 0.5 天 |
| Day 2 | 提示词优化 | 1 天 |
| Day 3 | 批量生成测试 | 1 天 |
| Day 4 | 质量优化 | 1 天 |
| **总计** | | **4 天** |

---

## 下一步行动

### 立即执行（今天）

1. [ ] 下载安装 Fooocus
2. [ ] 测试基础生成功能
3. [ ] 尝试 5 个推荐风格预设

### 短期计划（本周）

4. [ ] 优化提示词模板
5. [ ] 生成 20 张测试图片
6. [ ] 评估效果并调整参数

### 中期计划（2 周内）

7. [ ] 建立标准操作流程
8. [ ] 培训团队成员
9. [ ] 开始批量生产

---

## 附录

### A. 完整风格列表

访问 [Fooocus 风格预设大全](https://github.com/lllyasviel/Fooocus/discussions/143) 查看所有 184 种风格示例

### B. 常见问题

**Q: Fooocus 和 ComfyUI 有什么区别？**
A: Fooocus 更简单易用，ComfyUI 更灵活可定制。Fooocus 适合快速上手。

**Q: 可以商用吗？**
A: 可以，Fooocus 基于 SDXL，允许商业使用。

**Q: 生成速度慢怎么办？**
A: 降低 Performance 设置到 "Speed" 或升级 GPU。

**Q: 如何提高一致性？**
A: 使用固定的 seed 值和相同的风格预设。

### C. 提示词库

```python
# 场景类
scenes = ["kitchen table", "living room sofa", "bedroom nightstand", 
          "office desk", "dining table", "coffee table"]

# 光线类
lighting = ["warm morning light", "soft afternoon light", "golden hour light",
            "cozy evening light", "natural window light"]

# 材质类
materials = ["ceramic glaze", "cotton weave", "wood grain", "linen texture",
             "glass transparency", "metal brushed finish"]

# 氛围类
atmosphere = ["cozy", "lived-in", "candid", "casual", "intimate", "homey"]
```

---

**文档版本**：v1.0  
**创建日期**：2026-04-24  
**最后更新**：2026-04-24  
**适用场景**：快速上手的电商产品图生成方案
