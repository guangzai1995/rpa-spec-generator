#!/bin/bash
set -e

# 确保 CUDA .so 文件可访问
for dir in \
  /usr/local/cuda/targets/x86_64-linux/lib \
  /usr/local/lib/python3.11/dist-packages/nvidia/cublas/lib \
  /usr/local/lib/python3.11/dist-packages/nvidia/cudnn/lib; do
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
