#!/usr/bin/env python3
"""
核心数据结构定义

参考 STS-AI-Master，使用 dataclass 实现强类型状态管理。
这是整个 AI 系统的基础，所有模块都依赖这些数据类。

设计原则：
- 使用 dataclass 确保不可变性（frozen=True）
- 提供 from_dict() 方法兼容旧版 JSON 格式
- 所有状态都有类型注解
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class RoomPhase(Enum):
    """房间阶段"""
    COMBAT = "COMBAT"
    EVENT = "EVENT"
    MAP = "MAP"
    SHOP = "SHOP"
    REST = "REST"
    BOSS = "BOSS"
    NONE = "NONE"
    CARD_REWARD = "CARD_REWARD"
    UNKNOWN = "UNKNOWN"


class CardType(Enum):
    """卡牌类型"""
    ATTACK = "ATTACK"
    SKILL = "SKILL"
    POWER = "POWER"
    STATUS = "STATUS"
    CURSE = "CURSE"
    UNKNOWN = "UNKNOWN"


class IntentType(Enum):
    """怪物意图"""
    ATTACK = "ATTACK"
    ATTACK_BUFF = "ATTACK_BUFF"
    ATTACK_DEBUFF = "ATTACK_DEBUFF"
    DEFEND = "DEFEND"
    BUFF = "BUFF"
    DEBUFF = "DEBUFF"
    UNKNOWN = "UNKNOWN"
    NONE = "NONE"


@dataclass(frozen=True)
class Card:
    """卡牌

    不可变数据类，确保状态不会被意外修改。
    """
    id: str
    name: str
    cost: int
    card_type: CardType
    is_playable: bool = True
    has_target: bool = False
    damage: Optional[int] = None
    block: Optional[int] = None
    magic_number: Optional[int] = None
    upgradable: bool = True
    is_ethereal: bool = False  # 虚无牌（使用后消失）

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Card':
        """从字典创建（兼容旧版 JSON 格式）

        Args:
            d: 来自 CommunicationMod 的卡牌字典

        Returns:
            Card 对象
        """
        # 解析卡牌类型
        type_str = d.get("type", "SKILL")
        try:
            card_type = CardType(type_str)
        except ValueError:
            card_type = CardType.SKILL

        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            cost=d.get("cost", 0),
            card_type=card_type,
            is_playable=d.get("is_playable", True),
            has_target=d.get("has_target", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "id": self.id,
            "name": self.name,
            "cost": self.cost,
            "type": self.card_type.value,
            "is_playable": self.is_playable,
            "has_target": self.has_target,
        }


@dataclass
class Player:
    """玩家状态

    可变数据类，因为玩家状态会在游戏中变化。
    """
    energy: int
    max_energy: int
    current_hp: int
    max_hp: int
    block: int = 0
    gold: int = 0

    # Power 效果
    strength: int = 0
    dexterity: int = 0
    weak: int = 0
    vulnerable: int = 0
    frail: int = 0
    focus: int = 0  # 集中（缺陷角色）

    # 牌库信息（扩展）
    hand_size: int = 0  # 手牌数量
    draw_pile_count: int = 0  # 抽牌堆数量
    discard_pile_count: int = 0  # 弃牌堆数量
    exhaust_pile_count: int = 0  # 消耗堆数量

    # 额外状态
    orbs: int = 0  # 能量槽（缺陷）
    draw_this_turn: int = 0  # 本回合额外抽牌数
    ethereal_count: int = 0  # 虚无牌数量
    temp_hand_size: int = 0  # 临时手牌（能量）

    @property
    def hp_ratio(self) -> float:
        """血量比例 (0-1)"""
        if self.max_hp == 0:
            return 0.0
        return max(0.0, min(1.0, self.current_hp / self.max_hp))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Player':
        """从字典创建"""
        return cls(
            energy=d.get("energy", 0),
            max_energy=d.get("max_energy", 3),
            current_hp=d.get("current_hp", 70),
            max_hp=d.get("max_hp", 70),
            block=d.get("block", 0),
            gold=d.get("gold", 0),
            draw_pile_count=d.get("draw_pile", 0),
            discard_pile_count=d.get("discard", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "energy": self.energy,
            "max_energy": self.max_energy,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "block": self.block,
            "gold": self.gold,
            "strength": self.strength,
            "dexterity": self.dexterity,
            "weak": self.weak,
            "vulnerable": self.vulnerable,
            "frail": self.frail,
            "focus": self.focus,
            "hand_size": self.hand_size,
            "draw_pile": self.draw_pile_count,
            "discard": self.discard_pile_count,
            "exhaust": self.exhaust_pile_count,
        }


@dataclass
class Monster:
    """怪物状态"""
    id: str
    name: str
    current_hp: int
    max_hp: int
    intent: IntentType
    intent_damage: int = 0
    block: int = 0
    move_index: int = 0
    is_gone: bool = False

    # Power 效果
    strength: int = 0
    dexterity: int = 0
    weak: int = 0
    vulnerable: int = 0

    @property
    def is_alive(self) -> bool:
        """是否存活"""
        return not self.is_gone and self.current_hp > 0

    @property
    def hp_ratio(self) -> float:
        """血量比例 (0-1)"""
        if self.max_hp == 0:
            return 0.0
        return max(0.0, min(1.0, self.current_hp / self.max_hp))

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Monster':
        """从字典创建"""
        # 解析意图
        intent_str = d.get("intent", "UNKNOWN")
        try:
            intent = IntentType(intent_str.upper())
        except ValueError:
            intent = IntentType.UNKNOWN

        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            current_hp=d.get("current_hp", 0),
            max_hp=d.get("max_hp", 1),
            intent=intent,
            intent_damage=d.get("intent_damage", 0),
            block=d.get("block", 0),
            move_index=d.get("move", 0),
            is_gone=d.get("is_gone", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "intent": self.intent.value,
            "intent_damage": self.intent_damage,
            "block": self.block,
            "move": self.move_index,
            "is_gone": self.is_gone,
            "strength": self.strength,
            "weak": self.weak,
            "vulnerable": self.vulnerable,
        }


@dataclass
class CombatState:
    """战斗状态"""
    hand: List[Card]
    player: Player
    monsters: List[Monster]
    turn: int
    draw_pile_count: int = 0
    discard_pile_count: int = 0

    # 药水（扩展）
    potions: List[str] = field(default_factory=list)  # 药水ID列表

    def get_valid_card_indices(self) -> List[int]:
        """获取可出的牌索引（考虑能量和 is_playable）

        Returns:
            可出的牌索引列表（0-based）
        """
        valid = []
        for i, card in enumerate(self.hand):
            if card.is_playable and (card.cost <= self.player.energy or card.cost < 0):
                valid.append(i)
        return valid

    def get_living_monsters(self) -> List[Monster]:
        """获取活着的怪物"""
        return [m for m in self.monsters if m.is_alive]

    def get_living_monster_indices(self) -> List[int]:
        """获取活着的怪物索引"""
        return [i for i, m in enumerate(self.monsters) if m.is_alive]

    @property
    def total_monster_hp(self) -> int:
        """所有怪物总血量"""
        return sum(m.current_hp for m in self.monsters if m.is_alive)

    @property
    def is_monsters_attacking(self) -> bool:
        """是否有怪物在攻击"""
        return any(m.intent == IntentType.ATTACK for m in self.get_living_monsters())

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'CombatState':
        """从字典创建"""
        hand = [Card.from_dict(c) for c in d.get("hand", [])]
        player = Player.from_dict(d.get("player", {}))
        monsters = [Monster.from_dict(m) for m in d.get("monsters", [])]

        return cls(
            hand=hand,
            player=player,
            monsters=monsters,
            turn=d.get("turn", 1),
            draw_pile_count=d.get("draw_pile", 0),
            discard_pile_count=d.get("discard", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hand": [c.to_dict() for c in self.hand],
            "player": self.player.to_dict(),
            "monsters": [m.to_dict() for m in self.monsters],
            "turn": self.turn,
            "draw_pile": self.draw_pile_count,
            "discard": self.discard_pile_count,
        }


@dataclass
class GameState:
    """完整游戏状态

    这是整个 AI 系统的核心数据结构。
    所有模块都基于这个强类型状态进行决策。
    """
    room_phase: RoomPhase
    floor: int
    act: int
    combat: Optional[CombatState] = None
    screen_type: Optional[str] = None
    in_game: bool = True
    available_commands: List[str] = field(default_factory=list)
    ready_for_command: bool = False

    # 扩展字段
    relics: List[str] = field(default_factory=list)  # 遗物ID列表
    choice_list: List[Any] = field(default_factory=list)  # 选择列表（商店/奖励/事件）
    draw: int = 0  # 抽牌数
    discard: int = 0  # 弃牌数
    exhaust: int = 0  # 消耗数

    @property
    def is_combat(self) -> bool:
        """是否在战斗中"""
        return self.room_phase == RoomPhase.COMBAT and self.combat is not None

    @property
    def is_ready_for_combat(self) -> bool:
        """是否可以发送战斗命令"""
        return (
            self.in_game and
            self.is_combat and
            self.ready_for_command and
            any(cmd in self.available_commands for cmd in ["play", "end"])
        )

    @classmethod
    def from_mod_response(cls, response: Dict[str, Any]) -> 'GameState':
        """从 Mod 响应创建（兼容 CommunicationMod 格式）

        Args:
            response: 来自 CommunicationMod 的完整 JSON 响应

        Returns:
            GameState 对象
        """
        gs = response.get("game_state", {})

        # 解析 room_phase
        phase_str = gs.get("room_phase", "NONE")
        try:
            room_phase = RoomPhase(phase_str)
        except ValueError:
            room_phase = RoomPhase.UNKNOWN

        # 解析战斗状态
        combat = None
        if gs.get("combat_state"):
            combat = CombatState.from_dict(gs["combat_state"])

        # 解析遗物
        relics = gs.get("relics", [])

        # 解析选择列表
        choice_list = gs.get("choices", gs.get("cards", gs.get("event", [])))

        return cls(
            room_phase=room_phase,
            floor=gs.get("floor", 0),
            act=gs.get("act", 1),
            combat=combat,
            screen_type=gs.get("screen_type"),
            in_game=response.get("in_game", True),
            available_commands=response.get("available_commands", []),
            ready_for_command=response.get("ready_for_command", False),
            relics=relics,
            choice_list=choice_list,
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        # 处理 room_phase（兼容枚举和字符串）
        phase = self.room_phase
        if hasattr(phase, "value"):
            phase = phase.value

        return {
            "room_phase": phase,
            "floor": self.floor,
            "act": self.act,
            "combat_state": self.combat.to_dict() if self.combat else None,
            "screen_type": self.screen_type,
            "in_game": self.in_game,
            "available_commands": self.available_commands,
            "ready_for_command": self.ready_for_command,
            "relics": self.relics,
            "choices": self.choice_list,
        }

    def hash(self) -> str:
        """生成状态哈希（用于去重）"""
        canonical = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        import hashlib
        return hashlib.sha256(canonical.encode()).hexdigest()


# 预定义常量
ACTION_END = 99  # 结束回合的固定 ID（兼容旧版）
