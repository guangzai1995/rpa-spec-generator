"""企业微信推送服务（预留）"""
import os
import requests
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

WECOM_WEBHOOK = os.getenv("WECOM_WEBHOOK", "")


def send_wecom_text(content: str, webhook: Optional[str] = None) -> bool:
    """发送企微文本消息（预留）"""
    url = webhook or WECOM_WEBHOOK
    if not url:
        logger.info("企微 Webhook 未配置，跳过推送")
        return False

    payload = {
        "msgtype": "text",
        "text": {"content": content}
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("企微文本消息推送成功")
        return True
    except Exception as e:
        logger.warning(f"企微推送失败: {e}")
        return False


def send_wecom_file(file_path: str, webhook: Optional[str] = None) -> bool:
    """发送企微文件消息（预留，需要先上传到企微临时素材）"""
    logger.info(f"企微文件推送预留，文件: {file_path}")
    # TODO: 实现文件上传到企微临时素材 + 发送
    return False
