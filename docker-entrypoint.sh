#!/usr/bin/env bash
# ================================================================
# docker-entrypoint.sh — 容器一键启动脚本
# 负责：环境校验 → CUDA 配置 → 模型检查 → nginx → 后端服务
# ================================================================
set -euo pipefail

# ---------- 颜色输出 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   RPA 需求规格说明书生成系统 — 容器启动          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ----------------------------------------------------------------
# 1. 加载 .env（如挂载了 backend/.env 则生效）
# ----------------------------------------------------------------
ENV_FILE="/app/backend/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    ok "已加载环境配置: $ENV_FILE"
else
    warn "未找到 $ENV_FILE，将使用环境变量或默认值"
fi

# ----------------------------------------------------------------
# 2. 必要环境变量检查
# ----------------------------------------------------------------
step "检查关键配置"
MISSING=()
[ -z "${LLM_API_KEY:-}" ]   && MISSING+=("LLM_API_KEY")
[ -z "${LLM_BASE_URL:-}" ]  && MISSING+=("LLM_BASE_URL")
[ -z "${LLM_MODEL:-}" ]     && MISSING+=("LLM_MODEL")

if [ ${#MISSING[@]} -gt 0 ]; then
    warn "以下环境变量未配置，部分功能可能不可用: ${MISSING[*]}"
    warn "请通过 --env-file backend/.env 或 -e 参数传入"
else
    ok "LLM 配置检查通过"
fi

# ----------------------------------------------------------------
# 3. CUDA 库路径配置（GPU 可用时生效，CPU 环境静默跳过）
# ----------------------------------------------------------------
step "配置 CUDA 运行时库"
PYTHON_SITE=$(python - <<'PY'
import site, sys
dirs = site.getsitepackages()
print(dirs[0] if dirs else "")
PY
)

CUDA_CONFIGURED=false
for dir in \
    /usr/local/cuda/targets/x86_64-linux/lib \
    "${PYTHON_SITE}/nvidia/cublas/lib" \
    "${PYTHON_SITE}/nvidia/cudnn/lib"; do
    if [ -d "$dir" ]; then
        find "$dir" -name "*.so*" -exec chmod a+rx {} \; 2>/dev/null || true
        export LD_LIBRARY_PATH="${dir}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        CUDA_CONFIGURED=true
    fi
done
ldconfig 2>/dev/null || true

if [ "$CUDA_CONFIGURED" = true ]; then
    ok "CUDA 库路径已配置"
else
    info "未检测到 CUDA 库目录，将以 CPU 模式运行"
fi

# GPU 可用性检测（非阻断）
if command -v nvidia-smi >/dev/null 2>&1; then
    info "检测到 GPU:"
    nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader 2>/dev/null \
        | while IFS= read -r line; do echo "       GPU $line"; done
else
    info "未检测到 nvidia-smi，ASR 将使用 CPU 模式"
fi

# ----------------------------------------------------------------
# 4. Whisper 模型检查
# ----------------------------------------------------------------
step "检查 Whisper 模型"
WHISPER_MODEL_DIR="${WHISPER_MODEL_DIR:-}"
WHISPER_MODEL_SIZE="${WHISPER_MODEL_SIZE:-large-v3-turbo}"
WHISPER_DEVICE="${WHISPER_DEVICE:-cuda}"
WHISPER_DEVICE_INDEX="${WHISPER_DEVICE_INDEX:-0}"

# device_index 合法性校验（必须为非负整数）
if ! [[ "$WHISPER_DEVICE_INDEX" =~ ^[0-9]+$ ]]; then
    warn "WHISPER_DEVICE_INDEX='${WHISPER_DEVICE_INDEX}' 不合法，已重置为 0"
    WHISPER_DEVICE_INDEX=0
fi
export WHISPER_DEVICE_INDEX

info "Whisper 设备: ${WHISPER_DEVICE}  卡号: ${WHISPER_DEVICE_INDEX}"

# 推断默认模型路径
if [ -z "$WHISPER_MODEL_DIR" ]; then
    WHISPER_MODEL_DIR="/app/backend/models/pengzhendong/faster-whisper-${WHISPER_MODEL_SIZE}"
fi

if [ -f "${WHISPER_MODEL_DIR}/model.bin" ]; then
    MODEL_SIZE=$(du -sh "${WHISPER_MODEL_DIR}/model.bin" 2>/dev/null | cut -f1 || echo "?")
    ok "Whisper 模型就绪: ${WHISPER_MODEL_DIR} (model.bin: ${MODEL_SIZE})"
    export WHISPER_MODEL_DIR
else
    warn "未找到 Whisper 模型: ${WHISPER_MODEL_DIR}/model.bin"
    warn "ASR 转录将不可用。如需下载模型，构建时传入 --build-arg DOWNLOAD_MODEL=true"
    warn "或运行容器后手动执行: python /app/backend/scripts/download_model.py"
fi

# ----------------------------------------------------------------
# 5. 运行时目录确保存在（volumes 挂载后可能为空）
# ----------------------------------------------------------------
step "初始化运行时目录"
mkdir -p \
    /app/backend/static/screenshots \
    /app/backend/static/docs \
    /app/backend/uploads \
    /app/backend/note_results \
    /app/backend/templates
ok "运行时目录就绪"

# ----------------------------------------------------------------
# 6. 启动 nginx（前端静态服务 + 反代）
# ----------------------------------------------------------------
step "启动 nginx"
# 测试配置合法性
nginx -t 2>/dev/null || fail "nginx 配置校验失败，请检查 /etc/nginx/conf.d/default.conf"
nginx
ok "nginx 已启动"

# ----------------------------------------------------------------
# 7. 启动后端（前台运行，接管容器生命周期）
# ----------------------------------------------------------------
BACKEND_PORT="${BACKEND_PORT:-8480}"
step "启动后端服务 (port=${BACKEND_PORT})"

echo ""
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
ok "服务启动中..."
info "前端入口:  http://0.0.0.0:80"
info "后端 API:  http://0.0.0.0:${BACKEND_PORT}"
info "健康检查:  http://0.0.0.0:${BACKEND_PORT}/api/health"
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo ""

cd /app/backend
exec python main.py
