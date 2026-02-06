#!/usr/bin/env python3
"""
测试新增字段编码

验证 P0/P1 优先级的新增字段是否正确工作：
1. 角色类 one-hot (game_state.class)
2. 逆飞等级 (ascension_level)
3. 商店删牌信息 (purge_available/cost)
4. 正在打出的牌 (card_in_play)
5. 能量球状态 (player.orbs)
6. 受击次数 (times_damaged)
7. 奖励类型 (rewards)
"""
import sys
sys.path.insert(0, '/Volumes/T7/AI_THE_SPIRE')

import numpy as np
from src.training.encoder import encode


def test_player_class_encoding():
    """测试角色类编码"""
    print("=" * 80)
    print("测试1：角色类编码 (game_state.class)")
    print("=" * 80)

    # 测试静默角色
    test_state = {
        "game_state": {
            "class": "THE_SILENT",
            "floor": 10,
            "act": 1,
            "current_hp": 50,
            "max_hp": 70,
            "gold": 100,
            "combat_state": {
                "player": {"energy": 3, "max_hp": 70, "current_hp": 50, "block": 0},
                "hand": [], "draw_pile": [], "discard_pile": [], "exhaust_pile": [], "monsters": [],
                "turn": 1, "cards_discarded_this_turn": 0, "times_damaged": 0,
            },
            "relics": [], "potions": [], "screen_state": {"options": []},
        },
        "available_commands": ["play", "end"], "ready_for_command": True, "in_game": True,
    }

    encoded = encode(test_state)
    global_start = 2445

    # [201-203] 角色类 one-hot
    print(f"\n[201-203] 角色类编码:")
    print(f"  THE_SILENT: {encoded[global_start + 201]:.1f} - 预期: 1.0")
    print(f"  THE_IRONCLAD: {encoded[global_start + 202]:.1f} - 预期: 0.0")
    print(f"  THE_DEFECT: {encoded[global_start + 203]:.1f} - 预期: 0.0")

    if encoded[global_start + 201] == 1.0:
        print("  ✅ 角色类编码正确")
        return True
    else:
        print("  ❌ 角色类编码错误")
        return False


def test_ascension_level():
    """测试逆飞等级"""
    print("\n" + "=" * 80)
    print("测试2：逆飞等级 (ascension_level)")
    print("=" * 80)

    test_state = {
        "game_state": {
            "class": "THE_SILENT",
            "ascension_level": 15,
            "floor": 10, "act": 1, "current_hp": 50, "max_hp": 70, "gold": 100,
            "combat_state": {
                "player": {"energy": 3, "max_hp": 70, "current_hp": 50, "block": 0},
                "hand": [], "draw_pile": [], "discard_pile": [], "exhaust_pile": [], "monsters": [],
                "turn": 1, "cards_discarded_this_turn": 0, "times_damaged": 0,
            },
            "relics": [], "potions": [], "screen_state": {"options": []},
        },
        "available_commands": ["play", "end"], "ready_for_command": True, "in_game": True,
    }

    encoded = encode(test_state)
    global_start = 2445

    # [204] 逆飞等级
    ascension = encoded[global_start + 204]
    expected = 15 / 20  # 归一化
    print(f"\n[204] 逆飞等级: {ascension:.4f} - 预期: {expected:.4f} (15/20)")

    if abs(ascension - expected) < 0.01:
        print("  ✅ 逆飞等级编码正确")
        return True
    else:
        print("  ❌ 逆飞等级编码错误")
        return False


def test_purge_info():
    """测试商店删牌信息"""
    print("\n" + "=" * 80)
    print("测试3：商店删牌信息 (purge_available/cost)")
    print("=" * 80)

    test_state = {
        "game_state": {
            "class": "THE_SILENT", "floor": 10, "act": 1,
            "current_hp": 50, "max_hp": 70, "gold": 200,
            "combat_state": {
                "player": {"energy": 3, "max_hp": 70, "current_hp": 50, "block": 0},
                "hand": [], "draw_pile": [], "discard_pile": [], "exhaust_pile": [], "monsters": [],
                "turn": 1, "cards_discarded_this_turn": 0, "times_damaged": 0,
            },
            "relics": [], "potions": [],
            "screen_state": {
                "options": [],
                "purge_available": True,
                "purge_cost": 125,
            },
        },
        "available_commands": ["proceed"], "ready_for_command": True, "in_game": True,
    }

    encoded = encode(test_state)
    global_start = 2445

    # [205-206] 商店删牌信息
    purge_avail = encoded[global_start + 205]
    purge_cost = encoded[global_start + 206]
    expected_cost = 125 / 150  # 归一化

    print(f"\n[205] 可删牌: {purge_avail:.1f} - 预期: 1.0")
    print(f"[206] 删牌价格: {purge_cost:.4f} - 预期: {expected_cost:.4f} (125/150)")

    if purge_avail == 1.0 and abs(purge_cost - expected_cost) < 0.01:
        print("  ✅ 商店删牌信息编码正确")
        return True
    else:
        print("  ❌ 商店删牌信息编码错误")
        return False


