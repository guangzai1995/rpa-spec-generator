"""RPA 需求规格说明书生成主流水线"""
import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from app.db.engine import SessionLocal
from app.db.models import (
    Requirement, Asset, TimelineStep, Extraction, SpecDoc, LLMProvider,
    RequirementStatus
)
from app.gpt.extractor import RPAExtractor
from app.models.schemas import ExtractionResult
from app.services.parser import (
    transcribe_video, extract_keyframes, get_video_info, FrameInfo
)
from app.services.doc_generator import generate_spec_doc
from app.utils.logger import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _update_status(requirement_id: str, status: str, error_message: str = None):
    """更新需求状态"""
    db = SessionLocal()
    try:
        req = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        if req:
            req.status = status
            req.error_message = error_message
            req.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()

    # 同时写状态文件（便于轮询）
    status_file = OUTPUT_DIR / f"{requirement_id}.status.json"
    status_data = {"status": status, "error_message": error_message}
    status_file.write_text(json.dumps(status_data, ensure_ascii=False), encoding="utf-8")


def run_pipeline(requirement_id: str):
    """
    主流水线：
    1. 预处理（视频信息提取）
    2. ASR 转录
    3. 关键帧提取
    4. LLM 结构化拆解
    5. Word 文档生成
    """
    db = SessionLocal()
    try:
        req = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        if not req:
            logger.error(f"需求 {requirement_id} 不存在")
            return

        # 获取视频素材
        asset = db.query(Asset).filter(
            Asset.requirement_id == requirement_id,
            Asset.kind == "video"
        ).first()
        if not asset:
            _update_status(requirement_id, RequirementStatus.FAILED.value,
                          "未找到上传的视频文件")
            return

        video_path = asset.path
        if not os.path.exists(video_path):
            _update_status(requirement_id, RequirementStatus.FAILED.value,
                          f"视频文件不存在: {video_path}")
            return

        # 解析表单信息
        form_info = json.loads(req.payload_json) if req.payload_json else {}
        glossary = form_info.get("glossary", [])

        # 获取 LLM 配置
        provider = db.query(LLMProvider).filter(LLMProvider.enabled == 1).first()
        if not provider:
            _update_status(requirement_id, RequirementStatus.FAILED.value,
                          "未配置 LLM Provider，请先在设置中添加")
            return

    finally:
        db.close()

    try:
        # ========== 1. 预处理 ==========
        _update_status(requirement_id, RequirementStatus.PREPROCESSING.value)
        logger.info(f"[{requirement_id}] 开始预处理...")
        video_info = get_video_info(video_path)
        logger.info(f"[{requirement_id}] 视频信息: {video_info}")

        # ========== 2. ASR 转录 ==========
        _update_status(requirement_id, RequirementStatus.TRANSCRIBING.value)
        logger.info(f"[{requirement_id}] 开始 ASR 转录...")

        whisper_model = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
        whisper_device = os.getenv("WHISPER_DEVICE", "cuda")
        whisper_model_dir = os.getenv("WHISPER_MODEL_DIR", None)

        transcript = transcribe_video(
            video_path=video_path,
            requirement_id=requirement_id,
            glossary=glossary,
            model_size=whisper_model,
            device=whisper_device,
            model_dir=whisper_model_dir,
        )
        logger.info(f"[{requirement_id}] ASR 完成，共 {len(transcript.segments)} 段")

        # ========== 3. 关键帧提取 ==========
        _update_status(requirement_id, RequirementStatus.ANALYZING.value)
        logger.info(f"[{requirement_id}] 提取关键帧...")

        frames = extract_keyframes(
            video_path=video_path,
            requirement_id=requirement_id,
            interval=max(5, int(video_info.get("duration", 300) / 40)),
            max_frames=40,
        )

        # 保存 TimelineStep 到数据库
        _save_timeline_steps(requirement_id, transcript, frames)

        # ========== 4. LLM 结构化拆解 ==========
        _update_status(requirement_id, RequirementStatus.EXTRACTING.value)
        logger.info(f"[{requirement_id}] LLM 结构化拆解...")

        # 构建 LLM 输入
        asr_text = transcript.full_text
        timeline_text = _format_timeline_for_llm(transcript, frames)

        extractor = RPAExtractor(
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=provider.model_name,
        )

        extraction = extractor.extract(
            form_info=json.dumps(form_info, ensure_ascii=False),
            asr_text=asr_text,
            timeline_steps=timeline_text,
        )

        # 保存拆解结果
        _save_extraction(requirement_id, extraction, provider.model_name)

        # ========== 5. Word 文档生成 ==========
        _update_status(requirement_id, RequirementStatus.GENERATING.value)
        logger.info(f"[{requirement_id}] 生成 Word 文档...")

        screenshot_paths = [f.path for f in frames if f.path and os.path.exists(f.path)]
        logger.info(f"[{requirement_id}] 可用截图数: {len(screenshot_paths)}")

        doc_path = generate_spec_doc(
            requirement_id=requirement_id,
            title=req.title or form_info.get("title", "RPA 需求规格说明书"),
            form_info={**form_info, "requirement_id": requirement_id},
            extraction=extraction,
            screenshot_paths=screenshot_paths,
        )

        # 保存文档记录
        _save_spec_doc(requirement_id, doc_path)

        # ========== 完成 ==========
        _update_status(requirement_id, RequirementStatus.SUCCESS.value)
        logger.info(f"[{requirement_id}] 流水线完成!")

    except Exception as e:
        logger.exception(f"[{requirement_id}] 流水线失败: {e}")
        _update_status(requirement_id, RequirementStatus.FAILED.value, str(e))


