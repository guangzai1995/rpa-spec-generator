"""需求管理 + 视频上传 + 任务提交"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.db.engine import SessionLocal
from app.db.models import Requirement, Asset, RequirementStatus
from app.models.schemas import RequirementCreate, RequirementResponse, TaskStatusResponse
from app.services.pipeline import run_pipeline, OUTPUT_DIR
from app.services.task_executor import task_executor
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/requirements", response_model=RequirementResponse)
async def create_requirement(data: RequirementCreate):
    """创建需求草稿"""
    req_id = str(uuid.uuid4())

    # 将表单数据序列化为 payload_json
    payload = data.model_dump(exclude_none=True)

    db = SessionLocal()
    try:
        req = Requirement(
            id=req_id,
            req_type=data.req_type,
            title=data.title,
            payload_json=json.dumps(payload, ensure_ascii=False),
            creator=data.req_owner,
            status=RequirementStatus.DRAFT.value,
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        return RequirementResponse(
            id=req.id,
            req_type=req.req_type,
            title=req.title,
            status=req.status,
            error_message=req.error_message,
            created_at=str(req.created_at) if req.created_at else None,
            updated_at=str(req.updated_at) if req.updated_at else None,
        )
    finally:
        db.close()


@router.post("/requirements/{req_id}/upload")
async def upload_video(
    req_id: str,
    file: UploadFile = File(...),
):
    """上传视频文件"""
    db = SessionLocal()
    try:
        req = db.query(Requirement).filter(Requirement.id == req_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="需求不存在")

        # 校验文件类型
        allowed_types = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {ext}，支持: {', '.join(allowed_types)}"
            )

        # 保存文件
        save_dir = UPLOAD_DIR / req_id
        save_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = save_dir / safe_filename

        content = await file.read()

        # 校验文件大小 (最大 1GB)
        if len(content) > 1 * 1024 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件过大，最大支持 1GB")

        with open(file_path, "wb") as f:
            f.write(content)

        # 保存素材记录
        asset = Asset(
            id=str(uuid.uuid4()),
            requirement_id=req_id,
            kind="video",
            path=str(file_path),
            original_name=file.filename,
        )
        db.add(asset)
        db.commit()

        return {"message": "上传成功", "asset_id": asset.id, "filename": file.filename}
    finally:
        db.close()


@router.post("/requirements/{req_id}/submit")
async def submit_requirement(req_id: str, background_tasks: BackgroundTasks):
    """提交需求，触发后台解析任务"""
    db = SessionLocal()
    try:
        req = db.query(Requirement).filter(Requirement.id == req_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="需求不存在")

        # 检查是否有视频
        asset = db.query(Asset).filter(
            Asset.requirement_id == req_id,
            Asset.kind == "video"
        ).first()
        if not asset:
            raise HTTPException(status_code=400, detail="请先上传视频文件")

        # 更新状态
        req.status = RequirementStatus.SUBMITTED.value
        req.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    # 异步执行流水线
    task_executor.submit(run_pipeline, req_id)
    logger.info(f"任务已提交: {req_id}")

    return {"message": "任务已提交", "requirement_id": req_id}


@router.get("/requirements/{req_id}/status", response_model=TaskStatusResponse)
async def get_task_status(req_id: str):
    """获取任务状态"""
    # 优先从状态文件读取（更实时）
    status_file = OUTPUT_DIR / f"{req_id}.status.json"
    if status_file.exists():
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
            return TaskStatusResponse(
                requirement_id=req_id,
                status=data.get("status", "unknown"),
                message=data.get("error_message"),
            )
        except Exception:
            pass

    # 从数据库读取
    db = SessionLocal()
    try:
        req = db.query(Requirement).filter(Requirement.id == req_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="需求不存在")

        return TaskStatusResponse(
            requirement_id=req_id,
            status=req.status,
            message=req.error_message,
        )
    finally:
        db.close()


@router.get("/requirements")
async def list_requirements():
    """获取需求列表"""
    db = SessionLocal()
    try:
        reqs = db.query(Requirement).order_by(Requirement.created_at.desc()).all()
        return [
            RequirementResponse(
                id=r.id,
                req_type=r.req_type,
                title=r.title,
                status=r.status,
                error_message=r.error_message,
                created_at=str(r.created_at) if r.created_at else None,
                updated_at=str(r.updated_at) if r.updated_at else None,
            )
            for r in reqs
        ]
    finally:
        db.close()


@router.get("/requirements/{req_id}")
async def get_requirement(req_id: str):
    """获取需求详情"""
    db = SessionLocal()
    try:
        req = db.query(Requirement).filter(Requirement.id == req_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="需求不存在")

        return {
            "id": req.id,
            "req_type": req.req_type,
            "title": req.title,
            "status": req.status,
            "payload": json.loads(req.payload_json) if req.payload_json else {},
            "error_message": req.error_message,
            "created_at": str(req.created_at),
            "updated_at": str(req.updated_at),
        }
    finally:
        db.close()


@router.delete("/requirements/{req_id}")
async def delete_requirement(req_id: str):
    """删除需求"""
    db = SessionLocal()
    try:
        req = db.query(Requirement).filter(Requirement.id == req_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="需求不存在")

        db.delete(req)
        db.commit()
        return {"message": "删除成功"}
    finally:
        db.close()
