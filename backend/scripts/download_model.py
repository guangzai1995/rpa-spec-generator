"""从 ModelScope 下载 faster-whisper-large-v3 模型"""
import os
import sys

def main():
    model_id = os.getenv("WHISPER_MODELSCOPE_ID", "pengzhendong/faster-whisper-large-v3")
    cache_dir = os.getenv("WHISPER_MODEL_DIR", os.path.join(os.path.dirname(__file__), "..", "models"))
    os.makedirs(cache_dir, exist_ok=True)

    print(f"模型 ID: {model_id}")
    print(f"下载目录: {os.path.abspath(cache_dir)}")

    from modelscope import snapshot_download
    local_path = snapshot_download(model_id, cache_dir=cache_dir)
    print(f"模型已下载到: {local_path}")
    return local_path

if __name__ == "__main__":
    main()
