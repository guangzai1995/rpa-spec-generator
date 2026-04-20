"""视频解析服务：预处理 + ASR + 关键帧提取"""
import json
import os
import subprocess
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass, asdict, field

import ffmpeg
from PIL import Image

from app.utils.logger import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR = Path(os.getenv("OUT_DIR", "./static/screenshots"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    full_text: str
    language: Optional[str] = None
    segments: List[TranscriptSegment] = field(default_factory=list)


@dataclass
class FrameInfo:
    timestamp: float
    path: str
    description: str = ""


def extract_audio(video_path: str, output_path: str = None) -> str:
    """从视频中提取音频（16kHz mono wav）"""
    if output_path is None:
        base = Path(video_path).stem
        output_path = str(OUTPUT_DIR / f"{base}_audio.wav")

    if os.path.exists(output_path):
        logger.info(f"音频缓存已存在: {output_path}")
        return output_path

    logger.info(f"提取音频: {video_path} -> {output_path}")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        "-y", output_path,
        "-hide_banner", "-loglevel", "error"
    ]
    subprocess.run(cmd, check=True)
    return output_path


def get_video_info(video_path: str) -> dict:
    """获取视频元信息"""
    try:
        probe = ffmpeg.probe(video_path)
        video_stream = next(
            (s for s in probe["streams"] if s["codec_type"] == "video"), None
        )
        info = {
            "duration": float(probe["format"].get("duration", 0)),
            "width": int(video_stream["width"]) if video_stream else 0,
            "height": int(video_stream["height"]) if video_stream else 0,
            "fps": eval(video_stream.get("r_frame_rate", "0/1")) if video_stream else 0,
        }
        return info
    except Exception as e:
        logger.warning(f"获取视频信息失败: {e}")
        return {"duration": 0, "width": 0, "height": 0, "fps": 0}


def extract_keyframes(
    video_path: str,
    requirement_id: str,
    interval: int = 5,
    max_frames: int = 50,
) -> List[FrameInfo]:
    """按固定间隔提取关键帧"""
    frame_dir = SCREENSHOT_DIR / requirement_id
    frame_dir.mkdir(parents=True, exist_ok=True)

    info = get_video_info(video_path)
    duration = info["duration"]
    if duration <= 0:
        logger.warning("视频时长为 0，跳过关键帧提取")
        return []

    timestamps = list(range(0, int(duration), interval))[:max_frames]
    frames: List[FrameInfo] = []

    for ts in timestamps:
        mm = int(ts // 60)
        ss = int(ts % 60)
        output_path = frame_dir / f"frame_{mm:02d}_{ss:02d}.jpg"

        cmd = [
            "ffmpeg", "-ss", str(ts),
            "-i", video_path,
            "-frames:v", "1", "-q:v", "2",
            "-y", str(output_path),
            "-hide_banner", "-loglevel", "error"
        ]
        try:
            subprocess.run(cmd, check=True, timeout=10)
            frames.append(FrameInfo(
                timestamp=ts,
                path=str(output_path),
                description=f"第 {mm:02d}:{ss:02d} 秒画面"
            ))
        except Exception as e:
            logger.warning(f"提取帧 {ts}s 失败: {e}")

    logger.info(f"共提取 {len(frames)} 个关键帧")
    return frames


def transcribe_video(
    video_path: str,
    requirement_id: str,
    glossary: Optional[List[str]] = None,
    model_size: str = "large-v3",
    device: str = "cuda",
    model_dir: str = None,
) -> TranscriptResult:
    """ASR 转录"""
    cache_file = OUTPUT_DIR / f"{requirement_id}_transcript.json"

    # 检查缓存
    if cache_file.exists():
        logger.info(f"发现 ASR 缓存: {cache_file}")
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            segments = [TranscriptSegment(**s) for s in data.get("segments", [])]
            return TranscriptResult(
                full_text=data["full_text"],
                language=data.get("language"),
                segments=segments,
            )
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")

    # 提取音频
    audio_path = extract_audio(video_path,
                                str(OUTPUT_DIR / f"{requirement_id}_audio.wav"))

    # 初始化 Whisper
    model_path = model_dir or os.getenv("WHISPER_MODEL_DIR") or model_size
    logger.info(f"初始化 Whisper (model={model_path}, device={device})")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.error("faster-whisper 未安装，请运行: pip install faster-whisper")
        raise

    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_path, device=device, compute_type=compute_type)

    # 构建 initial_prompt（注入业务术语）
    initial_prompt = None
    if glossary:
        initial_prompt = "以下是本视频涉及的业务术语：" + "、".join(glossary[:50])

    logger.info("开始 ASR 转录...")
    segments_iter, info = model.transcribe(
        audio_path,
        language="zh",
        initial_prompt=initial_prompt,
        beam_size=5,
        vad_filter=True,
    )

    segments = []
    for seg in segments_iter:
        segments.append(TranscriptSegment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip()
        ))

    full_text = " ".join(s.text for s in segments)
    result = TranscriptResult(
        full_text=full_text,
        language=info.language if hasattr(info, 'language') else "zh",
        segments=segments,
    )

    # 保存缓存
    cache_data = {
        "full_text": result.full_text,
        "language": result.language,
        "segments": [asdict(s) for s in result.segments],
    }
    cache_file.write_text(
        json.dumps(cache_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.info(f"ASR 转录完成，共 {len(segments)} 段")
    return result
