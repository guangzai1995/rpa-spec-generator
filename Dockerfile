FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NVIDIA_PYTHON_SITE=/usr/local/lib/python3.11/site-packages

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    pip install "nvidia-cublas-cu12>=12,<13" "nvidia-cudnn-cu12>=9,<10"

COPY backend/ ./backend/
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY --from=frontend-builder /app/frontend/dist/ /usr/share/nginx/html/

RUN chmod +x /docker-entrypoint.sh && \
    mkdir -p /app/backend/static/screenshots /app/backend/static/docs /app/backend/uploads /app/backend/note_results /app/backend/templates && \
    find "$NVIDIA_PYTHON_SITE/nvidia" -name "*.so*" -exec chmod a+rx {} \; 2>/dev/null || true && \
    ldconfig 2>/dev/null || true

ENV LD_LIBRARY_PATH="/usr/local/cuda/targets/x86_64-linux/lib:${NVIDIA_PYTHON_SITE}/nvidia/cublas/lib:${NVIDIA_PYTHON_SITE}/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

WORKDIR /app/backend

EXPOSE 80 8480

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8480/api/health || exit 1

CMD ["/docker-entrypoint.sh"]
