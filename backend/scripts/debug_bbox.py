#!/usr/bin/env python3
"""BBOX 检测独立调试脚本 — 对比 prompt 策略、图片尺寸、温度等因素。

用法:
    cd /work/development-code/RPA/rpa-spec-generator/backend
    python3 scripts/debug_bbox.py
"""
import base64, io, json, os, re, sys, time
from pathlib import Path
from openai import OpenAI
from PIL import Image as PILImage
import httpx

# ─── 配置 ───
VISION_API_KEY = os.getenv("VISION_API_KEY", "a83a3d2dc31f568de9ec1a2bf956bddfb53c8de4")
VISION_BASE_URL = os.getenv("VISION_BASE_URL", "https://aicp.teamshub.com/openai/v1")
VISION_MODEL = os.getenv("VISION_MODEL", "Qwen3_5-35B-A3B-FP8")

SCREENSHOTS_DIR = Path("static/screenshots/d06b8d47-3e49-49e3-a599-a30d4364f934")

# 测试用例：(帧文件, 要检测的目标, 人工标注的大致位置描述)
TEST_CASES = [
    {
        "frame": "frame_03_54.jpg",
        "targets": ["收支管理", "回款管理", "打印"],
        "description": "中国联通数智业务管理系统主页，左侧菜单可见'收支管理'(约x=190,y=205)"
    },
    {
        "frame": "frame_06_18.jpg",
        "targets": ["打印", "回款管理", "合同编号"],
        "description": "合同预回款核销单页面，底部有'打印'按钮(约x=525,y=355)"
    },
]

# ─── Prompt 策略 ───
PROMPT_STRATEGIES = {
    "A_极简": {
        "prompt": '请输出图中"{target}"的像素坐标(bbox)。\n格式: [x1,y1,x2,y2]\n仅输出坐标数组。',
        "max_tokens": 256,
        "temperature": 0.1,
    },
    "B_JSON格式": {
        "prompt": '/no_think\n请找到图片中"{target}"这个UI元素的位置，返回其边界框的像素坐标。\n\n要求：\n- 坐标格式为 [左上角x, 左上角y, 右下角x, 右下角y]\n- 只返回一个JSON: {{"bbox": [x1,y1,x2,y2]}}\n- 不要输出任何其他文字',
        "max_tokens": 128,
        "temperature": 0.0,
    },
    "C_英文prompt": {
        "prompt": '/no_think\nLocate the UI element "{target}" in this screenshot.\nReturn ONLY the bounding box as pixel coordinates: [x1,y1,x2,y2]\nNo explanation.',
        "max_tokens": 128,
        "temperature": 0.0,
    },
    "D_分步思考": {
        "prompt": '图片中有一个名为"{target}"的UI元素。\n第一步：描述它在图中的大致位置（左上/右下/中间等）。\n第二步：估算其边界框的像素坐标 [x1,y1,x2,y2]。\n最后一行只输出坐标数组。',
        "max_tokens": 512,
        "temperature": 0.1,
    },
    "E_grounding": {
        "prompt": '/no_think\n<|object_ref_start|>{target}<|object_ref_end|>',
        "max_tokens": 256,
        "temperature": 0.0,
    },
    "F_千分比坐标": {
        "prompt": '/no_think\n请找到图中"{target}"的位置，用千分比坐标表示其边界框。\n格式: <box>(x1,y1),(x2,y2)</box>\n其中坐标范围0-1000，(0,0)是左上角。\n仅输出<box>标签。',
        "max_tokens": 128,
        "temperature": 0.0,
    },
    "G_Qwen_VL_bbox": {
        "prompt": '请用<ref>{target}</ref>找到图中对应元素的位置，输出<box>坐标</box>。',
        "max_tokens": 256,
        "temperature": 0.0,
    },
}

# ─── 图片尺寸策略 ───
IMAGE_SIZES = {
    "original": None,       # 不缩放
    "1024px": 1024,         # 最大边 1024
    "768px": 768,           # 最大边 768
}


def encode_image(frame_path: str, max_size: int = None) -> tuple:
    """编码图片为 base64，返回 (b64_string, width, height)"""
    img = PILImage.open(frame_path).convert("RGB")
    w, h = img.size
    if max_size and max(w, h) > max_size:
        ratio = max_size / max(w, h)
        w_new, h_new = int(w * ratio), int(h * ratio)
        img = img.resize((w_new, h_new), PILImage.LANCZOS)
        w, h = w_new, h_new
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return b64, w, h


