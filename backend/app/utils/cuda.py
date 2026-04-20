"""CUDA 运行库与设备探测工具。"""
import os
import site
from pathlib import Path


def _candidate_cuda_lib_dirs() -> list[str]:
    dirs: list[str] = []
    seen: set[str] = set()

    candidates = [Path("/usr/local/cuda/targets/x86_64-linux/lib")]
    for base_dir in site.getsitepackages():
        base = Path(base_dir)
        candidates.extend([
            base / "nvidia" / "cublas" / "lib",
            base / "nvidia" / "cudnn" / "lib",
        ])

    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate.is_dir() and candidate_str not in seen:
            seen.add(candidate_str)
            dirs.append(candidate_str)

    return dirs


def configure_cuda_library_path() -> list[str]:
    extra_dirs = _candidate_cuda_lib_dirs()
    current_dirs = [item for item in os.environ.get("LD_LIBRARY_PATH", "").split(":") if item]

    merged_dirs: list[str] = []
    seen: set[str] = set()
    for item in [*extra_dirs, *current_dirs]:
        if item and item not in seen:
            seen.add(item)
            merged_dirs.append(item)

    if merged_dirs:
        os.environ["LD_LIBRARY_PATH"] = ":".join(merged_dirs)

    return extra_dirs


def resolve_whisper_device(requested_device: str) -> str:
    device = (requested_device or "cpu").lower()
    if device != "cuda":
        return device

    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass

    return "cpu"