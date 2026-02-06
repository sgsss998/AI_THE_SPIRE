#!/usr/bin/env python3
"""
验证 encode() 函数的索引拼接逻辑

确保每个区块的数据被正确放置在输出向量中
"""
import sys
sys.path.insert(0, '/Volumes/T7/AI_THE_SPIRE')

import numpy as np
from src.training.encoder import (
    _encode_block1_player_core,
    _encode_block2_hand,
    _encode_block3_draw_pile,
    _encode_block4_discard_pile,
    _encode_block5_exhaust_pile,
    _encode_block6_player_powers,
    _encode_block7_monsters,
    _encode_block8_relics,
    _encode_block9_potions,
    _encode_block10_global,
    encode,
    get_output_dim,
)
from src.training.encoder_dims import (
    BLOCK1_DIM, BLOCK2_DIM, BLOCK3_DIM, BLOCK4_DIM, BLOCK5_DIM,
    BLOCK6_DIM, BLOCK7_DIM, BLOCK8_DIM, BLOCK9_DIM, BLOCK10_DIM,
    OUTPUT_DIM, BLOCK_RANGES,
)


def test_block_dimensions():
    """测试每个区块的输出维度"""
    print("=" * 80)
    print("区块维度测试")
    print("=" * 80)

    # 创建测试用的 mod_response
    test_mod_response = {
        "game_state": {
            "current_hp": 50,
            "max_hp": 70,
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
                "options": []
            },
            "floor": 1,
            "act": 1,
            "room_phase": "COMBAT",
        },
        "available_commands": ["play", "end"],
        "ready_for_command": True,
        "in_game": True,
    }

    errors = []

    # 测试每个区块
    blocks = [
        ("区块1", _encode_block1_player_core, BLOCK1_DIM),
        ("区块2", _encode_block2_hand, BLOCK2_DIM),
        ("区块3", _encode_block3_draw_pile, BLOCK3_DIM),
        ("区块4", _encode_block4_discard_pile, BLOCK4_DIM),
        ("区块5", _encode_block5_exhaust_pile, BLOCK5_DIM),
        ("区块6", _encode_block6_player_powers, BLOCK6_DIM),
        ("区块7", _encode_block7_monsters, BLOCK7_DIM),
        ("区块8", _encode_block8_relics, BLOCK8_DIM),
        ("区块9", _encode_block9_potions, BLOCK9_DIM),
        ("区块10", _encode_block10_global, BLOCK10_DIM),
    ]

    for name, func, expected_dim in blocks:
        result = func(test_mod_response)
        actual_dim = len(result)
        status = "✅" if actual_dim == expected_dim else "❌"
        print(f"{status} {name}: {actual_dim} 维 (预期 {expected_dim})")
        if actual_dim != expected_dim:
            errors.append(f"{name}: {actual_dim} != {expected_dim}")

    return errors


def test_encode_function():
    """测试 encode() 函数的总输出"""
    print("\n" + "=" * 80)
    print("encode() 函数测试")
    print("=" * 80)

    test_mod_response = {
        "game_state": {
            "current_hp": 50,
            "max_hp": 70,
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
                "options": []
            },
            "floor": 1,
            "act": 1,
            "room_phase": "COMBAT",
        },
        "available_commands": ["play", "end"],
        "ready_for_command": True,
        "in_game": True,
    }

    result = encode(test_mod_response)
    actual_dim = len(result)
    expected_dim = get_output_dim()

    status = "✅" if actual_dim == expected_dim else "❌"
    print(f"{status} encode() 输出: {actual_dim} 维")
    print(f"   预期 OUTPUT_DIM: {expected_dim}")

    if actual_dim != expected_dim:
        print(f"   ❌ 维度不匹配！相差 {actual_dim - expected_dim}")
        return False

    # 检查归一化（所有值应该在 [0, 1] 范围内）
    if np.any((result < 0) | (result > 1)):
        print(f"   ⚠️  存在超出 [0, 1] 范围的值")
        print(f"      最小值: {result.min():.4f}")
        print(f"      最大值: {result.max():.4f}")
        return False

    print(f"   ✅ 归一化检查通过")
    return True


