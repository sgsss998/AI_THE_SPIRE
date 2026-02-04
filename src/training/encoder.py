#!/usr/bin/env python3
"""
扩展的状态编码器

将游戏状态编码为固定维度的向量，用于 ML/RL 模型。
支持简单模式（30维）和扩展模式（~180维）。
"""
import numpy as np
from typing import Dict, List, Any, Optional, Set

from src.core.game_state import (
    GameState, Card, CardType, Monster, IntentType, CombatState, RoomPhase
)


class StateEncoder:
    """
    扩展的状态编码器

    支持两种模式：
    - simple: 30维（基础版本，兼容旧版）
    - extended: ~180维（完整版本，支持所有游戏场景）
    """

    # ========== 常见遗物列表（前30个） ==========
    COMMON_RELICS = [
        # 通用遗物
        "anchor", "bag_of_preparation", "bell", "blood_vial", "busted_crown",
        "captor_ring", "ceramic_fish", "chemical_x", "cursed_key", "dream_catcher",
        "ectoplasm", "enchaved_coffee", "fire_breathing", "frozen_egg", "frozen_eye",
        "gambling_chip", "golden_eye", "greedy_hat", "hand_drill", "incense_burner",
        "ingot", "lantern", "lice", "matryoshka", "meat_bucket", "mjolnir",
        "monkey_paw", "odd_mushroom", "old_coin", "orange_pellets", "paper_frog",
        # 静默遗物
        "ring_of_the_snake", "kunai", "footwear", "nanowand", "shuriken",
        # 铁甲遗物
        "burning_blood", "cracked_core", "vajra",
    ]

    # ========== 卡牌池（扩展） ==========
    ALL_CARD_IDS = [
        # 铁甲战士
        'Strike_R', 'Strike_G', 'Strike_B',
        'Defend_R', 'Defend_G', 'Defend_B',
        'Bash', 'Cleave', 'Iron_Wave', 'Pommel_Strike',
        'Shrug_It_Off', 'Shield_Bash', 'Disarm', 'Iron_Wave',
        # 静默
        'Neutralize', 'Survivor', 'Backflip', 'Blade_Dance',
        'Deadly_Poison', 'All', 'Catalyze', 'Cloak_And_Dagger',
        'Dagger_Throw', 'Dodge_And_Roll', 'Flying_Knee', 'Footwork',
        'Outmaneuver', 'Poison_Stab', 'Precision', 'Prepared',
        'Slice', 'Sneaky_Strike', 'Sucker_Punch', 'Tesla_Coil',
        'Acrobatics', 'Adrenaline', 'Bane', 'Blade_Dance',
        'Bouncing_Flask', 'Bullet_Time', 'Burst', 'Calculated_Gamble',
        'Choke', 'Cloak_And_Dagger', 'Deadly_Poison', 'Deflect',
        'Dodge_And_Roll', 'Escape_Plan', 'Expertise', 'Finisher',
        'Flechettes', 'Flying_Knee', 'Footwork', 'Ghostly_Wield',
        'Grand_Finish', 'Heel_Hook', 'Infinite_Blades', 'Leg_Sweep',
        'Malaise', 'Masterful_Stab', 'Maven', 'No_Sleep',
        'Phantasmal_Killer', 'Predatory_Strike', 'Prepare', 'Quick_Play',
        'Riddle_With_Holes', 'Riddle_With_Hags', 'Rip_And_Tear', 'Security',
        'Setup', 'Shiv', 'Slice', 'Sly_Witness',
        'Smokescreen', 'Storm_Of_Steel', 'Sucker_Punch', 'Survivor',
        'Tactician', 'Technomancer', 'Thief', 'Trip',
        'Unload', 'Venomology', 'Vorpal_Strike', 'Weave',
        # 缺陷
        'Strike_D', 'Defend_D',
    ]

    # ========== 敌人意图 ==========
    INTENT_TYPES = ['ATTACK', 'DEFEND', 'BUFF', 'DEBUFF', 'ATTACK_BUFF', 'ATTACK_DEBUFF', 'UNKNOWN', 'NONE']

    # ========== 最大值 ==========
    MAX_MONSTERS = 6  # 史莱姆Boss分裂后最多6个
    MAX_HP = 999
    MAX_BLOCK = 50
    MAX_ENERGY = 10
    MAX_GOLD = 999
    MAX_POWER = 30
    MAX_FOCUS = 10
    MAX_HAND_SIZE = 10

    def __init__(self, mode: str = "extended"):
        """
        初始化编码器

        Args:
            mode: "simple" (30维) 或 "extended" (~180维)
        """
        self.mode = mode
        if mode == "simple":
            self.output_dim = 30
        else:
            # 计算扩展模式的总维度
            self.output_dim = self._calculate_extended_dim()

    def _calculate_extended_dim(self) -> int:
        """计算扩展模式的维度"""
        dim = 0
        # 手牌基础编码（卡牌池 one-hot）
        dim += len(self.ALL_CARD_IDS)  # ~90 维
        # 手牌详细信息
        dim += self.MAX_HAND_SIZE * 3  # cost + type + playable
        # 玩家状态
        dim += 15  # HP/block/energy/gold/power/etc
        # 怪物信息
        dim += self.MAX_MONSTERS * 10  # 6个怪物 × 10维
        # 遗物
        dim += len(self.COMMON_RELICS)  # 30 维
        # 牌库信息
        dim += 10
        # 房间信息
        dim += 5
        # 药水信息
        dim += 5
        return dim

    def encode_state(self, state: GameState) -> np.ndarray:
        """
        编码游戏状态

        Args:
            state: GameState 对象

        Returns:
            编码后的向量
        """
        if self.mode == "simple":
            return self._encode_simple(state)
        else:
            return self._encode_extended(state)

    def _encode_simple(self, state: GameState) -> np.ndarray:
        """简单编码（30维，兼容旧版）"""
        if state.combat is None:
            return np.zeros(30, dtype=np.float32)

        combat = state.combat

        # 静默默认卡牌
        SILENT_CARD_IDS = [
            'Strike_R', 'Strike_G', 'Strike_B',
            'Defend_R', 'Defend_G', 'Defend_B',
            'Neutralize', 'Survivor', 'Bash',
            'Backflip', 'Blade Dance', 'Deadly Poison', 'All',
        ]

        # 手牌编码（静默默认牌）
        hand_encoding = np.zeros(12, dtype=np.float32)
        for card in combat.hand:
            if card.id in SILENT_CARD_IDS:
                idx = SILENT_CARD_IDS.index(card.id)
                hand_encoding[idx] += 1

        # 其他信息
        hand_count = min(len(combat.hand), 10)
        energy = combat.player.energy
        player_hp = self._normalize_hp(combat.player.current_hp, combat.player.max_hp)
        player_block = min(combat.player.block, 20) / 20.0

        # 怪物编码（第一个活着的怪物）
        living = [m for m in combat.monsters if m.is_alive]
        if living:
            monster = living[0]
            monster_hp = self._normalize_hp(monster.current_hp, monster.max_hp)
            intent = self._encode_intent_simple(monster.intent)
        else:
            monster_hp = 0.0
            intent = np.zeros(5, dtype=np.float32)

        # 拼接
        encoding = np.concatenate([
            hand_encoding,
            [hand_count, energy, player_hp, player_block, monster_hp],
            intent,
        ])

        # 填充到30维
        if len(encoding) < 30:
            padded = np.zeros(30, dtype=np.float32)
            padded[:len(encoding)] = encoding
            return padded
        return encoding[:30].astype(np.float32)

    def _encode_extended(self, state: GameState) -> np.ndarray:
        """扩展编码（~180维）"""
        parts = []

        # 1. 手牌基础编码（卡牌池 one-hot）
        hand_base = self._encode_hand_base(state.combat)
        parts.append(hand_base)

        # 2. 手牌详细信息
        hand_detail = self._encode_hand_detail(state.combat)
        parts.append(hand_detail)

        # 3. 玩家状态
        player_state = self._encode_player_state(state)
        parts.append(player_state)

        # 4. 怪物信息（6个怪物 × 10维）
        monster_state = self._encode_monsters_extended(state.combat)
        parts.append(monster_state)

        # 5. 遗物编码
        relics = self._encode_relics(state)
        parts.append(relics)

        # 6. 牌库信息
        deck = self._encode_deck_info(state.combat)
        parts.append(deck)

        # 7. 房间信息
        room = self._encode_room_info(state)
        parts.append(room)

        # 8. 药水信息
        potions = self._encode_potions(state.combat)
        parts.append(potions)

        # 拼接所有部分
        encoding = np.concatenate(parts)

        # 填充或截断到目标维度
        return self._pad_or_truncate(encoding)

    def _encode_hand_base(self, combat: Optional[CombatState]) -> np.ndarray:
        """手牌基础编码（卡牌池 one-hot）"""
        encoding = np.zeros(len(self.ALL_CARD_IDS), dtype=np.float32)

        if combat is None:
            return encoding

        for card in combat.hand:
            if card.id in self.ALL_CARD_IDS:
                idx = self.ALL_CARD_IDS.index(card.id)
                encoding[idx] += 1

        return encoding

    def _encode_hand_detail(self, combat: Optional[CombatState]) -> np.ndarray:
        """手牌详细信息（cost + type + playable）"""
        encoding = np.zeros(self.MAX_HAND_SIZE * 3, dtype=np.float32)

        if combat is None:
            return encoding

        for i, card in enumerate(combat.hand[:self.MAX_HAND_SIZE]):
            # cost 归一化
            encoding[i * 3] = min(card.cost, 3) / 3.0
            # type one-hot
            encoding[i * 3 + 1] = self._card_type_to_int(card.card_type)
            # is_playable
            encoding[i * 3 + 2] = 1.0 if card.is_playable else 0.0

        return encoding

    def _encode_player_state(self, state: GameState) -> np.ndarray:
        """玩家状态编码"""
        if state.combat is None or state.combat.player is None:
            return np.zeros(15, dtype=np.float32)

        player = state.combat.player

        # 金币从 GameState 获取，如果没有则从 Player
        gold = state.gold if hasattr(state, 'gold') else player.gold

        return np.array([
            # HP 相关
            self._normalize_hp(player.current_hp, player.max_hp),
            min(player.block, self.MAX_BLOCK) / self.MAX_BLOCK,
            # 能量
            player.energy / self.MAX_ENERGY,
            player.max_energy / self.MAX_ENERGY,
            # 金币
            min(gold, self.MAX_GOLD) / self.MAX_GOLD,
            # 力量状态
            min(player.strength, self.MAX_POWER) / self.MAX_POWER,
            min(player.dexterity, self.MAX_POWER) / self.MAX_POWER,
            min(player.focus, self.MAX_FOCUS) / self.MAX_FOCUS,
            # 牌库信息
            min(player.orbs, 10) / 10.0,  # 能量槽
            # 抽弃信息
            min(state.draw, 10) / 10.0,
            min(state.discard, 10) / 10.0,
            min(state.exhaust, 10) / 10.0,
            # 其他
            float(player.draw_this_turn > 0),  # 是否有额外抽牌
            float(player.ethereal_count > 0),  # 是否有虚无牌
            float(player.temp_hand_size),  # 临时手牌（能量）
        ], dtype=np.float32)

    def _encode_monsters_extended(self, combat: Optional[CombatState]) -> np.ndarray:
        """怪物信息编码（6个怪物 × 10维）"""
        encoding = np.zeros(self.MAX_MONSTERS * 10, dtype=np.float32)

        if combat is None:
            return encoding

        living_monsters = [m for m in combat.monsters if m.is_alive][:self.MAX_MONSTERS]

        for i, monster in enumerate(living_monsters):
            base_idx = i * 10

            # HP 归一化
            encoding[base_idx] = self._normalize_hp(monster.current_hp, monster.max_hp)

            # 格挡归一化
            encoding[base_idx + 1] = min(monster.block, self.MAX_BLOCK) / self.MAX_BLOCK

            # 意图 one-hot（5维）
            intent_encoding = self._encode_intent_extended(monster.intent)
            encoding[base_idx + 2:base_idx + 7] = intent_encoding

            # 力量/敏捷
            encoding[base_idx + 7] = min(monster.strength, self.MAX_POWER) / self.MAX_POWER
            encoding[base_idx + 8] = min(monster.dexterity if hasattr(monster, 'dexterity') else 0, self.MAX_POWER) / self.MAX_POWER

            # 是否存活
            encoding[base_idx + 9] = 1.0 if monster.is_alive else 0.0

        return encoding

    def _encode_intent_simple(self, intent: IntentType) -> np.ndarray:
        """简单意图编码（5维）"""
        encoding = np.zeros(5, dtype=np.float32)
        intent_str = intent.value if hasattr(intent, 'value') else str(intent)

        mapping = {
            'ATTACK': 0,
            'DEFEND': 1,
            'BUFF': 2,
            'DEBUFF': 3,
            'UNKNOWN': 4,
        }

        if intent_str in mapping:
            encoding[mapping[intent_str]] = 1.0
        else:
            encoding[4] = 1.0

        return encoding

    def _encode_intent_extended(self, intent: IntentType) -> np.ndarray:
        """扩展意图编码（5维）"""
        encoding = np.zeros(5, dtype=np.float32)
        intent_str = intent.value if hasattr(intent, 'value') else str(intent)

        # 简化映射（合并复杂的意图类型）
        if 'ATTACK' in intent_str:
            encoding[0] = 1.0
        elif 'DEFEND' in intent_str:
            encoding[1] = 1.0
        elif 'BUFF' in intent_str or 'STRENGTH' in intent_str:
            encoding[2] = 1.0
        elif 'DEBUFF' in intent_str or 'WEAK' in intent_str or 'VULNERABLE' in intent_str:
            encoding[3] = 1.0
        else:
            encoding[4] = 1.0

        return encoding

    def _encode_relics(self, state: GameState) -> np.ndarray:
        """遗物编码（30维 one-hot）"""
        encoding = np.zeros(len(self.COMMON_RELICS), dtype=np.float32)

        if state.relics is None:
            return encoding

        for relic in state.relics:
            if relic in self.COMMON_RELICS:
                idx = self.COMMON_RELICS.index(relic)
                encoding[idx] = 1.0

        return encoding

    def _encode_deck_info(self, combat: Optional[CombatState]) -> np.ndarray:
        """牌库信息"""
        encoding = np.zeros(10, dtype=np.float32)

        if combat is None or combat.player is None:
            return encoding

        player = combat.player

        # 简化：按类型统计（攻击/技能/能力/其他）
        # 这里用归一化的数量代替
        encoding[0] = min(player.hand_size, 10) / 10.0
        encoding[1] = min(player.draw_pile_count, 20) / 20.0
        encoding[2] = min(player.discard_pile_count, 20) / 20.0
        encoding[3] = min(player.exhaust_pile_count, 10) / 10.0

        return encoding

    def _encode_room_info(self, state: GameState) -> np.ndarray:
        """房间信息"""
        encoding = np.zeros(5, dtype=np.float32)

        # 房间类型 one-hot（4维）
        if state.room_phase == RoomPhase.COMBAT:
            encoding[0] = 1.0
        elif state.room_phase == RoomPhase.SHOP:
            encoding[1] = 1.0
        elif state.room_phase == RoomPhase.REST:
            encoding[2] = 1.0
        elif state.room_phase == RoomPhase.EVENT:
            encoding[3] = 1.0

        # 楼层归一化（假设最多60层）
        encoding[4] = min(state.floor, 60) / 60.0

        return encoding

    def _encode_potions(self, combat: Optional[CombatState]) -> np.ndarray:
        """药水信息"""
        encoding = np.zeros(5, dtype=np.float32)

        if combat is None:
            return encoding

        # 是否有药水
        if combat.potions and len(combat.potions) > 0:
            encoding[0] = 1.0
            # 药水数量
            encoding[1] = min(len(combat.potions), 3) / 3.0
            # 常用药水类型简化
            for potion in combat.potions[:2]:
                if 'attack' in str(potion).lower():
                    encoding[2] = 1.0
                elif 'block' in str(potion).lower():
                    encoding[3] = 1.0
                elif 'flex' in str(potion).lower():
                    encoding[4] = 1.0

        return encoding

    def _card_type_to_int(self, card_type: CardType) -> float:
        """卡牌类型转换为数值"""
        mapping = {
            CardType.ATTACK: 0.3,
            CardType.SKILL: 0.6,
            CardType.POWER: 1.0,
            CardType.STATUS: 0.0,
            CardType.CURSE: 0.0,
            CardType.UNKNOWN: 0.0,
        }
        return mapping.get(card_type, 0.0)

    def _normalize_hp(self, current_hp: int, max_hp: int) -> float:
        """归一化血量"""
        if max_hp == 0:
            return 0.0
        return max(0.0, min(1.0, current_hp / max_hp))

    def _pad_or_truncate(self, encoding: np.ndarray) -> np.ndarray:
        """填充或截断到指定维度"""
        if len(encoding) < self.output_dim:
            padded = np.zeros(self.output_dim, dtype=np.float32)
            padded[:len(encoding)] = encoding
            return padded
        elif len(encoding) > self.output_dim:
            return encoding[:self.output_dim].astype(np.float32)
        return encoding.astype(np.float32)

    def get_output_dim(self) -> int:
        """获取输出维度"""
        return self.output_dim


