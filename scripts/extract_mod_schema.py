#!/usr/bin/env python3
"""
从 Raw_Data JSON 中提取 game_state / combat_state 的完整参数清单（Schema）。

用于「排除法」：先明确 Mod 日志中所有可用参数，再排除不需要的，剩下的即为 s 向量的参数上限。
"""
import json
import sys
from pathlib import Path
from collections import defaultdict


def collect_keys(obj, path="", keys_by_path: dict = None):
    """递归收集所有键，记录路径和类型"""
    if keys_by_path is None:
        keys_by_path = defaultdict(lambda: {"types": set(), "sample": None})

    if isinstance(obj, dict):
        for k, v in obj.items():
            full_path = f"{path}.{k}" if path else k
            keys_by_path[full_path]["types"].add(type(v).__name__)
            if keys_by_path[full_path]["sample"] is None and v is not None:
                if isinstance(v, (str, int, float, bool)):
                    keys_by_path[full_path]["sample"] = v
                elif isinstance(v, list) and len(v) > 0:
                    keys_by_path[full_path]["sample"] = f"list[{len(v)}]"
                elif isinstance(v, dict):
                    keys_by_path[full_path]["sample"] = "dict"
            collect_keys(v, full_path, keys_by_path)
    elif isinstance(obj, list) and len(obj) > 0:
        # 只取第一个元素推断结构，避免重复
        collect_keys(obj[0], path + "[]", keys_by_path)

    return keys_by_path


def main():
    data_dir = Path(__file__).parent.parent / "data" / "A20_Silent" / "Raw_Data_json_FORSL"
    all_keys = defaultdict(lambda: {"types": set(), "sample": None, "seen_in": set()})

    for f in sorted(data_dir.glob("*.json")):
        print(f"Processing {f.name}...", file=sys.stderr)
        try:
            with open(f) as fp:
                data = json.load(fp)
        except Exception as e:
            print(f"  Skip {f.name}: {e}", file=sys.stderr)
            continue

        frames = data if isinstance(data, list) else [data]
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            gs = frame.get("game_state")
            if not gs:
                continue

            # 只关注 game_state 及其子结构
            keys_in_file = collect_keys(gs, "game_state")
            for path, info in keys_in_file.items():
                all_keys[path]["types"].update(info["types"])
                if info["sample"] is not None:
                    all_keys[path]["sample"] = info["sample"]
                all_keys[path]["seen_in"].add(f.name)

    # 输出：按路径层级排序
    def sort_key(p):
        parts = p.split(".")
        # game_state 优先，combat_state 其次
        order = {"game_state": 0, "combat_state": 1}
        return (order.get(parts[0], 2), p)

    sorted_paths = sorted(all_keys.keys(), key=sort_key)

    # 分组输出
    gs_top = [p for p in sorted_paths if p.startswith("game_state.") and "combat_state" not in p and "[]" not in p]
    gs_nested = [p for p in sorted_paths if p.startswith("game_state.") and "combat_state" not in p and "[]" in p]
    combat_top = [p for p in sorted_paths if "combat_state" in p and "[]" not in p]
    combat_nested = [p for p in sorted_paths if "combat_state" in p and "[]" in p]

    print("\n" + "=" * 80)
    print("Mod 日志 game_state / combat_state 完整参数清单")
    print("=" * 80)

    print("\n## 1. game_state 顶层字段（非 combat_state）")
    print("-" * 60)
    for p in gs_top:
        info = all_keys[p]
        types_str = ", ".join(sorted(info["types"]))
        sample = info["sample"]
        sample_str = f"  # 示例: {sample}" if sample is not None else ""
        print(f"  {p}  ({types_str}){sample_str}")

    print("\n## 2. game_state 内嵌套结构（如 deck[], map[] 等）")
    print("-" * 60)
    for p in gs_nested:
        info = all_keys[p]
        types_str = ", ".join(sorted(info["types"]))
        sample = info["sample"]
        sample_str = f"  # 示例: {sample}" if sample is not None else ""
        print(f"  {p}  ({types_str}){sample_str}")

    print("\n## 3. combat_state 顶层字段")
    print("-" * 60)
    for p in combat_top:
        info = all_keys[p]
        types_str = ", ".join(sorted(info["types"]))
        sample = info["sample"]
        sample_str = f"  # 示例: {sample}" if sample is not None else ""
        print(f"  {p}  ({types_str}){sample_str}")

    print("\n## 4. combat_state 内嵌套结构（hand[], monsters[] 等）")
    print("-" * 60)
    for p in combat_nested:
        info = all_keys[p]
        types_str = ", ".join(sorted(info["types"]))
        sample = info["sample"]
        sample_str = f"  # 示例: {sample}" if sample is not None else ""
        print(f"  {p}  ({types_str}){sample_str}")

    print("\n" + "=" * 80)
    print(f"总计: {len(all_keys)} 个唯一路径")
    print("=" * 80)

    # 完整清单可运行本脚本查看 stdout，无需持久化


if __name__ == "__main__":
    main()