def _save_timeline_steps(
    requirement_id: str,
    transcript,
    frames: List[FrameInfo],
):
    """将解析结果保存为 TimelineStep"""
    db = SessionLocal()
    try:
        # 清除旧数据
        db.query(TimelineStep).filter(
            TimelineStep.requirement_id == requirement_id
        ).delete()

        # 将 ASR 段与关键帧对齐
        step_no = 0
        for seg in transcript.segments:
            step_no += 1
            # 找到最近的关键帧
            screenshot = None
            for f in frames:
                if abs(f.timestamp - seg.start) < 5:
                    screenshot = f.path
                    break

            step = TimelineStep(
                requirement_id=requirement_id,
                step_no=step_no,
                ts_start=seg.start,
                ts_end=seg.end,
                action="unknown",
                target_text="",
                asr_text=seg.text,
                screenshot_path=screenshot,
            )
            db.add(step)

        db.commit()
        logger.info(f"保存了 {step_no} 个 TimelineStep")
    finally:
        db.close()


def _save_extraction(requirement_id: str, result: ExtractionResult, model_name: str):
    """保存结构化拆解结果"""
    db = SessionLocal()
    try:
        existing = db.query(Extraction).filter(
            Extraction.requirement_id == requirement_id
        ).first()

        data = {
            "requirement_id": requirement_id,
            "business_overview": result.business_overview.model_dump_json(),
            "main_process": json.dumps(
                [p.model_dump() for p in result.main_process], ensure_ascii=False
            ),
            "rules": json.dumps(result.rules, ensure_ascii=False),
            "io_spec": result.io_spec.model_dump_json(),
            "system_env": json.dumps(
                [s.model_dump() for s in result.system_env], ensure_ascii=False
            ),
            "exceptions": json.dumps(
                [e.model_dump() for e in result.exceptions], ensure_ascii=False
            ),
            "model_name": model_name,
            "created_at": datetime.utcnow(),
        }

        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            db.add(Extraction(**data))

        db.commit()
    finally:
        db.close()


def _save_spec_doc(requirement_id: str, doc_path: str):
    """保存文档记录"""
    db = SessionLocal()
    try:
        doc = SpecDoc(
            id=str(uuid.uuid4()),
            requirement_id=requirement_id,
            version=1,
            path=doc_path,
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()


def _format_timeline_for_llm(transcript, frames: List[FrameInfo]) -> str:
    """格式化时间线供 LLM 消费"""
    lines = []
    for seg in transcript.segments:
        mm = int(seg.start // 60)
        ss = int(seg.start % 60)
        time_str = f"{mm:02d}:{ss:02d}"

        # 检查是否有对应关键帧
        has_frame = any(abs(f.timestamp - seg.start) < 5 for f in frames)
        frame_mark = " [有截图]" if has_frame else ""

        lines.append(f"[{time_str}]{frame_mark} {seg.text}")

    return "\n".join(lines)