# ========== 静默默认卡牌列表（简单模式用） ==========
SILENT_CARD_IDS = [
    'Strike_R', 'Strike_G', 'Strike_B',
    'Defend_R', 'Defend_G', 'Defend_B',
    'Neutralize', 'Survivor', 'Bash',
    'Backflip', 'Blade Dance', 'Deadly Poison', 'All',
]


# ========== 兼容旧版函数接口 ==========
def encode_state(state: Dict[str, Any]) -> np.ndarray:
    """
    旧版兼容接口（使用扩展模式）

    Args:
        state: 状态字典或 GameState 对象

    Returns:
        编码向量
    """
    if isinstance(state, dict):
        game_state = GameState.from_mod_response(state)
    else:
        game_state = state

    encoder = StateEncoder(mode="extended")
    return encoder.encode_state(game_state)


def encode_action(action_str: str, hand_size: int = 0) -> int:
    """
    编码动作为标签（简单模式，仅用于兼容）

    扩展模式请使用 Action.to_id()
    """
    if action_str == 'end':
        return 70  # 扩展模式的结束回合ID
    elif action_str.startswith('play'):
        try:
            parts = action_str.split()
            card_idx = int(parts[1]) - 1  # 转为 0-based
            if 0 <= card_idx <= 9:
                return card_idx  # 无目标
        except (ValueError, IndexError):
            pass
    return -1


def decode_action(action_id: int) -> str:
    """解码动作 ID（简单模式）"""
    if action_id >= 70:
        return 'end'
    elif 0 <= action_id <= 9:
        return f'play {action_id + 1} 0'
    else:
        return 'state'
