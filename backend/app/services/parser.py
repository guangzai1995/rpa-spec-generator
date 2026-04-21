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

from app.utils.cuda import resolve_whisper_device
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
        fps = 0
        if video_stream:
            fps_str = video_stream.get("r_frame_rate", "0/1")
            parts = fps_str.split("/")
            if len(parts) == 2 and parts[1] != "0":
                fps = int(parts[0]) / int(parts[1])
            else:
                fps = float(parts[0]) if parts[0] else 0
        info = {
            "duration": float(probe["format"].get("duration", 0)),
            "width": int(video_stream["width"]) if video_stream else 0,
            "height": int(video_stream["height"]) if video_stream else 0,
            "fps": fps,
        }
        return info
    except Exception as e:
        logger.warning(f"获取视频信息失败: {e}")
        return {"duration": 0, "width": 0, "height": 0, "fps": 0}


def _image_phash(image_path: str, hash_size: int = 8) -> Optional[int]:
    """计算图片感知哈希（pHash），用于相似度比较"""
    try:
        img = Image.open(image_path).convert("L").resize(
            (hash_size * 4, hash_size * 4), Image.LANCZOS
        )
        import numpy as np
        pixels = np.array(img, dtype=float)
        # DCT 简化：直接用均值二值化（轻量替代，效果足够）
        avg = pixels.mean()
        bits = (pixels.flatten()[:hash_size * hash_size] > avg)
        h = 0
        for b in bits:
            h = (h << 1) | int(b)
        return h
    except Exception as e:
        logger.warning(f"计算 pHash 失败 {image_path}: {e}")
        return None


def _hamming_distance(h1: int, h2: int) -> int:
    """计算两个哈希的汉明距离"""
    return bin(h1 ^ h2).count('1')


def extract_keyframes(
    video_path: str,
    requirement_id: str,
    interval: int = 5,
    max_frames: int = 50,
    similarity_threshold: int = 4,
) -> List[FrameInfo]:
    """提取关键帧，使用感知哈希去重近似重复帧

    Args:
        similarity_threshold: pHash 汉明距离阈值，低于此值视为重复帧（默认 6）
    """
    frame_dir = SCREENSHOT_DIR / requirement_id
    frame_dir.mkdir(parents=True, exist_ok=True)

    info = get_video_info(video_path)
    duration = info["duration"]
    if duration <= 0:
        logger.warning("视频时长为 0，跳过关键帧提取")
        return []

    timestamps = list(range(0, int(duration), interval))[:max_frames]
    raw_frames: List[Tuple[float, str]] = []

    # 第一步：提取所有候选帧
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
            raw_frames.append((ts, str(output_path)))
        except Exception as e:
            logger.warning(f"提取帧 {ts}s 失败: {e}")

    logger.info(f"提取了 {len(raw_frames)} 个候选帧，开始去重...")

    # 第二步：感知哈希去重
    # 计算所有帧的 pHash
    frame_hashes: List[Optional[int]] = []
    for ts, path in raw_frames:
        frame_hashes.append(_image_phash(path))

    kept_indices: List[int] = []
    prev_kept_hashes: List[int] = []

    for i, (ts, path) in enumerate(raw_frames):
        h = frame_hashes[i]
        is_duplicate = False
        if h is not None and prev_kept_hashes:
            # 与最近 5 个已保留帧比较（滑动窗口去重）
            for prev_h in prev_kept_hashes[-5:]:
                if _hamming_distance(h, prev_h) < similarity_threshold:
                    is_duplicate = True
                    break

        if not is_duplicate:
            kept_indices.append(i)
            if h is not None:
                prev_kept_hashes.append(h)

    # 第三步：最小密度保证 —— 如果连续保留帧之间时间间隔过大，补回最不相似的帧
    max_gap = max(120, int(duration / 10))  # 至少每 max_gap 秒保留一帧
    filled = True
    while filled:
        filled = False
        new_kept = list(kept_indices)
        for idx in range(len(new_kept)):
            cur_ts = raw_frames[new_kept[idx]][0]
            next_ts = raw_frames[new_kept[idx + 1]][0] if idx + 1 < len(new_kept) else duration
            gap = next_ts - cur_ts
            if gap > max_gap:
                # 在 gap 中找最不相似的候选帧（与两端距离最大的 pHash）
                best_candidate = None
                best_dist = -1
                start_raw = new_kept[idx]
                end_raw = new_kept[idx + 1] if idx + 1 < len(new_kept) else len(raw_frames)
                for j in range(start_raw + 1, end_raw):
                    if j in new_kept:
                        continue
                    h = frame_hashes[j]
                    if h is None:
                        continue
                    # 与 gap 两端的已保留帧的最小距离
                    left_h = frame_hashes[new_kept[idx]]
                    right_h = frame_hashes[new_kept[idx + 1]] if idx + 1 < len(new_kept) else None
                    d_left = _hamming_distance(h, left_h) if left_h is not None else 64
                    d_right = _hamming_distance(h, right_h) if right_h is not None else 64
                    min_d = min(d_left, d_right)
                    if min_d > best_dist:
                        best_dist = min_d
                        best_candidate = j
                if best_candidate is not None:
                    new_kept.append(best_candidate)
                    new_kept.sort()
                    filled = True
                    break  # 重新扫描
        kept_indices = new_kept

    # 构建结果，删除未保留的帧文件
    kept_set = set(kept_indices)
    frames: List[FrameInfo] = []
    for i, (ts, path) in enumerate(raw_frames):
        if i in kept_set:
            mm = int(ts // 60)
            ss = int(ts % 60)
            frames.append(FrameInfo(
                timestamp=ts,
                path=path,
                description=f"第 {mm:02d}:{ss:02d} 秒画面"
            ))
        else:
            try:
                os.remove(path)
            except OSError:
                pass

    logger.info(f"去重后保留 {len(frames)} 个关键帧（去除 {len(raw_frames) - len(frames)} 个重复帧，密度保证 max_gap={max_gap}s）")
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

    segments = []
    try:
        from faster_whisper import WhisperModel

        resolved_device = resolve_whisper_device(device)
        if resolved_device != device:
            logger.warning(f"Whisper 设备 {device} 不可用，回退到 {resolved_device}")

        compute_type = "float16" if resolved_device == "cuda" else "int8"
        model = WhisperModel(model_path, device=resolved_device, compute_type=compute_type)

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

        for seg in segments_iter:
            text = seg.text.strip()
            if text:
                segments.append(TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=text
                ))

    except ImportError:
        logger.warning("faster-whisper 未安装，ASR 跳过。将仅依赖视觉分析。")
    except Exception as e:
        logger.warning(f"ASR 转录失败: {e}。将仅依赖视觉分析。")

    # 如果没有有效段，创建基于时间的占位段
    if not segments:
        logger.info("ASR 无有效结果，创建基于视频时长的占位段")
        info_data = get_video_info(video_path)
        dur = info_data.get("duration", 10)
        interval = max(5, dur / 10)
        t = 0.0
        while t < dur:
            segments.append(TranscriptSegment(
                start=t, end=min(t + interval, dur),
                text=f"[视频画面 {int(t//60):02d}:{int(t%60):02d}]"
            ))
            t += interval

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
