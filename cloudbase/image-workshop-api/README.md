# CloudBase HTTP 云函数部署包

函数名建议：`image-workshop-api`

运行方式：CloudBase HTTP 云函数，`scf_bootstrap` 启动 FastAPI 并监听 `0.0.0.0:9000`。

需要配置的环境变量：

```env
DEFAULT_PROVIDER=zenmux
ALLOWED_ORIGINS=*

ZENMUX_API_KEY=填到腾讯云环境变量
ZENMUX_BASE_URL=https://zenmux.ai/api/vertex-ai
ZENMUX_IMAGE_MODEL=openai/gpt-image-2

ARK_API_KEY=填到腾讯云环境变量
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_IMAGE_MODEL=doubao-seedream-5-0-260128
```

部署包根目录需要包含：

```text
app.py
scf_bootstrap
requirements.txt
third_party/
backend/
```

`third_party/` 由打包脚本安装 Python 依赖生成，不提交到仓库。
