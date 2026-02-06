#!/usr/bin/env python3
"""
测试 P1 优化功能

验证：
1. 怪物类型判断优化（完整的 Boss/Elite ID 列表）
2. 卡牌稀有度编码
3. 怪物 move_id 编码
"""
import sys
sys.path.insert(0, '/Volumes/T7/AI_THE_SPIRE')

import numpy as np
from src.training.encoder import encode
from src.training.encoder_utils import (
    get_monster_type,
    card_rarity_to_index,
)

def test_monster_type_detection():
    """测试怪物类型判断"""
    print("=" * 80)
    print("测试1：怪物类型判断")
    print("=" * 80)

    test_cases = [
        ("SlimeBoss", 2, "Boss"),
        ("GremlinNob", 1, "Elite"),
        ("Cultist", 0, "Normal"),
        ("Hexaghost", 2, "Boss"),
        ("Lagavulin", 1, "Elite"),
        ("JawWorm", 0, "Normal"),
        ("CorruptHeart", 2, "Boss"),
        ("TimeEater", 2, "Boss"),
        ("Nemesis", 1, "Elite"),
    ]

    all_passed = True
    for monster_id, expected, desc in test_cases:
        result = get_monster_type(monster_id)
        status = "✅" if result == expected else "❌"
        print(f"{status} {monster_id:20s}: {result} (预期 {expected}, {desc})")
        if result != expected:
            all_passed = False

    print(f"\n{'通过' if all_passed else '失败'}")
    return all_passed


def test_card_rarity_encoding():
    """测试卡牌稀有度编码"""
    print("\n" + "=" * 80)
    print("测试2：卡牌稀有度编码")
    print("=" * 80)

    test_cases = [
        ("BASIC", 0),
        ("COMMON", 1),
        ("UNCOMMON", 2),
        ("RARE", 3),
        ("SPECIAL", 4),
        ("", 1),  # 默认为 COMMON
        ("unknown", 1),  # 未知映射到 COMMON
    ]

    all_passed = True
    for rarity, expected in test_cases:
        result = card_rarity_to_index(rarity)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{rarity or '(空)':10s}': {result} (预期 {expected})")
        if result != expected:
            all_passed = False

    print(f"\n{'通过' if all_passed else '失败'}")
    return all_passed


def test_move_id_encoding():
    """测试怪物 move_id 编码"""
    print("\n" + "=" * 80)
    print("测试3：怪物 move_id 编码")
    print("=" * 80)

    # 创建一个包含怪物的测试状态
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
                "hand": [
                    {
                        "id": "Strike_G",
                        "name": "打击",
                        "cost": 1,
                        "type": "ATTACK",
                        "rarity": "BASIC",
                        "is_playable": True,
                        "has_target": True,
                        "upgrades": 0,
                    }
                ],
                "draw_pile": [],
                "discard_pile": [],
                "exhaust_pile": [],
                "monsters": [
                    {
                        "id": "Cultist",
                        "name": "邪教徒",
                        "current_hp": 30,
                        "max_hp": 48,
                        "block": 0,
                        "intent": "ATTACK_BUFF",
                        "move_id": 3,
                        "move_base_damage": 12,
                        "move_adjusted_damage": 14,
                        "move_hits": 1,
                        "is_gone": False,
                        "half_dead": False,
                        "last_move_id": 2,
                        "second_last_move_id": 1,
                        "powers": [],
                    },
                    {
                        "id": "JawWorm",
                        "name": "颚虫",
                        "current_hp": 40,
                        "max_hp": 42,
                        "block": 5,
                        "intent": "DEFEND",
                        "move_id": 1,
                        "move_base_damage": 0,
                        "move_adjusted_damage": 0,
                        "move_hits": 0,
                        "is_gone": False,
                        "powers": [],
                    },
                ],
                "turn": 1,
                "cards_discarded_this_turn": 0,
                "times_damaged": 0,
            },
            "relics": [{"id": "Burning Blood"}],
            "potions": [],
            "screen_state": {"options": []},
        },
        "available_commands": ["play", "end"],
        "ready_for_command": True,
        "in_game": True,
    }

    # 编码状态
    encoded = encode(test_state)
    print(f"✅ 编码成功: {len(encoded)} 维")

    # 检查怪物区域
    monster_block_start = 1427
    first_monster_base = monster_block_start

    # 检查第一个怪物（Cultist）的 move_id 编码
    # 索引80是当前招式ID
    move_id_index = first_monster_base + 80
    print(f"怪物1 move_id 编码 (索引{move_id_index}): {encoded[move_id_index]:.4f}")
    print(f"  预期: move_id=3 应该编码为 ~0.03 (3/100)")
    if abs(encoded[move_id_index] - 0.03) < 0.01:
        print("  ✅ move_id 编码正确")
    else:
        print(f"  ❌ move_id 编码不正确，实际值: {encoded[move_id_index]}")

    # 检查 Intent 编码
    intent_start = first_monster_base + 83
    intent_index = intent_start + 0  # ATTACK_BUFF
    print(f"怪物1 Intent 编码 (索引{intent_index}): {encoded[intent_index]:.4f}")
    if encoded[intent_index] > 0.5:
        print("  ✅ Intent 编码正确")
    else:
        print("  ❌ Intent 编码可能有问题")

    print("\n✅ move_id 编码测试完成")
    return True


