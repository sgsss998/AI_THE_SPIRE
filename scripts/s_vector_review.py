#!/usr/bin/env python3
"""
S 向量设计审查报告

全面审查 encoder.py 中使用的字段，对比 MOD_LOG_PARAMETERS.md
找出所有 Mod 不提供的字段，并提出改进建议
"""
import sys
sys.path.insert(0, '/Volumes/T7/AI_THE_SPIRE')

# ============================================================
# 问题总结
# ============================================================

print("=" * 80)
print("S 向量设计审查报告 - 问题总结")
print("=" * 80)

issues = [
    {
        "category": "怪物字段",
        "severity": "高",
        "issues": [
            {
                "field": "is_boss",
                "location": "encoder.py:569, 744",
                "problem": "Mod 不提供 is_boss 字段",
                "fix": "完全依赖 ID 字符串匹配（已有 fallback）",
                "code": '删除 mon.get("is_boss", False)，只使用 ID 匹配'
            },
            {
                "field": "is_elite",
                "location": "encoder.py:571, 746",
                "problem": "Mod 不提供 is_elite 字段",
                "fix": "完全依赖 ID 字符串匹配（已有 fallback）",
                "code": '删除 mon.get("is_elite", False)，只使用 ID 匹配'
            },
        ]
    },
    {
        "category": "地图字段",
        "severity": "高",
        "issues": [
            {
                "field": "map 对象结构",
                "location": "encoder.py:764-768",
                "problem": "Mod 提供的 map 是数组，不是对象！无法访问 current_x/current_y",
                "fix": "删除地图坐标编码，或改为其他信息",
                "code": "删除 out[88], out[89]，设为预留"
            },
            {
                "field": "visited_rooms",
                "location": "encoder.py:767",
                "problem": "Mod 不提供 visited_rooms 字段",
                "fix": "使用 floor 字段替代",
                "code": "改为使用 floor 作为进度指标"
            },
            {
                "field": "connections",
                "location": "encoder.py:768",
                "problem": "Mod 不提供 connections 字段",
                "fix": "删除此编码",
                "code": "删除，设为预留"
            },
        ]
    },
    {
        "category": "玩家字段",
        "severity": "中",
        "issues": [
            {
                "field": "max_energy",
                "location": "encoder.py:165",
                "problem": "Mod 的 player 对象不提供 max_energy 字段",
                "fix": "使用固定值 3（或从其他来源推断）",
                "code": "max_energy = player.get('max_energy', 3)  # 使用默认值"
            },
        ]
    },
]

# 打印所有问题
for i, category in enumerate(issues, 1):
    print(f"\n【问题类别 {i}】{category['category']} (严重程度: {category['severity']})")
    print("-" * 70)
    for j, issue in enumerate(category['issues'], 1):
        print(f"\n  问题 {j}: {issue['field']}")
        print(f"    位置: {issue['location']}")
        print(f"    问题: {issue['problem']}")
        print(f"    修复: {issue['fix']}")
        print(f"    代码: {issue['code']}")

# ============================================================
# 改进建议
# ============================================================

print("\n" + "=" * 80)
print("S 向量改进建议")
print("=" * 80)

suggestions = [
    {
        "priority": "P0",
        "title": "删除 Mod 不提供的字段",
        "items": [
            "删除 is_boss / is_elite 的直接访问（保留 ID 匹配的 fallback）",
            "删除地图坐标编码（map.current_x, map.current_y）",
            "删除 visited_rooms / connections 编码",
        ]
    },
    {
        "priority": "P1",
        "title": "优化已有编码",
        "items": [
            "简化怪物类型判断：完全依赖 ID 字符串",
            "地图信息：只保留 floor（楼层）作为进度指标",
            "考虑添加实际战斗伤害统计（从 mod 日志推断）",
        ]
    },
    {
        "priority": "P2",
        "title": "增强编码（可选）",
        "items": [
            "添加手牌组合编码：如 '可以打出几张攻击牌'",
            "添加牌组质量评分：0费牌占比、升级牌占比等",
            "添加遗物协同编码：某些遗物组合效果显著",
            "添加敌人威胁度评估：综合考虑HP、意图、buff",
        ]
    },
]

for i, suggestion in enumerate(suggestions, 1):
    print(f"\n【{suggestion['priority']}】{suggestion['title']}")
    print("-" * 70)
    for item in suggestion['items']:
        print(f"  • {item}")

# ============================================================
# Mod 提供但未使用的字段
# ============================================================

print("\n" + "=" * 80)
print("Mod 提供但未充分利用的字段")
print("=" * 80)

unused_fields = [
    {
        "field": "card.uuid",
        "value": "唯一标识",
        "suggestion": "对AI无用，但可用于追踪单张牌的同一性"
    },
    {
        "field": "card.rarity",
        "value": "稀有度 (BASIC/COMMON/UNCOMMON/RARE/SPECIAL)",
        "suggestion": "可用于卡牌价值评估，当前未使用"
    },
    {
        "field": "monster.move_id",
        "value": "当前招式ID",
        "suggestion": "可用于区分同一意图的不同招式"
    },
    {
        "field": "monster.last_move_id",
        "value": "上一招式ID",
        "suggestion": "已使用，但可扩展为完整招式历史"
    },
    {
        "field": "monster.second_last_move_id",
        "value": "上个上个招式ID",
        "suggestion": "已使用，但可扩展为完整招式历史"
    },
    {
        "field": "monster.move_base_damage",
        "value": "基础伤害",
        "suggestion": "可用于计算伤害波动范围"
    },
    {
        "field": "monster.move_hits",
        "value": "打击次数",
        "suggestion": "已使用"
    },
    {
        "field": "monster.powers",
        "value": "怪物 buff/debuff",
        "suggestion": "当前只解析 strength/vulnerable，可扩展"
    },
    {
        "field": "relic.counter",
        "value": "遗物计数器",
        "suggestion": "某些遗物需要关注 counter 值"
    },
    {
        "field": "potion.can_use",
        "value": "药水是否可用",
        "suggestion": "已部分使用，但可增强"
    },
    {
        "field": "potion.can_discard",
        "value": "药水是否可丢弃",
        "suggestion": "Mod 提供，但未使用"
    },
    {
        "field": "potion.requires_target",
        "value": "药水是否需要目标",
        "suggestion": "已使用"
    },
    {
        "field": "screen_state.options",
        "value": "事件选项列表",
        "suggestion": "可用于事件决策，当前未充分编码"
    },
    {
        "field": "screen_state.selected / selected_cards",
        "value": "手牌选择屏幕的已选卡牌",
        "suggestion": "可用于了解选择了哪些牌"
    },
]

for field in unused_fields:
    print(f"\n• {field['field']}")
    print(f"  值: {field['value']}")
    print(f"  建议: {field['suggestion']}")

print("\n" + "=" * 80)
