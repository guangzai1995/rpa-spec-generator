# ================================================================
# RPA 需求规格说明书生成系统 — 全栈环境镜像
# 兼容 CUDA (GPU) / CPU 双模式运行
#
# 构建:
#   docker build -t rpa-spec:latest .
#
# 运行 (GPU):
#   docker run --rm --gpus all -p 80:80 -p 8480:8480 \
#     --env-file backend/.env \
#     rpa-spec:latest
#
# 运行 (CPU):
#   docker run --rm -p 80:80 -p 8480:8480 \
#     --env-file backend/.env \
#     -e WHISPER_DEVICE=cpu \
#     rpa-spec:latest
# ================================================================

ARG CUDA_BASE_IMAGE=nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# ----------------------------------------------------------------
# Stage 1: 前端构建
# ----------------------------------------------------------------
FROM node:20-bookworm-slim AS frontend-builder

# 使用淘宝 npm 镜像加速
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline --registry=$NPM_REGISTRY
COPY frontend/ ./
RUN npm run build

# ----------------------------------------------------------------
# Stage 2: 后端 Python 依赖构建（利用层缓存）
# ----------------------------------------------------------------
FROM ${CUDA_BASE_IMAGE} AS python-deps

# 使用清华 PyPI 镜像加速
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_HOST=pypi.tuna.tsinghua.edu.cn

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN python3 -m venv "$VIRTUAL_ENV" && \
    pip install --upgrade pip -i $PIP_INDEX --trusted-host $PIP_HOST && \
    pip install -r /tmp/requirements.txt -i $PIP_INDEX --trusted-host $PIP_HOST

# ----------------------------------------------------------------
# Stage 3: 最终运行时镜像
# ----------------------------------------------------------------
FROM ${CUDA_BASE_IMAGE} AS runtime

# ---------- Python 运行时环境变量 ----------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# ---------- 系统依赖（最小化） ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    fonts-wqy-zenhei \
    nginx \
    libgomp1 \
    python3 \
    python3-pip \
    && rm -f /etc/nginx/sites-enabled/default \
    && rm -rf /var/lib/apt/lists/*

# ---------- 从 python-deps stage 复制虚拟环境 ----------
COPY --from=python-deps /opt/venv /opt/venv

# ---------- CUDA so 文件权限修复 ----------
RUN find /usr/local/cuda -name "*.so*" -exec chmod a+rx {} \; 2>/dev/null || true && \
    ldconfig 2>/dev/null || true

# ---------- CUDA 库路径（GPU 可用时生效；CPU 环境下无 GPU 也可正常启动） ----------
ENV LD_LIBRARY_PATH="/usr/local/cuda/targets/x86_64-linux/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

# ---------- NVIDIA 容器运行时声明（docker run --gpus all 时自动注入驱动） ----------
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# ---------- 应用代码 ----------
WORKDIR /app

COPY backend/main.py ./backend/main.py
COPY backend/app/ ./backend/app/
COPY backend/scripts/ ./backend/scripts/
COPY backend/models/pengzhendong/ ./backend/models/pengzhendong/
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh

# ---------- 从前端构建 stage 复制静态产物 ----------
COPY --from=frontend-builder /app/frontend/dist/ /usr/share/nginx/html/

# ---------- 运行时目录 & 脚本权限 ----------
RUN chmod +x /docker-entrypoint.sh && \
    mkdir -p \
      /app/backend/static/screenshots \
      /app/backend/static/docs \
      /app/backend/uploads \
      /app/backend/note_results \
      /app/backend/templates

WORKDIR /app/backend

EXPOSE 80 8480

CMD ["/docker-entrypoint.sh"]
