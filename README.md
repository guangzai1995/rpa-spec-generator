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

### 本地调试

```bash
# 1. 后端
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 修改 LLM 配置
python main.py

# 2. 前端
cd frontend
npm install
npm run dev
```

### Docker 部署

```bash
# 单镜像一键部署
docker compose up -d

# 或构建镜像
docker build -t rpa-spec-generator .
docker run -p 80:80 -p 8480:8480 rpa-spec-generator
```

### Docker GPU 部署

```bash
# 需要宿主机已安装 NVIDIA Container Toolkit
docker compose up -d --build

# 或直接运行单镜像
docker build -t rpa-spec-generator .
docker run --gpus all -p 80:80 -p 8480:8480 \
	-e WHISPER_DEVICE=cuda \
	rpa-spec-generator
```

说明：

- Docker 镜像默认基于 CUDA runtime 基础镜像构建，不再通过 pip 单独下载超大的 NVIDIA wheel。
- 如果容器启动时没有可用 GPU，后端会自动回退到 CPU 模式，而不是直接崩溃。
- CPU 环境可以直接运行同一份镜像；如需强制 CPU 模式，启动时添加 -e WHISPER_DEVICE=cpu。
- 模型目录、上传文件、转写结果不会被打进构建上下文；请在运行时通过挂载卷或容器内下载模型。

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
├── docker-compose.yml
└── README.md
```
