#!/usr/bin/env bash
#=============================================================
# build.sh — RPA 需求规格说明书生成系统 Docker 镜像构建脚本
#
# 用法:
#   bash build.sh                    # 默认构建 (国内源)
#   bash build.sh --tag v1.2.3       # 指定版本标签
#   bash build.sh --no-cache         # 禁用 Docker 层缓存
#   bash build.sh --no-mirror        # 关闭国内镜像源（境外网络）
#   bash build.sh --push             # 构建后推送到镜像仓库
#   bash build.sh --registry myrepo  # 自定义镜像仓库前缀
#   bash build.sh --target <stage>   # 只构建到指定 stage
#   bash build.sh --help             # 显示帮助
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

# ---------- 默认参数 ----------
IMAGE_NAME="rpa-spec"
IMAGE_TAG="latest"
REGISTRY=""
USE_MIRROR=true
NO_CACHE=false
DO_PUSH=false
BUILD_TARGET=""
DOCKERFILE="$SCRIPT_DIR/Dockerfile"

# 国内镜像源
PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_HOST="pypi.tuna.tsinghua.edu.cn"
NPM_REGISTRY="https://registry.npmmirror.com"

# ---------- 参数解析 ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      IMAGE_TAG="$2"; shift 2 ;;
    --registry)
      REGISTRY="${2%/}/"; shift 2 ;;
    --no-cache)
      NO_CACHE=true; shift ;;
    --no-mirror)
      USE_MIRROR=false; shift ;;
    --push)
      DO_PUSH=true; shift ;;
    --target)
      BUILD_TARGET="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^#=====/p' "$0" | grep '^#' | sed 's/^# \?//'; exit 0 ;;
    *)
      warn "未知参数: $1"; shift ;;
  esac
done

# ---------- 完整镜像名 ----------
FULL_IMAGE="${REGISTRY}${IMAGE_NAME}:${IMAGE_TAG}"

# ---------- banner ----------
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   RPA 需求规格说明书生成系统 — 镜像构建脚本     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ---------- 检查依赖 ----------
command -v docker >/dev/null 2>&1 || fail "未找到 docker，请先安装"

# ---------- 构建参数组装 ----------
BUILD_ARGS=()

# 国内源开关
if [[ "$USE_MIRROR" == true ]]; then
  BUILD_ARGS+=(
    --build-arg "PIP_INDEX=$PIP_INDEX"
    --build-arg "PIP_HOST=$PIP_HOST"
    --build-arg "NPM_REGISTRY=$NPM_REGISTRY"
  )
  info "已启用国内镜像源 (pip: 清华 / npm: 淘宝)"
else
  warn "已关闭国内镜像源，使用默认上游源"
fi

# 无缓存构建
[[ "$NO_CACHE" == true ]] && BUILD_ARGS+=(--no-cache) && info "已禁用 Docker 层缓存"

# 指定构建目标 stage
[[ -n "$BUILD_TARGET" ]] && BUILD_ARGS+=(--target "$BUILD_TARGET") && info "构建目标 stage: $BUILD_TARGET"

# ---------- 显示构建信息 ----------
step "开始构建镜像"
info "镜像名称: $FULL_IMAGE"
info "Dockerfile: $DOCKERFILE"
echo ""

# ---------- 打印 Git 信息（可选，若无 git 则跳过） ----------
if command -v git >/dev/null 2>&1 && git -C "$SCRIPT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  GIT_COMMIT=$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
  GIT_BRANCH=$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
  info "Git commit: $GIT_COMMIT  branch: $GIT_BRANCH"
  BUILD_ARGS+=(--label "git.commit=$GIT_COMMIT" --label "git.branch=$GIT_BRANCH")
fi

# ---------- 记录构建开始时间 ----------
BUILD_START=$(date +%s)

# ---------- 执行构建 ----------
docker build \
  "${BUILD_ARGS[@]}" \
  --label "build.date=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t "$FULL_IMAGE" \
  -f "$DOCKERFILE" \
  "$SCRIPT_DIR"

BUILD_END=$(date +%s)
BUILD_ELAPSED=$(( BUILD_END - BUILD_START ))

echo ""
ok "镜像构建完成: $FULL_IMAGE  (耗时 ${BUILD_ELAPSED}s)"

# ---------- 显示镜像信息 ----------
echo ""
info "镜像详情:"
docker image inspect "$FULL_IMAGE" \
  --format '  大小: {{.Size | printf "%.0f"}} bytes  创建: {{.Created}}' 2>/dev/null || true

# ---------- 推送（可选） ----------
if [[ "$DO_PUSH" == true ]]; then
  [[ -z "$REGISTRY" ]] && fail "--push 需要同时指定 --registry <仓库地址>"
  step "推送镜像到仓库: $FULL_IMAGE"
  docker push "$FULL_IMAGE"
  ok "推送完成"
fi

# ---------- 使用提示 ----------
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
info "运行示例 (GPU):"
echo "  docker run --rm --gpus all -p 80:80 -p 8480:8480 \\"
echo "    --env-file backend/.env \\"
echo "    $FULL_IMAGE /docker-entrypoint.sh"
echo ""
info "运行示例 (CPU):"
echo "  docker run --rm -p 80:80 -p 8480:8480 \\"
echo "    --env-file backend/.env \\"
echo "    -e WHISPER_DEVICE=cpu \\"
echo "    $FULL_IMAGE /docker-entrypoint.sh"
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo ""
