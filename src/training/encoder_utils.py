#!/usr/bin/env python3
"""
Encoder 工具：ID 归一化 + 查表

把 Mod 日志里的 id 转成 encoder_ids.yaml 里的编号，供 encoder 用。
与 Mod 日志数据互通：支持 Mod 发送的各种 id 格式（空格/下划线、大小写）。
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_IDS_PATH = _PROJECT_ROOT / "configs" / "encoder_ids.yaml"

# 从 encoder_dims 导入维度常量（统一来源）
# 防止维度不一致问题
try:
    from src.training.encoder_dims import (
        CARD_DIM, RELIC_DIM, POTION_DIM, POWER_DIM, INTENT_DIM, MONSTER_DIM,
        ORB_TYPE_DIM, EVENT_DIM, ROOM_SUBTYPE_DIM, CARD_TYPE_DIM
    )
except ImportError:
    # 如果导入失败，使用备用定义
    CARD_DIM = 144
    RELIC_DIM = 180
    POTION_DIM = 45
    POWER_DIM = 80
    INTENT_DIM = 13
    MONSTER_DIM = 75
    ORB_TYPE_DIM = 5
    EVENT_DIM = 50
    ROOM_SUBTYPE_DIM = 15
    CARD_TYPE_DIM = 5

# 懒加载
_card_id_to_index: Optional[Dict[str, int]] = None
_relic_id_to_index: Optional[Dict[str, int]] = None
_potion_id_to_index: Optional[Dict[str, int]] = None
_power_id_to_index: Optional[Dict[str, int]] = None
_intent_to_index: Optional[Dict[str, int]] = None
_monster_id_to_index: Optional[Dict[str, int]] = None


def _load_ids() -> dict:
    """加载 encoder_ids.yaml"""
    with open(_IDS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_id(raw: str) -> str:
    """
    ID 归一化：忽略大小写、空格↔下划线互换。

    Args:
        raw: Mod 发送的原始 ID（如 "Blade Dance" 或 "Blade_Dance"）

    Returns:
        归一化后的 ID，用于查表
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = raw.strip().lower()
    # 空格与下划线统一为下划线
    s = re.sub(r"[\s_]+", "_", s)
    return s


def _build_card_id_to_index() -> Dict[str, int]:
    """构建 card_id -> index 字典"""
    data = _load_ids()
    cards: List[str] = data.get("cards", [])
    result = {}
    for idx, cid in enumerate(cards):
        if cid:
            norm = normalize_id(cid)
            if norm and norm not in result:
                result[norm] = idx
    return result


def card_id_to_index(card_id: str) -> int:
    """
    卡牌 id 查编号：0~270。找不到或超出容量返回 0（UNKNOWN）。
    与 Mod 日志互通：Mod 发送 id/name 均可，归一化后查表。
    """
    global _card_id_to_index
    if _card_id_to_index is None:
        _card_id_to_index = _build_card_id_to_index()
    norm = normalize_id(card_id)
    idx = _card_id_to_index.get(norm, 0)
    return idx if 0 <= idx < CARD_DIM else 0


def _build_relic_id_to_index() -> Dict[str, int]:
    """构建 relic_id -> index 字典"""
    data = _load_ids()
    relics: List[str] = data.get("relics", [])
    result = {}
    for idx, rid in enumerate(relics):
        if rid:
            norm = normalize_id(rid)
            if norm and norm not in result:
                result[norm] = idx
    return result


def relic_id_to_index(relic_id: str) -> int:
    """
    遗物 id 查编号：0~179。找不到返回 0（UNKNOWN）。
    Mod 可能发送 "Ring of the Snake" 或 "RingoftheSnake"，归一化后查表。
    """
    global _relic_id_to_index
    if _relic_id_to_index is None:
        _relic_id_to_index = _build_relic_id_to_index()
    norm = normalize_id(relic_id)
    idx = _relic_id_to_index.get(norm, 0)
    return idx if 0 <= idx < RELIC_DIM else 0


def _build_potion_id_to_index() -> Dict[str, int]:
    """构建 potion_id -> index 字典"""
    data = _load_ids()
    potions: List[str] = data.get("potions", [])
    result = {}
    for idx, pid in enumerate(potions):
        if pid:
            norm = normalize_id(pid)
            if norm and norm not in result:
                result[norm] = idx
    return result


