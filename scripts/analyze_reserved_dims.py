#!/usr/bin/env python3
"""
统计 S 向量中预留维度的比例

分析每个区块的预留空间，计算总预留维度占比
"""
import sys
sys.path.insert(0, '/Volumes/T7/AI_THE_SPIRE')

from src.training.encoder_dims import BLOCK1_DIM, BLOCK2_DIM, BLOCK3_DIM, BLOCK4_DIM, BLOCK5_DIM, BLOCK6_DIM, BLOCK7_DIM, BLOCK8_DIM, BLOCK9_DIM, BLOCK10_DIM, OUTPUT_DIM


def analyze_reserved_dimensions():
    """分析 S 向量的预留维度占比"""
    print("=" * 80)
    print("S 向量预留维度统计")
    print("=" * 80)

    # 定义每个区块的预留维度
    reserved_dims = {
        "区块1": {
            "total": BLOCK1_DIM,
            "reserved": 0,  # 无预留
            "description": "玩家核心（无预留）"
        },
        "区块2": {
            "total": BLOCK2_DIM,
            "reserved": 6,   # [384-389]
            "used": BLOCK2_DIM - 6,
            "description": "手牌（每张牌23维×10 + 统计10 + 预留6）"
        },
        "区块3": {
            "total": BLOCK3_DIM,
            "reserved": 113,  # [227-339]
            "used": BLOCK3_DIM - 113,
            "description": "抽牌堆（144 multi-hot + 统计83 + 预留113）"
        },
        "区块4": {
            "total": BLOCK4_DIM,
            "reserved": 113,  # [227-339]
            "used": BLOCK4_DIM - 113,
            "description": "弃牌堆（144 multi-hot + 统计83 + 预留113）"
        },
        "区块5": {
            "total": BLOCK5_DIM,
            "reserved": 13,  # [227-239]
            "used": BLOCK5_DIM - 13,
            "description": "消耗堆（144 multi-hot + 统计83 + 预留13）"
        },
        "区块6": {
            "total": BLOCK6_DIM,
            "reserved": 0,  # 无预留
            "used": BLOCK6_DIM,
            "description": "玩家 Powers（无预留）"
        },
        "区块7": {
            "total": BLOCK7_DIM,
            "reserved": 2,   # [103-104]
            "used": BLOCK7_DIM - 2,
            "description": "怪物（每怪103维×6，含2维预留）"
        },
        "区块8": {
            "total": BLOCK8_DIM,
            "reserved": 20,  # [180-199]
            "used": BLOCK8_DIM - 20,
            "description": "遗物（180 multi-hot + 统计20）"
        },
        "区块9": {
            "total": BLOCK9_DIM,
            "reserved": 128,  # [72-199]
            "used": BLOCK9_DIM - 128,
            "description": "药水（45 + 25 + 2 + 128）"
        },
        "区块10": {
            "total": BLOCK10_DIM,
            "reserved": 299,  # [201-499] (预留空间，已添加地图编码 [137-200])
            "used": BLOCK10_DIM - 299,
            "description": "全局（基础信息 + 事件 + 房间 + buffs + 地图编码 + 预留）"
        },
    }

    print(f"\n总维度: {OUTPUT_DIM}")
    print("-" * 70)

    total_reserved = 0
    total_used = 0

    for name, info in reserved_dims.items():
        reserved = info.get("reserved", 0)
        used = info["total"] - reserved
        total_reserved += reserved
        total_used += used

        pct = reserved / info["total"] * 100
        print(f"{name:10s}: {reserved:3d}/{info['total']:3d} = {pct:5.1f}% 预留 - {info['description']}")

    print(f"\n{'='*70}")
    print(f"总计:     {total_reserved:3d}/{OUTPUT_DIM:3d} = {total_reserved/OUTPUT_DIM*100:.1f}% 预留")
    print(f"使用:     {total_used:3d}/{OUTPUT_DIM:3d} = {total_used/OUTPUT_DIM*100:.1f}% 使用")
    print("=" * 70)

    # 详细分析全局区块的预留空间
    print("\n全局区块（区块10）预留空间详细分析:")
    print("-" * 70)
    global_reserved = 299
    global_used = BLOCK10_DIM - global_reserved

    print(f"总预留: {global_reserved} 维")
    print(f"使用情况:")
    print(f"  [0-22]   基础信息 (23维) - 楼层/章节/房间/命令")
    print(f"  [23-72]  事件ID (50维) - one-hot")
    print(f"  [73-87]  房间类型 (15维) - one-hot")
    print(f"  [88]      楼层进度 (1维) - floor")
    print(f"  [89-90]  预留 (2维) - 原地图坐标")
    print(f"  [91-92]  预留 (2维) - 原地图统计")
    print(f"  [93-112] 预留 (20维)")
    print(f"  [113-136] buff状态 (24维) - Strength/Dexterity/Weak等")
    print(f"  [137-200] 地图编码 (64维) - [新增] 已探索房间数/节点统计/可达房间/当前节点")
    print(f"  [201-499] 预留 (299维) - 保留为未来扩展")

    print("\n✅ 地图编码已添加到 [137-200]，使用 64 维")

    return {
        "total_reserved": total_reserved,
        "total_used": total_used,
        "reserved_pct": total_reserved / OUTPUT_DIM,
    }


def analyze_map_encoding():
    """分析地图编码方案"""
    print("\n" + "=" * 80)
    print("地图编码方案分析")
    print("=" * 80)

    print("\nMod 提供的 map 数据结构:")
    print("-" * 70)
    print("map: 数组，包含所有地图节点对象")
    print("  每个节点包含:")
    print("    - x, y: 坐标")
    print("    - symbol: 节点类型 (M/E?$等)")
    print("    - connected: 连接的节点")

    print("\n建议的地图编码方案:")
    print("-" * 70)
    print("方案A: 简化编码（推荐）")
    print("  [137] 当前楼层进度 (1维) - 已有")
    print("  [138] 已探索房间数 (1维) - 可添加")
    print("  [139-142] 路径节点类型统计 (4维) - elite/boss/event房间数")
    print("  [143-150] 下一层选项 (8维) - 可去的房间类型")

    print("\n方案B: 详细编码（如果空间充足）")
    print("  [137] 当前楼层进度")
    print("  [138-139] 当前坐标 (x, y)")
    print("  [140-142] 路径信息 (可到达的房间类型)")
    print("  [143-160] 最近节点历史")

    print("\n推荐: 方案A - 简化但有效的地图信息")


if __name__ == "__main__":
    stats = analyze_reserved_dimensions()
    analyze_map_encoding()
