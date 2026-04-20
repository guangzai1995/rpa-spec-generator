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
