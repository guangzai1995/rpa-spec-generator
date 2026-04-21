"""从 ModelScope 下载 faster-whisper 模型。"""
import os


MODEL_MAP = {
    "tiny": "pengzhendong/faster-whisper-tiny",
    "base": "pengzhendong/faster-whisper-base",
    "small": "pengzhendong/faster-whisper-small",
    "medium": "pengzhendong/faster-whisper-medium",
    "large-v1": "pengzhendong/faster-whisper-large-v1",
    "large-v2": "pengzhendong/faster-whisper-large-v2",
    "large-v3": "pengzhendong/faster-whisper-large-v3",
    "large-v3-turbo": "pengzhendong/faster-whisper-large-v3-turbo",
}

def main():
    model_size = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")
    model_id = os.getenv("WHISPER_MODELSCOPE_ID") or MODEL_MAP.get(model_size, model_size)
    cache_dir = os.getenv(
        "WHISPER_MODEL_DIR",
        os.path.join(os.path.dirname(__file__), "..", "models", model_id),
    )
    os.makedirs(cache_dir, exist_ok=True)

    print(f"模型规格: {model_size}")
    print(f"模型 ID: {model_id}")
    print(f"下载目录: {os.path.abspath(cache_dir)}")

    from modelscope import snapshot_download
    local_path = snapshot_download(model_id, local_dir=cache_dir)
    print(f"模型已下载到: {local_path}")
    return local_path

if __name__ == "__main__":
    main()
