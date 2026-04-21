"""集中化配置管理"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """应用配置 - 通过环境变量或 .env 文件加载"""

    # 数据库
    database_url: str = "sqlite:///rpa_spec.db"

    # 服务端口
    backend_port: int = 8480
    backend_host: str = "0.0.0.0"

    # LLM 默认配置
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "minimax-m2.7"
    llm_max_retries: int = 3
    llm_retry_backoff: float = 2.0

    # ASR 配置
    whisper_model_size: str = "large-v3-turbo"
    whisper_device: str = "cpu"
    whisper_model_dir: Optional[str] = None

    # 文件存储
    upload_dir: str = "uploads"
    static_dir: str = "static"
    note_output_dir: str = "note_results"

    # 多模态分析
    vision_enabled: bool = True
    vision_max_frames: int = 20

    # 企微
    wecom_webhook: str = ""

    # 任务
    task_max_workers: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def output_path(self) -> Path:
        p = Path(self.note_output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def screenshot_path(self) -> Path:
        p = Path(self.static_dir) / "screenshots"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def docs_path(self) -> Path:
        p = Path(self.static_dir) / "docs"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
