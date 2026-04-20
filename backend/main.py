import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv

# 设置 CUDA 库搜索路径（ctranslate2/faster-whisper 需要 libcublas/libcudnn）
_cuda_lib_dirs = [
    "/usr/local/cuda/targets/x86_64-linux/lib",
    "/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib",
    "/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib",
]
_extra = ":".join(d for d in _cuda_lib_dirs if os.path.isdir(d))
if _extra:
    _cur = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = f"{_extra}:{_cur}" if _cur else _extra

from app.db.init_db import init_db
from app.utils.logger import get_logger
from app import create_app

logger = get_logger(__name__)
load_dotenv()

# 确保目录存在
for d in ["static", "static/screenshots", "static/docs", "uploads", "note_results"]:
    os.makedirs(d, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("RPA 需求规格说明书自动生成系统启动完成")
    yield


app = create_app(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8480))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    logger.info(f"启动服务: {host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
