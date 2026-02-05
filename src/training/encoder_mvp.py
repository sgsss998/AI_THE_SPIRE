#!/usr/bin/env python3
"""
MVP 状态编码器：把 Mod 日志一帧转成 31 维向量 s

严格按 docs/planning_and_logs/MVP_s向量_实施计划.md 第二节映射表实现。
不依赖 encoder_utils、power_parser、encoder_ids.yaml。
"""
import numpy as np
from typing import Dict, Any


OUTPUT_DIM = 31


def encode(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    把 Mod 一帧的 JSON 转成 31 维向量 s。

    Args:
        mod_response: Mod 返回的整帧，含 game_state、available_commands 等。

    Returns:
        shape=(31,), dtype=float32
    """
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state")
    cmds = mod_response.get("available_commands") or []
    s = np.zeros(31, dtype=np.float32)

    # 0-4: 全局
    s[0] = min(gs.get("floor", 0), 15) / 15
    s[1] = min(gs.get("act", 1), 3) / 3
    s[2] = min(gs.get("gold", 0), 999) / 999
    player = ((cs or {}).get("player") or {})
    cur_hp = player.get("current_hp", gs.get("current_hp", 0))
    max_hp = max(player.get("max_hp", gs.get("max_hp", 70)), 1)
    s[3] = min(cur_hp, max_hp) / max_hp
    s[4] = min(max_hp, 999) / 999

    # 5-8: room_phase one-hot
    rp = gs.get("room_phase", "")
    for i, v in enumerate(["EVENT", "COMBAT", "COMPLETE", "INCOMPLETE"]):
        s[5 + i] = 1.0 if rp == v else 0.0

    # 9-19: screen_type one-hot
    st = gs.get("screen_type", "")
    for i, v in enumerate(
        [
            "EVENT",
            "MAP",
            "NONE",
            "COMBAT_REWARD",
            "CARD_REWARD",
            "SHOP_ROOM",
            "SHOP_SCREEN",
            "GRID",
            "REST",
            "CHEST",
            "HAND_SELECT",
        ]
    ):
        s[9 + i] = 1.0 if st == v else 0.0

    # 20-22: 可用命令
    s[20] = 1.0 if ("play" in cmds or "end" in cmds) else 0.0
    s[21] = 1.0 if "choose" in cmds else 0.0
    s[22] = 1.0 if "proceed" in cmds else 0.0

    # 23-29: 战斗（无 combat_state 则全 0）
    if cs:
        s[23] = min((cs.get("player") or {}).get("energy", 0), 10) / 10
        s[24] = min((cs.get("player") or {}).get("block", 0), 99) / 99
        s[25] = min(len(cs.get("hand") or []), 10) / 10
        s[26] = min(len(cs.get("draw_pile") or []), 80) / 80
        s[27] = min(len(cs.get("discard_pile") or []), 80) / 80
        monsters = [m for m in (cs.get("monsters") or []) if not m.get("is_gone")]
        s[28] = min(len(monsters), 6) / 6
        total_cur = sum(m.get("current_hp", 0) for m in monsters)
        total_max = sum(m.get("max_hp", 1) for m in monsters)
        s[29] = total_cur / max(1, total_max)

    # 30: choice_list
    cl = gs.get("choice_list") or []
    s[30] = min(len(cl), 60) / 60

    return s


def get_output_dim() -> int:
    """返回 31"""
    return OUTPUT_DIM