def potion_id_to_index(potion_id: str) -> int:
    """
    药水 id 查编号：0~44。找不到返回 0（UNKNOWN）。
    Mod 可能发送 "LiquidMemories" 或 "Liquid Memories"。
    """
    global _potion_id_to_index
    if _potion_id_to_index is None:
        _potion_id_to_index = _build_potion_id_to_index()
    norm = normalize_id(potion_id)
    idx = _potion_id_to_index.get(norm, 0)
    return idx if 0 <= idx < POTION_DIM else 0


def _build_power_id_to_index() -> Dict[str, int]:
    """构建 power_id -> index 字典"""
    data = _load_ids()
    powers: List[str] = data.get("powers", [])
    result = {}
    for idx, pid in enumerate(powers):
        if pid:
            norm = normalize_id(pid)
            if norm and norm not in result:
                result[norm] = idx
    return result


def power_id_to_index(power_id: str) -> int:
    """
    Power id 查编号：0~79。找不到返回 0（UNKNOWN）。
    Mod 发送如 "Anger", "Curl Up", "Vulnerable"。
    """
    global _power_id_to_index
    if _power_id_to_index is None:
        _power_id_to_index = _build_power_id_to_index()
    norm = normalize_id(power_id)
    idx = _power_id_to_index.get(norm, 0)
    return idx if 0 <= idx < POWER_DIM else 0


def _build_intent_to_index() -> Dict[str, int]:
    """构建 intent -> index 字典"""
    data = _load_ids()
    intents: List[str] = data.get("intents", [])
    result = {}
    for idx, iid in enumerate(intents):
        if iid:
            norm = normalize_id(iid)
            if norm and norm not in result:
                result[norm] = idx
    return result


def intent_to_index(intent: str) -> int:
    """
    意图 intent 查编号：0~12。找不到返回 0（UNKNOWN）。
    Mod 发送如 "ATTACK", "ATTACK_BUFF"。
    """
    global _intent_to_index
    if _intent_to_index is None:
        _intent_to_index = _build_intent_to_index()
    norm = normalize_id(intent)
    idx = _intent_to_index.get(norm, 0)
    return idx if 0 <= idx < INTENT_DIM else 0


def _build_monster_id_to_index() -> Dict[str, int]:
    """构建 monster_id -> index 字典"""
    data = _load_ids()
    monsters: List[str] = data.get("monsters", [])
    result = {}
    for idx, mid in enumerate(monsters):
        if mid:
            norm = normalize_id(mid)
            if norm and norm not in result:
                result[norm] = idx
    return result


def monster_id_to_index(monster_id: str) -> int:
    """
    怪物 id 查编号：0~74。找不到返回 0（UNKNOWN）。
    Mod 发送如 "SpikeSlime_S", "Cultist"。
    """
    global _monster_id_to_index
    if _monster_id_to_index is None:
        _monster_id_to_index = _build_monster_id_to_index()
    norm = normalize_id(monster_id)
    idx = _monster_id_to_index.get(norm, 0)
    return idx if 0 <= idx < MONSTER_DIM else 0


# ========== 球类型映射 (Orb Types) ==========
# 固定映射，不需要从 yaml 读取
_ORB_TYPE_MAP = {
    "frost": 0,      # 冰球
    "lightning": 1,  # 雷球
    "plasma": 2,     # 火球
    "dark": 3,       # 暗球
    "chaos": 4,      # 混沌球（观者）
    "empty": 0,      # 空槽映射到未知
}


def orb_type_to_index(orb_type: str) -> int:
    """
    球类型转编号：0~4。
    Mod 发送如 "Frost", "Lightning", "Plasma", "Dark", "Chaos"。
    """
    norm = normalize_id(orb_type)
    return _ORB_TYPE_MAP.get(norm, 0)


# ========== 事件 ID 映射 ==========
_event_id_to_index: Optional[Dict[str, int]] = None


def _build_event_id_to_index() -> Dict[str, int]:
    """构建 event_id -> index 字典"""
    data = _load_ids()
    events: List[str] = data.get("events", [])
    result = {}
    for idx, eid in enumerate(events):
        if eid:
            norm = normalize_id(eid)
            if norm and norm not in result:
                result[norm] = idx
    return result