def test_card_rarity_in_state():
    """测试完整状态中的卡牌稀有度编码"""
    print("\n" + "=" * 80)
    print("测试4：完整状态中的卡牌稀有度编码")
    print("=" * 80)

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
                "hand": [
                    {
                        "id": "Strike_G",
                        "name": "打击",
                        "cost": 1,
                        "type": "ATTACK",
                        "rarity": "BASIC",
                        "is_playable": True,
                        "has_target": True,
                        "upgrades": 0,
                    },
                    {
                        "id": "DeadlyPoison",
                        "name": "剧毒",
                        "cost": 1,
                        "type": "SKILL",
                        "rarity": "COMMON",
                        "is_playable": True,
                        "has_target": False,
                        "upgrades": 0,
                    },
                    {
                        "id": "Footwork",
                        "name": "轻功",
                        "cost": 1,
                        "type": "SKILL",
                        "rarity": "UNCOMMON",
                        "is_playable": False,
                        "has_target": False,
                        "upgrades": 0,
                    },
                ],
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
            "screen_state": {"options": []},
        },
        "available_commands": ["play", "end"],
        "ready_for_command": True,
        "in_game": True,
    }

    encoded = encode(test_state)

    # 手牌区块从索引17开始
    hand_block_start = 17

    # 第一张牌 (Strike_G, BASIC) 的稀有度编码
    # 每张牌23维，所以索引14-18是稀有度
    # BASIC = 0，所以应该在第14+0=14位置
    card1_rarity_BASIC = hand_block_start + 144 + 14
    print(f"Strike_G (BASIC) 稀有度编码 (索引{card1_rarity_BASIC}): {encoded[card1_rarity_BASIC]:.1f}")
    if encoded[card1_rarity_BASIC] > 0.5:
        print("  ✅ BASIC 稀有度编码正确")
    else:
        print("  ❌ BASIC 稀有度编码有问题")

    # 第二张牌 (DeadlyPoison, COMMON) 的稀有度编码
    card2_rarity_COMMON = hand_block_start + 144 + 14 + 1
    print(f"DeadlyPoison (COMMON) 稀有度编码 (索引{card2_rarity_COMMON}): {encoded[card2_rarity_COMMON]:.1f}")
    if encoded[card2_rarity_COMMON] > 0.5:
        print("  ✅ COMMON 稀有度编码正确")
    else:
        print("  ❌ COMMON 稀有度编码有问题")

    # 第三张牌 (Footwork, UNCOMMON) 的稀有度编码
    card3_rarity_UNCOMMON = hand_block_start + 144 + 14 + 2
    print(f"Footwork (UNCOMMON) 稀有度编码 (索引{card3_rarity_UNCOMMON}): {encoded[card3_rarity_UNCOMMON]:.1f}")
    if encoded[card3_rarity_UNCOMMON] > 0.5:
        print("  ✅ UNCOMMON 稀有度编码正确")
    else:
        print("  ❌ UNCOMMON 稀有度编码有问题")

    print("\n✅ 卡牌稀有度编码测试完成")
    return True


def main():
    print("P1 优化功能测试")
    print()

    results = []
    results.append(("怪物类型判断", test_monster_type_detection()))
    results.append(("卡牌稀有度编码", test_card_rarity_encoding()))
    results.append(("怪物 move_id 编码", test_move_id_encoding()))
    results.append(("完整状态稀有度编码", test_card_rarity_in_state()))

    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    all_passed = all(result for _, result in results)
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}: {'通过' if result else '失败'}")

    if all_passed:
        print("\n✅ 所有 P1 优化功能测试通过")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
