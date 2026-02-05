#!/usr/bin/env python3
"""
状态编码器：把 Mod 日志里的 state 转成 1840 维向量 s

与 Mod 日志数据互通：直接读取 game_state、combat_state 的字段路径，
缺失字段用默认值，非战斗时区块 2-9 填 0。

区块结构：
- s[0]~s[19]：玩家核心 20 维
- s[20]~s[350]：手牌 331 维（multi-hot 271 + 每槽 6 维）
- s[351]~s[629]：抽牌堆 279 维（multi-hot 271 + 类型占比 8）
- s[630]~s[900]：弃牌堆 271 维
- s[901]~s[1171]：消耗堆 271 维
- s[1172]~s[1251]：玩家 Powers 80 维
- s[1252]~s[1551]：怪物 300 维（6×50）
- s[1552]~s[1731]：遗物 180 维
- s[1732]~s[1796]：药水 65 维
- s[1797]~s[1839]：全局 43 维
"""
import hashlib
import numpy as np
from typing import Dict, Any, List

from src.training.encoder_utils import (
    card_id_to_index,
    relic_id_to_index,
    potion_id_to_index,
    power_id_to_index,
    intent_to_index,
    CARD_DIM,
    RELIC_DIM,
    POTION_DIM,
    POWER_DIM,
    INTENT_DIM,
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
MAX_ORB_SLOTS = 10  # 缺陷机器人 orb 槽位上限
MAX_DAMAGE = 99

# 卡牌类型 → 标量
CARD_TYPE_MAP = {
    "attack": 0.2,
    "skill": 0.4,
    "power": 0.6,
    "status": 0.0,
    "curse": 0.0,
}

OUTPUT_DIM = 1840


def _clamp_norm(val: float, max_val: float) -> float:
    """把数压到 0~1：val/max_val，max_val=0 时返回 0"""
    if max_val <= 0:
        return 0.0
    return float(np.clip(val / max_val, 0.0, 1.0))


def _encode_block1_player_core(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 1：玩家核心，20 维。非战斗时部分字段从 game_state 取。"""
    out = np.zeros(20, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    hand = cs.get("hand") or []
    draw_pile = cs.get("draw_pile") or []
    discard_pile = cs.get("discard_pile") or []
    exhaust_pile = cs.get("exhaust_pile") or []

    current_hp = player.get("current_hp", gs.get("current_hp", 0))
    max_hp = max(player.get("max_hp", gs.get("max_hp", 1)), 1)
    out[0] = _clamp_norm(current_hp, max_hp)
    out[1] = _clamp_norm(min(gs.get("max_hp", player.get("max_hp", 70)), MAX_HP), MAX_HP)
    out[2] = _clamp_norm(min(player.get("block", 0), MAX_BLOCK), MAX_BLOCK)
    out[3] = _clamp_norm(min(player.get("energy", 0), MAX_ENERGY), MAX_ENERGY)
    max_energy = 3  # Phase 1 固定
    out[4] = _clamp_norm(min(max_energy, MAX_ENERGY), MAX_ENERGY)
    out[5] = _clamp_norm(min(gs.get("gold", 0), MAX_GOLD), MAX_GOLD)

    powers = player.get("powers") or []
    out[6] = _clamp_norm(min(parse_strength(powers), MAX_POWER), MAX_POWER)
    out[7] = _clamp_norm(min(parse_dexterity(powers), 30), 30)
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
    # 缺陷机器人 orb 槽位：len(orbs) 为当前 orb 数，上限 10 槽
    orbs = player.get("orbs") or []
    out[18] = _clamp_norm(min(len(orbs), MAX_ORB_SLOTS), MAX_ORB_SLOTS)
    out[19] = _clamp_norm(min(cs.get("turn", 0), MAX_TURN), MAX_TURN)
    return out


def _encode_block2_hand(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 2：手牌 331 维（multi-hot 271 + 每槽 6 维×10）"""
    out = np.zeros(331, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    hand: List[Dict] = cs.get("hand") or []

    for card in hand:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    for i in range(10):
        base = 271 + i * 6
        if i < len(hand):
            c = hand[i]
            cost = max(c.get("cost", 0), 0)
            out[base + 0] = _clamp_norm(min(cost, 5), 5)
            type_str = (c.get("type") or "").lower()
            out[base + 1] = CARD_TYPE_MAP.get(type_str, 0.0)
            out[base + 2] = 1.0 if c.get("is_playable", False) else 0.0
            out[base + 3] = 1.0 if c.get("has_target", False) else 0.0
            upgrades = c.get("upgrades", 0)
            out[base + 4] = _clamp_norm(min(upgrades, 2), 2)
            ethereal = c.get("ethereal", False)
            exhausts = c.get("exhausts", False)
            out[base + 5] = 1.0 if (ethereal or exhausts) else 0.0
        # 空槽已为 0
    return out


def _count_type_ratio(pile: List[Dict], card_type: str) -> float:
    """统计牌堆中某类型的占比"""
    if not pile:
        return 0.0
    count = sum(1 for c in pile if (c.get("type") or "").lower() == card_type)
    return count / len(pile)


def _count_status_curse_ratio(pile: List[Dict]) -> float:
    if not pile:
        return 0.0
    count = sum(
        1
        for c in pile
        if (c.get("type") or "").lower() in ("status", "curse")
    )
    return count / len(pile)


def _encode_block3_draw_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 3：抽牌堆 279 维（multi-hot 271 + 类型占比 8）"""
    out = np.zeros(279, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    draw_pile = cs.get("draw_pile") or []
    discard_pile = cs.get("discard_pile") or []

    for card in draw_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1

    out[271] = _count_type_ratio(draw_pile, "attack")
    out[272] = _count_type_ratio(draw_pile, "skill")
    out[273] = _count_type_ratio(draw_pile, "power")
    out[274] = _count_status_curse_ratio(draw_pile)
    out[275] = _count_type_ratio(discard_pile, "attack")
    out[276] = _count_type_ratio(discard_pile, "skill")
    out[277] = _count_type_ratio(discard_pile, "power")
    out[278] = _count_status_curse_ratio(discard_pile)
    return out


def _encode_block4_discard_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 4：弃牌堆 271 维"""
    out = np.zeros(271, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    discard_pile = cs.get("discard_pile") or []
    for card in discard_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1
    return out


def _encode_block5_exhaust_pile(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 5：消耗堆 271 维"""
    out = np.zeros(271, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    exhaust_pile = cs.get("exhaust_pile") or []
    for card in exhaust_pile:
        cid = card.get("id") or card.get("name") or ""
        idx = card_id_to_index(cid)
        if 0 <= idx < CARD_DIM:
            out[idx] += 1
    return out


def _encode_block6_player_powers(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 6：玩家 Powers 80 维"""
    out = np.zeros(80, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    player = cs.get("player") or {}
    powers = player.get("powers") or []
    for p in powers:
        pid = p.get("id") or p.get("name") or ""
        idx = power_id_to_index(pid)
        if 0 <= idx < POWER_DIM:
            out[idx] += p.get("amount", 0)
    return out


def _encode_block7_monsters(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 7：怪物 300 维（6×50）"""
    out = np.zeros(300, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    monsters: List[Dict] = cs.get("monsters") or []
    for m in range(6):
        base = m * 50
        if m >= len(monsters):
            continue
        mon = monsters[m]
        chp = mon.get("current_hp", 0)
        mhp = max(mon.get("max_hp", 1), 1)
        out[base + 0] = _clamp_norm(chp, mhp)
        out[base + 1] = _clamp_norm(min(mon.get("block", 0), MAX_BLOCK), MAX_BLOCK)

        intent_str = mon.get("intent") or ""
        intent_idx = intent_to_index(intent_str)
        if 0 <= intent_idx < INTENT_DIM:
            out[base + 2 + intent_idx] = 1.0

        adj = mon.get("move_adjusted_damage", 0) or 0
        hits = mon.get("move_hits", 1) or 1
        dmg = max(0, adj * hits)
        out[base + 15] = _clamp_norm(min(dmg, MAX_DAMAGE), MAX_DAMAGE)
        out[base + 16] = 0.0 if mon.get("is_gone", False) else 1.0
        out[base + 17] = 1.0 if mon.get("half_dead", False) else 0.0

        mpowers = mon.get("powers") or []
        out[base + 18] = _clamp_norm(min(parse_strength(mpowers), 30), 30)
        out[base + 19] = _clamp_norm(min(parse_vulnerable(mpowers), MAX_DEBUFF), MAX_DEBUFF)
        out[base + 20] = _clamp_norm(min(parse_weak(mpowers), MAX_DEBUFF), MAX_DEBUFF)
        out[base + 21] = _clamp_norm(min(parse_poison(mpowers), 99), 99)
        out[base + 22] = _clamp_norm(min(parse_curl_up(mpowers), 10), 10)

        mid = mon.get("id") or mon.get("name") or ""
        h = int(hashlib.md5(mid.encode()).hexdigest(), 16) % 1000
        out[base + 23] = h / 1000.0
        # base+24 ~ base+49 预留，填 0
    return out


def _encode_block8_relics(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 8：遗物 180 维"""
    out = np.zeros(180, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    relics = gs.get("relics") or []
    for r in relics:
        rid = r.get("id") or r.get("name") or ""
        idx = relic_id_to_index(rid)
        if 0 <= idx < RELIC_DIM:
            out[idx] += 1
    return out


def _encode_block9_potions(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 9：药水 65 维（multi-hot 45 + 每槽 4 维×5）"""
    out = np.zeros(65, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    potions = gs.get("potions") or []
    for p in potions:
        pid = p.get("id") or p.get("name") or ""
        idx = potion_id_to_index(pid)
        if 0 <= idx < POTION_DIM:
            out[idx] += 1
    for i in range(5):
        base = 45 + i * 4
        if i < len(potions):
            pot = potions[i]
            out[base + 0] = 1.0 if pot.get("can_use", False) else 0.0
            out[base + 1] = 1.0 if pot.get("can_discard", False) else 0.0
            out[base + 2] = 1.0 if pot.get("requires_target", False) else 0.0
            out[base + 3] = 1.0
        else:
            out[base + 3] = 0.0
    return out


def _encode_block10_global(mod_response: Dict[str, Any]) -> np.ndarray:
    """区块 10：全局 43 维"""
    out = np.zeros(43, dtype=np.float32)
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

    phase = (gs.get("room_phase") or gs.get("screen_type") or "").upper()
    phase_map = {
        "COMBAT": 4,
        "EVENT": 5,
        "MAP": 6,
        "SHOP": 7,
        "REST": 8,
        "BOSS": 9,
        "NONE": 10,
        "CARD_REWARD": 11,
    }
    idx = phase_map.get(phase, 12)
    out[idx] = 1.0

    out[13] = 1.0 if "play" in cmds else 0.0
    out[14] = 1.0 if "end" in cmds else 0.0
    out[15] = 1.0 if "choose" in cmds else 0.0
    out[16] = 1.0 if "proceed" in cmds else 0.0
    out[17] = 1.0 if "potion" in cmds else 0.0
    out[18] = _clamp_norm(min(len(options), 60), 60)
    # 19-42 预留
    return out


def encode(mod_response: Dict[str, Any]) -> np.ndarray:
    """
    把 Mod 一帧的 JSON 转成 1840 维向量 s。

    与 Mod 日志互通：mod_response 为 Mod 返回的整帧，
    含 game_state、combat_state、available_commands 等。
    缺失 combat_state 时，区块 2-9 填 0。
    """
    s = np.zeros(OUTPUT_DIM, dtype=np.float32)
    gs = mod_response.get("game_state") or {}
    has_combat = bool(gs.get("combat_state"))

    b1 = _encode_block1_player_core(mod_response)
    s[0:20] = b1

    if has_combat:
        b2 = _encode_block2_hand(mod_response)
        b3 = _encode_block3_draw_pile(mod_response)
        b4 = _encode_block4_discard_pile(mod_response)
        b5 = _encode_block5_exhaust_pile(mod_response)
        b6 = _encode_block6_player_powers(mod_response)
        b7 = _encode_block7_monsters(mod_response)
        s[20:351] = b2
        s[351:630] = b3
        s[630:901] = b4
        s[901:1172] = b5
        s[1172:1252] = b6
        s[1252:1552] = b7
    # 非战斗时 20:1552 保持为 0

    b8 = _encode_block8_relics(mod_response)
    b9 = _encode_block9_potions(mod_response)
    b10 = _encode_block10_global(mod_response)
    s[1552:1732] = b8
    s[1732:1797] = b9
    s[1797:1840] = b10

    return s


def get_output_dim() -> int:
    """返回 1840"""
    return OUTPUT_DIM


class StateEncoder:
    """
    状态编码器包装类 - 供 sts_env、rl_agent 等使用

    将 GameState 转为 1840 维观察向量。
    mode 参数保留以兼容旧接口，当前仅支持 extended（1840 维）。
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
