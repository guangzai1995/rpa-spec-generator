# RPA 需求规格说明书自动生成系统

基于视频解析的 RPA 需求说明书自动生成系统（MVP 版）

## 功能

- 上传业务操作录屏视频
- 填写标准化需求表单
- AI 自动解析视频（ASR + 关键帧提取）
- LLM 结构化拆解（6 模块）
- 自动生成 Word 格式需求规格说明书
- 下载说明书文档

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite
- **ASR**: Faster-Whisper
- **LLM**: OpenAI 兼容接口（DeepSeek / Qwen / GPT）
- **文档生成**: python-docx / docxtpl
- **前端**: React + Vite + TypeScript
- **部署**: Docker

## 快速开始

### 1. 初始化环境文件

```bash
bash deploy.sh --init-env
```

生成 backend/.env 后，至少需要补齐以下配置：

- LLM_API_KEY
- LLM_BASE_URL
- LLM_MODEL
- VISION_API_KEY
- VISION_BASE_URL
- VISION_MODEL

如使用 GPU，还可以按需调整：

- WHISPER_DEVICE=cuda
- WHISPER_DEVICE_INDEX=0
- WHISPER_MODEL_SIZE=large-v3 或 large-v3-turbo

## 运行原理

系统的核心处理链路如下：

1. 用户在前端填写需求表单并上传业务录屏视频。
2. 后端创建需求记录，保存表单数据与视频素材，并将任务状态写入数据库和状态文件。
3. 异步流水线启动后，先读取视频基础信息，再并发执行两件事：
	- 使用 faster-whisper 做 ASR 转录
	- 按时间间隔抽取关键帧截图
4. 如果启用了多模态分析，系统会将采样后的关键帧送入视觉模型，提取页面标题、界面元素和操作线索。
5. 后端把表单信息、ASR 文本和时间线整理成统一上下文，交给 LLM 做结构化拆解，生成流程步骤、业务规则、输入输出、异常处理等内容。
6. 文档生成器根据结构化结果和截图，输出 Word 需求规格说明书；同时可生成流程图、截图标注和相关说明。
7. 前端通过轮询接口读取任务状态，处理完成后提供在线预览和文档下载。

从模块职责看：

- pipeline.py 负责主流水线编排与状态推进
- parser.py 负责视频解析、ASR 和关键帧抽取
- vision_analyzer.py 负责多模态视觉分析
- extractor.py 负责 LLM 结构化拆解
- doc_generator.py 负责 Word 文档与插图生成

整体上，这个系统是“表单输入 + 视频理解 + 多模态分析 + 文档生成”的串联流程，前端只负责提交和展示状态，核心计算都在后端异步完成。

### 2. 本地开发模式

首次启动前，建议先完成本地依赖安装。

系统依赖：

- Python 3.10+
- Node.js 20+
- ffmpeg
- GPU 场景下的 NVIDIA 驱动与 CUDA 运行环境

建议安装步骤：

```bash
# 后端依赖
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 前端依赖
cd ../frontend
npm install
```

使用 deploy.sh 启动本地前后端开发环境：

```bash
# 启动前后端
bash deploy.sh

# 仅启动后端
bash deploy.sh --backend-only

# 仅启动前端
bash deploy.sh --frontend-only

# 仅构建前端 dist
bash deploy.sh --build-only

# 查看状态
bash deploy.sh --status

# 停止本地服务
bash deploy.sh --stop
```

本地开发模式默认行为：

- 后端运行在 http://127.0.0.1:8480
- 前端运行在 http://127.0.0.1:3000
- 日志写入 logs/backend.log 和 logs/frontend.log
- 如果检测到 GPU，会继承当前环境中的 WHISPER_DEVICE_INDEX
- deploy.sh 会创建 backend/.venv，但当前不会自动执行 pip install -r backend/requirements.txt

### 3. Whisper 模型准备

Docker 镜像默认会将 backend/models/pengzhendong 下的模型打包进镜像；本地开发模式则需要自行确认模型目录存在。

默认规则：

- WHISPER_MODEL_SIZE=large-v3 时，默认模型目录为 backend/models/pengzhendong/faster-whisper-large-v3
- WHISPER_MODEL_SIZE=large-v3-turbo 时，默认模型目录为 backend/models/pengzhendong/faster-whisper-large-v3-turbo
- 如已配置 WHISPER_MODEL_DIR，则优先使用该目录

如需手动下载模型，可使用：

```bash
cd backend
source .venv/bin/activate

# 下载默认模型（由 WHISPER_MODEL_SIZE 决定）
python scripts/download_model.py

# 指定模型规格下载
WHISPER_MODEL_SIZE=large-v3 python scripts/download_model.py

# 指定下载目录
WHISPER_MODEL_DIR=models/pengzhendong/faster-whisper-large-v3 \
python scripts/download_model.py
```

模型下载脚本说明：

- 使用 ModelScope 下载 faster-whisper 转换模型
- 现在 `modelscope` 已包含在 backend/requirements.txt 中
- 如果目录下存在 model.bin，容器启动时会自动识别该模型

模型选择建议：

- GPU 优先：large-v3-turbo 或 large-v3
- CPU 优先：small、medium，或显式设置 WHISPER_DEVICE=cpu

