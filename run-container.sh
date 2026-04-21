#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

IMAGE_NAME="rpa-spec:latest"
CONTAINER_NAME="rpa-spec"
ENV_FILE="$SCRIPT_DIR/backend/.env"
APP_PORT="80"
BACKEND_PORT="8480"
MODE="gpu"
HOST_GPU_INDEX="${WHISPER_DEVICE_INDEX:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)
      IMAGE_NAME="$2"; shift 2 ;;
    --name)
      CONTAINER_NAME="$2"; shift 2 ;;
    --env-file)
      ENV_FILE="$2"; shift 2 ;;
    --app-port)
      APP_PORT="$2"; shift 2 ;;
    --backend-port)
      BACKEND_PORT="$2"; shift 2 ;;
    --gpu-index)
      HOST_GPU_INDEX="$2"; shift 2 ;;
    --cpu)
      MODE="cpu"; shift ;;
    -h|--help)
      cat <<'EOF'
用法:
  bash run-container.sh                    # 默认以 GPU 模式启动，使用宿主机 0 号卡
  bash run-container.sh --gpu-index 1      # 使用宿主机 1 号卡
  bash run-container.sh --cpu              # 以 CPU 模式启动
  bash run-container.sh --image repo/app:tag

说明:
  - backend/.env 会同时通过 --env-file 和只读挂载传入容器
  - 选择单张 GPU 时，容器内仅暴露该卡，因此 WHISPER_DEVICE_INDEX 固定传 0
EOF
      exit 0 ;;
    *)
      fail "未知参数: $1" ;;
  esac
done

command -v docker >/dev/null 2>&1 || fail "未找到 docker，请先安装"
[[ -f "$ENV_FILE" ]] || fail "未找到环境文件: $ENV_FILE"

if [[ "$MODE" == "gpu" ]] && ! [[ "$HOST_GPU_INDEX" =~ ^[0-9]+$ ]]; then
  fail "--gpu-index 必须为非负整数，当前值: $HOST_GPU_INDEX"
fi

step "准备启动容器"
info "镜像: $IMAGE_NAME"
info "容器名: $CONTAINER_NAME"
info "环境文件: $ENV_FILE"

if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
  warn "发现同名容器，先删除旧容器: $CONTAINER_NAME"
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

RUN_ARGS=(
  --detach
  --restart unless-stopped
  --name "$CONTAINER_NAME"
  -p "$APP_PORT:80"
  -p "$BACKEND_PORT:8480"
  --env-file "$ENV_FILE"
  -v "$ENV_FILE:/app/backend/.env:ro"
)

if [[ "$MODE" == "gpu" ]]; then
  RUN_ARGS+=(
    --gpus "device=$HOST_GPU_INDEX"
    -e WHISPER_DEVICE=cuda
    -e WHISPER_DEVICE_INDEX=0
  )
  info "GPU 模式: 宿主机卡号=$HOST_GPU_INDEX, 容器内 WHISPER_DEVICE_INDEX=0"
else
  RUN_ARGS+=(
    -e WHISPER_DEVICE=cpu
    -e WHISPER_DEVICE_INDEX=0
  )
  info "CPU 模式: 不向容器暴露 GPU"
fi

docker run "${RUN_ARGS[@]}" "$IMAGE_NAME" >/dev/null

ok "容器已启动: $CONTAINER_NAME"
info "前端入口: http://127.0.0.1:$APP_PORT"
info "后端 API: http://127.0.0.1:$BACKEND_PORT"
info "查看日志: docker logs -f $CONTAINER_NAME"