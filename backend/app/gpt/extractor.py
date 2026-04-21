import json
import os
import re
import time
from typing import Optional

from openai import OpenAI
import httpx

from app.gpt.prompts import SYSTEM_PROMPT, PROMPT_FULL_EXTRACTION
from app.models.schemas import ExtractionResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RPAExtractor:
    """调用 LLM 进行 RPA 需求结构化拆解"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(120.0, connect=30.0),
        )
        self.model = model
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        self.retry_backoff = float(os.getenv("LLM_RETRY_BACKOFF", "2.0"))

    def extract(
        self,
        form_info: str,
        asr_text: str,
        timeline_steps: str,
    ) -> ExtractionResult:
        """执行完整的结构化拆解"""
        prompt = PROMPT_FULL_EXTRACTION.format(
            form_info=form_info,
            asr_text=asr_text,
            timeline_steps=timeline_steps,
        )

        for attempt in range(self.max_retries):
            try:
                logger.info(f"LLM 结构化拆解 (尝试 {attempt + 1}/{self.max_retries})")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=4096,
                )

                content = response.choices[0].message.content.strip()
                logger.info(f"LLM 原始响应长度: {len(content)}")

                # 解析 JSON
                parsed = self._parse_json(content)
                result = ExtractionResult(**parsed)
                logger.info("结构化拆解成功")
                return result

            except Exception as e:
                logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff * (attempt + 1))

        # 返回默认空结果
        logger.error("所有重试均失败，返回默认结果")
        return ExtractionResult()

    def _parse_json(self, text: str) -> dict:
        """从 LLM 响应中提取 JSON（兼容 Qwen thinking 模式）"""
        # 移除 <think>...</think> 块
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试从第一个 { 开始提取到最后一个 }
        json_start = text.find("{")
        json_end = text.rfind("}")
        if json_start >= 0 and json_end > json_start:
            try:
                return json.loads(text[json_start:json_end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法从 LLM 响应中解析 JSON: {text[:200]}")
