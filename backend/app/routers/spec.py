"""说明书文档下载 + 结构化数据查询 + 时间线编辑"""
import json
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db.engine import SessionLocal
from app.db.models import SpecDoc, Extraction, TimelineStep
from app.models.schemas import TimelineStepSchema, TimelineStepUpdate, ExtractionResult
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/requirements/{req_id}/spec.docx")
async def download_spec(req_id: str):
    """下载需求规格说明书 Word 文档"""
    db = SessionLocal()
    try:
        doc = db.query(SpecDoc).filter(
            SpecDoc.requirement_id == req_id
        ).order_by(SpecDoc.version.desc()).first()

        if not doc:
            raise HTTPException(status_code=404, detail="说明书尚未生成")

        if not os.path.exists(doc.path):
            raise HTTPException(status_code=404, detail="文档文件不存在")

        return FileResponse(
            path=doc.path,
            filename=f"RPA需求规格说明书_{req_id[:8]}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    finally:
        db.close()


@router.get("/requirements/{req_id}/timeline")
async def get_timeline(req_id: str):
    """获取 TimelineStep 列表"""
    db = SessionLocal()
    try:
        steps = db.query(TimelineStep).filter(
            TimelineStep.requirement_id == req_id
        ).order_by(TimelineStep.step_no).all()

        return [
            TimelineStepSchema(
                step_no=s.step_no,
                ts_start=s.ts_start,
                ts_end=s.ts_end,
                action=s.action,
                target_text=s.target_text,
                context_text=s.context_text,
                asr_text=s.asr_text,
                screenshot_path=s.screenshot_path,
            )
            for s in steps
        ]
    finally:
        db.close()


@router.get("/requirements/{req_id}/extraction")
async def get_extraction(req_id: str):
    """获取结构化拆解结果"""
    db = SessionLocal()
    try:
        ext = db.query(Extraction).filter(
            Extraction.requirement_id == req_id
        ).first()

        if not ext:
            raise HTTPException(status_code=404, detail="尚未完成结构化拆解")

        return {
            "business_overview": json.loads(ext.business_overview) if ext.business_overview else {},
            "main_process": json.loads(ext.main_process) if ext.main_process else [],
            "rules": json.loads(ext.rules) if ext.rules else [],
            "io_spec": json.loads(ext.io_spec) if ext.io_spec else {},
            "system_env": json.loads(ext.system_env) if ext.system_env else [],
            "exceptions": json.loads(ext.exceptions) if ext.exceptions else [],
            "model_name": ext.model_name,
        }
    finally:
        db.close()


@router.put("/requirements/{req_id}/timeline/{step_no}")
async def update_timeline_step(req_id: str, step_no: int, data: TimelineStepUpdate):
    """人工修正时间线步骤"""
    db = SessionLocal()
    try:
        step = db.query(TimelineStep).filter(
            TimelineStep.requirement_id == req_id,
            TimelineStep.step_no == step_no,
        ).first()

        if not step:
            raise HTTPException(status_code=404, detail=f"步骤 {step_no} 不存在")

        if data.action is not None:
            step.action = data.action
        if data.target_text is not None:
            step.target_text = data.target_text
        if data.context_text is not None:
            step.context_text = data.context_text
        step.edited_by_user = 1
        db.commit()

        return {"message": "更新成功", "step_no": step_no}
    finally:
        db.close()


@router.get("/requirements/{req_id}/preview")
async def preview_spec(req_id: str):
    """获取说明书预览数据（JSON 格式，供前端渲染）"""
    db = SessionLocal()
    try:
        from app.db.models import Requirement
        req = db.query(Requirement).filter(Requirement.id == req_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="需求不存在")

        ext = db.query(Extraction).filter(Extraction.requirement_id == req_id).first()
        steps = db.query(TimelineStep).filter(
            TimelineStep.requirement_id == req_id
        ).order_by(TimelineStep.step_no).all()

        form_info = json.loads(req.payload_json) if req.payload_json else {}

        extraction_data = {}
        if ext:
            extraction_data = {
                "business_overview": json.loads(ext.business_overview) if ext.business_overview else {},
                "main_process": json.loads(ext.main_process) if ext.main_process else [],
                "rules": json.loads(ext.rules) if ext.rules else [],
                "io_spec": json.loads(ext.io_spec) if ext.io_spec else {},
                "system_env": json.loads(ext.system_env) if ext.system_env else [],
                "exceptions": json.loads(ext.exceptions) if ext.exceptions else [],
                "manual_flow_description": ext.manual_flow_description or "",
                "prerequisites": json.loads(ext.prerequisites) if ext.prerequisites else [],
                "security_requirements": json.loads(ext.security_requirements) if ext.security_requirements else [],
                "feasibility_notes": json.loads(ext.feasibility_notes) if ext.feasibility_notes else [],
                "pending_questions": json.loads(ext.pending_questions) if ext.pending_questions else [],
            }

        timeline = [
            {
                "step_no": s.step_no,
                "ts_start": s.ts_start,
                "ts_end": s.ts_end,
                "action": s.action,
                "target_text": s.target_text,
                "context_text": s.context_text,
                "asr_text": s.asr_text,
                "screenshot_path": s.screenshot_path,
            }
            for s in steps
        ]

        return {
            "title": req.title or form_info.get("title", "RPA 需求规格说明书"),
            "form_info": form_info,
            "extraction": extraction_data,
            "timeline": timeline,
            "status": req.status,
        }
    finally:
        db.close()
