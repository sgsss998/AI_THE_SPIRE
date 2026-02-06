#!/usr/bin/env python3
"""
验证 encoder.py 中使用的字段是否在 Mod 日志中提供

对比 MOD_LOG_PARAMETERS.md 和 encoder.py 中的字段使用
"""
import sys
sys.path.insert(0, '/Volumes/T7/AI_THE_SPIRE')

import re
from pathlib import Path

# Mod 提供的卡牌字段（从 MOD_LOG_PARAMETERS.md 提取）
MOD_CARD_FIELDS = {
    "id": True,          # ✅ 卡牌唯一ID
    "name": True,        # ✅ 卡牌名称（中文）
    "cost": True,        # ✅ 能量费用
    "type": True,        # ✅ 卡牌类型
    "is_playable": True, # ✅ 当前是否可打出
    "has_target": True,  # ✅ 是否需要选择目标
    "upgrades": True,    # ✅ 升级次数
    "rarity": True,      # ✅ 稀有度
    "ethereal": True,    # ✅ 是否虚无牌
    "exhausts": True,    # ✅ 是否消耗
    "uuid": True,        # ✅ 唯一标识（对AI无用）
}

# Mod 不提供的字段
MOD_MISSING_FIELDS = {
    "exhaust": "Mod 提供的是 'exhausts'，不是 'exhaust'",
    "is_stripped": "Mod 不提供此字段",
    "cost_for_turn": "Mod 不提供此字段（应该用 cost）",
}

# encoder.py 中使用的卡牌字段（从代码中提取）
ENCODER_CARD_FIELDS = [
    "id",
    "name",
    "cost",
    "type",
    "is_playable",
    "has_target",
    "upgrades",
    "ethereal",
    "exhaust",         # ❌ 应该用 exhausts
    "exhausts",        # ✅ 正确
    "is_stripped",     # ❌ Mod不提供
    "cost_for_turn",   # ❌ Mod不提供
]


def check_field_usage():
    """检查 encoder.py 中的字段使用"""
    print("=" * 80)
    print("Mod 字段可用性验证")
    print("=" * 80)

    encoder_file = Path("/Volumes/T7/AI_THE_SPIRE/src/training/encoder.py")
    content = encoder_file.read_text()

    print("\n【1】Mod 提供的卡牌字段：")
    for field in sorted(MOD_CARD_FIELDS.keys()):
        print(f"  ✅ {field:20s} - Mod 提供")

    print("\n【2】encoder.py 中使用的字段检查：")
    issues = []

    for field in ENCODER_CARD_FIELDS:
        if field in MOD_CARD_FIELDS:
            print(f"  ✅ {field:20s} - Mod 提供")
        elif field in MOD_MISSING_FIELDS:
            print(f"  ❌ {field:20s} - {MOD_MISSING_FIELDS[field]}")
            issues.append((field, MOD_MISSING_FIELDS[field]))
        else:
            print(f"  ⚠️  {field:20s} - 状态未知")
            issues.append((field, "未知状态"))

    print("\n【3】需要修复的问题：")
    if not issues:
        print("  ✅ 没有发现问题")
    else:
        for field, reason in issues:
            print(f"  ❌ {field}: {reason}")

            # 检查使用位置
            pattern = rf'c\.get\("{field}"'
            matches = re.finditer(pattern, content)
            for match in matches:
                # 获取行号
                line_num = content[:match.start()].count('\n') + 1
                print(f"     → 第 {line_num} 行")

    return issues


def suggest_fixes():
    """建议修复方案"""
    print("\n" + "=" * 80)
    print("修复建议")
    print("=" * 80)

    suggestions = [
        {
            "problem": "使用 `exhaust` 字段",
            "fix": "改为使用 `exhausts` 字段（Mod 提供的名称）",
            "code_before": 'c.get("exhaust", False) or c.get("exhausts", False)',
            "code_after": 'c.get("exhausts", False)',
        },
        {
            "problem": "使用 `is_stripped` 字段（Mod 不提供）",
            "fix": "删除此编码，或设为默认值 0",
            "code_before": 'out[base + 5] = 1.0 if c.get("is_stripped", False) else 0.0  # 被夺',
            "code_after": '# is_stripped 字段 Mod 不提供，已删除\nout[base + 5] = 0.0  # 预留',
        },
        {
            "problem": "使用 `cost_for_turn` 字段（Mod 不提供）",
            "fix": "使用 `cost` 字段代替",
            "code_before": 'cost_for_turn = c.get("cost_for_turn", cost)',
            "code_after": '# Mod 不提供 cost_for_turn，直接使用 cost\ncost_for_turn = cost',
        },
    ]

    for i, suggestion in enumerate(suggestions, 1):
        print(f"\n问题 {i}: {suggestion['problem']}")
        print(f"  修复方案: {suggestion['fix']}")
        if 'code_before' in suggestion:
            print(f"  修改前: {suggestion['code_before']}")
            print(f"  修改后: {suggestion['code_after']}")


def main():
    issues = check_field_usage()
    suggest_fixes()

    print("\n" + "=" * 80)
    print("总结")
    print("=" * 80)

    if issues:
        print(f"❌ 发现 {len(issues)} 个需要修复的问题")
        return 1
    else:
        print("✅ 所有字段验证通过")
        return 0


if __name__ == "__main__":
    sys.exit(main())
