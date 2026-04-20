"""系统健康检查"""
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "rpa-spec-generator"}
