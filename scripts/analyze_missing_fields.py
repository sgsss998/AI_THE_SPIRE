#!/usr/bin/env python3
"""
分析 Mod 日志中有价值但尚未充分利用的字段

找出高优先级字段，用于填充预留空间
"""
import sys
sys.path.insert(0, '/Volumes/T7/AI_THE_SPIRE')

print("=" * 80)
print("Mod 日志中有价值但尚未充分利用的字段分析")
print("=" * 80)

# 根据优先级排序的字段列表
missing_fields = {
    "⭐⭐⭐ 必须包含（缺失或未充分利用）": [
        {
            "field": "game_state.class",
            "type": "string",
            "values": "THE_SILENT, THE_IRONCLAD, THE_DEFECT",
            "description": "角色类 - 不同角色策略完全不同！",
            "suggestion": "添加到全局区块，3维 one-hot 编码",
            "priority": "P0",
        },
        {
            "field": "game_state.deck",
            "type": "array",
            "description": "完整牌组（所有卡牌）- 对长期决策至关重要",
            "suggestion": "添加新区块或使用预留空间编码牌组构成",
            "priority": "P0",
        },
        {
            "field": "game_state.choice_list",
            "type": "array",
            "description": "选择列表（商店商品/事件选项/卡牌奖励）",
            "suggestion": "添加到全局区块，编码可用选择",
            "priority": "P0",
        },
    ],

    "⭐⭐ 重要（缺失或未充分利用）": [
        {
            "field": "game_state.ascension_level",
            "type": "int",
            "values": "0-20",
            "description": "逆飞（难易度）等级 - 影响策略",
            "suggestion": "添加到全局区块，1维归一化",
            "priority": "P1",
        },
        {
            "field": "combat_state.card_in_play",
            "type": "object",
            "description": "正在打出的牌（等待效果结算）",
            "suggestion": "添加到全局区块，编码正在打出的牌",
            "priority": "P1",
        },
        {
            "field": "combat_state.player.orbs",
            "type": "array",
            "description": "能量球（缺陷角色）",
            "suggestion": "添加到玩家Powers区块，编码能量球状态",
            "priority": "P1",
        },
        {
            "field": "screen_state.purge_available",
            "type": "bool",
            "description": "商店是否可删牌",
            "suggestion": "添加到全局区块商店信息",
            "priority": "P1",
        },
        {
            "field": "screen_state.purge_cost",
            "type": "int",
            "description": "删牌价格",
            "suggestion": "添加到全局区块商店信息",
            "priority": "P1",
        },
        {
            "field": "screen_state.boss_relic",
            "type": "object",
            "description": "Boss遗物选择",
            "suggestion": "添加到全局区块编码可选Boss遗物",
            "priority": "P1",
        },
        {
            "field": "screen_state.selected_cards",
            "type": "array",
            "description": "手牌选择屏幕已选卡牌",
            "suggestion": "添加到全局区块编码已选卡牌",
            "priority": "P1",
        },
        {
            "field": "screen_state.rewards",
            "type": "array",
            "description": "奖励列表（金币/药水/卡牌）",
            "suggestion": "添加到全局区块编码奖励类型",
            "priority": "P1",
        },
        {
            "field": "potion.can_discard",
            "type": "bool",
            "description": "药水是否可丢弃",
            "suggestion": "添加到药水区块",
            "priority": "P1",
        },
    ],

    "⭐ 可选（可以添加）": [
        {
            "field": "combat_state.limbo",
            "type": "array",
            "description": "虚空牌（打出中）",
            "suggestion": "添加到全局区块",
            "priority": "P2",
        },
        {
            "field": "combat_state.times_damaged",
            "type": "int",
            "description": "本局受击次数",
            "suggestion": "添加到战斗统计",
            "priority": "P2",
        },
        {
            "field": "monster.half_dead",
            "type": "bool",
            "description": "是否半死状态（小史莱姆分裂后）",
            "suggestion": "添加到怪物区块",
            "priority": "P2",
        },
        {
            "field": "screen_state.event_name",
            "type": "string",
            "description": "事件名称",
            "suggestion": "已经有 event_id，可以不添加",
            "priority": "P2",
        },
        {
            "field": "relic.counter",
            "type": "int",
            "description": "遗物计数器值",
            "suggestion": "对某些遗物很重要",
            "priority": "P2",
        },
    ],
}

# 打印分析结果
for category, fields in missing_fields.items():
    print(f"\n{category}")
    print("-" * 70)
    for i, field in enumerate(fields, 1):
        print(f"\n  {i}. {field['field']}")
        print(f"     类型: {field['type']}")
        if 'values' in field:
            print(f"     值: {field['values']}")
        print(f"     描述: {field['description']}")
        print(f"     优先级: {field['priority']}")
        print(f"     建议: {field['suggestion']}")

# 推荐的填充方案
print("\n" + "=" * 80)
print("推荐填充方案（按优先级）")
print("=" * 80)

recommendations = [
    {
        "priority": "P0 - 最高优先级",
        "fields": [
            ("game_state.class", "3维 one-hot", "全局区块 [201-203]"),
        ],
        "reason": "角色类是最重要的缺失信息，不同角色策略完全不同",
    },
    {
        "priority": "P1 - 高优先级",
        "fields": [
            ("game_state.ascension_level", "1维 归一化", "全局区块 [204]"),
            ("screen_state.purge_available", "1维 bool", "全局区块 [205]"),
            ("screen_state.purge_cost", "1维 归一化", "全局区块 [206]"),
            ("combat_state.card_in_play.id", "1维 卡牌ID索引", "全局区块 [207]"),
            ("combat_state.card_in_play.upgrades", "1维 bool", "全局区块 [208]"),
        ],
        "reason": "难度等级、商店删牌、正在打出的牌都是重要决策信息",
    },
    {
        "priority": "P2 - 中等优先级",
        "fields": [
            ("combat_state.player.orbs", "5×3=15维（类型×层数）", "全局区块 [209-223]"),
            ("combat_state.times_damaged", "1维", "全局区块 [224]"),
            ("screen_state.rewards", "4维", "全局区块 [225-228]"),
            ("monster.half_dead", "1维/怪物", "怪物区块预留空间"),
            ("potion.can_discard", "1维/药水", "药水区块预留空间"),
        ],
        "reason": "能量球、受击次数、奖励等信息对决策有帮助",
    },
]

for i, rec in enumerate(recommendations, 1):
    print(f"\n【{rec['priority']}】")
    print(f"原因: {rec['reason']}")
    print(f"建议添加:")
    for field, encoding, location in rec['fields']:
        print(f"  - {field}: {encoding} → {location}")

# 计算可用的预留空间
print("\n" + "=" * 80)
print("可用预留空间统计")
print("=" * 80)

reserved_spaces = [
    ("区块3 抽牌堆", 113),
    ("区块4 弃牌堆", 113),
    ("区块5 消耗堆", 13),
    ("区块9 药水", 128),
    ("区块10 全局", 299),
]

total_reserved = sum(count for _, count in reserved_spaces)
print(f"\n总预留: {total_reserved} 维")
print(f"占比: {total_reserved}/2945 = {total_reserved/2945*100:.1f}%")

for block, count in reserved_spaces:
    print(f"  {block}: {count} 维")

print(f"\n💡 建议优先使用全局区块的 299 维预留空间")
