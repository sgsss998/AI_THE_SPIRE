#!/usr/bin/env python3
"""
从 Raw_Data_json_FORSL 读取每帧 JSON，输出对应的 s 向量（31 维）
用法: python scripts/raw_to_s_vectors.py [--output out.json] [--limit N]
"""
import json
import argparse
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.training.encoder_mvp import encode, get_output_dim


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", help="输出文件路径（默认 stdout）")
    parser.add_argument("--limit", "-n", type=int, default=None, help="每文件最多输出 N 帧")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "data" / "A20_Silent" / "Raw_Data_json_FORSL"
    if not data_dir.exists():
        print(f"数据目录不存在: {data_dir}", file=sys.stderr)
        return 1

    files = sorted(data_dir.glob("*.json"))
    lines = []
    lines.append(f"输出维度: {get_output_dim()}")
    lines.append("=" * 80)

    for json_file in files:
        with open(json_file) as f:
            frames = json.load(f)
        lines.append(f"\n【文件】{json_file.name}  共 {len(frames)} 帧\n")
        limit = args.limit or len(frames)
        for i, frame in enumerate(frames[:limit]):
            s = encode(frame)
            gs = frame.get("game_state", {})
            rp = gs.get("room_phase", "")
            st = gs.get("screen_type", "")
            lines.append(f"--- 帧 {i} ---")
            lines.append(f"  room_phase={rp}, screen_type={st}")
            lines.append(f"  s = {s.tolist()}")
            lines.append("")
        if len(frames) > limit:
            lines.append(f"  ... 其余 {len(frames)-limit} 帧省略 ...\n")

    lines.append("=" * 80)
    out = "\n".join(lines)

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"已写入 {args.output}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
