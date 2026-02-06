#!/usr/bin/env python3
"""
状态编码器 V2 - 静默专用：把 Mod 日志里的 state 转成 S 向量

与 Mod 日志数据互通：直接读取 game_state、combat_state 的字段路径，
缺失字段用默认值，非战斗时区块 2-7 填 0。

静默猎手专用：固定 A20 难度 + 静默职业，只拿猎人职业牌

10 区块结构 V2 - 静默专用（总计 2945 维）：
- s[0]~s[16]：玩家核心 17 维（核心战斗状态，无预留）
- s[17]~s[406]：手牌 390 维（144 multi-hot + 21×10 + 统计）
- s[407]~s[746]：抽牌堆 340 维（144 multi-hot + 统计）
- s[747]~s[1086]：弃牌堆 340 维（144 multi-hot + 统计）
- s[1087]~s[1326]：消耗堆 240 维（144 multi-hot + 统计）
- s[1327]~s[1426]：玩家 Powers 100 维
- s[1427]~s[2044]：怪物 618 维（每怪103维×6）
- s[2045]~s[2244]：遗物 200 维
- s[2245]~s[2444]：药水 200 维
- s[2445]~s[2944]：全局 500 维

静默专用改进：
1. 删除角色编码（固定静默）
2. 删除难度编码（固定A20）
3. 删除Orbs编码（静默不用）
4. 精简卡牌池（只保留静默+诅咒+状态+无色，144张）
5. 简化升级逻辑（静默无无限升级牌）
6. 调整参数上限（MAX_HP=200, MAX_BLOCK=999, MAX_ENERGY=20, MAX_POWER=99）
7. 简化金币和能量编码（金币单维度，能量像血量一样表示）
8. 区块1精简（删除与区块10重复的章节/房间/Buff信息）
"""
import numpy as np
from typing import Dict, Any, List

# 从 encoder_dims 导入统一的维度常量
try:
    from src.training.encoder_dims import (
        CARD_DIM, RELIC_DIM, POTION_DIM, POWER_DIM, INTENT_DIM, MONSTER_DIM,
        EVENT_DIM, ROOM_SUBTYPE_DIM, CARD_TYPE_DIM,
        BLOCK1_DIM, BLOCK2_DIM, BLOCK3_DIM, BLOCK4_DIM, BLOCK5_DIM,
        BLOCK6_DIM, BLOCK7_DIM, BLOCK8_DIM, BLOCK9_DIM, BLOCK10_DIM,
        OUTPUT_DIM,
        MAX_HP, MAX_BLOCK, MAX_ENERGY, MAX_GOLD, MAX_POWER, MAX_DEBUFF,
        MAX_HAND, MAX_DRAW, MAX_DISCARD, MAX_EXHAUST, MAX_CARDS_DISCARDED,
        MAX_TIMES_DAMAGED, MAX_TURN, MAX_ORB_SLOTS, MAX_DAMAGE,
    )
