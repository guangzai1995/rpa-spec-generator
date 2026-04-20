"""Word 文档生成器：使用 docxtpl 渲染 RPA 需求规格说明书"""
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from PIL import Image as PILImage

from app.models.schemas import ExtractionResult
from app.utils.logger import get_logger

logger = get_logger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
OUTPUT_DIR = Path(os.getenv("STATIC_DIR", "static")) / "docs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_image(path: str) -> io.BytesIO:
    """用 PIL 重新编码图片，确保 python-docx 能识别格式"""
    img = PILImage.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_spec_doc(
    requirement_id: str,
    title: str,
    form_info: dict,
    extraction: ExtractionResult,
    screenshot_paths: Optional[List[str]] = None,
    template_path: Optional[str] = None,
) -> str:
    """生成 RPA 需求规格说明书 Word 文档"""
    if template_path is None:
        template_path = str(TEMPLATE_DIR / "rpa_spec_template.docx")

    if not os.path.exists(template_path):
        logger.warning(f"模板文件不存在: {template_path}，使用纯 python-docx 生成")
        return _generate_without_template(
            requirement_id, title, form_info, extraction, screenshot_paths
        )

    logger.info(f"使用模板生成文档: {template_path}")
    doc = DocxTemplate(template_path)

    # 构建模板上下文
    context = _build_context(title, form_info, extraction)

    # 插入截图
    if screenshot_paths:
        images = []
        for i, path in enumerate(screenshot_paths):
            if os.path.exists(path):
                try:
                    img_buf = _normalize_image(path)
                    img = InlineImage(doc, img_buf, width=Mm(140))
                    images.append({"no": i + 1, "image": img, "desc": f"步骤 {i + 1} 截图"})
                except Exception as e:
                    logger.warning(f"插入截图失败 {path}: {e}")
        context["screenshots"] = images

    doc.render(context)
    output_path = str(OUTPUT_DIR / f"{requirement_id}_spec.docx")
    doc.save(output_path)
    logger.info(f"文档已生成: {output_path}")
    return output_path


