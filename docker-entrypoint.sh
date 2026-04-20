#!/bin/bash
set -e

# 确保 CUDA .so 文件可访问
PYTHON_SITE=$(python - <<'PY'
import site
print(site.getsitepackages()[0])
PY
)

for dir in \
  /usr/local/cuda/targets/x86_64-linux/lib \
  "$PYTHON_SITE/nvidia/cublas/lib" \
  "$PYTHON_SITE/nvidia/cudnn/lib"; do
  if [ -d "$dir" ]; then
    find "$dir" -name "*.so*" -exec chmod a+rx {} \; 2>/dev/null || true
    export LD_LIBRARY_PATH="${dir}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
done
ldconfig 2>/dev/null || true

# 启动 nginx
nginx

# 启动后端
cd /app/backend
exec python main.py
