#!/usr/bin/env python3
"""
Encoder V2 工具：ID 归一化 + 查表

把 Mod 日志里的 id 转成 encoder_v2_ids.yaml 里的编号，供编码用。
与 Mod 日志数据互通：支持 Mod 发送的各种 id 格式（空格/下划线、大小写）。
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_IDS_PATH = _PROJECT_ROOT / "configs" / "encoder_v2_ids.yaml"

# 穷尽维度（与 Mod 日志互通，索引超出时映射到 0）
CARD_DIM = 271
RELIC_DIM = 180
POTION_DIM = 45
POWER_DIM = 80
INTENT_DIM = 13

# 懒加载
_card_id_to_index: Optional[Dict[str, int]] = None
_relic_id_to_index: Optional[Dict[str, int]] = None
_potion_id_to_index: Optional[Dict[str, int]] = None
_power_id_to_index: Optional[Dict[str, int]] = None
_intent_to_index: Optional[Dict[str, int]] = None


def _load_ids() -> dict:
    """加载 encoder_v2_ids.yaml"""
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