def test_card_in_play():
    """测试正在打出的牌"""
    print("\n" + "=" * 80)
    print("测试4：正在打出的牌 (card_in_play)")
    print("=" * 80)

    test_state = {
        "game_state": {
            "class": "THE_SILENT", "floor": 10, "act": 1,
            "current_hp": 50, "max_hp": 70, "gold": 100,
            "combat_state": {
                "player": {"energy": 3, "max_hp": 70, "current_hp": 50, "block": 0},
                "hand": [],
                "draw_pile": [], "discard_pile": [], "exhaust_pile": [], "monsters": [],
                "turn": 1, "cards_discarded_this_turn": 0, "times_damaged": 0,
                "card_in_play": {
                    "id": "Backstab",
                    "name": "背刺",
                    "upgrades": 1,
                },
            },
            "relics": [], "potions": [], "screen_state": {"options": []},
        },
        "available_commands": ["play", "end"], "ready_for_command": True, "in_game": True,
    }

    encoded = encode(test_state)
    global_start = 2445

    # [207-208] 正在打出的牌
    card_idx = encoded[global_start + 207]
    is_upgraded = encoded[global_start + 208]

    print(f"\n[207] 卡牌ID: {card_idx:.4f}")
    print(f"[208] 是否升级: {is_upgraded:.1f} - 预期: 1.0")

    if is_upgraded == 1.0 and card_idx > 0:
        print("  ✅ 正在打出的牌编码正确")
        return True
    else:
        print("  ❌ 正在打出的牌编码错误")
        return False


def test_orbs():
    """测试能量球状态"""
    print("\n" + "=" * 80)
    print("测试5：能量球状态 (player.orbs)")
    print("=" * 80)

    test_state = {
        "game_state": {
            "class": "THE_DEFECT", "floor": 10, "act": 1,
            "current_hp": 50, "max_hp": 70, "gold": 100,
            "combat_state": {
                "player": {
                    "energy": 3, "max_hp": 70, "current_hp": 50, "block": 0,
                    "orbs": [
                        {"id": "Plasma", "amount": 5, "focus_evoke_amount": 10},
                        {"id": "Frost", "amount": 3, "focus_evoke_amount": 5},
                        {"id": "Lightning", "amount": 2, "focus_evoke_amount": 8},
                    ],
                },
                "hand": [], "draw_pile": [], "discard_pile": [], "exhaust_pile": [], "monsters": [],
                "turn": 1, "cards_discarded_this_turn": 0, "times_damaged": 0,
            },
            "relics": [], "potions": [], "screen_state": {"options": []},
        },
        "available_commands": ["play", "end"], "ready_for_command": True, "in_game": True,
    }

    encoded = encode(test_state)
    global_start = 2445

    # [209-223] 能量球状态 (15维)
    print(f"\n[209-223] 能量球状态:")

    # 第一个能量球: Plasma (索引2)
    orb1_base = global_start + 209
    print(f"  能量球1 (Plasma):")
    print(f"    Plasma类型: {encoded[orb1_base + 2]:.1f} - 预期: 1.0")
    print(f"    层数: {encoded[orb1_base + 4]:.4f} - 预期: ~0.25 (5/20)")

    # 第二个能量球: Frost (索引0)
    orb2_base = global_start + 214
    print(f"  能量球2 (Frost):")
    print(f"    Frost类型: {encoded[orb2_base + 0]:.1f} - 预期: 1.0")
    print(f"    层数: {encoded[orb2_base + 4]:.4f} - 预期: ~0.15 (3/20)")

    # 第三个能量球: Lightning (索引1)
    orb3_base = global_start + 219
    print(f"  能量球3 (Lightning):")
    print(f"    Lightning类型: {encoded[orb3_base + 1]:.1f} - 预期: 1.0")
    print(f"    层数: {encoded[orb3_base + 4]:.4f} - 预期: ~0.10 (2/20)")

    if (encoded[orb1_base + 2] == 1.0 and
        encoded[orb2_base + 0] == 1.0 and
        encoded[orb3_base + 1] == 1.0):
        print("  ✅ 能量球状态编码正确")
        return True
    else:
        print("  ❌ 能量球状态编码错误")
        return False


