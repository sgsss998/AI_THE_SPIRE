#!/usr/bin/env python3
"""
Power 解析：从 player.powers 里把力量、虚弱、易伤等数值扒出来

Mod 不直接给 strength、weak、vulnerable 这些，得从 powers 列表里找对应 id 的 amount 加起来。
"""
from typing import List, Dict, Any

from src.training.encoder_utils import normalize_id

# Power 的 id（Mod 原字）→ 解析成啥
STRENGTH_IDS = {"strength", "anger", "flex", "ritual", "inflame", "spot_weakness", "limit_break", "demon_form"}  # 力量
DEXTERITY_IDS = {"dexterity", "footwork"}  # 敏捷
WEAK_IDS = {"weakened", "weak"}  # 虚弱
VULNERABLE_IDS = {"vulnerable"}  # 易伤
FRAIL_IDS = {"frail"}  # 脆弱
FOCUS_IDS = {"bias", "focus"}  # 集中（缺陷用）


def _sum_power_amounts(powers: List[Dict[str, Any]], target_ids: set) -> int:
    """对 powers 中 id 在 target_ids 内的 amount 求和"""
    total = 0
    for p in powers or []:
        pid = p.get("id") or p.get("name", "")
        if normalize_id(pid) in target_ids:
            total += p.get("amount", 0)
    return total


def parse_strength(powers: List[Dict[str, Any]]) -> int:
    """从 player.powers 解析力量值"""
    return _sum_power_amounts(powers, STRENGTH_IDS)


def parse_dexterity(powers: List[Dict[str, Any]]) -> int:
    """从 player.powers 解析敏捷值"""
    return _sum_power_amounts(powers, DEXTERITY_IDS)


def parse_weak(powers: List[Dict[str, Any]]) -> int:
    """从 player.powers 解析虚弱层数"""
    return _sum_power_amounts(powers, WEAK_IDS)


def parse_vulnerable(powers: List[Dict[str, Any]]) -> int:
    """从 player.powers 解析易伤层数"""
    return _sum_power_amounts(powers, VULNERABLE_IDS)


def parse_frail(powers: List[Dict[str, Any]]) -> int:
    """从 player.powers 解析脆弱层数"""
    return _sum_power_amounts(powers, FRAIL_IDS)


def parse_focus(powers: List[Dict[str, Any]]) -> int:
    """从 player.powers 解析集中值（缺陷角色）"""
    return _sum_power_amounts(powers, FOCUS_IDS)
