#!/usr/bin/env python3
"""
测试 encoder_v2：Mod 日志 → 1840 维 s 向量

验证与 Mod 日志数据互通：字段路径、缺失处理、非战斗帧。
"""
import numpy as np
import pytest

from src.training.encoder_v2 import encode, get_output_dim, OUTPUT_DIM


def test_output_dim():
    """输出维度为 1840"""
    assert get_output_dim() == 1840
    assert OUTPUT_DIM == 1840


def test_encode_shape():
    """encode 返回 shape=(1840,)"""
    mod_response = {"game_state": {}, "available_commands": []}
    s = encode(mod_response)
    assert s.shape == (1840,)
    assert s.dtype == np.float32


def test_encode_empty_mod_response():
    """空 Mod 响应：全部默认值，无异常"""
    mod_response = {}
    s = encode(mod_response)
    assert s.shape == (1840,)
    assert np.all(np.isfinite(s))
    assert np.all(s >= 0) and np.all(s <= 1)


def test_encode_combat_frame():
    """战斗帧：区块 1-10 有数据"""
    mod_response = {
        "game_state": {
            "floor": 5,
            "act": 1,
            "room_phase": "COMBAT",
            "gold": 100,
            "relics": [{"id": "Ring of the Snake"}],
            "potions": [{"id": "Fire Potion", "can_use": True, "can_discard": False, "requires_target": True}],
            "combat_state": {
                "hand": [
                    {"id": "Strike_G", "cost": 1, "type": "ATTACK", "is_playable": True, "has_target": False, "upgrades": 0},
                    {"id": "Defend_G", "cost": 1, "type": "SKILL", "is_playable": True, "has_target": False, "upgrades": 0},
                ],
                "draw_pile": [{"id": "Neutralize", "type": "ATTACK"}],
                "discard_pile": [],
                "exhaust_pile": [],
                "monsters": [
                    {
                        "id": "Louse",
                        "current_hp": 10,
                        "max_hp": 12,
                        "block": 0,
                        "intent": "ATTACK",
                        "move_adjusted_damage": 6,
                        "move_hits": 1,
                        "is_gone": False,
                        "half_dead": False,
                        "powers": [],
                    }
                ],
                "player": {
                    "energy": 3,
                    "current_hp": 65,
                    "max_hp": 70,
                    "block": 5,
                    "powers": [],
                },
                "turn": 1,
                "cards_discarded_this_turn": 0,
                "times_damaged": 0,
            },
        },
        "available_commands": ["play", "end"],
    }
    s = encode(mod_response)
    assert s.shape == (1840,)

    # 区块 1：玩家核心
    assert 0 < s[0] < 1  # hp_ratio
    assert s[3] > 0  # energy
    assert s[12] > 0  # hand_count

    # 区块 2：手牌 multi-hot 应有非零（Strike_G, Defend_G）
    hand_multi = s[20:291]
    assert np.sum(hand_multi) >= 2

    # 区块 8：遗物应有 Ring of the Snake
    relic_multi = s[1552:1732]
    assert np.sum(relic_multi) >= 1

    # 区块 10：room_phase COMBAT
    assert s[1801] == 1.0  # room_COMBAT
    assert s[1810] == 1.0  # available_play


def test_encode_non_combat_frame():
    """非战斗帧：区块 2-9 填 0，区块 1/10 有数据"""
    mod_response = {
        "game_state": {
            "floor": 3,
            "act": 1,
            "room_phase": "MAP",
            "gold": 250,
            "current_hp": 60,
            "max_hp": 70,
        },
        "available_commands": ["choose", "proceed"],
    }
    s = encode(mod_response)
    assert s.shape == (1840,)

    # 区块 1：hp, gold 有值
    assert s[0] > 0  # hp_ratio
    assert s[5] > 0  # gold_norm
    assert s[3] == 0  # energy（非战斗）
    assert s[12] == 0  # hand_count（非战斗）

    # 区块 2-7：全 0
    assert np.all(s[20:1552] == 0)

    # 区块 8-9：遗物/药水可能为 0（无数据）
    # 区块 10：room MAP（s[1797]+6 = s[1803]）
    assert s[1803] == 1.0  # room_MAP
    assert s[1812] == 1.0  # available_choose


def test_encode_missing_fields():
    """缺失字段不抛异常，用默认值"""
    mod_response = {
        "game_state": {
            "combat_state": {
                "hand": [{"id": "Strike_G"}],  # 仅 id，其他缺失
                "player": {},
                "monsters": [],
            }
        },
    }
    s = encode(mod_response)
    assert s.shape == (1840,)
    assert np.all(np.isfinite(s))
