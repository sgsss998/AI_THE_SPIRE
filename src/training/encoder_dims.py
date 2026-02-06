#!/usr/bin/env python3
"""
编码器维度常量 - 静默猎手专用

所有维度定义的单一来源，确保各个文件之间的一致性。

## 总览
- 总维度 (OUTPUT_DIM): 2945
- 区块数: 10

## 维度设计原则
1. 所有参数来源于 Mod 日志（无外部信息）
2. 单个游戏参数可映射到多个向量维度
3. 非战斗状态使用零填充
4. 静默专用：固定 A20 难度 + 静默职业

## 版本记录
- V2 (2026-02-06): 静默专用，卡牌池 144 张，总维度 2929
"""

from typing import Dict, List, Tuple
import sys
from pathlib import Path

# 项目根目录（用于导入）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ============================================================
# 卡牌池统计
# ============================================================

# 静默猎手专用卡牌池详细分类
# 总计: 144 张
CARD_POOL: Dict[str, int] = {
    "UNKNOWN": 1,        # 未知卡牌（占位符）
    "CURSE": 14,         # 诅咒: AscendersBane + 13个
    "STATUS": 5,         #状态: Burn, Dazed, Slimed, Void, Wound
    "SILENT_BASIC": 4,   # 静默基础: Strike_G, Defend_G, Neutralize, Survivor
    "SILENT_COMMON": 40, # 静默普通
    "SILENT_UNCOMMON": 19, # 静默罕见
    "SILENT_RARE": 8,    # 静稀罕见
    "SILENT_BONUS": 6,   # 静默补充: Adrenaline, All Out Attack, Dagger Spray, Precise Strike, Rapture, Throwing Knife
    "COLORLESS": 47,     # 无色牌
}

CARD_DIM = sum(CARD_POOL.values())  # 144

# ============================================================
# 区块维度定义
# ============================================================

# 区块1: 玩家核心 (17维)
BLOCK1_STRUCTURE = """
玩家核心状态，删除与区块10重复的信息
├── [0-6]   HP/能量/护甲/金币 (7维)
├── [7-12]  本回合统计 + 牌堆数量 (6维)
├── [13-15] 钥匙状态 (3维)
└── [16]    回合 (1维)
"""
BLOCK1_DIM = 17

# 区块2: 手牌 (390维)
BLOCK2_STRUCTURE = """
├── [0-143]     144维 卡牌 multi-hot
├── [144-353]   210维 每张牌21属性×10张
│   └── 每张牌21维:
│       ├── [0-6]   cost, is_playable, has_target, ethereal, exhaust, stripped, cost_for_turn
│       ├── [7-11]  type one-hot (5维)
│       └── [12-20] 升级状态 + 预留
├── [354-363]   10维 统计
└── [364-389]   26维 预留
"""
BLOCK2_DIM = 390

# 区块3: 抽牌堆 (340维)
BLOCK3_STRUCTURE = """
├── [0-143]     144维 卡牌 multi-hot
├── [144-226]   83维 详细统计
│   ├── 基础统计: size, zero_cost, zero_cost_ratio
│   ├── 类型数量和占比: attack, skill, power, status_curse (8维)
│   ├── 升级牌统计: count, ratio (2维)
│   ├── 特殊属性: ethereal, exhaust (2维)
│   └── 费用统计: avg_cost, total_cost (2维)
└── [227-339]   113维 预留
"""
BLOCK3_DIM = 340

# 区块4: 弃牌堆 (340维)
BLOCK4_STRUCTURE = """
├── [0-143]     144维 卡牌 multi-hot
├── [144-226]   83维 详细统计（同区块3，但包含本回合弃牌数）
└── [227-339]   113维 预留
"""
BLOCK4_DIM = 340

# 区块5: 消耗堆 (240维)
BLOCK5_STRUCTURE = """
├── [0-143]     144维 卡牌 multi-hot
├── [144-226]   83维 详细统计（基础+类型+升级+特殊属性）
└── [227-239]   13维 预留
"""
BLOCK5_DIM = 240

# 区块6: 玩家 Powers (100维)
BLOCK6_STRUCTURE = """
Power 效果 one-hot 编码，包括 strength, dexterity, weak, vulnerable 等
"""
BLOCK6_DIM = 100

