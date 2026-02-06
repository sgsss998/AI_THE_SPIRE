#!/usr/bin/env python3
"""
状态编码器 V2 - 静默专用：把 Mod 日志里的 state 转成 S 向量

与 Mod 日志数据互通：直接读取 game_state、combat_state 的字段路径，
缺失字段用默认值，非战斗时区块 2-7 填 0。

静默猎手专用：固定 A20 难度 + 静默职业，只拿猎人职业牌

10 区块结构 V2 - 静默专用（总计 ~3002 维）：
- s[0]~s[45]：玩家核心 46 维（删除角色/难度/Orbs编码）
- s[46]~s[423]：手牌 378 维（136 multi-hot + 21×10 + 统计）
- s[424]~s[751]：抽牌堆 328 维（136 multi-hot + 统计）
- s[752]~s[1079]：弃牌堆 328 维（136 multi-hot + 统计）
- s[1080]~s[1367]：消耗堆 228 维（136 multi-hot + 统计）
- s[1368]~s[1407]：玩家 Powers 100 维
- s[1408]~s[2025]：怪物 618 维（每怪103维×6）
- s[2026]~s[2225]：遗物 200 维
- s[2226]~s[2425]：药水 200 维
- s[2426]~s[2925]：全局 500 维

静默专用改进：
1. 删除角色编码（固定静默）
2. 删除难度编码（固定A20）
3. 删除Orbs编码（静默不用）
4. 精简卡牌池（只保留静默+诅咒+状态+无色，136张）
5. 简化升级逻辑（静默无无限升级牌）
6. 调整参数上限（MAX_HP=200, MAX_BLOCK=999, MAX_ENERGY=20, MAX_POWER=99）
"""
import numpy as np
from typing import Dict, Any, List

from src.training.encoder_utils import (
    card_id_to_index,
    relic_id_to_index,
    potion_id_to_index,
    power_id_to_index,
    intent_to_index,
    monster_id_to_index,
    event_id_to_index,
    room_subtype_to_index,
    card_type_to_index,
    CARD_DIM,
    RELIC_DIM,
    POTION_DIM,
    POWER_DIM,
    INTENT_DIM,
    MONSTER_DIM,
    EVENT_DIM,
    ROOM_SUBTYPE_DIM,
    CARD_TYPE_DIM,
)
from src.training.power_parser import (
    parse_strength,
    parse_dexterity,
    parse_weak,
    parse_vulnerable,
    parse_frail,
    parse_focus,
    parse_poison,
    parse_curl_up,
    # 新增 V2
    parse_ritual,
    parse_artifact,
    parse_regen,
    parse_thorns,
    parse_plated_armor,
    parse_intangible,
    parse_buffer,
    parse_evolve,
    parse_combust,
    parse_juggernaut,
    parse_after_image,
    parse_barricade,
    parse_corruption,
    parse_berserk,
    parse_metallicize,
)

# 归一化用的最大值（与 Mod 日志数值范围兼容）
# 静默猎手专用调整
MAX_HP = 200          # 静默血量较低，降低上限
MAX_BLOCK = 999        # 静默可以叠很高的护甲
MAX_ENERGY = 20        # 预留更多能量空间
MAX_GOLD = 999
MAX_POWER = 99         # 提高Power上限
MAX_DEBUFF = 15
MAX_HAND = 10
MAX_DRAW = 80
MAX_DISCARD = 80
MAX_EXHAUST = 50
MAX_CARDS_DISCARDED = 15
MAX_TIMES_DAMAGED = 50
MAX_TURN = 50
MAX_ORB_SLOTS = 10
MAX_DAMAGE = 99

# 区块维度 V2 - 静默专用
# 区块1: 简化为 46 维（删除角色/难度/Orbs编码，静默不用）
BLOCK1_DIM = 46
BLOCK2_DIM = 384  # 手牌（136 multi-hot + 21×10 牌属性 + 统计）
BLOCK3_DIM = 334  # 抽牌堆（136 multi-hot + 更多统计）
BLOCK4_DIM = 334  # 弃牌堆（136 multi-hot + 更多统计）
BLOCK5_DIM = 234  # 消耗堆（136 multi-hot + 更多统计）
BLOCK6_DIM = 100  # 玩家 Powers
BLOCK7_DIM = 618  # 怪物（扩展：每怪103维×6）
BLOCK8_DIM = 200  # 遗物
BLOCK9_DIM = 200  # 药水
BLOCK10_DIM = 500  # 全局（大幅扩展：地图/事件/房间细分）

OUTPUT_DIM = (
    BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM
    + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM + BLOCK9_DIM + BLOCK10_DIM
)

