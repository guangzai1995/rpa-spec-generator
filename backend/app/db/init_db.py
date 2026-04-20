from app.db.engine import engine, Base
from app.db.models import (
    Requirement, Asset, TimelineStep, Extraction, SpecDoc, LLMProvider
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def init_db():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表初始化完成")