def _generate_without_template(
    requirement_id: str,
    title: str,
    form_info: dict,
    extraction: ExtractionResult,
    screenshot_paths: Optional[List[str]] = None,
) -> str:
    """不使用模板，直接用 python-docx 生成文档"""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = Document()

    # ========== 设置默认字体 ==========
    style = doc.styles['Normal']
    font = style.font
    font.name = '宋体'
    font.size = Pt(11)

    # ========== 封面 ==========
    doc.add_paragraph("")
    doc.add_paragraph("")
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_title.add_run(f"{title or 'RPA 需求规格说明书'}")
    run.font.size = Pt(22)
    run.font.bold = True

    doc.add_paragraph("")
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p_sub.add_run("RPA 需求规格说明书")
    run.font.size = Pt(16)

    doc.add_paragraph("")
    doc.add_paragraph("")

    # 文档信息表
    info_table = doc.add_table(rows=4, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_data = [
        ("文档编号", requirement_id[:8].upper()),
        ("版本号", "V1.0"),
        ("编写日期", datetime.now().strftime("%Y-%m-%d")),
        ("需求部门", form_info.get("req_dept", "")),
    ]
    for i, (k, v) in enumerate(info_data):
        info_table.cell(i, 0).text = k
        info_table.cell(i, 1).text = v

    doc.add_page_break()

    # ========== 1. 客户需求概述 ==========
    doc.add_heading("1. 客户需求概述", level=1)

    doc.add_heading("1.1 需求来源", level=2)
    doc.add_paragraph(f"需求部门：{form_info.get('req_dept', '—')}")
    doc.add_paragraph(f"需求提出人：{form_info.get('req_owner', '—')}")

    doc.add_heading("1.2 需求背景", level=2)
    overview = extraction.business_overview
    doc.add_paragraph(overview.scope if overview.scope else "通过 RPA 自动化替代人工重复操作，提升效率。")

    doc.add_heading("1.3 自动化目标", level=2)
    doc.add_paragraph(overview.auto_goal if overview.auto_goal else "—")

    # ========== 2. 业务需求分析 ==========
    doc.add_heading("2. 业务需求分析", level=1)

    doc.add_heading("2.1 需求类型", level=2)
    doc.add_paragraph(f"业务类型：{form_info.get('req_type', '—')}")

    doc.add_heading("2.2 业务场景", level=2)
    doc.add_paragraph(f"执行频率：{form_info.get('exec_frequency', '—')}")
    doc.add_paragraph(f"目标系统：{form_info.get('target_url', '—')}")
    doc.add_paragraph(f"是否需要登录：{'是' if form_info.get('login_required') else '否'}")

    # ========== 3. 系统需求分析 ==========
    doc.add_heading("3. 系统需求分析", level=1)

    doc.add_heading("3.1 涉及系统", level=2)
    if extraction.system_env:
        sys_table = doc.add_table(rows=1, cols=3)
        sys_table.style = 'Table Grid'
        hdr = sys_table.rows[0].cells
        hdr[0].text = "系统名称"
        hdr[1].text = "认证方式"
        hdr[2].text = "浏览器要求"
        for env in extraction.system_env:
            row = sys_table.add_row().cells
            row[0].text = env.name
            row[1].text = env.auth or "—"
            row[2].text = env.browser or "—"
    else:
        doc.add_paragraph("—")

    # ========== 4. 功能需求描述 ==========
    doc.add_heading("4. 功能需求描述", level=1)

    doc.add_heading("4.1 处理流程", level=2)
    for proc in extraction.main_process:
        doc.add_heading(f"4.1.{extraction.main_process.index(proc) + 1} {proc.name}", level=3)

        step_table = doc.add_table(rows=1, cols=4)
        step_table.style = 'Table Grid'
        hdr = step_table.rows[0].cells
        hdr[0].text = "序号"
        hdr[1].text = "操作类型"
        hdr[2].text = "操作目标"
        hdr[3].text = "参数/值"

        for step in proc.steps:
            row = step_table.add_row().cells
            row[0].text = str(step.no)
            row[1].text = step.action
            row[2].text = step.target
            row[3].text = step.value or step.result_file or "—"

        # 插入对应截图（为每个流程均匀分配截图）
        if screenshot_paths:
            # 计算当前流程对应的截图范围
            total_procs = len(extraction.main_process)
            proc_idx = extraction.main_process.index(proc)
            per_proc = max(1, len(screenshot_paths) // total_procs)
            start_idx = proc_idx * per_proc
            end_idx = start_idx + per_proc if proc_idx < total_procs - 1 else len(screenshot_paths)
            # 取该范围的中间帧作为代表
            mid_idx = (start_idx + end_idx) // 2
            if mid_idx < len(screenshot_paths):
                path = screenshot_paths[mid_idx]
                if os.path.exists(path):
                    doc.add_paragraph("")
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    try:
                        img_buf = _normalize_image(path)
                        run = p.add_run()
                        run.add_picture(img_buf, width=Inches(5.0))
                    except Exception as e:
                        logger.warning(f"插入截图失败 {path}: {e}")
                    cap = doc.add_paragraph()
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cap_run = cap.add_run(f"图 {proc_idx + 1}: {proc.name}")
                    cap_run.font.size = Pt(9)
                    cap_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    # ========== 4.2 输入输出规范 ==========
    doc.add_heading("4.2 输入输出规范", level=2)

    doc.add_heading("4.2.1 输入", level=3)
    for item in extraction.io_spec.input:
        doc.add_paragraph(f"• {item}")

    doc.add_heading("4.2.2 输出", level=3)
    for item in extraction.io_spec.output:
        doc.add_paragraph(f"• {item}")

    # ========== 5. 业务规则与约束 ==========
    doc.add_heading("5. 业务规则与约束", level=1)
    if extraction.rules:
        for i, rule in enumerate(extraction.rules, 1):
            doc.add_paragraph(f"{i}. {rule}")
    else:
        doc.add_paragraph("暂无特殊业务规则。")

    # ========== 6. 异常处理 ==========
    doc.add_heading("6. 异常处理", level=1)
    if extraction.exceptions:
        exc_table = doc.add_table(rows=1, cols=2)
        exc_table.style = 'Table Grid'
        hdr = exc_table.rows[0].cells
        hdr[0].text = "异常代码"
        hdr[1].text = "处理方式"
        for exc in extraction.exceptions:
            row = exc_table.add_row().cells
            row[0].text = exc.code
            row[1].text = exc.handler
    else:
        doc.add_paragraph("暂无异常处理策略。")

    # ========== 7. 非功能需求 ==========
    doc.add_heading("7. 非功能需求", level=1)
    doc.add_paragraph("1. 执行环境：Windows 10 及以上")
    doc.add_paragraph("2. 浏览器：Chrome 120 及以上版本")
    doc.add_paragraph("3. 网络要求：可访问目标系统")
    doc.add_paragraph("4. 性能要求：单次执行时间 ≤ 10 分钟")
    doc.add_paragraph("5. 日志：执行过程需记录详细日志")

    # 保存
    output_path = str(OUTPUT_DIR / f"{requirement_id}_spec.docx")
    doc.save(output_path)
    logger.info(f"文档已生成（无模板模式）: {output_path}")
    return output_path


def _build_context(title: str, form_info: dict, extraction: ExtractionResult) -> dict:
    """构建 docxtpl 模板上下文"""
    now = datetime.now()
    return {
        "doc_title": title or "RPA 需求规格说明书",
        "doc_id": form_info.get("requirement_id", "")[:8].upper(),
        "doc_version": "V1.0",
        "doc_date": now.strftime("%Y-%m-%d"),
        "req_dept": form_info.get("req_dept", ""),
        "req_owner": form_info.get("req_owner", ""),
        "req_type": form_info.get("req_type", ""),
        "target_url": form_info.get("target_url", ""),
        "login_required": "是" if form_info.get("login_required") else "否",
        "exec_frequency": form_info.get("exec_frequency", ""),
        "auto_goal": extraction.business_overview.auto_goal,
        "scope": extraction.business_overview.scope,
        "main_process": [
            {
                "name": p.name,
                "steps": [
                    {
                        "no": s.no,
                        "action": s.action,
                        "target": s.target,
                        "value": s.value or s.result_file or "",
                    }
                    for s in p.steps
                ],
            }
            for p in extraction.main_process
        ],
        "io_input": extraction.io_spec.input,
        "io_output": extraction.io_spec.output,
        "rules": extraction.rules,
        "system_env": [
            {"name": e.name, "auth": e.auth or "", "browser": e.browser or ""}
            for e in extraction.system_env
        ],
        "exceptions": [
            {"code": e.code, "handler": e.handler}
            for e in extraction.exceptions
        ],
    }
