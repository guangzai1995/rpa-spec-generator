FROM python:3.11-slim AS backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl nginx nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 后端
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# 前端构建
COPY frontend/ ./frontend/
WORKDIR /app/frontend
RUN npm install && npm run build

# Nginx 配置
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default
RUN cp -r /app/frontend/dist /usr/share/nginx/html

WORKDIR /app/backend
RUN mkdir -p static/screenshots static/docs uploads note_results templates

# CUDA / cuDNN .so 搜索路径（faster-whisper + ctranslate2 需要）
ENV LD_LIBRARY_PATH="/usr/local/cuda/targets/x86_64-linux/lib:/usr/local/lib/python3.11/dist-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/dist-packages/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# 确保 .so 文件权限可执行（避免 dlopen 权限问题）
RUN find /usr/local/lib/python3.11/dist-packages/nvidia -name "*.so*" -exec chmod a+rx {} \; 2>/dev/null || true && \
    ldconfig 2>/dev/null || true

EXPOSE 80 8480

# 启动脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8480/api/health || exit 1

CMD ["/docker-entrypoint.sh"]
