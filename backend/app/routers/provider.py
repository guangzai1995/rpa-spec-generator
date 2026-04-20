"""LLM Provider 管理"""
import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from openai import OpenAI

from app.db.engine import SessionLocal
from app.db.models import LLMProvider
from app.models.schemas import LLMProviderCreate, LLMProviderResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/providers")
async def list_providers():
    """获取所有 Provider"""
    db = SessionLocal()
    try:
        providers = db.query(LLMProvider).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "base_url": p.base_url,
                "model_name": p.model_name,
                "api_key_masked": p.api_key[:8] + "****" if p.api_key else "",
                "enabled": p.enabled,
            }
            for p in providers
        ]
    finally:
        db.close()


@router.post("/providers")
async def add_provider(data: LLMProviderCreate):
    """添加 Provider"""
    db = SessionLocal()
    try:
        provider = LLMProvider(
            id=str(uuid.uuid4()),
            name=data.name,
            api_key=data.api_key,
            base_url=data.base_url,
            model_name=data.model_name,
            enabled=1,
        )
        db.add(provider)
        db.commit()
        return {"message": "添加成功", "id": provider.id}
    finally:
        db.close()


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, data: LLMProviderCreate):
    """更新 Provider"""
    db = SessionLocal()
    try:
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider 不存在")

        provider.name = data.name
        provider.api_key = data.api_key
        provider.base_url = data.base_url
        provider.model_name = data.model_name
        db.commit()
        return {"message": "更新成功"}
    finally:
        db.close()


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """删除 Provider"""
    db = SessionLocal()
    try:
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider 不存在")

        db.delete(provider)
        db.commit()
        return {"message": "删除成功"}
    finally:
        db.close()


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: str):
    """测试 Provider 连通性"""
    db = SessionLocal()
    try:
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider 不存在")

        try:
            client = OpenAI(api_key=provider.api_key, base_url=provider.base_url)
            client.models.list()
            return {"success": True, "message": "连接成功"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}
    finally:
        db.close()