def call_vlm(client, b64: str, prompt: str, max_tokens: int, temperature: float) -> dict:
    """调用 VLM，返回 {content, coords, elapsed}"""
    t0 = time.time()
    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}", "detail": "high"
                    }},
                ],
            }],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = (response.choices[0].message.content or "").strip()
        elapsed = time.time() - t0
    except Exception as e:
        return {"content": f"ERROR: {e}", "coords": None, "elapsed": time.time() - t0}

    # 去除 thinking 块
    clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    # 尝试提取坐标 — 多种格式
    coords = None

    # 格式1: [x1,y1,x2,y2]
    m = re.search(r'\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]', clean)
    if m:
        coords = [int(m.group(i)) for i in range(1, 5)]

    # 格式2: <box>(x1,y1),(x2,y2)</box>
    if not coords:
        m = re.search(r'<box>\((\d+),\s*(\d+)\),\s*\((\d+),\s*(\d+)\)</box>', clean)
        if m:
            coords = [int(m.group(i)) for i in range(1, 5)]
            coords = [coords[0], coords[1], coords[2], coords[3]]  # 千分比坐标

    # 格式3: (x1, y1, x2, y2)
    if not coords:
        m = re.search(r'\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', clean)
        if m:
            coords = [int(m.group(i)) for i in range(1, 5)]

    # 格式4: bbox JSON
    if not coords:
        m = re.search(r'"bbox"\s*:\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]', clean)
        if m:
            coords = [int(m.group(i)) for i in range(1, 5)]

    return {"content": clean, "coords": coords, "elapsed": elapsed}


def main():
    client = OpenAI(
        api_key=VISION_API_KEY,
        base_url=VISION_BASE_URL,
        timeout=httpx.Timeout(60.0, connect=15.0),
    )

    print(f"{'='*80}")
    print(f"BBOX 检测调试  |  模型: {VISION_MODEL}")
    print(f"{'='*80}\n")

    results = []
    total_tests = 0
    total_success = 0

    for case in TEST_CASES:
        frame_file = SCREENSHOTS_DIR / case["frame"]
        if not frame_file.exists():
            print(f"[SKIP] 帧文件不存在: {frame_file}")
            continue

        print(f"\n{'━'*80}")
        print(f"📷 帧: {case['frame']}")
        print(f"   {case['description']}")
        print(f"{'━'*80}")

        for size_name, max_size in IMAGE_SIZES.items():
            b64, w, h = encode_image(str(frame_file), max_size)
            print(f"\n  📐 图片尺寸: {size_name} ({w}x{h})")

            for target in case["targets"][:2]:  # 每帧测2个目标
                print(f"\n    🎯 目标: \"{target}\"")
                print(f"    {'─'*60}")

                for strat_name, strat in PROMPT_STRATEGIES.items():
                    prompt = strat["prompt"].format(target=target)
                    result = call_vlm(client, b64, prompt, strat["max_tokens"], strat["temperature"])

                    total_tests += 1
                    success = result["coords"] is not None
                    if success:
                        total_success += 1

                    status = "✅" if success else "❌"
                    coords_str = str(result["coords"]) if result["coords"] else "无"

                    # 截断内容显示
                    content_preview = result["content"][:120].replace("\n", " ")
                    if len(result["content"]) > 120:
                        content_preview += "..."

                    print(f"    {status} {strat_name:18s} | {result['elapsed']:.1f}s | 坐标: {coords_str}")
                    print(f"       响应: {content_preview}")

                    results.append({
                        "frame": case["frame"],
                        "target": target,
                        "image_size": size_name,
                        "strategy": strat_name,
                        "coords": result["coords"],
                        "elapsed": result["elapsed"],
                        "content_len": len(result["content"]),
                        "success": success,
                    })

                    # 避免 API 限速
                    time.sleep(0.5)

            # 只用 original 尺寸做全策略测试，其他尺寸跳过以节省时间
            if size_name == "original":
                break  # 移除此行可测试所有尺寸

    # ─── 汇总 ───
    print(f"\n\n{'='*80}")
    print(f"📊 汇总报告")
    print(f"{'='*80}")
    print(f"总测试数: {total_tests}  |  成功提取坐标: {total_success}  |  成功率: {total_success/max(total_tests,1)*100:.0f}%\n")

    # 按策略统计
    strat_stats = {}
    for r in results:
        s = r["strategy"]
        if s not in strat_stats:
            strat_stats[s] = {"total": 0, "success": 0, "elapsed": []}
        strat_stats[s]["total"] += 1
        strat_stats[s]["success"] += int(r["success"])
        strat_stats[s]["elapsed"].append(r["elapsed"])

    print(f"  {'策略':20s} | {'成功率':>8s} | {'平均耗时':>8s}")
    print(f"  {'─'*50}")
    for s, v in sorted(strat_stats.items(), key=lambda x: -x[1]["success"]):
        rate = f"{v['success']}/{v['total']}"
        avg_t = f"{sum(v['elapsed'])/len(v['elapsed']):.1f}s"
        print(f"  {s:20s} | {rate:>8s} | {avg_t:>8s}")

    # 保存详细结果
    out_file = Path("scripts/bbox_debug_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存: {out_file}")


if __name__ == "__main__":
    main()
