#!/usr/bin/env bash
#=============================================================
# deploy.sh  — 一键部署 RPA 需求规格说明书生成系统
#
# 支持两种部署模式:
#   1. 本地开发模式 (默认)  — venv + npm dev server
#   2. Docker 生产模式      — docker compose 一体化容器
#
# 用法:
#   bash deploy.sh                  # 本地启动前后端
#   bash deploy.sh --docker         # Docker 生产部署
#   bash deploy.sh --stop           # 停止所有服务
#   bash deploy.sh --status         # 查看服务状态
#   bash deploy.sh --backend-only   # 仅启动后端
#   bash deploy.sh --frontend-only  # 仅启动前端
#   bash deploy.sh --build-only     # 仅构建前端 dist
#   bash deploy.sh --logs           # 跟踪日志输出
#   bash deploy.sh --init-env       # 生成 .env 模板
#=============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- 颜色输出 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

# ---------- 参数解析 ----------
MODE_DOCKER=false; BUILD_ONLY=false; BACKEND_ONLY=false; FRONTEND_ONLY=false
CMD_STOP=false; CMD_STATUS=false; CMD_LOGS=false; CMD_INIT_ENV=false
DOCKER_BUILD_FLAG=""

for arg in "$@"; do
  case "$arg" in
    --docker)        MODE_DOCKER=true ;;
    --build-only)    BUILD_ONLY=true ;;
    --backend-only)  BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    --stop)          CMD_STOP=true ;;
    --status)        CMD_STATUS=true ;;
    --logs)          CMD_LOGS=true ;;
    --init-env)      CMD_INIT_ENV=true ;;
    --rebuild)       DOCKER_BUILD_FLAG="--build --force-recreate" ;;
    -h|--help)
      sed -n '2,/^#=====/p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0 ;;
    *)
      warn "未知参数: $arg (使用 --help 查看用法)"
      ;;
  esac
done

# ---------- 配置 ----------
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/logs"
BACKEND_PORT="${BACKEND_PORT:-8480}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
DOCKER_APP_PORT="${APP_PORT:-80}"
BACKEND_PID_FILE="$SCRIPT_DIR/.backend.pid"
FRONTEND_PID_FILE="$SCRIPT_DIR/.frontend.pid"
COMPOSE_PROJECT="rpa-spec"

# ====================================================================
#                           工具函数
# ====================================================================

banner() {
  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║   RPA 需求规格说明书生成系统 — 一键部署脚本     ║${NC}"
  echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
  echo ""
}

# --- 进程管理 ---
stop_process() {
  local pid_file="$1" name="$2"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(cat "$pid_file" 2>/dev/null || true)
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      info "停止 $name (PID=$pid) ..."
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
      ok "$name 已停止"
    else
      info "$name 未在运行 (旧 PID=$pid)"
    fi
    rm -f "$pid_file"
  fi
}

cleanup_port() {
  local port="$1" name="$2"
  local pids
  pids=$(python3 - "$port" <<'PY'
import os
import socket
import sys

port = int(sys.argv[1])
target_hex = f"{port:04X}"
listen_inodes = set()

for proc_file in ("/proc/net/tcp", "/proc/net/tcp6"):
  try:
    with open(proc_file, "r", encoding="utf-8") as handle:
      next(handle, None)
      for line in handle:
        parts = line.split()
        if len(parts) < 10:
          continue
        local_addr = parts[1]
        state = parts[3]
        inode = parts[9]
        if state != "0A":
          continue
        try:
          _, port_hex = local_addr.rsplit(":", 1)
        except ValueError:
          continue
        if port_hex.upper() == target_hex:
          listen_inodes.add(inode)
  except FileNotFoundError:
    continue

if not listen_inodes:
  sys.exit(0)

matched_pids = set()
for pid in filter(str.isdigit, os.listdir("/proc")):
  fd_dir = f"/proc/{pid}/fd"
  if not os.path.isdir(fd_dir):
    continue
  try:
    for fd in os.listdir(fd_dir):
      fd_path = os.path.join(fd_dir, fd)
      try:
        link = os.readlink(fd_path)
      except OSError:
        continue
      if link.startswith("socket:[") and link[8:-1] in listen_inodes:
        matched_pids.add(pid)
        break
  except OSError:
    continue

print(" ".join(sorted(matched_pids)))
PY
)
  if [[ -n "$pids" ]]; then
    info "清理 $name 端口占用 ($port) ..."
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
}

