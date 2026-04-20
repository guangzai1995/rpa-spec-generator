#!/usr/bin/env bash
#=============================================================
# deploy.sh  — 一键拉起 RPA 需求规格说明书生成系统
# 用法: bash deploy.sh [--build-only] [--backend-only] [--frontend-only]
#=============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- 颜色输出 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ---------- 参数解析 ----------
BUILD_ONLY=false; BACKEND_ONLY=false; FRONTEND_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --build-only)    BUILD_ONLY=true ;;
    --backend-only)  BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    -h|--help)
      echo "用法: bash deploy.sh [--build-only] [--backend-only] [--frontend-only]"
      exit 0 ;;
  esac
done

# ---------- 配置 ----------
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
BACKEND_PORT="${BACKEND_PORT:-8480}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_PID_FILE="$SCRIPT_DIR/.backend.pid"
FRONTEND_PID_FILE="$SCRIPT_DIR/.frontend.pid"

# CUDA 库路径 (.so 权限 & 搜索路径)
CUDA_LIB_DIRS=(
  "/usr/local/cuda/targets/x86_64-linux/lib"
  "/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib"
  "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib"
)

# ---------- 工具函数 ----------
stop_process() {
  local pid_file="$1" name="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(cat "$pid_file" 2>/dev/null || true)
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      info "停止旧的 $name 进程 (PID=$pid) ..."
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

health_check() {
  local url="$1" name="$2" max_wait="${3:-60}" interval=2 elapsed=0
  info "等待 $name 就绪 ($url) ..."
  while (( elapsed < max_wait )); do
    if curl -sf "$url" > /dev/null 2>&1; then
      ok "$name 健康检查通过 (${elapsed}s)"
      return 0
    fi
    sleep "$interval"
    elapsed=$(( elapsed + interval ))
  done
  warn "$name 未在 ${max_wait}s 内就绪"
  return 1
}

setup_ld_library_path() {
  local extra=""
  for d in "${CUDA_LIB_DIRS[@]}"; do
    if [[ -d "$d" ]]; then
      # 确保 .so 文件可读可执行
      find "$d" -name "*.so*" -exec chmod a+rx {} \; 2>/dev/null || true
      extra="${extra:+$extra:}$d"
    fi
  done
  if [[ -n "$extra" ]]; then
    export LD_LIBRARY_PATH="${extra}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    info "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
  fi
}

# ---------- 后端 ----------
start_backend() {
  info "===== 启动后端 ====="
  stop_process "$BACKEND_PID_FILE" "Backend"

  # 检查 venv
  if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    info "创建 Python 虚拟环境 ..."
    python3 -m venv "$VENV_DIR"
  fi

  # 激活 venv
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  # 安装依赖（已安装则跳过）
  if python -c "import fastapi, uvicorn, faster_whisper" 2>/dev/null; then
    ok "Python 依赖已就绪，跳过安装"
  else
    info "安装 Python 依赖 ..."
    pip install -q --timeout 30 -i https://pypi.tuna.tsinghua.edu.cn/simple \
      -r "$BACKEND_DIR/requirements.txt" || {
      warn "依赖安装失败，尝试继续..."
    }
  fi

  # CUDA .so 路径
  setup_ld_library_path

  # 确保必要目录存在
  cd "$BACKEND_DIR"
  mkdir -p static/screenshots static/docs uploads note_results templates

  # 启动
  info "启动后端 (port=$BACKEND_PORT) ..."
  nohup python main.py > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
  local pid=$!
  echo "$pid" > "$BACKEND_PID_FILE"
  ok "后端进程已启动 (PID=$pid)"

  # 健康检查
  health_check "http://127.0.0.1:$BACKEND_PORT/api/health" "Backend" 120
}

# ---------- 前端 ----------
start_frontend() {
  info "===== 启动前端 ====="
  stop_process "$FRONTEND_PID_FILE" "Frontend"

  cd "$FRONTEND_DIR"

  # 安装依赖（已安装则跳过）
  if [[ -d "node_modules" ]]; then
    ok "前端依赖已就绪，跳过安装"
  else
    info "安装前端依赖 (npm install) ..."
    npm install --silent
  fi

  if [[ "$BUILD_ONLY" == true ]]; then
    info "构建前端 (npm run build) ..."
    npm run build
    ok "前端构建完成: $FRONTEND_DIR/dist/"
    return 0
  fi

  # 开发模式启动
  info "启动前端 (port=$FRONTEND_PORT) ..."
  nohup npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
  local pid=$!
  echo "$pid" > "$FRONTEND_PID_FILE"
  ok "前端进程已启动 (PID=$pid)"

  health_check "http://127.0.0.1:$FRONTEND_PORT" "Frontend" 30
}

# ---------- 主流程 ----------
main() {
  mkdir -p "$SCRIPT_DIR/logs"

  echo ""
  echo "============================================"
  echo "  RPA 需求规格说明书生成系统 — 部署脚本"
  echo "============================================"
  echo ""

  if [[ "$FRONTEND_ONLY" == true ]]; then
    start_frontend
  elif [[ "$BACKEND_ONLY" == true ]]; then
    start_backend
  else
    start_backend
    start_frontend
  fi

  echo ""
  echo "============================================"
  ok "部署完成!"
  [[ "$FRONTEND_ONLY" != true ]] && info "后端: http://127.0.0.1:$BACKEND_PORT"
  [[ "$BACKEND_ONLY" != true && "$BUILD_ONLY" != true ]] && info "前端: http://127.0.0.1:$FRONTEND_PORT"
  info "日志目录: $SCRIPT_DIR/logs/"
  echo "============================================"
  echo ""
}

main
