#!/usr/bin/env python3
"""
状态编码器 V2：把 Mod 日志里的 state 转成 723 维向量 s

目前只实现了前 218 维：
- s[0]~s[17]：玩家核心 18 维
- s[18]~s[217]：手牌 multi-hot 200 维（multi-hot=多热编码，每张卡一个位置）
- s[218]~s[722]：先填 0
"""
import numpy as np
from typing import Dict, Any, List

from src.training.encoder_utils import card_id_to_index
from src.training.power_parser import (
    parse_strength,
    parse_dexterity,
    parse_weak,
    parse_vulnerable,
    parse_frail,
    parse_focus,
)

# 归一化用的最大值
MAX_HP = 999
MAX_BLOCK = 50
MAX_ENERGY = 10
MAX_GOLD = 999
MAX_POWER = 30
MAX_DEBUFF = 10
MAX_HAND = 10
MAX_DRAW = 50
MAX_DISCARD = 50
MAX_EXHAUST = 30
MAX_CARDS_DISCARDED = 10
MAX_TIMES_DAMAGED = 50

OUTPUT_DIM = 723


def _clamp_norm(val: float, max_val: float) -> float:
    """把数压到 0~1：val/max_val，max_val=0 时返回 0"""
    if max_val <= 0:
        return 0.0
    return float(np.clip(val / max_val, 0.0, 1.0))


def _encode_block1_player_core(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 1：玩家核心，s[0]~s[17]，18 维

    s[0]  当前血量比例 hp_ratio
    s[1]  最大血量 max_hp_norm
    s[2]  格挡 block_norm
    s[3]  当前能量 energy_norm
    s[4]  最大能量 max_energy_norm
    s[5]  金币 gold_norm
    s[6]  力量 strength_norm（从 powers 解析）
    s[7]  敏捷 dexterity_norm
    s[8]  虚弱 weak_norm
    s[9]  易伤 vulnerable_norm
    s[10] 脆弱 frail_norm
    s[11] 集中 focus_norm（缺陷用）
    s[12] 手牌数量 hand_count_norm
    s[13] 抽牌堆数量 draw_count_norm
    s[14] 弃牌堆数量 discard_count_norm
    s[15] 消耗堆数量 exhaust_count_norm
    s[16] 本回合已弃牌数 cards_discarded_norm
    s[17] 本回合已受伤次数 times_damaged_norm
    """
    out = np.zeros(18, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    hand = cs.get("hand") or []
    draw_pile = cs.get("draw_pile") or []
    discard_pile = cs.get("discard_pile") or []
    exhaust_pile = cs.get("exhaust_pile") or []

    # 血量：战斗时用 player，非战斗用 game_state
    current_hp = player.get("current_hp", gs.get("current_hp", 0))
    max_hp = max(player.get("max_hp", gs.get("max_hp", 1)), 1)
    out[0] = _clamp_norm(current_hp, max_hp)
    out[1] = _clamp_norm(min(gs.get("max_hp", player.get("max_hp", 70)), MAX_HP), MAX_HP)
    out[2] = _clamp_norm(min(player.get("block", 0), MAX_BLOCK), MAX_BLOCK)
    out[3] = _clamp_norm(min(player.get("energy", 0), MAX_ENERGY), MAX_ENERGY)
    max_energy = 3  # 暂时写死，后面可从遗物推
    out[4] = _clamp_norm(min(max_energy, MAX_ENERGY), MAX_ENERGY)
    out[5] = _clamp_norm(min(gs.get("gold", 0), MAX_GOLD), MAX_GOLD)

    powers = player.get("powers") or []
    out[6] = _clamp_norm(min(parse_strength(powers), MAX_POWER), MAX_POWER)
    out[7] = _clamp_norm(min(parse_dexterity(powers), MAX_POWER), MAX_POWER)
    out[8] = _clamp_norm(min(parse_weak(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[9] = _clamp_norm(min(parse_vulnerable(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[10] = _clamp_norm(min(parse_frail(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[11] = _clamp_norm(min(parse_focus(powers), MAX_DEBUFF), MAX_DEBUFF)

    out[12] = _clamp_norm(min(len(hand), MAX_HAND), MAX_HAND)
    out[13] = _clamp_norm(min(len(draw_pile), MAX_DRAW), MAX_DRAW)
    out[14] = _clamp_norm(min(len(discard_pile), MAX_DISCARD), MAX_DISCARD)
    out[15] = _clamp_norm(min(len(exhaust_pile), MAX_EXHAUST), MAX_EXHAUST)
    out[16] = _clamp_norm(
        min(cs.get("cards_discarded_this_turn", 0), MAX_CARDS_DISCARDED),
        MAX_CARDS_DISCARDED,
    )
    out[17] = _clamp_norm(
        min(cs.get("times_damaged", 0), MAX_TIMES_DAMAGED),
        MAX_TIMES_DAMAGED,
    )
    return out


def _encode_block2a_hand_multihot(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 2a：手牌 multi-hot，s[18]~s[217]，200 维

    每张手牌按 id 查表得到编号 k，s[18+k] 加 1；同一种卡多张就多加
    """
    out = np.zeros(200, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    hand: List[Dict] = cs.get("hand") or []
    for card in hand:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < 200:
            out[idx] += 1
    return out


def encode(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    把 Mod 一帧的 JSON 转成 723 维向量 s

    现在只填了 s[0]~s[217]，后面全 0。

    mod_response：Mod 返回的整帧，里面有 game_state、combat_state
    返回：shape=(723,)，dtype=float32
    """
    s = np.zeros(OUTPUT_DIM, dtype=np.float32)
    b1 = _encode_block1_player_core(mod_response)
    b2a = _encode_block2a_hand_multihot(mod_response)
    s[0:18] = b1
    s[18:218] = b2a
    return s


def get_output_dim() -> int:
    """返回 723"""
    return OUTPUT_DIM
