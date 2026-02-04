#!/usr/bin/env python3
"""
Encoder V2 工具：ID 归一化 + 查表

把 Mod 日志里的 id 转成 encoder_v2_ids.yaml 里的编号，供编码用。
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_IDS_PATH = _PROJECT_ROOT / "configs" / "encoder_v2_ids.yaml"

# 懒加载
_card_id_to_index: Optional[Dict[str, int]] = None


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
    卡牌 id 查编号：0~199。找不到就返回 0（UNKNOWN 未知卡）。
    """
    global _card_id_to_index
    if _card_id_to_index is None:
        _card_id_to_index = _build_card_id_to_index()
    norm = normalize_id(card_id)
    return _card_id_to_index.get(norm, 0)