def test_block_ranges():
    """测试区块索引范围"""
    print("\n" + "=" * 80)
    print("区块索引范围验证")
    print("=" * 80)

    offset = 0
    errors = []

    for start, end, name in BLOCK_RANGES:
        if start != offset:
            errors.append(f"{name} 起始索引错误: expected {offset}, got {start}")
            print(f"❌ [{offset:4d}?-{end:4d}] ({end-offset:3d}维): {name}")
        else:
            print(f"✅ [{start:4d}-{end:4d}] ({end-start:3d}维): {name}")

        if end <= start:
            errors.append(f"{name} 结束索引({end}) <= 起始索引({start})")

        offset = end

    if offset != OUTPUT_DIM:
        errors.append(f"总索引偏移({offset}) != OUTPUT_DIM({OUTPUT_DIM})")
        print(f"\n❌ 总偏移: {offset}, 预期: {OUTPUT_DIM}")
    else:
        print(f"\n✅ 总偏移正确: {offset}")

    return errors


def test_block_data_placement():
    """测试区块数据是否正确放置"""
    print("\n" + "=" * 80)
    print("区块数据放置测试")
    print("=" * 80)

    test_mod_response = {
        "game_state": {
            "current_hp": 50,
            "max_hp": 70,
            "gold": 100,
            "combat_state": {
                "player": {
                    "energy": 3,
                    "max_energy": 3,
                    "current_hp": 50,
                    "max_hp": 70,
                    "block": 10,
                },
                "hand": [
                    {
                        "id": "Strike_G",
                        "name": "打击",
                        "cost": 1,
                        "type": "ATTACK",
                        "is_playable": True,
                        "has_target": True,
                    }
                ],
                "draw_pile": [
                    {
                        "id": "Defend_G",
                        "name": "防御",
                        "cost": 1,
                        "type": "SKILL",
                        "is_playable": False,
                    }
                ],
                "discard_pile": [],
                "exhaust_pile": [],
                "monsters": [],
                "turn": 1,
                "cards_discarded_this_turn": 0,
                "times_damaged": 0,
            },
            "relics": [{"id": "Burning Blood"}],
            "potions": [],
            "screen_state": {
                "options": []
            },
            "floor": 1,
            "act": 1,
            "room_phase": "COMBAT",
        },
        "available_commands": ["play", "end"],
        "ready_for_command": True,
        "in_game": True,
    }

    result = encode(test_mod_response)

    # 验证区块1（玩家核心）
    block1 = result[0:BLOCK1_DIM]
    if block1[0] != 0.714:  # 50/70 ≈ 0.714
        print(f"⚠️  区块1 HP比例: {block1[0]:.4f} (预期 ~0.714)")

    # 验证区块2（手牌）
    block2_start = BLOCK1_DIM
    block2_end = BLOCK1_DIM + BLOCK2_DIM
    block2 = result[block2_start:block2_end]
    if block2[0] != 1.0:  # Strike_G 应该在索引20
        print(f"⚠️  区块2 卡牌编码: {block2[0]:.4f} (预期 1.0)")

    # 验证区块8（遗物）
    block8_start = (
        BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM
        + BLOCK6_DIM + BLOCK7_DIM
    )
    block8_end = block8_start + BLOCK8_DIM
    block8 = result[block8_start:block8_end]
    if block8[3] != 1.0:  # Burning Blood 应该在索引3
        print(f"⚠️  区块8 遗物编码: {block8[3]:.4f} (预期 1.0)")

    print("✅ 区块数据放置检查完成")

    return True


def main():
    print("编码器索引拼接逻辑验证")
    print()

    all_errors = []

    # 测试1: 区块维度
    errors = test_block_dimensions()
    all_errors.extend(errors)

    # 测试2: encode() 函数
    if not test_encode_function():
        all_errors.append("encode() 函数测试失败")

    # 测试3: 区块索引范围
    errors = test_block_ranges()
    all_errors.extend(errors)

    # 测试4: 数据放置
    test_block_data_placement()

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    if not all_errors:
        print("✅ 所有测试通过")
        return 0
    else:
        print(f"❌ 发现 {len(all_errors)} 个错误:")
        for error in all_errors:
            print(f"  - {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