# 区块7: 怪物 (618维)
BLOCK7_STRUCTURE = """
每个怪物 103 维：
├── [0-74]      Monster ID multi-hot (75维)
├── [75]        HP比例
├── [76]        护甲
├── [77-79]     怪物类型 one-hot (3维：普通/精英/Boss)
├── [80-82]     预留
├── [83-95]     Intent one-hot (13维)
├── [96]        预计伤害
├── [97]        存活状态
├── [98]        半死状态
├── [99-100]    动作历史
└── [101-102]   Strength, Vulnerable

总共支持 6 个怪物
"""
BLOCK7_DIM = 618

# 区块8: 遗物 (200维)
BLOCK8_STRUCTURE = """
├── [0-179]     180维 遗物 multi-hot
└── [180-199]   20维 统计和预留
"""
BLOCK8_DIM = 200

# 区块9: 药水 (200维)
BLOCK9_STRUCTURE = """
├── [0-44]      药水 multi-hot (45维)
├── [45-69]     5个槽位×5属性 = 25维
├── [70-71]     统计 2维
└── [72-199]    128维 预留
"""
BLOCK9_DIM = 200

# 区块10: 全局 (500维) - 静默专用
BLOCK10_STRUCTURE = """
├── [0-22]      基础信息（楼层、章节、房间阶段、可用命令）
├── [23-72]     事件ID one-hot (50维)
├── [73-87]     房间细分类型 one-hot (15维)
├── [88-112]    地图路径信息 (25维)
├── [113-136]   更多buff/debuff状态 (24维)
├── [137-200]   地图编码 (64维)
│   ├── [137]       已探索房间数
│   ├── [138-145]   节点类型统计 (8维)
│   ├── [146-153]   可到达房间类型 (8维)
│   ├── [154-165]   当前节点信息 (12维)
│   └── [166-200]   预留 (35维)
├── [201-209]   新增重要字段 (9维) - 静默专用
│   ├── [201-202]   商店删牌信息 (2维)
│   ├── [203-204]   正在打出的牌 (2维)
│   ├── [205]       受击次数 (1维)
│   └── [206-209]   奖励类型 (4维)
├── [210-320]   战斗动态信息 (111维) - 从Mod日志提取
│   ├── [210-212]   limbo牌信息 (3维) - 正在打出中的牌
│   ├── [213-220]   怪物行为模式 (8维) - 每怪2维（last/second_last_move）
│   ├── [221-230]   预计伤害来源 (10维) - 每怪预计伤害
│   ├── [231-250]   本回合动态 (20维) - 牌堆变化、能量使用等
│   └── [251-320]   预留 (70维)
├── [321-400]   牌组变化统计 (80维)
│   ├── [321-335]   牌组构成变化 (15维) - 相对初始的变化
│   ├── [336-370]   已消耗牌统计 (35维) - 消耗堆分析
│   ├── [371-385]   升级牌统计 (15维) - 升级牌数量
│   └── [386-400]   预留 (15维)
└── [401-499]   预留 (99维)
"""
BLOCK10_DIM = 500

# ============================================================
# 总维度
# ============================================================

OUTPUT_DIM = (
    BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM
    + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM + BLOCK9_DIM + BLOCK10_DIM
)
# OUTPUT_DIM = 17 + 390 + 340 + 340 + 240 + 100 + 618 + 200 + 200 + 500 = 2945

# ============================================================
# 归一化上限
# ============================================================

# 玩家相关
MAX_HP = 200           # 静默血量较低
MAX_BLOCK = 999        # 静默可以叠很高的护甲
MAX_ENERGY = 20        # 预留更多能量空间
MAX_GOLD = 999

# Power 相关
MAX_POWER = 99         # Power 层数上限
MAX_DEBUFF = 15        # Debuff 层数上限

# 牌堆相关
MAX_HAND = 10
MAX_DRAW = 80
MAX_DISCARD = 80
MAX_EXHAUST = 50
MAX_CARDS_DISCARDED = 15
MAX_TIMES_DAMAGED = 50
MAX_TURN = 50
MAX_ORB_SLOTS = 10
MAX_DAMAGE = 99

# ============================================================
# 区块索引范围
# ============================================================