### 4. Docker 镜像构建

推荐使用 build.sh 构建镜像，而不是手写 docker build 命令：

```bash
# 默认构建 CUDA 兼容镜像
bash build.sh

# 指定镜像标签
bash build.sh --tag v1.2.3

# 禁用缓存
bash build.sh --no-cache

# 使用默认上游源而不是国内镜像源
bash build.sh --no-mirror

# 自定义 CUDA 基础镜像
bash build.sh --cuda-image nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# 构建后推送镜像
bash build.sh --registry your-registry --push
```

当前默认镜像特性：

- 基于 CUDA runtime 基础镜像构建，默认兼容 GPU 运行
- 无 GPU 时可回退 CPU 模式运行
- 默认会将 backend/models/pengzhendong 下的 Whisper 模型打进镜像
- 已内置中文字体，支持流程图和截图底部中文标注

### 5. Docker 运行

推荐使用 run-container.sh 启动容器：

```bash
# 默认使用宿主机 0 号 GPU，并传入 backend/.env
bash run-container.sh

# 指定宿主机 1 号 GPU
bash run-container.sh --gpu-index 1

# CPU 模式启动
bash run-container.sh --cpu

# 指定镜像名和容器名
bash run-container.sh --image rpa-spec:v1.2.3 --name rpa-spec-prod
```

脚本行为说明：

- 同时通过 --env-file 和只读挂载把 backend/.env 传入容器
- GPU 单卡模式下，宿主机卡号会映射为容器内 WHISPER_DEVICE_INDEX=0
- 默认映射端口为 80 和 8480
- 若存在同名容器，会先删除旧容器再启动新容器

如果你确实需要手动运行 docker run，可以参考：

```bash
# GPU
docker run --rm --gpus all -p 80:80 -p 8480:8480 \
	--env-file backend/.env \
	rpa-spec:latest

# CPU
docker run --rm -p 80:80 -p 8480:8480 \
	--env-file backend/.env \
	-e WHISPER_DEVICE=cpu \
	rpa-spec:latest
```

### 6. 访问地址

- 本地开发前端：http://localhost:3000
- Docker 前端入口：http://localhost
- 后端健康检查：http://localhost:8480/api/health

说明：

- 当前仓库没有可直接使用的 docker-compose.yml，因此 README 不再推荐 compose 部署。
- deploy.sh 的 Docker 模式仍依赖 docker-compose.yml；如果后续补回 compose 文件，再开启这条路径更合理。
- run-container.sh 适合当前仓库的单镜像部署方式。

### 7. 常见问题

- 本地执行 python scripts/download_model.py 报 `No module named modelscope`：重新激活 backend/.venv 后执行 `pip install -r backend/requirements.txt`
- 容器日志提示找不到 Whisper 模型：检查 WHISPER_MODEL_DIR 是否指向包含 model.bin 的目录
- 无 GPU 环境运行：设置 WHISPER_DEVICE=cpu，并优先使用较小模型
- 本地启动后端失败且日志提示 ffmpeg 不存在：先安装系统级 ffmpeg

## 使用流程

1. 打开浏览器访问 http://localhost:3000（开发）或 http://localhost（Docker）
2. 在"设置"页面配置 LLM Provider（DeepSeek / Qwen / OpenAI）
3. 回到首页，填写需求基础信息
4. 上传操作录屏视频
5. 点击"提交并生成说明书"
6. 等待处理完成后下载 Word 文档

## 目录结构

```
rpa-spec-generator/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── requirements.txt
│   ├── app/
│   │   ├── routers/         # API 路由
│   │   │   ├── requirement.py  # 需求 CRUD + 上传 + 提交
│   │   │   ├── spec.py        # 文档下载 + 数据查询
│   │   │   ├── provider.py    # LLM Provider 管理
│   │   │   └── system.py      # 健康检查
│   │   ├── services/         # 业务逻辑
│   │   │   ├── pipeline.py    # 主流水线
│   │   │   ├── parser.py      # 视频解析（ASR + 关键帧）
│   │   │   ├── doc_generator.py  # Word 文档生成
│   │   │   ├── task_executor.py  # 异步任务执行
│   │   │   └── wecom.py       # 企微推送（预留）
│   │   ├── gpt/              # LLM 集成
│   │   │   ├── extractor.py   # 结构化拆解
│   │   │   └── prompts.py     # RPA 专用 Prompt
│   │   ├── db/               # 数据库
│   │   │   ├── engine.py
│   │   │   ├── init_db.py
│   │   │   └── models.py
│   │   └── models/           # Pydantic Schema
│   │       └── schemas.py
│   └── templates/            # Word 模板目录
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── HomePage.tsx    # 需求提交 + 进度 + 下载
│   │   │   └── SettingsPage.tsx # LLM Provider 配置
│   │   └── services/
│   │       └── api.ts          # API 客户端
├── nginx/
│   └── default.conf
├── Dockerfile                 # 单镜像（前后端一体）
├── Dockerfile.backend         # 后端镜像
├── build.sh                   # Docker 镜像构建脚本
├── deploy.sh                  # 本地开发启动脚本
├── run-container.sh           # 单镜像容器启动脚本
└── README.md
```