# 卡牌类型 → 标量
CARD_TYPE_MAP = {
    "attack": 0.2,
    "skill": 0.4,
    "power": 0.6,
    "status": 0.0,
    "curse": 0.0,
}


def _clamp_norm(val: float, max_val: float) -> float:
    """把数压到 0~1：val/max_val，max_val=0 时返回 0"""
    if max_val <= 0:
        return 0.0
    return float(np.clip(val / max_val, 0.0, 1.0))


def _encode_block1_player_core(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 1：玩家核心 V2 - 静默专用，46 维。

    新结构（删除角色/难度/Orbs编码）：
    [0-7]   HP/能量/护甲/金币（简化冗余）
    [8-11]  章节 one-hot (4维)
    [12-18] 房间阶段 one-hot (7维)
    [19-23] Buff/Debuff (5维)
    [24]    回合
    [25-30] 本回合统计 + 牌堆数量 (6维)
    [31-33] 钥匙状态（红/蓝/绿宝石）
    [34]    最大能量
    [35-45] 预留 (11维，用于未来扩展)
    """
    out = np.zeros(BLOCK1_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    hand = cs.get("hand") or []
    draw_pile = cs.get("draw_pile") or []
    discard_pile = cs.get("discard_pile") or []
    exhaust_pile = cs.get("exhaust_pile") or []
    deck = gs.get("deck") or []

    # [0-7] HP/能量/护甲/金币（简化冗余）
    current_hp = player.get("current_hp", gs.get("current_hp", 0))
    max_hp = max(player.get("max_hp", gs.get("max_hp", 1)), 1)
    out[0] = _clamp_norm(current_hp, max_hp)
    out[1] = _clamp_norm(min(max_hp, MAX_HP), MAX_HP)
    out[2] = _clamp_norm(min(player.get("energy", 0), MAX_ENERGY), MAX_ENERGY)
    out[3] = _clamp_norm(min(3, MAX_ENERGY), MAX_ENERGY)  # 基础能量
    out[4] = _clamp_norm(min(player.get("block", 0), MAX_BLOCK), MAX_BLOCK)
    out[5] = min(player.get("block", 0) / 100.0, 1.0)
    out[6] = _clamp_norm(min(gs.get("gold", 0), MAX_GOLD), MAX_GOLD)
    out[7] = min(gs.get("gold", 0) / 999.0, 1.0)

    # [8-11] 章节 one-hot 4 维
    act = gs.get("act", 1)
    if act == 1:
        out[8] = 1.0
    elif act == 2:
        out[9] = 1.0
    elif act == 3:
        out[10] = 1.0
    else:
        out[11] = 1.0

    # [12-18] 房间阶段 one-hot 7 维
    phase = (gs.get("room_phase") or gs.get("screen_type") or "").upper()
    phase_map = {
        "COMBAT": 12, "EVENT": 13, "MAP": 14, "SHOP": 15,
        "REST": 16, "BOSS": 17, "NONE": 18,
    }
    idx = phase_map.get(phase, 18)
    out[idx] = 1.0

    # [19-23] Buff/Debuff 计数 5 维
    powers = player.get("powers") or []
    out[19] = _clamp_norm(min(parse_strength(powers), MAX_POWER), MAX_POWER)
    out[20] = _clamp_norm(min(parse_dexterity(powers), 30), 30)
    out[21] = _clamp_norm(min(parse_weak(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[22] = _clamp_norm(min(parse_vulnerable(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[23] = _clamp_norm(min(parse_frail(powers), MAX_DEBUFF), MAX_DEBUFF)

    # [24] 回合
    out[24] = _clamp_norm(min(cs.get("turn", 0), MAX_TURN), MAX_TURN)

    # [25-30] 本回合统计 + 牌堆数量 (6维)
    out[25] = _clamp_norm(
        min(cs.get("cards_discarded_this_turn", 0), MAX_CARDS_DISCARDED),
        MAX_CARDS_DISCARDED,
    )
    out[26] = _clamp_norm(
        min(cs.get("times_damaged", 0), MAX_TIMES_DAMAGED),
        MAX_TIMES_DAMAGED,
    )
    out[27] = _clamp_norm(min(len(hand), MAX_HAND), MAX_HAND)
    out[28] = _clamp_norm(min(len(draw_pile), MAX_DRAW), MAX_DRAW)
    out[29] = _clamp_norm(min(len(discard_pile), MAX_DISCARD), MAX_DISCARD)
    out[30] = _clamp_norm(min(len(exhaust_pile), MAX_EXHAUST), MAX_EXHAUST)

    # [31-33] 钥匙状态（红/蓝/绿宝石）
    relics = gs.get("relics") or []
    relic_ids = [r.get("id", r.get("name", "")).lower() for r in relics]
    out[31] = 1.0 if any("ruby" in rid for rid in relic_ids) else 0.0  # 红宝石
    out[32] = 1.0 if any("sapphire" in rid or "blue" in rid for rid in relic_ids) else 0.0  # 蓝宝石
    out[33] = 1.0 if any("emerald" in rid or "green" in rid for rid in relic_ids) else 0.0  # 绿宝石

    # [34] 最大能量
    max_energy = player.get("max_energy", 3)
    out[34] = _clamp_norm(min(max_energy, 20), 20)  # MAX_ENERGY=20

    # [35-45] 预留 (11维)
    # 未来可扩展：更多状态信息

    return out


def _encode_block2_hand(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 2：手牌 V2 - 静默专用，384 维。

    新结构：
    [0-135]     136维 卡牌 multi-hot（静默专用）
    [136-345]   210维 每张牌21属性×10张
                每张牌21维：
                - cost (1)
                - is_playable (1)
                - has_target (1)
                - is_ethereal (1) 虚无
                - is_exhaust (1) 消耗
                - is_stripped (1) 被夺
                - cost_for_turn (1) 本回合费用
                - type one-hot (5) 攻击/技能/能力/状态/诅咒
                - is_upgraded (1) 是否升级（静默无无限升级牌）
                - upgrade_times (1) 升级次数（简化）
                - reserved (3)
    [346-355]   10维 统计
    [356-383]   28维 预留
    """
    out = np.zeros(BLOCK2_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    hand: List[Dict] = cs.get("hand") or []

    # [0-135] 卡牌 multi-hot
    for card in hand:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    # [136-345] 每张牌21属性×10张
    for i in range(10):
        base = 136 + i * 21
        if i < len(hand):
            c = hand[i]
            # 基础属性
            cost = max(c.get("cost", 0), 0)
            out[base + 0] = _clamp_norm(min(cost, 5), 5)
            out[base + 1] = 1.0 if c.get("is_playable", False) else 0.0
            out[base + 2] = 1.0 if c.get("has_target", False) else 0.0

            # 新增属性
            out[base + 3] = 1.0 if c.get("ethereal", False) else 0.0  # 虚无
            out[base + 4] = 1.0 if c.get("exhaust", False) or c.get("exhausts", False) else 0.0  # 消耗
            out[base + 5] = 1.0 if c.get("is_stripped", False) else 0.0  # 被夺

            # cost_for_turn - 本回合实际费用（可能有费用变化）
            cost_for_turn = c.get("cost_for_turn", cost)
            out[base + 6] = _clamp_norm(min(cost_for_turn, 5), 5)

            # 类型 one-hot (5维)
            card_type = (c.get("type") or "").lower()
            type_idx = card_type_to_index(card_type)
            if 0 <= type_idx < 5:
                out[base + 7 + type_idx] = 1.0

            # 升级状态（静默无无限升级牌，简化逻辑）
            upgrades = c.get("upgrades", 0) or 0
            is_status_curse = card_type in ("status", "curse")

            if is_status_curse:
                # 状态/诅咒牌永远不可升级
                out[base + 12] = 0.0
                out[base + 13] = 0.0
            else:
                # 普通牌：最多升级1次
                out[base + 12] = 1.0 if upgrades > 0 else 0.0
                out[base + 13] = 1.0 if upgrades > 0 else 0.0

            # [14-16] 预留（11-16维预留）
        else:
            # 超过10张牌的部分留空
            pass

    # [346-355] 手牌统计
    base = 346
    out[base + 0] = min(len(hand), 10) / 10.0
    zero_cost = sum(1 for c in hand if (c.get("cost") or 0) == 0)
    out[base + 1] = min(zero_cost, 10) / 10.0
    playable = sum(1 for c in hand if c.get("is_playable", False))
    out[base + 2] = min(playable, 10) / 10.0
    attack_cnt = sum(1 for c in hand if (c.get("type") or "").lower() == "attack")
    out[base + 3] = min(attack_cnt, 10) / 10.0
    skill_cnt = sum(1 for c in hand if (c.get("type") or "").lower() == "skill")
    out[base + 4] = min(skill_cnt, 10) / 10.0
    power_cnt = sum(1 for c in hand if (c.get("type") or "").lower() == "power")
    out[base + 5] = min(power_cnt, 10) / 10.0
    status_curse_cnt = sum(1 for c in hand if (c.get("type") or "").lower() in ("status", "curse"))
    out[base + 6] = min(status_curse_cnt, 10) / 10.0
    upgraded_cnt = sum(1 for c in hand if c.get("upgrades", 0) > 0)
    out[base + 7] = min(upgraded_cnt, 10) / 10.0
    total_cost = sum(max(c.get("cost", 0), 0) for c in hand)
    out[base + 8] = _clamp_norm(min(total_cost, 20), 20)
    out[base + 9] = 0.0  # 预留

    # [356-383] 预留 (28维)
    # 未来可扩展：手牌位置信息、连击信息等

    return out


def _count_type_ratio(pile: List[Dict], card_type: str) -> float:
    if not pile:
        return 0.0
    count = sum(1 for c in pile if (c.get("type") or "").lower() == card_type)
    return count / len(pile)


def _count_status_curse_ratio(pile: List[Dict]) -> float:
    if not pile:
        return 0.0
    count = sum(
        1 for c in pile
        if (c.get("type") or "").lower() in ("status", "curse")
    )
    return count / len(pile)


def _encode_block3_draw_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 3：抽牌堆 V2 - 静默专用，334 维。

    新结构：
    [0-135]     136维 卡牌 multi-hot（静默专用）
    [136-205]   70维 详细统计
    [206-333]   128维 预留
    """
    out = np.zeros(BLOCK3_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    draw_pile = cs.get("draw_pile") or []

    # [0-135] 卡牌 multi-hot
    for card in draw_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    # [136-218] 详细统计
    base = 136
    pile_size = len(draw_pile)

    # 基础统计
    out[base + 0] = _clamp_norm(min(pile_size, 80), 80)
    zero_cost = sum(1 for c in draw_pile if (c.get("cost") or 0) == 0)
    out[base + 1] = _clamp_norm(min(zero_cost, 80), 80)
    out[base + 2] = zero_cost / max(pile_size, 1)  # 0费占比

    # 类型数量和占比
    attack_cnt = sum(1 for c in draw_pile if (c.get("type") or "").lower() == "attack")
    skill_cnt = sum(1 for c in draw_pile if (c.get("type") or "").lower() == "skill")
    power_cnt = sum(1 for c in draw_pile if (c.get("type") or "").lower() == "power")
    status_curse_cnt = sum(1 for c in draw_pile if (c.get("type") or "").lower() in ("status", "curse"))

    out[base + 3] = _clamp_norm(min(attack_cnt, 80), 80)
    out[base + 4] = attack_cnt / max(pile_size, 1)
    out[base + 5] = _clamp_norm(min(skill_cnt, 80), 80)
    out[base + 6] = skill_cnt / max(pile_size, 1)
    out[base + 7] = _clamp_norm(min(power_cnt, 80), 80)
    out[base + 8] = power_cnt / max(pile_size, 1)
    out[base + 9] = _clamp_norm(min(status_curse_cnt, 80), 80)
    out[base + 10] = status_curse_cnt / max(pile_size, 1)

    # 升级牌统计
    upgraded_cnt = sum(1 for c in draw_pile if c.get("upgrades", 0) > 0)
    out[base + 11] = _clamp_norm(min(upgraded_cnt, 80), 80)
    out[base + 12] = upgraded_cnt / max(pile_size, 1)

    # 特殊属性牌统计
    ethereal_cnt = sum(1 for c in draw_pile if c.get("ethereal", False))
    exhaust_cnt = sum(1 for c in draw_pile if c.get("exhaust", False) or c.get("exhausts", False))
    out[base + 13] = _clamp_norm(min(ethereal_cnt, 80), 80)
    out[base + 14] = _clamp_norm(min(exhaust_cnt, 80), 80)

    # 费用统计
    costs = [c.get("cost", 0) for c in draw_pile if c.get("cost", 0) >= 0]
    if costs:
        avg_cost = sum(costs) / len(costs)
        total_cost = sum(costs)
        out[base + 15] = _clamp_norm(min(avg_cost, 5), 5)
        out[base + 16] = _clamp_norm(min(total_cost, 300), 300)
    else:
        out[base + 15] = 0.0
        out[base + 16] = 0.0

    # [17-69] 预留 (53维)
    # 未来可用于更复杂的统计

    return out


def _encode_block4_discard_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 4：弃牌堆 V2 - 静默专用，334 维。

    新结构：
    [0-135]     136维 卡牌 multi-hot（静默专用）
    [136-205]   70维 详细统计
    [206-333]   128维 预留
    """
    out = np.zeros(BLOCK4_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    discard_pile = cs.get("discard_pile") or []

    # [0-135] 卡牌 multi-hot
    for card in discard_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    # [136-218] 详细统计
    base = 136
    pile_size = len(discard_pile)

    # 基础统计
    out[base + 0] = _clamp_norm(min(pile_size, 80), 80)

    # 类型数量和占比
    attack_cnt = sum(1 for c in discard_pile if (c.get("type") or "").lower() == "attack")
    skill_cnt = sum(1 for c in discard_pile if (c.get("type") or "").lower() == "skill")
    power_cnt = sum(1 for c in discard_pile if (c.get("type") or "").lower() == "power")
    status_curse_cnt = sum(1 for c in discard_pile if (c.get("type") or "").lower() in ("status", "curse"))

    out[base + 1] = _clamp_norm(min(attack_cnt, 80), 80)
    out[base + 2] = attack_cnt / max(pile_size, 1)
    out[base + 3] = _clamp_norm(min(skill_cnt, 80), 80)
    out[base + 4] = skill_cnt / max(pile_size, 1)
    out[base + 5] = _clamp_norm(min(power_cnt, 80), 80)
    out[base + 6] = power_cnt / max(pile_size, 1)
    out[base + 7] = _clamp_norm(min(status_curse_cnt, 80), 80)
    out[base + 8] = status_curse_cnt / max(pile_size, 1)

    # 本回合弃牌数（弃牌堆特有）
    out[base + 9] = _clamp_norm(
        min(cs.get("cards_discarded_this_turn", 0), MAX_CARDS_DISCARDED),
        MAX_CARDS_DISCARDED,
    )

    # 升级牌统计
    upgraded_cnt = sum(1 for c in discard_pile if c.get("upgrades", 0) > 0)
    out[base + 10] = _clamp_norm(min(upgraded_cnt, 80), 80)
    out[base + 11] = upgraded_cnt / max(pile_size, 1)

    # 特殊属性牌统计
    ethereal_cnt = sum(1 for c in discard_pile if c.get("ethereal", False))
    exhaust_cnt = sum(1 for c in discard_pile if c.get("exhaust", False) or c.get("exhausts", False))
    out[base + 12] = _clamp_norm(min(ethereal_cnt, 80), 80)
    out[base + 13] = _clamp_norm(min(exhaust_cnt, 80), 80)

    # [14-69] 预留 (56维)

    return out


def _encode_block5_exhaust_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 5：消耗堆 V2 - 静默专用，234 维。

    新结构：
    [0-135]     136维 卡牌 multi-hot（静默专用）
    [136-185]   50维 详细统计
    [186-233]   48维 预留
    """
    out = np.zeros(BLOCK5_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    exhaust_pile = cs.get("exhaust_pile") or []

    # [0-135] 卡牌 multi-hot
    for card in exhaust_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    # [136-198] 详细统计
    base = 136
    pile_size = len(exhaust_pile)

    # 基础统计
    out[base + 0] = _clamp_norm(min(pile_size, 50), 50)

    # 类型数量和占比
    attack_cnt = sum(1 for c in exhaust_pile if (c.get("type") or "").lower() == "attack")
    skill_cnt = sum(1 for c in exhaust_pile if (c.get("type") or "").lower() == "skill")
    power_cnt = sum(1 for c in exhaust_pile if (c.get("type") or "").lower() == "power")
    status_curse_cnt = sum(1 for c in exhaust_pile if (c.get("type") or "").lower() in ("status", "curse"))

    out[base + 1] = _clamp_norm(min(attack_cnt, 50), 50)
    out[base + 2] = attack_cnt / max(pile_size, 1)
    out[base + 3] = _clamp_norm(min(skill_cnt, 50), 50)
    out[base + 4] = skill_cnt / max(pile_size, 1)
    out[base + 5] = _clamp_norm(min(power_cnt, 50), 50)
    out[base + 6] = power_cnt / max(pile_size, 1)
    out[base + 7] = _clamp_norm(min(status_curse_cnt, 50), 50)
    out[base + 8] = status_curse_cnt / max(pile_size, 1)

    # 升级牌统计（消耗堆中可能有升级的牌被消耗）
    upgraded_cnt = sum(1 for c in exhaust_pile if c.get("upgrades", 0) > 0)
    out[base + 9] = _clamp_norm(min(upgraded_cnt, 50), 50)
    out[base + 10] = upgraded_cnt / max(pile_size, 1)

    # [11-49] 预留 (39维)

    return out


def _encode_block6_player_powers(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 6：玩家 Powers 100 维"""
    out = np.zeros(BLOCK6_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    powers = player.get("powers") or []
    for p in powers:
        pid = p.get("id") or p.get("name") or ""
        idx = power_id_to_index(pid)
        if 0 <= idx < POWER_DIM:
            out[idx] += _clamp_norm(p.get("amount", 0), 10)
    return out


def _encode_block7_monsters(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 7：怪物 V2，618 维（6×103）。

    每个怪物 103 维新结构：
    [0-74]      Monster ID multi-hot (75维)
    [75]        HP比例
    [76]        护甲
    [77-79]     怪物类型 one-hot (3维：普通/精英/Boss) [新增]
    [80-82]     预留
    [83-95]     Intent one-hot (13维)
    [96]        预计伤害
    [97]        存活状态 (is_gone反向)
    [98]        半死状态 (half_dead)
    [99-100]    动作历史 (last_move, second_last_move)
    [101]       Strength
    [102]       Vulnerable
    [103]       Weak
    [104]       Poison (仅在基础维度内，103维时不含此)
                注：实际每怪103维，Poison等额外buff通过区块6编码
    """
    out = np.zeros(BLOCK7_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    monsters: List[Dict] = cs.get("monsters") or []

    # 判断怪物类型的辅助函数
    def get_monster_type(mon_id: str, mon: Dict) -> int:
        """返回怪物类型：0=普通, 1=精英, 2=Boss"""
        mid_lower = mon_id.lower()
        # 检查是否是Boss
        if any(boss in mid_lower for boss in ["slimeboss", "guardian", "hexaghost", "bronzeautomaton",
                                                "collector", "champ", "awakenedone", "timeeater",
                                                "donu", "deca", "heart", "corrupt", "spire"]):
            return 2
        # 检查是否是精英
        if any(elite in mid_lower for elite in ["gremlinnob", "lagavulin", "bookofstabbing",
                                                 "gremlinleader", "slaverboss", "gianthead",
                                                 "nemesis", "reptomancer"]):
            return 1
        # 通过标志判断
        if mon.get("is_boss", False):
            return 2
        if mon.get("is_elite", False):
            return 1
        return 0

    for m in range(6):
        base = m * 103  # 每怪103维
        if m >= len(monsters):
            continue
        mon = monsters[m]

        # [0-74] Monster ID multi-hot
        mid = mon.get("id") or mon.get("name") or ""
        midx = monster_id_to_index(mid)
        if 0 <= midx < MONSTER_DIM:
            out[base + midx] = 1.0

        # [75] HP比例
        out[base + 75] = _clamp_norm(
            mon.get("current_hp", 0),
            max(mon.get("max_hp", 1), 1),
        )

        # [76] 护甲
        out[base + 76] = _clamp_norm(min(mon.get("block", 0), MAX_BLOCK), MAX_BLOCK)

        # [77-79] 怪物类型 one-hot (3维：普通/精英/Boss) [新增]
        mon_type = get_monster_type(mid, mon)
        out[base + 77 + mon_type] = 1.0

        # [80-82] 预留

        # [83-95] Intent one-hot (13维)
        intent_str = mon.get("intent") or ""
        intent_idx = intent_to_index(intent_str)
        if 0 <= intent_idx < INTENT_DIM:
            out[base + 83 + intent_idx] = 1.0

        # [96] 预计伤害
        adj = mon.get("move_adjusted_damage", 0) or 0
        hits = mon.get("move_hits", 1) or 1
        dmg = max(0, adj * hits)
        out[base + 96] = _clamp_norm(min(dmg, MAX_DAMAGE), MAX_DAMAGE)

        # [97] 存活状态
        out[base + 97] = 0.0 if mon.get("is_gone", False) else 1.0

        # [98] 半死状态
        out[base + 98] = 1.0 if mon.get("half_dead", False) else 0.0

        # [99-100] 动作历史
        out[base + 99] = _clamp_norm(mon.get("last_move_id", 0) or 0, 100)
        out[base + 100] = _clamp_norm(mon.get("second_last_move_id", 0) or 0, 100)

        # [101-102] Buff/Debuff (简化版，更多buff通过区块6编码)
        mpowers = mon.get("powers") or []
        out[base + 101] = _clamp_norm(min(parse_strength(mpowers), 30), 30)
        out[base + 102] = _clamp_norm(min(parse_vulnerable(mpowers), MAX_DEBUFF), MAX_DEBUFF)
        # 注意：由于103维限制，Weak/Poison等已移除

    return out


def _encode_block8_relics(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 8：遗物 200 维（multi-hot 180 + 统计）"""
    out = np.zeros(BLOCK8_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    relics = gs.get("relics") or []
    for r in relics:
        rid = r.get("id") or r.get("name") or ""
        idx = relic_id_to_index(rid)
        if 0 <= idx < RELIC_DIM:
            out[idx] += 1
    out[180] = min(len(relics), 50) / 50.0
    return out


def _encode_block9_potions(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 9：药水 200 维（multi-hot 45 + 每槽 5×5 + 统计）"""
    out = np.zeros(BLOCK9_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    potions = gs.get("potions") or []
    for p in potions:
        pid = p.get("id") or p.get("name") or ""
        idx = potion_id_to_index(pid)
        if 0 <= idx < POTION_DIM:
            out[idx] += 1
    for i in range(5):
        base = 45 + i * 5
        if i < len(potions):
            pot = potions[i]
            out[base + 0] = 1.0 if pot.get("can_use", False) else 0.0
            out[base + 1] = 1.0 if pot.get("can_discard", False) else 0.0
            out[base + 2] = 1.0 if pot.get("requires_target", False) else 0.0
            out[base + 3] = 1.0
        else:
            out[base + 3] = 0.0
    out[70] = min(len(potions), 5) / 5.0
    usable = sum(1 for p in potions if p.get("can_use", False))
    out[71] = min(usable, 5) / 5.0
    return out


def _encode_block10_global(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 10：全局 V2，500 维。

    新结构：
    [0-22]      基础信息（楼层、章节、房间阶段、可用命令）
    [23-72]     事件ID one-hot (50维) [新增]
    [73-87]     房间细分类型 one-hot (15维) [新增]
    [88-112]    地图路径信息 (25维) [新增]
    [113-136]   更多buff/debuff状态 (37维) [新增]
    [150-499]   预留 (350维)
    """
    out = np.zeros(BLOCK10_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cmds = mod_response.get("available_commands") or []
    ss = gs.get("screen_state") or {}
    options = ss.get("options") or []

    # [0-22] 基础信息（保持原有）
    out[0] = _clamp_norm(min(gs.get("floor", 0), 60), 60)
    act = gs.get("act", 1)
    if act == 1:
        out[1] = 1.0
    elif act == 2:
        out[2] = 1.0
    elif act == 3:
        out[3] = 1.0
    else:
        out[4] = 1.0

    phase = (gs.get("room_phase") or gs.get("screen_type") or "").upper()
    phase_map = {
        "COMBAT": 5, "EVENT": 6, "MAP": 7, "SHOP": 8,
        "REST": 9, "BOSS": 10, "NONE": 11, "CARD_REWARD": 12,
    }
    idx = phase_map.get(phase, 11)
    out[idx] = 1.0

    out[13] = 1.0 if "play" in cmds else 0.0
    out[14] = 1.0 if "end" in cmds else 0.0
    out[15] = 1.0 if "choose" in cmds else 0.0
    out[16] = 1.0 if "proceed" in cmds else 0.0
    out[17] = 1.0 if "potion" in cmds else 0.0
    out[18] = 1.0 if "confirm" in cmds else 0.0
    out[19] = _clamp_norm(min(len(options), 60), 60)
    out[20] = min(len(cmds), 20) / 20.0
    out[21] = _clamp_norm(min(len(options), 60), 60)
    out[22] = 0.0  # 预留

    # [23-72] 事件ID one-hot (50维) [新增]
    # 从 screen_state 或 game_state 中获取当前事件
    event_id = ss.get("event_id") or gs.get("event_id") or ""
    if event_id:
        event_idx = event_id_to_index(event_id)
        if 0 <= event_idx < 50:
            out[23 + event_idx] = 1.0

    # [73-87] 房间细分类型 one-hot (15维) [新增]
    # 根据房间阶段和其他信息判断房间细分类型
    room_subtype = 13  # 默认未知
    if phase == "COMBAT":
        # 判断是否是精英或Boss
        monsters = gs.get("combat_state", {}).get("monsters") or []
        if any(m.get("is_boss", False) or "boss" in str(m.get("id", "")).lower() for m in monsters):
            room_subtype = 2  # Boss房
        elif any(m.get("is_elite", False) or any(e in str(m.get("id", "")).lower() for e in ["nob", "lagavulin", "book", "leader"]) for m in monsters):
            room_subtype = 1  # 精英房
        else:
            room_subtype = 0  # 普通怪物房
    elif phase == "REST":
        room_subtype = 3  # 普通休息室（可根据具体休息类型细分）
    elif phase == "SHOP":
        room_subtype = 7  # 商店
    elif phase == "EVENT":
        room_subtype = 8  # 事件房
    elif phase == "MAP":
        room_subtype = 12  # 地图

    if 0 <= room_subtype < 15:
        out[73 + room_subtype] = 1.0

    # [88-112] 地图路径信息 (25维) [新增]
    # 从 game_state 中获取地图信息（如果可用）
    map_data = gs.get("map") or gs.get("map_data") or {}
    out[88] = _clamp_norm(min(map_data.get("current_x", 0), 15), 15)  # 当前X坐标
    out[89] = _clamp_norm(min(map_data.get("current_y", 0), 15), 15)  # 当前Y坐标
    out[90] = _clamp_norm(min(map_data.get("visited_rooms", 0), 60), 60)  # 已访问房间数
    out[91] = _clamp_norm(min(map_data.get("connections", 0), 100), 100)  # 连接数
    # [92-112] 预留 (21维) - 未来可用于更复杂的地图信息

    # [113-136] 更多buff/debuff状态 (37维) [新增]
    # 这些是全局或特殊状态，不适合放在区块1或6
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    powers = player.get("powers") or []

    out[113] = _clamp_norm(min(parse_strength(powers), MAX_POWER), MAX_POWER)
    out[114] = _clamp_norm(min(parse_dexterity(powers), 30), 30)
    out[115] = _clamp_norm(min(parse_weak(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[116] = _clamp_norm(min(parse_vulnerable(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[117] = _clamp_norm(min(parse_frail(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[118] = _clamp_norm(min(parse_ritual(powers), 50), 50)
    out[119] = _clamp_norm(min(parse_artifact(powers), 20), 20)
    out[120] = _clamp_norm(min(parse_regen(powers), 30), 30)
    out[121] = _clamp_norm(min(parse_thorns(powers), 20), 20)
    out[122] = _clamp_norm(min(parse_plated_armor(powers), 50), 50)
    out[123] = _clamp_norm(min(parse_intangible(powers), 10), 10)
    out[124] = _clamp_norm(min(parse_buffer(powers), 10), 10)
    out[125] = _clamp_norm(min(parse_evolve(powers), 10), 10)
    out[126] = _clamp_norm(min(parse_combust(powers), 20), 20)
    out[127] = _clamp_norm(min(parse_juggernaut(powers), 20), 20)
    out[128] = _clamp_norm(min(parse_after_image(powers), 10), 10)
    out[129] = _clamp_norm(min(parse_corruption(powers), 1), 1)  # 腐化是bool
    out[136] = _clamp_norm(min(parse_barricade(powers), 1), 1)  # 路障是bool
    # [131-136] 预留 (19维) - 更多buff/debuff

    # [150-499] 预留 (350维)
    # 未来可扩展：
    # - 地图历史（访问路径）
    # - 事件选择历史
    # - 商店层级
    # - 更多全局状态

    return out


def encode(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    把 Mod 一帧的 JSON 转成 S 向量 V2

    与 Mod 日志互通：mod_response 为 Mod 返回的整帧，
    含 game_state、combat_state、available_commands 等。
    缺失 combat_state 时，区块 2-7 填 0。

    V2 变化：
    - 区块1: 50 → 58 维 (+8)
    - 区块2: 400 → 500 维 (+100)
    - 后续索引相应调整
    """
    s = np.zeros(OUTPUT_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    has_combat = bool(gs.get("combat_state"))

    b1 = _encode_block1_player_core(mod_response)
    s[0:BLOCK1_DIM] = b1

    if has_combat:
        b2 = _encode_block2_hand(mod_response)
        b3 = _encode_block3_draw_pile(mod_response)
        b4 = _encode_block4_discard_pile(mod_response)
        b5 = _encode_block5_exhaust_pile(mod_response)
        b6 = _encode_block6_player_powers(mod_response)
        b7 = _encode_block7_monsters(mod_response)
        # 新索引：区块1(58) + 区块2(500) + 区块3(400) + ...
        s[BLOCK1_DIM:BLOCK1_DIM + BLOCK2_DIM] = b2
        s[BLOCK1_DIM + BLOCK2_DIM:BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM] = b3
        s[BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM:BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM] = b4
        s[BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM:BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM] = b5
        s[BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM:BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM] = b6
        s[BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM:BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM] = b7

    b8 = _encode_block8_relics(mod_response)
    b9 = _encode_block9_potions(mod_response)
    b10 = _encode_block10_global(mod_response)
    s[BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM:BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM] = b8
    s[BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM:BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM + BLOCK9_DIM] = b9
    s[BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM + BLOCK9_DIM:BLOCK1_DIM + BLOCK2_DIM + BLOCK3_DIM + BLOCK4_DIM + BLOCK5_DIM + BLOCK6_DIM + BLOCK7_DIM + BLOCK8_DIM + BLOCK9_DIM + BLOCK10_DIM] = b10

    return s


def get_output_dim() -> int:
    """返回 ~2900"""
    return OUTPUT_DIM


class StateEncoder:
    """
    状态编码器包装类 - 供 sts_env、rl_agent 等使用

    将 GameState 转为 ~2900 维观察向量。
    mode 参数保留以兼容旧接口，当前仅支持 extended（~2900 维）。
    """
    def __init__(self, mode: str = "extended"):
        self.mode = mode
        self._dim = OUTPUT_DIM

    def get_output_dim(self) -> int:
        return self._dim

    def encode_state(self, state) -> np.ndarray:
        """将 GameState 编码为观察向量"""
        if state is None:
            return np.zeros(self._dim, dtype=np.float32)
        mod_response = state.to_mod_response()
        return encode(mod_response)