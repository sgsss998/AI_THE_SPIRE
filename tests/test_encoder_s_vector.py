#!/usr/bin/env python3
"""
S 向量编码器单元测试

验证 10 区块 ~2900 维编码器与 Mod 日志格式兼容。
"""
import sys
from pathlib import Path

# 项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from src.training.encoder import encode, get_output_dim, OUTPUT_DIM, StateEncoder


def test_output_dim():
    """验证输出维度为 2900"""
    assert get_output_dim() == 2900, f"Expected 2900, got {get_output_dim()}"
    assert OUTPUT_DIM == 2900, f"Expected 2900, got {OUTPUT_DIM}"


def test_encode_empty():
    """空响应应返回全零向量（除区块1、8、9、10可能有默认值）"""
    empty = {}
    s = encode(empty)
    assert s.shape == (2900,), f"Expected shape (2900,), got {s.shape}"
    assert s.dtype == np.float32


def test_encode_minimal_combat():
    """最小战斗状态"""
    mod_response = {
        "game_state": {
            "act": 1,
            "floor": 5,
            "gold": 100,
            "class": "THE_SILENT",
            "combat_state": {
                "turn": 1,
                "hand": [
                    {"id": "Strike_G", "cost": 1, "is_playable": True, "has_target": True},
                ],
                "draw_pile": [],
                "discard_pile": [],
                "exhaust_pile": [],
                "player": {
                    "energy": 3,
                    "current_hp": 70,
                    "max_hp": 70,
                    "block": 0,
                    "powers": [{"id": "Strength", "amount": 2}],
                },
                "monsters": [
                    {
                        "id": "Cultist",
                        "current_hp": 50,
                        "max_hp": 50,
                        "block": 0,
                        "intent": "ATTACK",
                        "move_adjusted_damage": 6,
                        "move_hits": 1,
                        "is_gone": False,
                        "half_dead": False,
                        "powers": [],
                    },
                ],
            },
            "relics": [{"id": "Ring of the Snake"}],
            "potions": [{"id": "AttackPotion", "can_use": True, "can_discard": True, "requires_target": True}],
        },
        "available_commands": ["play", "end", "potion"],
    }
    s = encode(mod_response)
    assert s.shape == (2900,)
    assert s[0] > 0  # HP ratio
    assert s[9] == 1.0  # Silent one-hot
    assert s[14] == 1.0  # Act 1
    assert np.any(s[50:50 + 271] > 0)  # 手牌 multi-hot 有值
    assert np.any(s[1650:1650 + 600] > 0)  # 怪物区块有值
    assert np.any(s[2250:2250 + 200] > 0)  # 遗物区块有值


def test_state_encoder_class():
    """StateEncoder 类接口"""
    enc = StateEncoder(mode="extended")
    assert enc.get_output_dim() == 2900
    s = enc.encode_state(None)
    assert s.shape == (2900,)
    assert np.all(s == 0)


if __name__ == "__main__":
    test_output_dim()
    print("test_output_dim OK")
    test_encode_empty()
    print("test_encode_empty OK")
    test_encode_minimal_combat()
    print("test_encode_minimal_combat OK")
    test_state_encoder_class()
    print("test_state_encoder_class OK")
    print("All tests passed.")
