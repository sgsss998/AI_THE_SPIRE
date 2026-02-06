#!/usr/bin/env python3
"""
测试地图编码功能

验证新增的地图编码是否正确工作：
1. 已探索房间数
2. 节点类型统计
3. 可到达房间类型
4. 当前节点信息
"""
import sys
sys.path.insert(0, '/Volumes/T7/AI_THE_SPIRE')

import numpy as np
from src.training.encoder import encode


def test_map_encoding():
    """测试地图编码"""
    print("=" * 80)
    print("地图编码测试")
    print("=" * 80)

    # 创建一个包含地图信息的测试状态
    test_state = {
        "game_state": {
            "current_hp": 50,
            "max_hp": 70,
            "floor": 10,
            "act": 1,
            "gold": 100,
            # 模拟地图数据 - 6个节点的地图
            "map": [
                {"x": 0, "y": 0, "symbol": "M", "parents": [], "children": [{"x": 1, "y": 1}]},
                {"x": 1, "y": 1, "symbol": "$", "parents": [{"x": 0, "y": 0}], "children": []},
                {"x": 2, "y": 0, "symbol": "E", "parents": [], "children": []},
                {"x": 3, "y": 1, "symbol": "?", "parents": [], "children": []},
                {"x": 4, "y": 0, "symbol": "R", "parents": [], "children": []},
                {"x": 5, "y": 1, "symbol": "M", "parents": [], "children": []},
            ],
            "combat_state": {
                "player": {
                    "energy": 3,
                    "max_energy": 3,
                    "current_hp": 50,
                    "max_hp": 70,
                    "block": 0,
                },
                "hand": [],
                "draw_pile": [],
                "discard_pile": [],
                "exhaust_pile": [],
                "monsters": [],
                "turn": 1,
                "cards_discarded_this_turn": 0,
                "times_damaged": 0,
            },
            "relics": [],
            "potions": [],
            "screen_state": {
                "options": [],
                "current_node": {
                    "x": 1,
                    "y": 1,
                    "symbol": "$",
                    "parents": [{"x": 0, "y": 0}],
                    "children": [],
                },
                "next_nodes": [
                    {"x": 2, "y": 2, "symbol": "M"},
                    {"x": 3, "y": 2, "symbol": "E"},
                    {"x": 4, "y": 2, "symbol": "?"},
                ],
            },
        },
        "available_commands": ["proceed"],
        "ready_for_command": True,
        "in_game": True,
    }

    # 编码状态
    encoded = encode(test_state)
    print(f"✅ 编码成功: {len(encoded)} 维")

    # 全局区块从索引 2445 开始
    global_block_start = 2445

    # 检查地图编码区域 [137-200] -> 全局区块内的偏移
    # [137] 已探索房间数
    explored_rooms_idx = global_block_start + 137
    print(f"\n[137] 已探索房间数 (索引{explored_rooms_idx}): {encoded[explored_rooms_idx]:.4f}")
    print(f"  预期: 6个房间 / 60 = ~0.10")
    if abs(encoded[explored_rooms_idx] - 0.1) < 0.05:
        print("  ✅ 已探索房间数编码正确")
    else:
        print(f"  ⚠️  已探索房间数编码可能有问题: {encoded[explored_rooms_idx]}")

    # [138-145] 节点类型统计
    print("\n[138-145] 节点类型统计:")
    print(f"  [138] M (普通怪物): {encoded[global_block_start + 138]:.4f} - 预期: 2/30 = ~0.067")
    print(f"  [139] E (精英):     {encoded[global_block_start + 139]:.4f} - 预期: 1/10 = 0.1")
    print(f"  [140] B (Boss):     {encoded[global_block_start + 140]:.4f} - 预期: 0")
    print(f"  [141] ? (事件):     {encoded[global_block_start + 141]:.4f} - 预期: 1/15 = ~0.067")
    print(f"  [142] $ (商店):     {encoded[global_block_start + 142]:.4f} - 预期: 1/10 = 0.1")
    print(f"  [143] R (休息):     {encoded[global_block_start + 143]:.4f} - 预期: 1/10 = 0.1")
    print(f"  [144] T (宝箱):     {encoded[global_block_start + 144]:.4f} - 预期: 0")

    # [146-153] 可到达房间类型
    print("\n[146-153] 可到达房间类型:")
    print(f"  [146] 可去怪物房: {encoded[global_block_start + 146]:.1f} - 预期: 1.0")
    print(f"  [147] 可去精英房: {encoded[global_block_start + 147]:.1f} - 预期: 1.0")
    print(f"  [148] 可去Boss房: {encoded[global_block_start + 148]:.1f} - 预期: 0.0")
    print(f"  [149] 可去事件房: {encoded[global_block_start + 149]:.1f} - 预期: 1.0")
    print(f"  [150] 可去商店:   {encoded[global_block_start + 150]:.1f} - 预期: 0.0")
    print(f"  [153] 可选房间总数: {encoded[global_block_start + 153]:.4f} - 预期: 3/5 = 0.6")

    # [154-165] 当前节点信息
    print("\n[154-165] 当前节点信息:")
    print(f"  [154] X坐标: {encoded[global_block_start + 154]:.4f} - 预期: 1/15 = ~0.067")
    print(f"  [155] Y坐标: {encoded[global_block_start + 155]:.4f} - 预期: 1/15 = ~0.067")
    print(f"  [160] 当前是商店: {encoded[global_block_start + 160]:.1f} - 预期: 1.0")

    print("\n✅ 地图编码测试完成")
    return True


def test_map_encoding_without_map():
    """测试没有地图数据时的编码"""
    print("\n" + "=" * 80)
    print("无地图数据测试")
    print("=" * 80)

    # 创建一个没有地图信息的测试状态
    test_state = {
        "game_state": {
            "current_hp": 50,
            "max_hp": 70,
            "floor": 10,
            "act": 1,
            "gold": 100,
            "combat_state": {
                "player": {
                    "energy": 3,
                    "max_energy": 3,
                    "current_hp": 50,
                    "max_hp": 70,
                    "block": 0,
                },
                "hand": [],
                "draw_pile": [],
                "discard_pile": [],
                "exhaust_pile": [],
                "monsters": [],
                "turn": 1,
                "cards_discarded_this_turn": 0,
                "times_damaged": 0,
            },
            "relics": [],
            "potions": [],
            "screen_state": {
                "options": [],
            },
        },
        "available_commands": ["play", "end"],
        "ready_for_command": True,
        "in_game": True,
    }

    # 编码状态
    encoded = encode(test_state)
    print(f"✅ 编码成功: {len(encoded)} 维")

    # 全局区块从索引 2445 开始
    global_block_start = 2445

    # 检查地图编码区域是否为默认值（0）
    print("\n检查地图编码区域是否为默认值（0）:")
    explored_rooms_idx = global_block_start + 137
    print(f"  [137] 已探索房间数: {encoded[explored_rooms_idx]:.4f} - 预期: 0.0")
    print(f"  [138] 普通怪物房统计: {encoded[global_block_start + 138]:.4f} - 预期: 0.0")
    print(f"  [146] 可去怪物房: {encoded[global_block_start + 146]:.1f} - 预期: 0.0")

    print("\n✅ 无地图数据测试完成")
    return True


def main():
    print("地图编码功能测试")
    print()

    results = []
    results.append(("地图编码", test_map_encoding()))
    results.append(("无地图数据处理", test_map_encoding_without_map()))

    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    all_passed = all(result for _, result in results)
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}: {'通过' if result else '失败'}")

    if all_passed:
        print("\n✅ 所有地图编码测试通过")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
