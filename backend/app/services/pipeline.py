"""RPA 需求规格说明书生成主流水线 - 借鉴 OpenAdapt 多模态方法"""
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from app.services.vision_analyzer import VisionAnalyzer
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

        # 获取 LLM 配置（结构化文本提取）
        provider = db.query(LLMProvider).filter(LLMProvider.enabled == 1).first()
        llm_api_key = os.getenv("LLM_API_KEY") or (provider.api_key if provider else None)
        llm_base_url = os.getenv("LLM_BASE_URL") or (provider.base_url if provider else None)
        llm_model = os.getenv("LLM_MODEL") or (provider.model_name if provider else None)

        if not all([llm_api_key, llm_base_url, llm_model]):
            _update_status(requirement_id, RequirementStatus.FAILED.value,
                          "未配置 LLM Provider（.env 或数据库中均未找到）")
            return

        # 获取视觉分析模型配置（多模态，可独立于文本模型）
        vision_api_key = os.getenv("VISION_API_KEY") or llm_api_key
        vision_base_url = os.getenv("VISION_BASE_URL") or llm_base_url
        vision_model = os.getenv("VISION_MODEL") or llm_model

        logger.info(f"[{requirement_id}] 文本模型: {llm_model} | 视觉模型: {vision_model}")

    finally:
        db.close()

    try:
        timings = {}
        pipeline_start = time.time()

        # ========== 1. 预处理 ==========
        _update_status(requirement_id, RequirementStatus.PREPROCESSING.value)
        logger.info(f"[{requirement_id}] 开始预处理...")
        t0 = time.time()
        video_info = get_video_info(video_path)
        logger.info(f"[{requirement_id}] 视频信息: {video_info}")
        timings["preprocess"] = time.time() - t0

        # ========== 2+3. ASR 转录 ‖ 关键帧提取（并发）==========
        _update_status(requirement_id, RequirementStatus.TRANSCRIBING.value)
        logger.info(f"[{requirement_id}] 开始 ASR 转录 + 关键帧提取（并发）...")

        whisper_model = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")
        whisper_device = os.getenv("WHISPER_DEVICE", "cuda")
        whisper_model_dir = os.getenv("WHISPER_MODEL_DIR", None)

        duration = video_info.get("duration", 300)
        frame_interval = max(3, int(duration / 60))

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="stage2") as pool:
            asr_future = pool.submit(
                transcribe_video,
                video_path=video_path,
                requirement_id=requirement_id,
                glossary=glossary,
                model_size=whisper_model,
                device=whisper_device,
                model_dir=whisper_model_dir,
            )
            frames_future = pool.submit(
                extract_keyframes,
                video_path=video_path,
                requirement_id=requirement_id,
                interval=frame_interval,
                max_frames=60,
            )
            transcript = asr_future.result()
            frames = frames_future.result()
        timings["asr_and_keyframes"] = time.time() - t0
        logger.info(f"[{requirement_id}] ASR 完成 {len(transcript.segments)} 段 + 关键帧 {len(frames)} 帧 (并发耗时 {timings['asr_and_keyframes']:.1f}s)")

        # ========== 3.5 多模态视觉分析（并发 API 调用）==========
        _update_status(requirement_id, RequirementStatus.ANALYZING.value)
        vision_enabled = os.getenv("VISION_ENABLED", "true").lower() == "true"
        frame_analyses = []
        if vision_enabled and frames:
            logger.info(f"[{requirement_id}] 多模态视觉分析 (model={vision_model}, 并发模式)...")
            t0 = time.time()
            try:
                analyzer = VisionAnalyzer(
                    api_key=vision_api_key,
                    base_url=vision_base_url,
                    model=vision_model,
                )
                # 采样帧
                max_vision = 15
                if len(frames) > max_vision:
                    step = len(frames) / max_vision
                    sampled_frames = [frames[int(i * step)] for i in range(max_vision)]
                else:
                    sampled_frames = frames

                # 并发分析帧（3 线程并发调用 API）
                vision_concurrency = int(os.getenv("VISION_CONCURRENCY", "3"))
                frame_analyses = [None] * len(sampled_frames)

                def _analyze_one(idx, frame):
                    analysis = analyzer.analyze_frame(frame.path)
                    analysis["timestamp"] = frame.timestamp
                    return idx, analysis

                with ThreadPoolExecutor(max_workers=vision_concurrency, thread_name_prefix="vision") as pool:
                    futures = [pool.submit(_analyze_one, i, f) for i, f in enumerate(sampled_frames)]
                    for future in as_completed(futures):
                        idx, analysis = future.result()
                        frame_analyses[idx] = analysis
                        logger.info(f"  帧 {analysis['timestamp']:.1f}s: {analysis.get('description', '')[:60]}")

                # 序列分析
                if frame_analyses:
                    vision_steps = analyzer.analyze_sequence(
                        frame_analyses, transcript.full_text
                    )
                    logger.info(f"[{requirement_id}] 视觉分析识别出 {len(vision_steps)} 个操作步骤")
            except Exception as ve:
                logger.warning(f"[{requirement_id}] 视觉分析失败（降级继续）: {ve}")
                frame_analyses = []
            timings["vision_analysis"] = time.time() - t0
            logger.info(f"[{requirement_id}] 视觉分析耗时: {timings['vision_analysis']:.1f}s")

        # 保存 TimelineStep 到数据库
        _save_timeline_steps(requirement_id, transcript, frames, frame_analyses)

        # ========== 4. LLM 结构化拆解 ==========
        _update_status(requirement_id, RequirementStatus.EXTRACTING.value)
        logger.info(f"[{requirement_id}] LLM 结构化拆解...")
        t0 = time.time()

        # 构建 LLM 输入（融合 ASR + 视觉分析）
        asr_text = transcript.full_text
        timeline_text = _format_timeline_for_llm(transcript, frames, frame_analyses)

        extractor = RPAExtractor(
            api_key=llm_api_key,
            base_url=llm_base_url,
            model=llm_model,
        )

        extraction = extractor.extract(
            form_info=json.dumps(form_info, ensure_ascii=False),
            asr_text=asr_text,
            timeline_steps=timeline_text,
        )
        timings["llm_extraction"] = time.time() - t0
        logger.info(f"[{requirement_id}] LLM 拆解耗时: {timings['llm_extraction']:.1f}s")

        # 保存拆解结果
        _save_extraction(requirement_id, extraction, llm_model)

        # ========== 5. Word 文档生成 ==========
        _update_status(requirement_id, RequirementStatus.GENERATING.value)
        logger.info(f"[{requirement_id}] 生成 Word 文档...")
        t0 = time.time()

        screenshot_paths = [(f.path, f.timestamp) for f in frames if f.path and os.path.exists(f.path)]
        logger.info(f"[{requirement_id}] 可用截图数: {len(screenshot_paths)}")

        # 构建帧描述映射（timestamp → 视觉描述）供文档生成器做相关性过滤
        frame_desc_map = {}
        if frame_analyses:
            for a in frame_analyses:
                ts = a.get("timestamp", 0)
                desc = a.get("description", "")
                page = a.get("page_title", "")
                if page and desc:
                    frame_desc_map[ts] = f"{page} - {desc}"
                elif desc:
                    frame_desc_map[ts] = desc
                elif page:
                    frame_desc_map[ts] = page

        doc_path = generate_spec_doc(
            requirement_id=requirement_id,
            title=req.title or form_info.get("title", "RPA 需求规格说明书"),
            form_info={**form_info, "requirement_id": requirement_id},
            extraction=extraction,
            screenshot_paths=screenshot_paths,
            frame_descriptions=frame_desc_map if frame_desc_map else None,
        )
        timings["doc_generation"] = time.time() - t0
        logger.info(f"[{requirement_id}] 文档生成耗时: {timings['doc_generation']:.1f}s")

        # 保存文档记录
        _save_spec_doc(requirement_id, doc_path)

        # ========== 完成 ==========
        timings["total"] = time.time() - pipeline_start
        _update_status(requirement_id, RequirementStatus.SUCCESS.value)

        # 输出性能报告
        logger.info(f"[{requirement_id}] ===== 性能报告 =====")
        for stage, elapsed in timings.items():
            logger.info(f"[{requirement_id}]   {stage}: {elapsed:.1f}s")
        logger.info(f"[{requirement_id}] 流水线完成! 总耗时 {timings['total']:.1f}s")

    except Exception as e:
        logger.exception(f"[{requirement_id}] 流水线失败: {e}")
        _update_status(requirement_id, RequirementStatus.FAILED.value, str(e))