def test_times_damaged():
    """测试受击次数"""
    print("\n" + "=" * 80)
    print("测试6：受击次数 (times_damaged)")
    print("=" * 80)

    test_state = {
        "game_state": {
            "class": "THE_SILENT", "floor": 10, "act": 1,
            "current_hp": 50, "max_hp": 70, "gold": 100,
            "combat_state": {
                "player": {"energy": 3, "max_hp": 70, "current_hp": 50, "block": 0},
                "hand": [], "draw_pile": [], "discard_pile": [], "exhaust_pile": [], "monsters": [],
                "turn": 1, "cards_discarded_this_turn": 0, "times_damaged": 5,
            },
            "relics": [], "potions": [], "screen_state": {"options": []},
        },
        "available_commands": ["play", "end"], "ready_for_command": True, "in_game": True,
    }

    encoded = encode(test_state)
    global_start = 2445

    # [224] 受击次数
    times_damaged = encoded[global_start + 224]
    expected = 5 / 20  # 归一化

    print(f"\n[224] 受击次数: {times_damaged:.4f} - 预期: {expected:.4f} (5/20)")

    if abs(times_damaged - expected) < 0.01:
        print("  ✅ 受击次数编码正确")
        return True
    else:
        print("  ❌ 受击次数编码错误")
        return False


def test_rewards():
    """测试奖励类型"""
    print("\n" + "=" * 80)
    print("测试7：奖励类型 (rewards)")
    print("=" * 80)

    test_state = {
        "game_state": {
            "class": "THE_SILENT", "floor": 10, "act": 1,
            "current_hp": 50, "max_hp": 70, "gold": 100,
            "combat_state": {
                "player": {"energy": 3, "max_hp": 70, "current_hp": 50, "block": 0},
                "hand": [], "draw_pile": [], "discard_pile": [], "exhaust_pile": [], "monsters": [],
                "turn": 1, "cards_discarded_this_turn": 0, "times_damaged": 0,
            },
            "relics": [], "potions": [],
            "screen_state": {
                "options": [],
                "rewards": [
                    {"reward_type": "GOLD", "gold": 100},
                    {"reward_type": "CARD", "cards": []},
                    {"reward_type": "POTION", "potion": {}},
                ],
            },
        },
        "available_commands": ["choose"], "ready_for_command": True, "in_game": True,
    }

    encoded = encode(test_state)
    global_start = 2445

    # [225-228] 奖励类型
    card_reward = encoded[global_start + 225]
    potion_reward = encoded[global_start + 226]
    gold_reward = encoded[global_start + 227]
    relic_reward = encoded[global_start + 228]

    print(f"\n[225-228] 奖励类型:")
    print(f"  卡牌: {card_reward:.1f} - 预期: 1.0")
    print(f"  药水: {potion_reward:.1f} - 预期: 1.0")
    print(f"  金币: {gold_reward:.4f} - 预期: ~0.667 (100/50)")
    print(f"  遗物: {relic_reward:.1f} - 预期: 0.0")

    if (card_reward == 1.0 and potion_reward == 1.0 and
        abs(gold_reward - 0.667) < 0.1 and relic_reward == 0.0):
        print("  ✅ 奖励类型编码正确")
        return True
    else:
        print("  ❌ 奖励类型编码错误")
        return False


def main():
    print("新增字段编码测试")
    print()

    results = []
    results.append(("角色类编码", test_player_class_encoding()))
    results.append(("逆飞等级", test_ascension_level()))
    results.append(("商店删牌信息", test_purge_info()))
    results.append(("正在打出的牌", test_card_in_play()))
    results.append(("能量球状态", test_orbs()))
    results.append(("受击次数", test_times_damaged()))
    results.append(("奖励类型", test_rewards()))

    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    all_passed = all(result for _, result in results)
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}: {'通过' if result else '失败'}")

    if all_passed:
        print("\n✅ 所有新增字段测试通过")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