BLOCK_RANGES: List[Tuple[int, int, str]] = [
    (0, BLOCK1_DIM, "玩家核心"),
    (BLOCK1_DIM, BLOCK1_DIM + BLOCK2_DIM, "手牌"),
    (BLOCK1_DIM + BLOCK2_DIM, BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM, "抽牌堆"),
    (BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM, BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM, "弃牌堆"),
    (BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM, BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM, "消耗堆"),
    (BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM, BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM, "玩家Powers"),
    (BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM, BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM, "怪物"),
    (BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM, BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM, "遗物"),
    (BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM, BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM + BLOCK9_DIM, "药水"),
    (BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM + BLOCK9_DIM, OUTPUT_DIM, "全局"),
]

# ============================================================
# 其他维度常量
# ============================================================

# 从 encoder_utils.py 迁移
RELIC_DIM = 180
POTION_DIM = 45
POWER_DIM = 80
INTENT_DIM = 13
MONSTER_DIM = 75
ORB_TYPE_DIM = 5
EVENT_DIM = 50
ROOM_SUBTYPE_DIM = 15
CARD_TYPE_DIM = 5

# ============================================================
# 验证函数
# ============================================================

def validate_dimensions() -> Dict[str, any]:
    """
    验证编码器维度一致性

    Returns:
        dict: 包含验证结果和错误信息
    """
    errors = []
    warnings = []

    # 1. 验证卡牌维度
    calculated_card_dim = sum(CARD_POOL.values())
    if calculated_card_dim != CARD_DIM:
        errors.append(f"CARD_POOL 总和={calculated_card_dim} 但 CARD_DIM={CARD_DIM}")

    # 2. 验证总维度
    calculated_output = (
        BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM
        + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM + BLOCK9_DIM + BLOCK10_DIM
    )
    if calculated_output != OUTPUT_DIM:
        errors.append(f"计算得 OUTPUT_DIM={calculated_output} 但定义为 {OUTPUT_DIM}")

    # 3. 验证区块索引范围
    offset = 0
    for start, end, name in BLOCK_RANGES:
        if start != offset:
            errors.append(f"{name} 起始索引错误: expected {offset}, got {start}")
        if end <= start:
            errors.append(f"{name} 结束索引({end}) <= 起始索引({start})")
        offset = end

    if offset != OUTPUT_DIM:
        errors.append(f"总索引偏移({offset}) != OUTPUT_DIM({OUTPUT_DIM})")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "CARD_DIM": CARD_DIM,
            "OUTPUT_DIM": OUTPUT_DIM,
            "num_blocks": len(BLOCK_RANGES),
        }
    }


def print_dimension_summary():
    """打印维度摘要"""
    print("=" * 80)
    print("编码器维度摘要")
    print("=" * 80)

    print(f"\n总维度: {OUTPUT_DIM}")
    print(f"卡牌池: {CARD_DIM} 张")
    print(f"\n区块明细:")
    print("-" * 60)

    offset = 0
    for start, end, name in BLOCK_RANGES:
        dim = end - start
        print(f"  {offset:4d}-{end:4d} ({dim:3d}维): {name}")
        offset = end

    print(f"\n  总计: {OUTPUT_DIM} 维")
    print("=" * 80)


# ============================================================
# 导出列表
# ============================================================

__all__ = [
    # 卡牌池
    "CARD_POOL",
    "CARD_DIM",

    # 区块维度
    "BLOCK1_DIM",
    "BLOCK2_DIM",
    "BLOCK3_DIM",
    "BLOCK4_DIM",
    "BLOCK5_DIM",
    "BLOCK6_DIM",
    "BLOCK7_DIM",
    "BLOCK8_DIM",
    "BLOCK9_DIM",
    "BLOCK10_DIM",
    "OUTPUT_DIM",

    # 归一化上限
    "MAX_HP",
    "MAX_BLOCK",
    "MAX_ENERGY",
    "MAX_GOLD",
    "MAX_POWER",
    "MAX_DEBUFF",

    # 其他维度
    "RELIC_DIM",
    "POTION_DIM",
    "POWER_DIM",
    "INTENT_DIM",
    "MONSTER_DIM",

    # 验证
    "validate_dimensions",
    "print_dimension_summary",
    "BLOCK_RANGES",
]


# 当直接运行此模块时，执行验证
if __name__ == "__main__":
    import sys

    # 验证维度
    result = validate_dimensions()

    if result["valid"]:
        print("✅ 所有维度验证通过")
        sys.exit(0)
    else:
        print("❌ 维度验证失败:")
        for error in result["errors"]:
            print(f"  - {error}")
        sys.exit(1)