def _save_timeline_steps(
    requirement_id: str,
    transcript,
    frames: List[FrameInfo],
    frame_analyses: List[dict] = None,
):
    """将解析结果保存为 TimelineStep（融合 ASR + 视觉分析）"""
    db = SessionLocal()
    try:
        # 清除旧数据
        db.query(TimelineStep).filter(
            TimelineStep.requirement_id == requirement_id
        ).delete()

        # 构建帧分析索引
        analysis_map = {}
        if frame_analyses:
            for a in frame_analyses:
                ts = a.get("timestamp", 0)
                analysis_map[ts] = a

        # 将 ASR 段与关键帧对齐
        step_no = 0
        for seg in transcript.segments:
            step_no += 1
            # 找到最近的关键帧
            screenshot = None
            context_text = ""
            action = "unknown"
            target_text = ""

            best_frame = None
            best_dist = float("inf")
            for f in frames:
                dist = abs(f.timestamp - seg.start)
                if dist < best_dist:
                    best_dist = dist
                    best_frame = f

            if best_frame and best_dist < 8:
                screenshot = best_frame.path
                # 查找视觉分析结果
                analysis = analysis_map.get(best_frame.timestamp, {})
                if analysis:
                    action_hint = analysis.get("cursor_action", "")
                    if "点击" in action_hint:
                        action = "click"
                    elif "输入" in action_hint:
                        action = "input"
                    elif "选择" in action_hint:
                        action = "select"

                    target_text = analysis.get("cursor_target", "")
                    context_text = analysis.get("description", "")

            step = TimelineStep(
                requirement_id=requirement_id,
                step_no=step_no,
                ts_start=seg.start,
                ts_end=seg.end,
                action=action,
                target_text=target_text,
                context_text=context_text,
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
            "manual_flow_description": result.manual_flow_description or "",
            "prerequisites": json.dumps(result.prerequisites, ensure_ascii=False),
            "security_requirements": json.dumps(result.security_requirements, ensure_ascii=False),
            "feasibility_notes": json.dumps(result.feasibility_notes, ensure_ascii=False),
            "pending_questions": json.dumps(result.pending_questions, ensure_ascii=False),
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


def _format_timeline_for_llm(transcript, frames: List[FrameInfo], frame_analyses: List[dict] = None) -> str:
    """格式化时间线供 LLM 消费（融合 ASR + 视觉分析）"""
    # 构建帧分析索引
    analysis_map = {}
    if frame_analyses:
        for a in frame_analyses:
            ts = a.get("timestamp", 0)
            analysis_map[ts] = a

    lines = []
    for seg in transcript.segments:
        mm = int(seg.start // 60)
        ss = int(seg.start % 60)
        time_str = f"{mm:02d}:{ss:02d}"

        # 找最近的关键帧及其分析
        vision_info = ""
        for f in frames:
            if abs(f.timestamp - seg.start) < 8:
                analysis = analysis_map.get(f.timestamp, {})
                if analysis:
                    page = analysis.get("page_title", "")
                    desc = analysis.get("description", "")
                    cursor = analysis.get("cursor_action", "")
                    target = analysis.get("cursor_target", "")
                    parts = []
                    if page:
                        parts.append(f"页面:{page}")
                    if desc:
                        parts.append(f"画面:{desc}")
                    if cursor and cursor != "无光标":
                        parts.append(f"操作:{cursor}")
                    if target:
                        parts.append(f"目标:{target}")
                    if parts:
                        vision_info = " | " + " | ".join(parts)
                break

        has_frame = any(abs(f.timestamp - seg.start) < 8 for f in frames)
        frame_mark = " [截图]" if has_frame else ""

        lines.append(f"[{time_str}]{frame_mark}{vision_info} 语音: {seg.text}")

    return "\n".join(lines)