# --- 健康检查 ---
health_check() {
  local url="$1" name="$2" max_wait="${3:-60}" interval=2 elapsed=0
  info "等待 $name 就绪 ($url) ..."
  while (( elapsed < max_wait )); do
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
      ok "$name 健康检查通过 (${elapsed}s)"
      return 0
    fi
    sleep "$interval"
    elapsed=$(( elapsed + interval ))
  done
  warn "$name 未在 ${max_wait}s 内就绪，请检查日志"
  return 1
}

# --- CUDA 库路径 ---
setup_ld_library_path() {
  local extra=""
  local cuda_lib_dirs=("/usr/local/cuda/targets/x86_64-linux/lib")
  if command -v python3 >/dev/null 2>&1; then
    while IFS= read -r site_dir; do
      [[ -z "$site_dir" ]] && continue
      cuda_lib_dirs+=("$site_dir/nvidia/cublas/lib" "$site_dir/nvidia/cudnn/lib")
    done < <(python3 - <<'PY'
import site
for item in site.getsitepackages():
    print(item)
PY
)
  fi

  for d in "${cuda_lib_dirs[@]}"; do
    if [[ -d "$d" ]]; then
      find "$d" -name "*.so*" -exec chmod a+rx {} \; 2>/dev/null || true
      extra="${extra:+$extra:}$d"
    fi
  done
  if [[ -n "$extra" ]]; then
    export LD_LIBRARY_PATH="${extra}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    info "LD_LIBRARY_PATH 已配置 (${#cuda_lib_dirs[@]} 个路径)"
  fi
}

load_backend_env() {
  if [[ -f "$BACKEND_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.env"
    set +a
    return 0
  fi
  return 1
}

build_chat_endpoint() {
  local base_url="$1"
  base_url="${base_url%/}"
  if [[ "$base_url" == *"/chat/completions" ]]; then
    echo "$base_url"
  else
    echo "$base_url/chat/completions"
  fi
}

test_model_connectivity() {
  local name="$1" endpoint="$2" api_key="$3" payload="$4"
  local http_code response_file
  response_file=$(mktemp)

  http_code=$(curl -sS --max-time 30 \
    -o "$response_file" \
    -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $api_key" \
    -d "$payload" \
    "$endpoint" 2>/dev/null || echo "000")

  if [[ "$http_code" =~ ^2[0-9][0-9]$ ]] && grep -q '"choices"' "$response_file"; then
    ok "$name 连通性测试通过"
    rm -f "$response_file"
    return 0
  fi

  warn "$name 连通性测试失败 (HTTP $http_code)"
  if grep -q '"message"' "$response_file"; then
    local msg
    msg=$(tr -d '\n' < "$response_file" | sed -E 's/.*"message"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' || true)
    [[ -n "$msg" ]] && warn "$name 错误信息: $msg"
  fi
  rm -f "$response_file"
  return 1
}

run_model_connectivity_checks() {
  if ! load_backend_env; then
    warn "未找到 $BACKEND_DIR/.env，跳过模型连通性测试"
    return 0
  fi

  step "启动前模型连通性测试"

  [[ -n "${LLM_API_KEY:-}" ]] || fail "LLM_API_KEY 未配置，无法进行 LLM 连通性测试"
  [[ -n "${LLM_BASE_URL:-}" ]] || fail "LLM_BASE_URL 未配置，无法进行 LLM 连通性测试"
  [[ -n "${LLM_MODEL:-}" ]]   || fail "LLM_MODEL 未配置，无法进行 LLM 连通性测试"

  local llm_endpoint llm_payload
  llm_endpoint=$(build_chat_endpoint "$LLM_BASE_URL")
  llm_payload=$(cat <<JSON
{"model":"$LLM_MODEL","messages":[{"role":"user","content":"请仅回复:ok"}],"temperature":0,"max_tokens":16}
JSON
)

  test_model_connectivity "LLM" "$llm_endpoint" "$LLM_API_KEY" "$llm_payload" || \
    fail "LLM 连通性测试未通过，启动中止"

  if [[ "${VISION_ENABLED:-true}" == "1" || "${VISION_ENABLED:-true}" == "true" || "${VISION_ENABLED:-true}" == "TRUE" ]]; then
    [[ -n "${VISION_API_KEY:-}" ]] || fail "VISION_API_KEY 未配置，无法进行多模态连通性测试"
    [[ -n "${VISION_BASE_URL:-}" ]] || fail "VISION_BASE_URL 未配置，无法进行多模态连通性测试"
    [[ -n "${VISION_MODEL:-}" ]]   || fail "VISION_MODEL 未配置，无法进行多模态连通性测试"

    local vision_endpoint vision_payload
    vision_endpoint=$(build_chat_endpoint "$VISION_BASE_URL")
    vision_payload=$(cat <<JSON
{"model":"$VISION_MODEL","messages":[{"role":"user","content":[{"type":"text","text":"请判断这是否为测试图并回复ok"},{"type":"image_url","image_url":{"url":"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6p6dQAAAAASUVORK5CYII="}}]}],"temperature":0,"max_tokens":16}
JSON
)

    test_model_connectivity "多模态模型" "$vision_endpoint" "$VISION_API_KEY" "$vision_payload" || \
      fail "多模态模型连通性测试未通过，启动中止"
  else
    info "VISION_ENABLED=false，跳过多模态连通性测试"
  fi
}

# --- 日志轮转 ---
rotate_log() {
  local log_file="$1" max_size=$((10 * 1024 * 1024))  # 10MB
  if [[ -f "$log_file" ]] && (( $(stat -c%s "$log_file" 2>/dev/null || echo 0) > max_size )); then
    local ts
    ts=$(date +%Y%m%d_%H%M%S)
    mv "$log_file" "${log_file%.log}_${ts}.log"
    info "日志已轮转: ${log_file%.log}_${ts}.log"
    # 保留最近 5 个归档
    ls -t "${log_file%.log}"_*.log 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
  fi
}

# --- 前置检查 ---
preflight_check() {
  local mode="$1" missing=()

  step "前置环境检查 ..."

  if [[ "$mode" == "docker" ]]; then
    command -v docker >/dev/null 2>&1   || missing+=("docker")
    if ! docker compose version >/dev/null 2>&1 && ! docker-compose --version >/dev/null 2>&1; then
      missing+=("docker-compose")
    fi
  else
    command -v python3 >/dev/null 2>&1  || missing+=("python3")
    command -v curl    >/dev/null 2>&1   || missing+=("curl")
    if [[ "$FRONTEND_ONLY" != true && "$BUILD_ONLY" != true ]]; then
      command -v ffmpeg >/dev/null 2>&1  || missing+=("ffmpeg")
    fi
    if [[ "$BACKEND_ONLY" != true ]]; then
      command -v node >/dev/null 2>&1    || missing+=("node")
      command -v npm  >/dev/null 2>&1    || missing+=("npm")
    fi
  fi

  if (( ${#missing[@]} > 0 )); then
    fail "缺少必要工具: ${missing[*]}，请先安装后重试"
  fi

  # 检查 .env
  if [[ ! -f "$BACKEND_DIR/.env" ]]; then
    warn "未找到 $BACKEND_DIR/.env，使用 --init-env 生成模板"
  fi

  # GPU 检测（非阻断）
  if command -v nvidia-smi >/dev/null 2>&1; then
    local gpu_info
    gpu_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    ok "GPU 检测: $gpu_info"
  else
    warn "未检测到 GPU (nvidia-smi)，ASR 将使用 CPU 模式"
  fi

  ok "环境检查通过"
}

# ====================================================================
#                    .env 模板生成
# ====================================================================

cmd_init_env() {
  local env_file="$BACKEND_DIR/.env"
  if [[ -f "$env_file" ]]; then
    warn "$env_file 已存在，跳过生成 (如需覆盖请先删除)"
    return 0
  fi

  cat > "$env_file" << 'ENV_TEMPLATE'
# RPA 需求规格说明书自动生成系统 — 环境配置
# ================================================

DATABASE_URL=sqlite:///rpa_spec.db
BACKEND_PORT=8480
BACKEND_HOST=0.0.0.0

# LLM 配置 — 结构化文本提取
LLM_API_KEY=<your-llm-api-key>
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL=minimax-m2.7

# 多模态视觉分析模型（Qwen VL）
VISION_ENABLED=true
VISION_API_KEY=<your-vision-api-key>
VISION_BASE_URL=https://api.example.com/v1
VISION_MODEL=Qwen3_5-35B-A3B-FP8

# ASR 配置（默认尝试 cuda，不可用时自动回退 cpu）
WHISPER_MODEL_SIZE=large-v3
WHISPER_DEVICE=cuda
WHISPER_MODEL_DIR=models/pengzhendong/faster-whisper-large-v3

# 文件存储
UPLOAD_DIR=uploads
STATIC_DIR=static
NOTE_OUTPUT_DIR=note_results

# 截图标注：VLM bbox 检测（实验性，0=关闭 1=开启）
ENABLE_BBOX_DETECTION=1

# 企微 Webhook（可选）
WECOM_WEBHOOK=
ENV_TEMPLATE

  ok "已生成 $env_file，请编辑填入 API Key"
}

# ====================================================================
#                    Docker 部署模式
# ====================================================================

docker_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose -p "$COMPOSE_PROJECT" "$@"
  else
    docker-compose -p "$COMPOSE_PROJECT" "$@"
  fi
}

docker_deploy() {
  step "Docker 生产模式部署"
  preflight_check "docker"

  if [[ ! -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
    fail "未找到 docker-compose.yml"
  fi

  # 如果 backend/.env 存在，将关键变量导出给 compose
  if [[ -f "$BACKEND_DIR/.env" ]]; then
    load_backend_env
    info "已加载 $BACKEND_DIR/.env"
  fi

  run_model_connectivity_checks

  info "构建并启动容器 ..."
  # shellcheck disable=SC2086
  docker_compose_cmd up -d $DOCKER_BUILD_FLAG

  echo ""
  info "容器状态:"
  docker_compose_cmd ps

  # 健康检查
  health_check "http://127.0.0.1:$BACKEND_PORT/api/health" "Backend (Docker)" 120
  ok "Docker 部署完成"
  echo ""
  info "前端入口: http://<host>:$DOCKER_APP_PORT"
  info "后端 API: http://<host>:$BACKEND_PORT"
  info "查看日志: bash deploy.sh --docker --logs"
}

docker_stop() {
  step "停止 Docker 容器"
  docker_compose_cmd down
  ok "容器已停止"
}

docker_status() {
  step "Docker 容器状态"
  docker_compose_cmd ps
}

docker_logs() {
  docker_compose_cmd logs -f --tail=100
}

# ====================================================================
#                    本地开发模式
# ====================================================================

start_backend() {
  step "启动后端服务"
  stop_process "$BACKEND_PID_FILE" "Backend"
  cleanup_port "$BACKEND_PORT" "Backend"

  # 检查 / 创建 venv
  if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    info "创建 Python 虚拟环境 ..."
    python3 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  # 每次启动同步 requirements，避免已有 venv 漏装后来新增的依赖
  # info "同步 Python 依赖 ..."
  # pip install -q --timeout 60 -i https://pypi.tuna.tsinghua.edu.cn/simple \
  #   -r "$BACKEND_DIR/requirements.txt" \
  #   "nvidia-cublas-cu12>=12,<13" "nvidia-cudnn-cu12>=9,<10" || {
  #   warn "部分依赖安装失败，尝试继续..."
  # }
  # ok "Python 依赖同步完成"

  # CUDA 库路径
  setup_ld_library_path

  # 确保目录
  cd "$BACKEND_DIR"
  mkdir -p static/screenshots static/docs uploads note_results templates

  # 日志轮转
  rotate_log "$LOG_DIR/backend.log"

  # 启动
  info "启动后端 (port=$BACKEND_PORT) ..."
  nohup python main.py >> "$LOG_DIR/backend.log" 2>&1 &
  local pid=$!
  echo "$pid" > "$BACKEND_PID_FILE"
  ok "后端已启动 (PID=$pid, 日志: logs/backend.log)"

  health_check "http://127.0.0.1:$BACKEND_PORT/api/health" "Backend" 120
}

start_frontend() {
  step "启动前端服务"
  stop_process "$FRONTEND_PID_FILE" "Frontend"
  cleanup_port "$FRONTEND_PORT" "Frontend"

  cd "$FRONTEND_DIR"

  # 安装依赖
  if [[ -d "node_modules" ]]; then
    ok "前端依赖已就绪"
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

  # 日志轮转
  rotate_log "$LOG_DIR/frontend.log"

  # 开发模式启动
  info "启动前端 (port=$FRONTEND_PORT) ..."
  nohup ./node_modules/.bin/vite --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort >> "$LOG_DIR/frontend.log" 2>&1 &
  local pid=$!
  echo "$pid" > "$FRONTEND_PID_FILE"
  ok "前端已启动 (PID=$pid, 日志: logs/frontend.log)"

  health_check "http://127.0.0.1:$FRONTEND_PORT" "Frontend" 30
}

# ====================================================================
#                    停止 / 状态 / 日志
# ====================================================================

cmd_stop() {
  if [[ "$MODE_DOCKER" == true ]]; then
    docker_stop
  else
    banner
    step "停止本地服务"
    stop_process "$BACKEND_PID_FILE"  "Backend"
    stop_process "$FRONTEND_PID_FILE" "Frontend"

    # 兜底: 按端口清理残留进程
    cleanup_port "$BACKEND_PORT" "Backend"
    cleanup_port "$FRONTEND_PORT" "Frontend"

    ok "所有本地服务已停止"
  fi
}

cmd_status() {
  if [[ "$MODE_DOCKER" == true ]]; then
    docker_status
    return
  fi

  banner
  step "服务状态"
  echo ""

  # 后端
  if [[ -f "$BACKEND_PID_FILE" ]]; then
    local bpid
    bpid=$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)
    if [[ -n "$bpid" ]] && kill -0 "$bpid" 2>/dev/null; then
      ok "后端  ✓  运行中  PID=$bpid  http://127.0.0.1:$BACKEND_PORT"
    else
      warn "后端  ✗  PID=$bpid 已退出"
    fi
  else
    info "后端  -  未启动"
  fi

  # 前端
  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    local fpid
    fpid=$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)
    if [[ -n "$fpid" ]] && kill -0 "$fpid" 2>/dev/null; then
      ok "前端  ✓  运行中  PID=$fpid  http://127.0.0.1:$FRONTEND_PORT"
    else
      warn "前端  ✗  PID=$fpid 已退出"
    fi
  else
    info "前端  -  未启动"
  fi

  # GPU
  echo ""
  if command -v nvidia-smi >/dev/null 2>&1; then
    info "GPU 使用情况:"
    nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total \
      --format=csv,noheader 2>/dev/null | while IFS= read -r line; do
      echo "       $line"
    done
  fi

  # 磁盘占用
  echo ""
  info "数据目录占用:"
  for d in uploads static note_results; do
    if [[ -d "$BACKEND_DIR/$d" ]]; then
      local sz
      sz=$(du -sh "$BACKEND_DIR/$d" 2>/dev/null | cut -f1)
      echo "       $d/  $sz"
    fi
  done
  echo ""
}

cmd_logs() {
  if [[ "$MODE_DOCKER" == true ]]; then
    docker_logs
  else
    info "跟踪本地日志 (Ctrl+C 退出) ..."
    tail -f "$LOG_DIR"/backend.log "$LOG_DIR"/frontend.log 2>/dev/null || {
      warn "日志文件不存在，请先启动服务"
    }
  fi
}

# ====================================================================
#                           主流程
# ====================================================================

main() {
  mkdir -p "$LOG_DIR"

  # 优先处理命令型参数
  if [[ "$CMD_INIT_ENV" == true ]]; then
    cmd_init_env
    exit 0
  fi
  if [[ "$CMD_STOP" == true ]]; then
    cmd_stop
    exit 0
  fi
  if [[ "$CMD_STATUS" == true ]]; then
    cmd_status
    exit 0
  fi
  if [[ "$CMD_LOGS" == true ]]; then
    cmd_logs
    exit 0
  fi

  banner

  # Docker 模式
  if [[ "$MODE_DOCKER" == true ]]; then
    docker_deploy
    exit 0
  fi

  # 本地开发模式
  preflight_check "local"

  if [[ "$FRONTEND_ONLY" != true && "$BUILD_ONLY" != true ]]; then
    run_model_connectivity_checks
  fi

  if [[ "$FRONTEND_ONLY" == true ]]; then
    start_frontend
  elif [[ "$BACKEND_ONLY" == true ]]; then
    start_backend
  else
    start_backend
    [[ "$BUILD_ONLY" != true ]] && echo ""
    start_frontend
  fi

  echo ""
  echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
  ok "部署完成!"
  echo ""
  [[ "$FRONTEND_ONLY" != true ]] && \
    info "后端 API:  http://127.0.0.1:$BACKEND_PORT"
  [[ "$BACKEND_ONLY" != true && "$BUILD_ONLY" != true ]] && \
    info "前端页面:  http://127.0.0.1:$FRONTEND_PORT"
  info "日志目录:  $LOG_DIR/"
  info "停止服务:  bash deploy.sh --stop"
  info "查看状态:  bash deploy.sh --status"
  echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
  echo ""
}

main