def event_id_to_index(event_id: str) -> int:
    """
    事件 id 查编号：0~EVENT_DIM-1。找不到返回 0（UNKNOWN）。
    Mod 发送事件名，如 "The Shrine", "Big Fish"。
    """
    global _event_id_to_index
    if _event_id_to_index is None:
        _event_id_to_index = _build_event_id_to_index()
    norm = normalize_id(event_id)
    idx = _event_id_to_index.get(norm, 0)
    return idx if 0 <= idx < EVENT_DIM else 0


# ========== 房间细分类型映射 ==========
# 固定映射，不需要从 yaml 读取
_ROOM_SUBTYPE_MAP = {
    # 怪物房
    "monster_normal": 0,    # 普通怪物房
    "monster_elite": 1,     # 精英房
    "monster_boss": 2,      # Boss房
    # 休息室
    "rest_normal": 3,       # 普通休息室（火堆）
    "rest_fire": 4,         # 升级火堆
    "rest_massage": 5,      # 按摩
    "rest_match": 6,        # 举重
    # 商店
    "shop": 7,              # 商店
    # 事件房
    "event": 8,             # 普通事件
    "event_shrine": 9,      # 祭坛事件
    # 其他
    "treasure": 10,         # 宝箱房
    "super_secret": 11,     # 超级秘密房
    "secret": 12,           # 秘密房
    "none": 13,             # 无房间类型
    "unknown": 13,          # 未知
}


def room_subtype_to_index(subtype: str) -> int:
    """
    房间细分类型转编号：0~13。
    根据 room_phase 和其他信息综合判断。
    """
    norm = normalize_id(subtype)
    return _ROOM_SUBTYPE_MAP.get(norm, 13)


# ========== 怪物类型判断 ==========
# 完整的 Boss ID 列表（用于判断怪物类型）
_BOSS_IDS = {
    "slimeboss", "guardian", "hexaghost", "bronzeautomaton",
    "collector", "champ", "awakenedone", "timeeater",
    "donu", "deca", "heart", "corrupt", "spire",
    "theguardian", "thecollector", "thechamp", "theawakenedone",
    "thetimeeater", "corruptheart", "spireshield", "spirespear",
}

# 完整的精英 ID 列表
_ELITE_IDS = {
    "gremlinnob", "lagavulin", "bookofstabbing",
    "gremlinleader", "slaverboss", "gianthead",
    "nemesis", "reptomancer",
}


def get_monster_type(monster_id: str) -> int:
    """
    根据怪物 ID 判断类型：0=普通, 1=精英, 2=Boss

    Args:
        monster_id: 怪物 ID（会自动归一化）

    Returns:
        int: 0=普通, 1=精英, 2=Boss
    """
    mid_lower = normalize_id(monster_id)

    # 检查是否是 Boss
    if any(boss in mid_lower for boss in _BOSS_IDS):
        return 2

    # 检查是否是精英
    if any(elite in mid_lower for elite in _ELITE_IDS):
        return 1

    return 0


# ========== 卡牌类型映射 ==========
_CARD_TYPE_MAP = {
    "attack": 0,
    "skill": 1,
    "power": 2,
    "status": 3,
    "curse": 4,
}


def card_type_to_index(card_type: str) -> int:
    """
    卡牌类型转编号：0~4。
    Mod 发送如 "Attack", "Skill", "Power", "Status", "Curse"。
    """
    norm = normalize_id(card_type)
    return _CARD_TYPE_MAP.get(norm, 0)


# ========== 卡牌稀有度映射 ==========
_RARITY_MAP = {
    "basic": 0,
    "common": 1,
    "uncommon": 2,
    "rare": 3,
    "special": 4,
}


def card_rarity_to_index(rarity: str) -> int:
    """
    卡牌稀有度转编号：0~4。
    Mod 发送如 "BASIC", "COMMON", "UNCOMMON", "RARE", "SPECIAL"。
    """
    norm = normalize_id(rarity)
    return _RARITY_MAP.get(norm, 1)  # 默认为 COMMON