except ImportError:
    # 备用定义
    CARD_DIM = 144
    RELIC_DIM = 180
    POTION_DIM = 45
    POWER_DIM = 80
    INTENT_DIM = 13
    MONSTER_DIM = 75
    EVENT_DIM = 50
    ROOM_SUBTYPE_DIM = 15
    CARD_TYPE_DIM = 5
    BLOCK1_DIM = 17
    BLOCK2_DIM = 390
    BLOCK3_DIM = 340
    BLOCK4_DIM = 340
    BLOCK5_DIM = 240
    BLOCK6_DIM = 100
    BLOCK7_DIM = 618
    BLOCK8_DIM = 200
    BLOCK9_DIM = 200
    BLOCK10_DIM = 500
    OUTPUT_DIM = 2945
    MAX_HP = 200
    MAX_BLOCK = 999
    MAX_ENERGY = 20
    MAX_GOLD = 999
    MAX_POWER = 99
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
    card_rarity_to_index,
    get_monster_type,
)
from src.training.power_parser import (
    parse_strength,
    parse_dexterity,
    parse_weak,
    parse_vulnerable,
    parse_frail,
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
    区块 1：玩家核心 V2 - 静默专用，17 维。

    精简结构（删除与区块10重复的章节/房间/Buff信息）：
    [0-6]   HP/能量/护甲/金币（7维）
    [7-12]  本回合统计 + 牌堆数量（6维）
    [13-15] 钥匙状态（3维）
    [16]    回合（1维）
    """
    out = np.zeros(BLOCK1_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    hand = cs.get("hand") or []
    draw_pile = cs.get("draw_pile") or []
    discard_pile = cs.get("discard_pile") or []
    exhaust_pile = cs.get("exhaust_pile") or []

    # [0-6] HP/能量/护甲/金币（简化，像血量一样表示能量）
    current_hp = player.get("current_hp", gs.get("current_hp", 0))
    max_hp = max(player.get("max_hp", gs.get("max_hp", 1)), 1)
    out[0] = _clamp_norm(current_hp, max_hp)  # 当前HP/最大HP
    out[1] = _clamp_norm(min(max_hp, MAX_HP), MAX_HP)  # 最大HP/MAX_HP

    max_energy = player.get("max_energy", 3)
    current_energy = player.get("energy", 0)
    out[2] = _clamp_norm(current_energy, max(max_energy, 1))  # 当前能量/最大能量
    out[3] = _clamp_norm(min(max_energy, MAX_ENERGY), MAX_ENERGY)  # 最大能量/MAX_ENERGY

    out[4] = _clamp_norm(min(player.get("block", 0), MAX_BLOCK), MAX_BLOCK)  # 护甲/MAX_BLOCK
    out[5] = _clamp_norm(min(gs.get("gold", 0), MAX_GOLD), MAX_GOLD)  # 金币/MAX_GOLD
    out[6] = 0.0  # 预留（保持7维对齐）

    # [7-12] 本回合统计 + 牌堆数量 (6维)
    out[7] = _clamp_norm(
        min(cs.get("cards_discarded_this_turn", 0), MAX_CARDS_DISCARDED),
        MAX_CARDS_DISCARDED,
    )
    out[8] = _clamp_norm(
        min(cs.get("times_damaged", 0), MAX_TIMES_DAMAGED),
        MAX_TIMES_DAMAGED,
    )
    out[9] = _clamp_norm(min(len(hand), MAX_HAND), MAX_HAND)
    out[10] = _clamp_norm(min(len(draw_pile), MAX_DRAW), MAX_DRAW)
    out[11] = _clamp_norm(min(len(discard_pile), MAX_DISCARD), MAX_DISCARD)
    out[12] = _clamp_norm(min(len(exhaust_pile), MAX_EXHAUST), MAX_EXHAUST)

    # [13-15] 钥匙状态（红/蓝/绿宝石）
    relics = gs.get("relics") or []
    relic_ids = [r.get("id", r.get("name", "")).lower() for r in relics]
    out[13] = 1.0 if any("ruby" in rid for rid in relic_ids) else 0.0  # 红宝石
    out[14] = 1.0 if any("sapphire" in rid or "blue" in rid for rid in relic_ids) else 0.0  # 蓝宝石
    out[15] = 1.0 if any("emerald" in rid or "green" in rid for rid in relic_ids) else 0.0  # 绿宝石

    # [16] 回合
    out[16] = _clamp_norm(min(cs.get("turn", 0), MAX_TURN), MAX_TURN)

    return out


def _encode_block2_hand(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 2：手牌 V2 - 静默专用，384 维。

    新结构：
    [0-143]     144维 卡牌 multi-hot（静默专用）
    [144-373]   230维 每张牌23属性×10张
                每张牌23维：
                - cost (1)
                - is_playable (1)
                - has_target (1)
                - is_ethereal (1) 虚无
                - is_exhaust (1) 消耗
                - reserved (1) 原is_stripped，Mod不提供
                - cost_for_turn (1) 本回合费用（同cost）
                - type one-hot (5) 攻击/技能/能力/状态/诅咒
                - is_upgraded (1) 是否升级
                - upgrade_times (1) 升级次数
                - rarity one-hot (5) BASIC/COMMON/UNCOMMON/RARE/SPECIAL [新增]
    [374-383]   10维 统计
    [384-390]   6维 预留（部分用于rarity编码）
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

    # [144-353] 每张牌21属性×10张
    for i in range(10):
        base = 144 + i * 21
        if i < len(hand):
            c = hand[i]
            # 基础属性
            cost = max(c.get("cost", 0), 0)
            out[base + 0] = _clamp_norm(min(cost, 5), 5)
            out[base + 1] = 1.0 if c.get("is_playable", False) else 0.0
            out[base + 2] = 1.0 if c.get("has_target", False) else 0.0

            # 新增属性
            out[base + 3] = 1.0 if c.get("ethereal", False) else 0.0  # 虚无
            out[base + 4] = 1.0 if c.get("exhausts", False) else 0.0  # 消耗
            out[base + 5] = 0.0  # is_stripped 字段 Mod 不提供，预留

            # cost_for_turn - Mod 不提供，直接使用 cost
            cost_for_turn = cost
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

            # [14-18] 稀有度 one-hot (5维) [新增]
            rarity = c.get("rarity") or ""
            rarity_idx = card_rarity_to_index(rarity)
            out[base + 14 + rarity_idx] = 1.0

        else:
            # 超过10张牌的部分留空
            pass

    # [374-383] 手牌统计
    base = 374
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

    # [384-389] 预留 (6维)
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
    区块 3：抽牌堆 V2 - 静默专用，340 维。

    结构：
    [0-143]     144维 卡牌 multi-hot
    [144-226]   83维 详细统计（基础统计+类型占比+升级+特殊属性+费用）
    [227-339]   113维 预留
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

    # [144-226] 详细统计
    base = 144
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
    exhaust_cnt = sum(1 for c in draw_pile if c.get("exhausts", False))
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

    # [17-198] 预留 (182维)
    # 未来可用于更复杂的统计

    return out


def _encode_block4_discard_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 4：弃牌堆 V2 - 静默专用，340 维。

    结构：
    [0-143]     144维 卡牌 multi-hot
    [144-226]   83维 详细统计（基础统计+类型占比+本回合弃牌+升级+特殊属性）
    [227-339]   113维 预留
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

    # [144-226] 详细统计
    base = 144
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
    exhaust_cnt = sum(1 for c in discard_pile if c.get("exhausts", False))
    out[base + 12] = _clamp_norm(min(ethereal_cnt, 80), 80)
    out[base + 13] = _clamp_norm(min(exhaust_cnt, 80), 80)

    # [14-198] 预留 (185维)

    return out


def _encode_block5_exhaust_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    区块 5：消耗堆 V2 - 静默专用，240 维。

    结构：
    [0-143]     144维 卡牌 multi-hot
    [144-226]   83维 详细统计（基础统计+类型占比+升级牌+特殊属性）
    [227-239]   13维 预留
    """
    out = np.zeros(BLOCK5_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    exhaust_pile = cs.get("exhaust_pile") or []

    # [0-143] 卡牌 multi-hot
    for card in exhaust_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    # [144-226] 详细统计
    base = 144
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

    # [11-98] 预留 (88维)

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

    每个怪物 103 维结构：
    [0-74]      Monster ID multi-hot (75维)
    [75]        HP比例
    [76]        护甲
    [77-79]     怪物类型 one-hot (3维：普通/精英/Boss)
    [80]       当前招式 ID (move_id) [新增]
    [81-82]     预留
    [83-95]     Intent one-hot (13维)
    [96]        预计伤害
    [97]        存活状态 (is_gone反向)
    [98]        半死状态 (half_dead)
    [99-100]    动作历史 (last_move, second_last_move)
    [101]       Strength
    [102]       Vulnerable
    [103-104]   预留（Weak/Poison等通过区块6编码）
    """
    out = np.zeros(BLOCK7_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    monsters: List[Dict] = cs.get("monsters") or []

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

        # [77-79] 怪物类型 one-hot (3维：普通/精英/Boss)
        mon_type = get_monster_type(mid)
        out[base + 77 + mon_type] = 1.0

        # [80] 当前招式 ID [新增]
        # Mod 提供的 move_id 比 intent 更精确
        move_id = mon.get("move_id", 0) or 0
        out[base + 80] = _clamp_norm(min(move_id, 100), 100)

        # [81-82] 预留

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
        # [103-104] 预留（Weak/Poison等更多buff通过区块6编码）

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
    """
    区块 9：药水 200 维

    结构：
    [0-44]     药水 multi-hot (45维)
    [45-69]    5个槽位×5属性 = 25维 (can_use/can_discard/requires_target/预留×2)
    [70-71]    统计 2维 (药水总数/可用数)
    [72-199]   预留 128维
    """
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
    区块 10：全局 V2 - 静默专用，500 维。

    新结构（已删除角色/难度/Orbs编码，添加战斗动态和牌组变化）：
    [0-22]      基础信息（楼层、章节、房间阶段、可用命令）
    [23-72]     事件ID one-hot (50维)
    [73-87]     房间细分类型 one-hot (15维)
    [88-112]    地图路径信息 (25维)
    [113-136]   更多buff/debuff状态 (24维)
    [137-200]   地图编码 (64维) - 从 Mod 的 map 数组提取
    [201-209]   新增重要字段 (9维) - 静默专用
    [210-320]   战斗动态信息 (111维) - 从Mod日志提取
    [321-400]   牌组变化统计 (80维)
    [401-499]   预留 (99维)

    地图编码详情 [137-200]:
    [137]       已探索房间数
    [138-145]   节点类型统计 (8维) - M/E/B/?/$/R/T/O
    [146-153]   可到达房间类型 (8维) - 下一层选项
    [154-165]   当前节点信息 (12维) - 坐标/类型/连接数
    [166-200]   预留 (35维)

    新增字段详情 [201-209]（静默专用）：
    [201-202]   商店删牌信息 (2维)
    [203-204]   正在打出的牌 (2维)
    [205]       受击次数 (1维)
    [206-209]   奖励类型 (4维)

    战斗动态信息 [210-320]（基于Mod日志）：
    [210-212]   limbo牌信息 (3维) - 虚空牌数量/卡牌ID/升级状态
    [213-220]   怪物行为模式 (8维) - 每怪last/second_last_move
    [221-230]   预计伤害来源 (10维) - 每怪预计伤害
    [231-250]   本回合动态 (20维) - 手牌/牌堆/费用分布/能量
    [251-320]   预留 (70维)

    牌组变化统计 [321-400]（从deck推断）：
    [321-335]   牌组构成变化 (15维) - 总数/类型分布/升级分布
    [336-370]   已消耗牌统计 (35维) - 消耗堆分析
    [371-385]   升级牌统计 (15维) - 各位置升级牌数量
    [386-400]   预留 (15维)
    """
    out = np.zeros(BLOCK10_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cmds = mod_response.get("available_commands") or []
    ss = gs.get("screen_state") or {}
    options = ss.get("options") or []

    # 获取战斗状态变量（用于新增的战斗动态信息）
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    hand = cs.get("hand") or []
    draw_pile = cs.get("draw_pile") or []
    discard_pile = cs.get("discard_pile") or []
    exhaust_pile = cs.get("exhaust_pile") or []

    # [0-22] 基础信息（保持原有）
    floor = gs.get("floor", 0)
    out[0] = _clamp_norm(min(floor, 60), 60)
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

    # [73-87] 房间细分类型 one-hot (15维)
    # 根据房间阶段和怪物ID判断房间细分类型
    room_subtype = 13  # 默认未知
    if phase == "COMBAT":
        # 判断是否是精英或Boss（使用统一的 monster type 函数）
        monsters = gs.get("combat_state", {}).get("monsters") or []
        if any(get_monster_type(m.get("id", "")) == 2 for m in monsters):
            room_subtype = 2  # Boss房
        elif any(get_monster_type(m.get("id", "")) == 1 for m in monsters):
            room_subtype = 1  # 精英房
        else:
            room_subtype = 0  # 普通怪物房
    elif phase == "REST":
        room_subtype = 3  # 普通休息室
    elif phase == "SHOP":
        room_subtype = 7  # 商店
    elif phase == "EVENT":
        room_subtype = 8  # 事件房
    elif phase == "MAP":
        room_subtype = 12  # 地图

    if 0 <= room_subtype < 15:
        out[73 + room_subtype] = 1.0

    # [88-112] 地图相关信息 (25维)
    # Mod 提供的 map 是数组，无法直接获取坐标
    # 使用 floor 作为进度指标，其他预留
    out[88] = _clamp_norm(min(floor, 60), 60)  # 当前楼层作为进度指标
    # out[89] - 预留（原 current_x，Mod 不提供）
    # out[90] - 预留（原 current_y，Mod 不提供）
    # out[91] - 预留（原 visited_rooms，Mod 不提供）
    # out[92] - 预留（原 connections，Mod 不提供）
    # [93-112] 预留 (20维)

    # [113-136] 更多buff/debuff状态 (24维)
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
    out[130] = _clamp_norm(min(parse_berserk(powers), 1), 1)  # 狂暴是bool
    out[131] = _clamp_norm(min(parse_metallicize(powers), 50), 50)  # 金属化
    out[132] = 0.0  # 预留
    out[133] = 0.0  # 预留
    out[134] = 0.0  # 预留
    out[135] = 0.0  # 预留
    out[136] = _clamp_norm(min(parse_barricade(powers), 1), 1)  # 路障是bool

    # [137-200] 地图编码 (64维) - 从 Mod 提供的 map 数组中提取信息
    # Mod 提供的 map 是数组，包含所有地图节点对象
    # 每个节点包含: x, y, symbol (M/?/$/E/R/T), parents, children
    map_nodes = gs.get("map") or []
    screen_map_current = ss.get("current_node") or {}
    screen_map_next = ss.get("next_nodes") or []

    # [137] 已探索房间数 (1维)
    # 使用 map 数组的长度作为已探索房间数
    out[137] = _clamp_norm(min(len(map_nodes), 60), 60)

    # [138-145] 节点类型统计 (8维)
    # 统计地图上各类型房间的数量
    # M=普通怪物, E=精英, B=Boss, ?=事件, $=商店, R=休息, T=宝箱
    symbol_counts = {
        "M": 0,   # 普通怪物
        "E": 0,   # 精英
        "B": 0,   # Boss
        "?": 0,   # 事件
        "$": 0,   # 商店
        "R": 0,   # 休息
        "T": 0,   # 宝箱
        "O": 0,   # 其他
    }
    for node in map_nodes:
        symbol = node.get("symbol", "O")
        if symbol not in symbol_counts:
            symbol = "O"
        symbol_counts[symbol] += 1

    out[138] = _clamp_norm(min(symbol_counts["M"], 30), 30)  # 普通怪物房数量
    out[139] = _clamp_norm(min(symbol_counts["E"], 10), 10)  # 精英房数量
    out[140] = _clamp_norm(min(symbol_counts["B"], 5), 5)    # Boss房数量
    out[141] = _clamp_norm(min(symbol_counts["?"], 15), 15)  # 事件房数量
    out[142] = _clamp_norm(min(symbol_counts["$"], 10), 10)  # 商店数量
    out[143] = _clamp_norm(min(symbol_counts["R"], 10), 10)  # 休息室数量
    out[144] = _clamp_norm(min(symbol_counts["T"], 5), 5)    # 宝箱房数量
    out[145] = _clamp_norm(min(symbol_counts["O"], 10), 10)  # 其他类型

    # [146-153] 可到达的房间类型统计 (8维) - 下一层选项
    # 从 screen_state.next_nodes 中统计可去的房间类型
    next_symbol_counts = {
        "M": 0, "E": 0, "B": 0, "?": 0,
        "$": 0, "R": 0, "T": 0, "O": 0,
    }
    for node in screen_map_next:
        symbol = node.get("symbol", "O")
        if symbol not in next_symbol_counts:
            symbol = "O"
        next_symbol_counts[symbol] += 1

    out[146] = 1.0 if next_symbol_counts["M"] > 0 else 0.0  # 可去普通怪物房
    out[147] = 1.0 if next_symbol_counts["E"] > 0 else 0.0  # 可去精英房
    out[148] = 1.0 if next_symbol_counts["B"] > 0 else 0.0  # 可去Boss房
    out[149] = 1.0 if next_symbol_counts["?"] > 0 else 0.0  # 可去事件房
    out[150] = 1.0 if next_symbol_counts["$"] > 0 else 0.0  # 可去商店
    out[151] = 1.0 if next_symbol_counts["R"] > 0 else 0.0  # 可去休息室
    out[152] = 1.0 if next_symbol_counts["T"] > 0 else 0.0  # 可去宝箱房
    out[153] = _clamp_norm(min(len(screen_map_next), 5), 5)  # 可选房间总数

    # [154-165] 当前节点信息 (12维)
    # 当前节点的坐标和类型
    current_x = screen_map_current.get("x", -1)
    current_y = screen_map_current.get("y", -1)
    current_symbol = screen_map_current.get("symbol", "")

    out[154] = _clamp_norm(min(current_x if current_x >= 0 else 0, 15), 15)  # 当前X坐标
    out[155] = _clamp_norm(min(current_y if current_y >= 0 else 0, 15), 15)  # 当前Y坐标
    out[156] = 1.0 if current_symbol == "M" else 0.0  # 当前是怪物房
    out[157] = 1.0 if current_symbol == "E" else 0.0  # 当前是精英房
    out[158] = 1.0 if current_symbol == "B" else 0.0  # 当前是Boss房
    out[159] = 1.0 if current_symbol == "?" else 0.0  # 当前是事件房
    out[160] = 1.0 if current_symbol == "$" else 0.0  # 当前是商店
    out[161] = 1.0 if current_symbol == "R" else 0.0  # 当前是休息室
    out[162] = 1.0 if current_symbol == "T" else 0.0  # 当前是宝箱房

    # 当前节点的连接数（父节点和子节点数量）
    current_parents = screen_map_current.get("parents") or []
    current_children = screen_map_current.get("children") or []
    out[163] = _clamp_norm(min(len(current_parents), 3), 3)  # 父节点数量
    out[164] = _clamp_norm(min(len(current_children), 4), 4)  # 子节点数量
    out[165] = 0.0  # 预留

    # [166-200] 预留 (35维) - 可用于扩展
    # [201-209] 新增重要字段 (9维) - 静默专用
    # 已删除：角色编码（固定静默）、逆飞等级（固定A20）、能量球（静默不用）

    # [201-202] 商店删牌信息 (2维) [P1]
    purge_available = ss.get("purge_available", False)
    purge_cost = ss.get("purge_cost", 0)
    out[201] = 1.0 if purge_available else 0.0  # 是否可删牌
    out[202] = _clamp_norm(min(purge_cost, 150), 150) if purge_available else 0.0  # 删牌价格

    # [203-204] 正在打出的牌 (2维) [P1]
    # card_in_play 是正在打出但未结算的牌（如等待目标选择）
    card_in_play = cs.get("card_in_play") or {}
    if card_in_play:
        card_id = card_in_play.get("id") or card_in_play.get("name") or ""
        card_idx = card_id_to_index(card_id)
        out[203] = _clamp_norm(min(card_idx, CARD_DIM), CARD_DIM) / CARD_DIM  # 卡牌ID归一化
        out[204] = 1.0 if card_in_play.get("upgrades", 0) > 0 else 0.0  # 是否升级
    else:
        out[203] = 0.0  # 无牌在打出中
        out[204] = 0.0

    # [205] 受击次数 (1维) [P1]
    # 本局战斗受击次数，反映生存压力
    times_damaged = cs.get("times_damaged", 0)
    out[205] = _clamp_norm(min(times_damaged, 20), 20)

    # [206-209] 奖励类型 (4维) [P1]
    # 卡牌奖励屏幕、宝箱等的奖励类型统计
    rewards = ss.get("rewards") or []
    reward_types = {"CARD": 0, "POTION": 0, "GOLD": 0, "RELIC": 0}
    for reward in rewards:
        reward_type = reward.get("reward_type", "")
        if reward_type in reward_types:
            reward_types[reward_type] += 1
    out[206] = 1.0 if reward_types["CARD"] > 0 else 0.0
    out[207] = 1.0 if reward_types["POTION"] > 0 else 0.0
    out[208] = _clamp_norm(min(reward_types["GOLD"], 300), 300) / 50.0  # 归一化金币奖励
    out[209] = 1.0 if reward_types["RELIC"] > 0 else 0.0

    # [210-320] 战斗动态信息 (111维) - 从Mod日志提取
    # [210-212] limbo牌信息 (3维) - 虚空牌（正在打出中的牌，等待效果结算）
    limbo = cs.get("limbo") or []
    out[210] = min(len(limbo), 5) / 5.0  # limbo中牌的数量归一化
    if limbo:
        # limbo第一张牌的卡牌ID（归一化）
        first_limbo = limbo[0] if isinstance(limbo[0], dict) else {"id": str(limbo[0])}
        limbo_id = first_limbo.get("id") or first_limbo.get("name") or ""
        limbo_idx = card_id_to_index(limbo_id)
        out[211] = _clamp_norm(min(limbo_idx, CARD_DIM), CARD_DIM) / CARD_DIM
        out[212] = 1.0 if first_limbo.get("upgrades", 0) > 0 else 0.0
    else:
        out[211] = 0.0
        out[212] = 0.0

    # [213-220] 怪物行为模式 (8维) - 每个怪物的last_move_id归一化
    monsters = cs.get("monsters") or []
    for i in range(4):  # 最多4个怪物
        base = 213 + i * 2
        if i < len(monsters):
            m = monsters[i]
            last_move = m.get("last_move_id", 0) or 0
            second_last_move = m.get("second_last_move_id", 0) or 0
            out[base] = _clamp_norm(min(last_move, 50), 50) / 50.0
            out[base + 1] = _clamp_norm(min(second_last_move, 50), 50) / 50.0
        else:
            out[base] = 0.0
            out[base + 1] = 0.0

    # [221-230] 预计伤害来源 (10维) - 每个怪物的预计伤害
    for i in range(6):  # 最多6个怪物
        if i < len(monsters):
            m = monsters[i]
            adj_damage = m.get("move_adjusted_damage", 0) or 0
            hits = m.get("move_hits", 1) or 1
            dmg = max(0, adj_damage * hits) if adj_damage > 0 else 0
            out[221 + i] = _clamp_norm(min(dmg, 50), 50) / 50.0
        else:
            out[221 + i] = 0.0

    # [231-250] 本回合动态 (20维)
    # 手牌数量变化、能量使用、牌堆变化等动态信息
    out[231] = _clamp_norm(min(len(hand), MAX_HAND), MAX_HAND)  # 当前手牌数
    out[232] = _clamp_norm(min(len(draw_pile), MAX_DRAW), MAX_DRAW)  # 当前抽牌堆数
    out[233] = _clamp_norm(min(len(discard_pile), MAX_DISCARD), MAX_DISCARD)  # 当前弃牌堆数
    out[234] = _clamp_norm(min(len(exhaust_pile), MAX_EXHAUST), MAX_EXHAUST)  # 当前消耗堆数

    # 手牌费用分布 (5维: 0费/1费/2费/3费/高费)
    cost_distribution = [0] * 5
    for card in hand:
        cost = max(card.get("cost", 0), 0)
        if cost == 0:
            cost_distribution[0] += 1
        elif cost == 1:
            cost_distribution[1] += 1
        elif cost == 2:
            cost_distribution[2] += 1
        elif cost == 3:
            cost_distribution[3] += 1
        else:
            cost_distribution[4] += 1
    for i in range(5):
        out[235 + i] = min(cost_distribution[i], 10) / 10.0

    # 本回合可出牌数量
    playable = sum(1 for c in hand if c.get("is_playable", False))
    out[240] = min(playable, 10) / 10.0

    # [241-250] 能量和伤害相关 (10维)
    current_energy = player.get("energy", 0)
    max_energy = player.get("max_energy", 3)
    out[241] = _clamp_norm(min(current_energy, max(max_energy, 1)), max(max_energy, 1))  # 剩余能量
    out[242] = _clamp_norm(min(max_energy, MAX_ENERGY), MAX_ENERGY)  # 最大能量

    # 预计下回合伤害（从怪物意图统计）
    total_expected_damage = 0
    for m in monsters:
        if not m.get("is_gone", False):
            intent = (m.get("intent") or "").lower()
            if "attack" in intent:
                adj_dmg = m.get("move_adjusted_damage", 0) or 0
                hits = m.get("move_hits", 1) or 1
                total_expected_damage += max(0, adj_dmg * hits) if adj_dmg > 0 else 0
    out[243] = _clamp_norm(min(total_expected_damage, 100), 100) / 100.0

    # [244-250] 预留 (7维)

    # [251-320] 预留 (70维)

    # [321-400] 牌组变化统计 (80维)
    deck = gs.get("deck") or []

    # [321-335] 牌组构成变化 (15维)
    # 当前牌组总数（相对于初始牌组的规模变化）
    out[321] = _clamp_norm(min(len(deck), 80), 80) / 80.0  # 牌组总数

    # 牌组类型分布 (5维: 攻击/技能/能力/状态/诅咒)
    deck_type_dist = [0] * 5
    for card in deck:
        card_type = (card.get("type") or "").lower()
        if card_type == "attack":
            deck_type_dist[0] += 1
        elif card_type == "skill":
            deck_type_dist[1] += 1
        elif card_type == "power":
            deck_type_dist[2] += 1
        elif card_type == "status":
            deck_type_dist[3] += 1
        elif card_type == "curse":
            deck_type_dist[4] += 1
    total_deck = max(len(deck), 1)
    for i in range(5):
        out[322 + i] = deck_type_dist[i] / total_deck

    # [327-335] 升级牌数量 (5维: 各类型升级牌数量)
    upgrade_dist = [0] * 5
    for card in deck:
        card_type = (card.get("type") or "").lower()
        upgrades = card.get("upgrades", 0) or 0
        if upgrades > 0:
            if card_type == "attack":
                upgrade_dist[0] += 1
            elif card_type == "skill":
                upgrade_dist[1] += 1
            elif card_type == "power":
                upgrade_dist[2] += 1
            elif card_type == "status":
                upgrade_dist[3] += 1
            elif card_type == "curse":
                upgrade_dist[4] += 1
    for i in range(5):
        out[327 + i] = min(upgrade_dist[i], 20) / 20.0

    # [336-370] 已消耗牌统计 (35维) - 消耗堆的详细分析
    exhaust_pile = cs.get("exhaust_pile") or []
    out[336] = _clamp_norm(min(len(exhaust_pile), MAX_EXHAUST), MAX_EXHAUST)  # 消耗堆总数

    # 消耗堆类型分布 (5维)
    exhaust_type_dist = [0] * 5
    for card in exhaust_pile:
        card_type = (card.get("type") or "").lower()
        if card_type == "attack":
            exhaust_type_dist[0] += 1
        elif card_type == "skill":
            exhaust_type_dist[1] += 1
        elif card_type == "power":
            exhaust_type_dist[2] += 1
        elif card_type == "status":
            exhaust_type_dist[3] += 1
        elif card_type == "curse":
            exhaust_type_dist[4] += 1
    for i in range(5):
        out[337 + i] = min(exhaust_type_dist[i], 20) / 20.0

    # 消耗堆中特定卡牌统计 (25维) - 检查一些重要的消耗牌
    important_exhaust = [
        "AscendersBane", "Injury", "Regret", "Pain", "Shame",
        "Normality", "Doubt", "Writhe", "Necronomicurse", "Clumsy",
        "Decay", "CurseOfTheBell", "Parasite",
        # 静默可能消耗的牌
        "Deadly Poison", "Catalyst", "Bane",
    ]
    for i, card_id in enumerate(important_exhaust):
        if i < 25:
            has_card = any(c.get("id") == card_id for c in exhaust_pile)
            out[342 + i] = 1.0 if has_card else 0.0

    # [371-385] 升级牌统计 (15维)
    # 手牌中的升级牌数量
    hand_upgrades = sum(1 for c in hand if c.get("upgrades", 0) > 0)
    out[371] = min(hand_upgrades, 10) / 10.0

    # 抽牌堆中的升级牌数量（估算，从multi-hot推断）
    draw_upgraded = sum(1 for c in draw_pile if c.get("upgrades", 0) > 0)
    out[372] = min(draw_upgraded, 20) / 20.0

    # 弃牌堆中的升级牌数量
    discard_upgraded = sum(1 for c in discard_pile if c.get("upgrades", 0) > 0)
    out[373] = min(discard_upgraded, 20) / 20.0

    # 总升级牌数量
    total_upgraded = sum(1 for c in deck if c.get("upgrades", 0) > 0)
    out[374] = min(total_upgraded, 30) / 30.0

    # [375-385] 预留 (11维)

    # [386-400] 预留 (15维)

    # [401-499] 预留 (99维)

    return out


def encode(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    把 Mod 一帧的 JSON 转成 S 向量 V2

    与 Mod 日志互通：mod_response 为 Mod 返回的整帧，
    含 game_state、combat_state、available_commands 等。
    缺失 combat_state 时，区块 2-7 填 0。

    总维度: 2949
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
        # 新索引：区块1(17) + 区块2(390) + 区块3(340) + ...
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
    """返回 2945"""
    return OUTPUT_DIM


class StateEncoder:
    """
    状态编码器包装类 - 供 sts_env、rl_agent 等使用

    将 GameState 转为 2945 维观察向量。
    mode 参数保留以兼容旧接口，当前仅支持 extended（2945 维）。
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