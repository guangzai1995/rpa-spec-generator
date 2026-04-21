"""多模态视觉分析服务 - 借鉴 OpenAdapt 的 VLM 方法分析关键帧"""
import base64
import json
import os
from pathlib import Path
from typing import List, Optional

from openai import OpenAI
from PIL import Image

from app.utils.logger import get_logger

logger = get_logger(__name__)

VISION_PROMPT = """/no_think
你是一个专业的 GUI 操作分析师。请仔细分析这张屏幕截图，识别：

1. **当前页面/系统**：这是什么应用或网页？
2. **可见的 UI 元素**：按钮、输入框、菜单、表格等
3. **鼠标位置和可能的操作**：如果能看到光标，描述光标附近的元素
4. **页面状态**：登录页？数据列表？表单？报表？
5. **关键文本内容**：页面上的重要文字信息

请以 JSON 格式输出：
```json
{
  "page_title": "页面标题或系统名称",
  "page_type": "login|form|list|report|dashboard|dialog|other",
  "visible_elements": [
    {"type": "button|input|menu|link|table|text|image", "text": "元素文本", "location": "页面位置描述"}
  ],
  "cursor_action": "点击/输入/选择/无光标",
  "cursor_target": "光标指向的元素描述",
  "key_text": ["页面上的关键文字"],
  "description": "一句话描述当前画面操作"
}
```
仅输出 JSON，不要输出思考过程。"""

SEQUENCE_PROMPT = """/no_think
你是一个专业的 RPA 操作分析师。以下是一组按时间顺序排列的屏幕截图描述，来自一段业务操作录屏。

请分析这些截图的操作序列，归纳出具体的操作步骤。

## 截图分析结果（按时间顺序）
{frame_analyses}

## ASR 语音转录（如果有）
{asr_text}

请输出 JSON 格式的操作步骤：
```json
{{
  "steps": [
    {{
      "step_no": 1,
      "action": "open_url|click|input|select|login|download|export|query|scroll|switch",
      "target": "操作目标描述",
      "context": "操作上下文说明",
      "related_frames": [0, 1]
    }}
  ]
}}
```

要求：
1. 将多个截图归纳为实际的业务操作步骤
2. 相似/连续的截图应归为同一步骤
3. action 使用标准化动作类型
4. related_frames 标注该步骤对应的截图索引
5. 仅输出 JSON"""


def encode_image_base64(image_path: str, max_size: int = 1024) -> str:
    """将图片编码为 base64，自动缩放"""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class VisionAnalyzer:
    """使用多模态 LLM 分析屏幕截图"""

    def __init__(self, api_key: str, base_url: str, model: str):
        import httpx
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(120.0, connect=30.0),
        )
        self.model = model

    def analyze_frame(self, image_path: str) -> dict:
        """分析单张截图"""
        if not os.path.exists(image_path):
            logger.warning(f"图片不存在: {image_path}")
            return {"description": "图片不存在", "page_type": "unknown"}

        try:
            b64 = encode_image_base64(image_path)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VISION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64}",
                                    "detail": "high"
                                },
                            },
                        ],
                    }
                ],
                temperature=0.2,
                max_tokens=1024,
            )
            content = response.choices[0].message.content.strip()
            return self._parse_json(content)
        except Exception as e:
            logger.warning(f"视觉分析失败 {image_path}: {e}")
            return {"description": f"分析失败: {str(e)}", "page_type": "unknown"}

    def analyze_sequence(
        self,
        frame_analyses: List[dict],
        asr_text: str = "",
    ) -> List[dict]:
        """分析截图序列，归纳操作步骤"""
        if not frame_analyses:
            return []

        analyses_text = ""
        for i, analysis in enumerate(frame_analyses):
            ts = analysis.get("timestamp", 0)
            desc = analysis.get("description", "")
            page = analysis.get("page_title", "")
            mm = int(ts // 60)
            ss = int(ts % 60)
            analyses_text += f"[{mm:02d}:{ss:02d}] 截图{i}: {page} - {desc}\n"
            elements = analysis.get("visible_elements", [])
            if elements:
                for elem in elements[:5]:
                    analyses_text += f"  - {elem.get('type', '')}: {elem.get('text', '')}\n"

        prompt = SEQUENCE_PROMPT.format(
            frame_analyses=analyses_text,
            asr_text=asr_text or "无语音转录",
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是 RPA 操作分析专家。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            content = response.choices[0].message.content.strip()
            parsed = self._parse_json(content)
            return parsed.get("steps", [])
        except Exception as e:
            logger.warning(f"序列分析失败: {e}")
            return []

    def _parse_json(self, text: str) -> dict:
        """从 LLM 响应中提取 JSON（兼容 Qwen 的 thinking 模式）"""
        import re

        # 移除 Qwen 的 <think>...</think> 块
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 移除编号列表形式的思考过程（如 "1. **分析**：..."）
        # 只在文本开头有思考过程、末尾有 JSON 时处理
        json_start = text.find("{")
        if json_start > 0:
            # 尝试从第一个 { 开始解析
            candidate = text[json_start:]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {"description": text[:200], "page_type": "unknown"}
