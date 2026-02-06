#!/usr/bin/env python3
"""
状态编码器：把 Mod 日志里的 state 转成 ~2900 维 S 向量

与 Mod 日志数据互通：直接读取 game_state、combat_state 的字段路径，
缺失字段用默认值，非战斗时区块 2-7 填 0。

10 区块结构：
- s[0]~s[49]：玩家核心 50 维
- s[50]~s[449]：手牌 400 维
- s[450]~s[849]：抽牌堆 400 维
- s[850]~s[1249]：弃牌堆 400 维
- s[1250]~s[1549]：消耗堆 300 维
- s[1550]~s[1649]：玩家 Powers 100 维
- s[1650]~s[2249]：怪物 600 维
- s[2250]~s[2449]：遗物 200 维
- s[2450]~s[2649]：药水 200 维
- s[2650]~s[2899]：全局 250 维
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
    CARD_DIM,
    RELIC_DIM,
    POTION_DIM,
    POWER_DIM,
    INTENT_DIM,
    MONSTER_DIM,
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
)

# 归一化用的最大值（与 Mod 日志数值范围兼容）
MAX_HP = 999
MAX_BLOCK = 99
MAX_ENERGY = 10
MAX_GOLD = 999
MAX_POWER = 50
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

# 区块维度
BLOCK1_DIM = 50
BLOCK2_DIM = 400
BLOCK3_DIM = 400
BLOCK4_DIM = 400
BLOCK5_DIM = 300
BLOCK6_DIM = 100
BLOCK7_DIM = 600
BLOCK8_DIM = 200
BLOCK9_DIM = 200
BLOCK10_DIM = 250

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
    """区块 1：玩家核心，50 维。含角色 one-hot、章节 one-hot、难度。"""
    out = np.zeros(BLOCK1_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    hand = cs.get("hand") or []
    draw_pile = cs.get("draw_pile") or []
    discard_pile = cs.get("discard_pile") or []
    exhaust_pile = cs.get("exhaust_pile") or []
    deck = gs.get("deck") or []

    current_hp = player.get("current_hp", gs.get("current_hp", 0))
    max_hp = max(player.get("max_hp", gs.get("max_hp", 1)), 1)
    out[0] = _clamp_norm(current_hp, max_hp)
    out[1] = _clamp_norm(min(max_hp, MAX_HP), MAX_HP)
    out[2] = _clamp_norm(min(player.get("energy", 0), MAX_ENERGY), MAX_ENERGY)
    out[3] = _clamp_norm(min(3, MAX_ENERGY), MAX_ENERGY)
    out[4] = _clamp_norm(min(player.get("block", 0), MAX_BLOCK), MAX_BLOCK)
    out[5] = min(player.get("block", 0) / 100.0, 1.0)
    out[6] = _clamp_norm(min(gs.get("gold", 0), MAX_GOLD), MAX_GOLD)
    out[7] = min(gs.get("gold", 0) / 999.0, 1.0)

    # 角色 one-hot 4 维 (8-11)
    char = (gs.get("class") or "").upper()
    if "IRONCLAD" in char or "THE_IRONCLAD" in char:
        out[8] = 1.0
    elif "SILENT" in char or "THE_SILENT" in char:
        out[9] = 1.0
    elif "DEFECT" in char or "THE_DEFECT" in char:
        out[10] = 1.0
    elif "WATCHER" in char or "THE_WATCHER" in char:
        out[11] = 1.0

    # 难度 ascension (12-13)
    asc = gs.get("ascension_level", 0)
    out[12] = _clamp_norm(min(asc, 20), 20)
    out[13] = min(asc, 20) / 20.0

    # 章节 one-hot 4 维 (14-17)
    act = gs.get("act", 1)
    if act == 1:
        out[14] = 1.0
    elif act == 2:
        out[15] = 1.0
    elif act == 3:
        out[16] = 1.0
    else:
        out[17] = 1.0

    # 核心状态 one-hot (18-24)
    phase = (gs.get("room_phase") or gs.get("screen_type") or "").upper()
    phase_map = {
        "COMBAT": 18, "EVENT": 19, "MAP": 20, "SHOP": 21,
        "REST": 22, "BOSS": 23, "NONE": 24,
    }
    idx = phase_map.get(phase, 24)
    out[idx] = 1.0

    # Buff/Debuff 计数 (25-29)
    powers = player.get("powers") or []
    out[25] = _clamp_norm(min(parse_strength(powers), MAX_POWER), MAX_POWER)
    out[26] = _clamp_norm(min(parse_dexterity(powers), 30), 30)
    out[27] = _clamp_norm(min(parse_weak(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[28] = _clamp_norm(min(parse_vulnerable(powers), MAX_DEBUFF), MAX_DEBUFF)
    out[29] = _clamp_norm(min(parse_frail(powers), MAX_DEBUFF), MAX_DEBUFF)

    # 回合 (30-31)
    out[30] = _clamp_norm(min(cs.get("turn", 0), MAX_TURN), MAX_TURN)
    out[31] = min(cs.get("turn", 0), MAX_TURN) / 50.0

    # 牌组统计 (32-33)
    deck_size = len(deck) if deck else len(hand) + len(draw_pile) + len(discard_pile) + len(exhaust_pile)
    out[32] = _clamp_norm(min(deck_size, 50), 50)
    out[33] = min(deck_size, 50) / 50.0

    # 本回合统计 (34-35)
    out[34] = _clamp_norm(
        min(cs.get("cards_discarded_this_turn", 0), MAX_CARDS_DISCARDED),
        MAX_CARDS_DISCARDED,
    )
    out[35] = _clamp_norm(
        min(cs.get("times_damaged", 0), MAX_TIMES_DAMAGED),
        MAX_TIMES_DAMAGED,
    )

    # 手牌/牌堆数量 (36-39)
    out[36] = _clamp_norm(min(len(hand), MAX_HAND), MAX_HAND)
    out[37] = _clamp_norm(min(len(draw_pile), MAX_DRAW), MAX_DRAW)
    out[38] = _clamp_norm(min(len(discard_pile), MAX_DISCARD), MAX_DISCARD)
    out[39] = _clamp_norm(min(len(exhaust_pile), MAX_EXHAUST), MAX_EXHAUST)

    # 缺陷 orb 槽 (40)
    orbs = player.get("orbs") or []
    out[40] = _clamp_norm(min(len(orbs), MAX_ORB_SLOTS), MAX_ORB_SLOTS)
    # 41-49 预留
    return out


def _encode_block2_hand(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 2：手牌 400 维（multi-hot 271 + 10×3 属性 + 10 统计 + 预留）"""
    out = np.zeros(BLOCK2_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    hand: List[Dict] = cs.get("hand") or []

    for card in hand:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    for i in range(10):
        base = 271 + i * 3
        if i < len(hand):
            c = hand[i]
            cost = max(c.get("cost", 0), 0)
            out[base + 0] = _clamp_norm(min(cost, 5), 5)
            out[base + 1] = 1.0 if c.get("is_playable", False) else 0.0
            out[base + 2] = 1.0 if c.get("has_target", False) else 0.0

    # 手牌统计 (301-310)
    base = 301
    out[base] = min(len(hand), 10) / 10.0
    zero_cost = sum(1 for c in hand if (c.get("cost") or 0) == 0)
    out[base + 1] = min(zero_cost, 10) / 10.0
    playable = sum(1 for c in hand if c.get("is_playable", False))
    out[base + 2] = min(playable, 10) / 10.0
    attack_cnt = sum(1 for c in hand if (c.get("type") or "").lower() == "attack")
    out[base + 3] = min(attack_cnt, 10) / 10.0
    skill_cnt = sum(1 for c in hand if (c.get("type") or "").lower() == "skill")
    out[base + 4] = min(skill_cnt, 10) / 10.0
    total_cost = sum(max(c.get("cost", 0), 0) for c in hand)
    out[base + 5] = _clamp_norm(min(total_cost, 20), 20)
    # 307-309 预留
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
    """区块 3：抽牌堆 400 维（multi-hot 271 + 统计 + 类型占比）"""
    out = np.zeros(BLOCK3_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    draw_pile = cs.get("draw_pile") or []

    for card in draw_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    base = 271
    out[base] = min(len(draw_pile), 80) / 80.0
    zero_cost = sum(1 for c in draw_pile if (c.get("cost") or 0) == 0)
    out[base + 1] = min(zero_cost, 80) / 80.0
    out[base + 2] = _count_type_ratio(draw_pile, "attack")
    out[base + 3] = _count_type_ratio(draw_pile, "skill")
    out[base + 4] = _count_type_ratio(draw_pile, "power")
    out[base + 5] = _count_status_curse_ratio(draw_pile)
    return out


def _encode_block4_discard_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 4：弃牌堆 400 维（multi-hot 271 + 统计）"""
    out = np.zeros(BLOCK4_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    discard_pile = cs.get("discard_pile") or []

    for card in discard_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    base = 271
    out[base] = min(len(discard_pile), 80) / 80.0
    out[base + 1] = _count_type_ratio(discard_pile, "attack")
    out[base + 2] = _count_type_ratio(discard_pile, "skill")
    out[base + 3] = _count_type_ratio(discard_pile, "power")
    out[base + 4] = _count_status_curse_ratio(discard_pile)
    out[base + 5] = _clamp_norm(
        min(cs.get("cards_discarded_this_turn", 0), MAX_CARDS_DISCARDED),
        MAX_CARDS_DISCARDED,
    )
    return out


def _encode_block5_exhaust_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 5：消耗堆 300 维（multi-hot 271 + 统计）"""
    out = np.zeros(BLOCK5_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    exhaust_pile = cs.get("exhaust_pile") or []

    for card in exhaust_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    base = 271
    out[base] = min(len(exhaust_pile), 50) / 50.0
    out[base + 1] = _count_type_ratio(exhaust_pile, "attack")
    out[base + 2] = _count_type_ratio(exhaust_pile, "skill")
    out[base + 3] = _count_type_ratio(exhaust_pile, "power")
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
    """区块 7：怪物 600 维（6×100，含 monster_id、last_move_id、powers）"""
    out = np.zeros(BLOCK7_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    monsters: List[Dict] = cs.get("monsters") or []
    for m in range(6):
        base = m * 100
        if m >= len(monsters):
            continue
        mon = monsters[m]
        mid = mon.get("id") or mon.get("name") or ""
        midx = monster_id_to_index(mid)
        if 0 <= midx < MONSTER_DIM:
            out[base + midx] = 1.0
        out[base + 75] = _clamp_norm(
            mon.get("current_hp", 0),
            max(mon.get("max_hp", 1), 1),
        )
        out[base + 76] = _clamp_norm(min(mon.get("block", 0), MAX_BLOCK), MAX_BLOCK)
        intent_str = mon.get("intent") or ""
        intent_idx = intent_to_index(intent_str)
        if 0 <= intent_idx < INTENT_DIM:
            out[base + 77 + intent_idx] = 1.0
        adj = mon.get("move_adjusted_damage", 0) or 0
        hits = mon.get("move_hits", 1) or 1
        dmg = max(0, adj * hits)
        out[base + 90] = _clamp_norm(min(dmg, MAX_DAMAGE), MAX_DAMAGE)
        out[base + 91] = 0.0 if mon.get("is_gone", False) else 1.0
        out[base + 92] = 1.0 if mon.get("half_dead", False) else 0.0
        out[base + 93] = _clamp_norm(mon.get("last_move_id", 0) or 0, 100)
        out[base + 94] = _clamp_norm(mon.get("second_last_move_id", 0) or 0, 100)
        mpowers = mon.get("powers") or []
        out[base + 95] = _clamp_norm(min(parse_strength(mpowers), 30), 30)
        out[base + 96] = _clamp_norm(min(parse_vulnerable(mpowers), MAX_DEBUFF), MAX_DEBUFF)
        out[base + 97] = _clamp_norm(min(parse_weak(mpowers), MAX_DEBUFF), MAX_DEBUFF)
        out[base + 98] = _clamp_norm(min(parse_poison(mpowers), 99), 99)
        out[base + 99] = _clamp_norm(min(parse_curl_up(mpowers), 10), 10)
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
    """区块 10：全局 250 维（楼层、章节、命令、选项、防卡住等）"""
    out = np.zeros(BLOCK10_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cmds = mod_response.get("available_commands") or []
    ss = gs.get("screen_state") or {}
    options = ss.get("options") or []

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
    return out


def encode(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    把 Mod 一帧的 JSON 转成 ~2900 维 S 向量

    与 Mod 日志互通：mod_response 为 Mod 返回的整帧，
    含 game_state、combat_state、available_commands 等。
    缺失 combat_state 时，区块 2-7 填 0。
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
        s[50:50 + BLOCK2_DIM] = b2
        s[450:450 + BLOCK3_DIM] = b3
        s[850:850 + BLOCK4_DIM] = b4
        s[1250:1250 + BLOCK5_DIM] = b5
        s[1550:1550 + BLOCK6_DIM] = b6
        s[1650:1650 + BLOCK7_DIM] = b7

    b8 = _encode_block8_relics(mod_response)
    b9 = _encode_block9_potions(mod_response)
    b10 = _encode_block10_global(mod_response)
    s[2250:2250 + BLOCK8_DIM] = b8
    s[2450:2450 + BLOCK9_DIM] = b9
    s[2650:2650 + BLOCK10_DIM] = b10

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
