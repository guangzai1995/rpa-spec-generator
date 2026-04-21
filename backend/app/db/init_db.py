import os
import uuid
from app.db.engine import engine, Base, SessionLocal
from app.db.models import (
    Requirement, Asset, TimelineStep, Extraction, SpecDoc, LLMProvider
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def init_db():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表初始化完成")
    _sync_env_providers()


def _sync_env_providers():
    """将 .env 中的 LLM 配置自动同步到 DB LLMProvider 表"""
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    if not all([api_key, base_url, model]):
        return

    db = SessionLocal()
    try:
        # 查找是否已有匹配的 provider
        existing = db.query(LLMProvider).filter(
            LLMProvider.model_name == model,
            LLMProvider.base_url == base_url,
        ).first()
        if existing:
            # 更新 api_key 并确保启用
            if existing.api_key != api_key:
                existing.api_key = api_key
            existing.enabled = 1
            db.commit()
            logger.info(f"同步 LLM Provider: {model} (已存在，已更新)")
        else:
            # 禁用其他 provider，插入新的
            db.query(LLMProvider).update({LLMProvider.enabled: 0})
            provider = LLMProvider(
                id=str(uuid.uuid4()),
                name=model,
                api_key=api_key,
                base_url=base_url,
                model_name=model,
                enabled=1,
            )
            db.add(provider)
            db.commit()
            logger.info(f"同步 LLM Provider: {model} (新增)")
    except Exception as e:
        logger.warning(f"同步 LLM Provider 失败: {e}")
        db.rollback()
    finally:
        db.close()
