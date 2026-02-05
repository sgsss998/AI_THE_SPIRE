#!/usr/bin/env python3
"""
验证 MVP 编码器：对 Raw_Data JSON 跑 encode，检查无异常、shape=(31,)
"""
import sys
import json
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.training.encoder_mvp import encode, get_output_dim


def main():
    data_dir = Path(__file__).parent.parent / "data" / "A20_Slient" / "Raw_Data_json_FORSL"
    if not data_dir.exists():
        print(f"数据目录不存在: {data_dir}")
        return 1

    json_files = sorted(data_dir.glob("*.json"))
    if not json_files:
        print(f"未找到 JSON 文件: {data_dir}")
        return 1

    print(f"输出维度: {get_output_dim()}")
    print(f"找到 {len(json_files)} 个日志文件\n")

    for json_file in json_files:
        print(f"--- {json_file.name} ---")
        with open(json_file) as f:
            frames = json.load(f)

        for i, frame in enumerate(frames[:5]):
            s = encode(frame)
            assert s.shape == (31,), f"帧{i} shape={s.shape}"
            assert s.dtype.name == "float32", f"帧{i} dtype={s.dtype}"
            print(f"  帧{i}: shape={s.shape}, dtype={s.dtype}, s[0:5]={s[:5]}")

        for i, frame in enumerate(frames):
            s = encode(frame)
            assert s.shape == (31,)
        print(f"  全文件 {len(frames)} 帧编码通过")

    print("\n验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
