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
POISON_IDS = {"poison"}  # 中毒（怪物）
CURL_UP_IDS = {"curl_up"}  # 蜷缩（怪物）

# 新增 V2
RITUAL_IDS = {"ritual"}  # Ritual 力量累积
ARTIFACT_IDS = {"artifact"}  # Artifact 法术护盾
REGEN_IDS = {"regeneration", "regen"}  # Regen 再生
ANGRY_IDS = {"anger"}  # Angry 怒气
THORNS_IDS = {"thorns"}  # Thorns 反伤
PLATED_ARMOR_IDS = {"plated_armor"}  # Plated Armor 板甲
MINION_IDS = {"minion"}  # Minion 小怪标记
SHACKLED_IDS = {"shackled"}  # Shackled 束缚
CHOKED_IDS = {"choked"}  # Choked 窒息
CONSTRICTED_IDS = {"constricted"}  # Constricted 收缩
ENTANGLED_IDS = {"entangled"}  # Entangled 纠缠
HEX_IDS = {"hex"}  # Hex 诅咒
DRAW_REDUCTION_IDS = {"draw_reduction", "drawreduction"}  # 抽牌减少
SLOW_IDS = {"slow"}  # Slow 缓慢
NO_DRAW_IDS = {"no_draw"}  # No Draw 无法抽牌
NO_BLOCK_IDS = {"no_block"}  # No Block 无法获得护甲
INTANGIBLE_IDS = {"intangible"}  # Intangible 虚无/无实体
BUFFER_IDS = {"buffer"}  # Buffer 缓冲
EVOLVE_IDS = {"evolve"}  # Evolve 进化
COMBUST_IDS = {"combust"}  # Combust 燃烧
CORPSE_EXPLOSION_IDS = {"corpse_explosion"}  # 尸体爆炸
FEEL_NO_PAIN_IDS = {"feel_no_pain"}  # 不知疼痛
JUGGERNAUT_IDS = {"juggernaut"}  # 刚毅
AFTER_IMAGE_IDS = {"after_image"}  # 残影
DARK_EMBRACE_IDS = {"dark_embrace"}  # 黑暗拥抱
CORRUPTION_IDS = {"corruption"}  # 腐化
DEMON_FORM_IDS = {"demon_form"}  # 恶魔形态
LIMIT_BREAK_IDS = {"limit_break"}  # 突破极限
BARRICADE_IDS = {"barricade"}  # 路障
BERSERK_IDS = {"berserk"}  # 狂暴
ENTRENCH_IDS = {"entrench"}  # 深挖
METALLICIZE_IDS = {"metallicize"}  # 金属化
TEMPORARY_CP_IDS = {"temporary_cp"}  # 临时集中力（观者）


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


def parse_poison(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析中毒层数（玩家或怪物）"""
    return _sum_power_amounts(powers, POISON_IDS)


def parse_curl_up(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析蜷缩层数（怪物）"""
    return _sum_power_amounts(powers, CURL_UP_IDS)


# ========== 新增 V2 解析函数 ==========

def parse_ritual(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Ritual 层数（力量累积）"""
    return _sum_power_amounts(powers, RITUAL_IDS)


def parse_artifact(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Artifact 层数（法术护盾，防止 debuff）"""
    return _sum_power_amounts(powers, ARTIFACT_IDS)


def parse_regen(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Regen 层数（再生，回合末回血）"""
    return _sum_power_amounts(powers, REGEN_IDS)


def parse_angry(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Angry 层数（怒气，受击时获得力量）"""
    return _sum_power_amounts(powers, ANGRY_IDS)


def parse_thorns(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Thorns 层数（反伤）"""
    return _sum_power_amounts(powers, THORNS_IDS)


def parse_plated_armor(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Plated Armor 层数（板甲）"""
    return _sum_power_amounts(powers, PLATED_ARMOR_IDS)


def parse_shackled(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Shackled 层数（束缚，减少能量）"""
    return _sum_power_amounts(powers, SHACKLED_IDS)


def parse_choked(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Choked 层数（窒息，回合末伤害）"""
    return _sum_power_amounts(powers, CHOKED_IDS)


def parse_constricted(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Constricted 层数（收缩，抽牌减少）"""
    return _sum_power_amounts(powers, CONSTRICTED_IDS)


def parse_entangled(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Entangled 层数（纠缠，无法攻击）"""
    return _sum_power_amounts(powers, ENTANGLED_IDS)


def parse_hex(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Hex 层数（诅咒）"""
    return _sum_power_amounts(powers, HEX_IDS)


def parse_draw_reduction(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Draw Reduction 层数（抽牌减少）"""
    return _sum_power_amounts(powers, DRAW_REDUCTION_IDS)


def parse_slow(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Slow 层数（缓慢）"""
    return _sum_power_amounts(powers, SLOW_IDS)


def parse_no_draw(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 No Draw 层数（无法抽牌，返回层数）"""
    return _sum_power_amounts(powers, NO_DRAW_IDS)


def parse_no_block(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 No Block 层数（无法获得护甲）"""
    return _sum_power_amounts(powers, NO_BLOCK_IDS)


def parse_intangible(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Intangible 层数（虚无/无实体，伤害-1）"""
    return _sum_power_amounts(powers, INTANGIBLE_IDS)


def parse_buffer(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Buffer 层数（缓冲）"""
    return _sum_power_amounts(powers, BUFFER_IDS)


def parse_evolve(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Evolve 层数（进化）"""
    return _sum_power_amounts(powers, EVOLVE_IDS)


def parse_combust(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Combust 层数（燃烧）"""
    return _sum_power_amounts(powers, COMBUST_IDS)


def parse_corpse_explosion(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Corpse Explosion 层数（尸体爆炸）"""
    return _sum_power_amounts(powers, CORPSE_EXPLOSION_IDS)


def parse_feel_no_pain(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Feel No Pain 层数（不知疼痛）"""
    return _sum_power_amounts(powers, FEEL_NO_PAIN_IDS)


def parse_juggernaut(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Juggernaut 层数（刚毅）"""
    return _sum_power_amounts(powers, JUGGERNAUT_IDS)


def parse_after_image(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 After Image 层数（残影）"""
    return _sum_power_amounts(powers, AFTER_IMAGE_IDS)


def parse_dark_embrace(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Dark Embrace 层数（黑暗拥抱）"""
    return _sum_power_amounts(powers, DARK_EMBRACE_IDS)


def parse_corruption(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Corruption 层数（腐化）"""
    return _sum_power_amounts(powers, CORRUPTION_IDS)


def parse_barricade(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Barricade 层数（路障，护甲不消失）"""
    return _sum_power_amounts(powers, BARRICADE_IDS)


def parse_berserk(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Berserk 层数（狂暴）"""
    return _sum_power_amounts(powers, BERSERK_IDS)


def parse_metallicize(powers: List[Dict[str, Any]]) -> int:
    """从 powers 解析 Metallicize 层数（金属化）"""
    return _sum_power_amounts(powers, METALLICIZE_IDS)
