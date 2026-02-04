#!/usr/bin/env python3
"""
核心数据类单元测试
"""
import pytest
import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.core.game_state import (
    RoomPhase, CardType, IntentType,
    Card, Player, Monster, CombatState, GameState,
    ACTION_END
)
from src.core.action import Action, ActionType


class TestCard:
    """卡牌测试"""

    def test_from_dict_basic(self):
        """测试基本字典转换"""
        d = {
            "id": "Strike_G",
            "name": "打击",
            "cost": 1,
            "type": "ATTACK",
            "is_playable": True,
            "has_target": True,
        }
        card = Card.from_dict(d)
        assert card.id == "Strike_G"
        assert card.name == "打击"
        assert card.cost == 1
        assert card.card_type == CardType.ATTACK
        assert card.is_playable is True

    def test_to_dict(self):
        """测试转换为字典"""
        card = Card(
            id="Defend_G",
            name="防御",
            cost=1,
            card_type=CardType.SKILL
        )
        d = card.to_dict()
        assert d["id"] == "Defend_G"
        assert d["name"] == "防御"
        assert d["cost"] == 1


class TestPlayer:
    """玩家测试"""

    def test_from_dict(self):
        """测试字典转换"""
        d = {
            "energy": 3,
            "current_hp": 60,
            "block": 5,
        }
        player = Player.from_dict(d)
        assert player.energy == 3
        assert player.current_hp == 60
        assert player.block == 5
        assert player.max_hp == 70  # 默认值

    def test_hp_ratio(self):
        """测试血量比例"""
        player = Player(
            energy=3,
            max_energy=3,
            current_hp=35,
            max_hp=70,
        )
        assert player.hp_ratio == 0.5


class TestMonster:
    """怪物测试"""

    def test_from_dict(self):
        """测试字典转换"""
        d = {
            "id": "Jaw Worm",
            "name": "下颚虫",
            "current_hp": 40,
            "max_hp": 44,
            "intent": "ATTACK",
            "block": 0,
        }
        monster = Monster.from_dict(d)
        assert monster.name == "下颚虫"
        assert monster.current_hp == 40
        assert monster.intent == IntentType.ATTACK

    def test_is_alive(self):
        """测试存活判断"""
        monster = Monster(
            id="test",
            name="Test",
            current_hp=10,
            max_hp=44,
            intent=IntentType.UNKNOWN,
        )
        assert monster.is_alive is True

        monster.current_hp = 0
        assert monster.is_alive is False

        monster.current_hp = 10
        monster.is_gone = True
        assert monster.is_alive is False


class TestCombatState:
    """战斗状态测试"""

    def test_get_valid_card_indices(self):
        """测试获取合法出牌索引"""
        hand = [
            Card(id="c1", name="C1", cost=0, card_type=CardType.ATTACK),
            Card(id="c2", name="C2", cost=1, card_type=CardType.SKILL),
            Card(id="c3", name="C3", cost=3, card_type=CardType.ATTACK, is_playable=False),
        ]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        combat = CombatState(hand=hand, player=player, monsters=[], turn=1)

        valid = combat.get_valid_card_indices()
        assert 0 in valid  # 0费可出
        assert 1 in valid  # 能量足够可出
        assert 2 not in valid  # is_playable=False

    def test_total_monster_hp(self):
        """测试总怪物血量"""
        monsters = [
            Monster(id="m1", name="M1", current_hp=20, max_hp=40, intent=IntentType.UNKNOWN),
            Monster(id="m2", name="M2", current_hp=10, max_hp=30, intent=IntentType.UNKNOWN),
            Monster(id="m3", name="M3", current_hp=0, max_hp=20, intent=IntentType.UNKNOWN),
        ]
        combat = CombatState(
            hand=[],
            player=Player(energy=3, max_energy=3, current_hp=70, max_hp=70),
            monsters=monsters,
            turn=1
        )

        assert combat.total_monster_hp == 30  # 只有活着的怪物


class TestGameState:
    """游戏状态测试"""

    def test_from_mod_response(self):
        """测试从 Mod 响应创建"""
        response = {
            "in_game": True,
            "ready_for_command": True,
            "available_commands": ["play", "end"],
            "game_state": {
                "room_phase": "COMBAT",
                "floor": 1,
                "act": 1,
                "combat_state": {
                    "hand": [
                        {"id": "Strike_G", "name": "打击", "cost": 1, "type": "ATTACK"},
                    ],
                    "player": {"energy": 3, "current_hp": 70, "block": 0},
                    "monsters": [
                        {"id": "Jaw Worm", "name": "下颚虫", "current_hp": 40, "max_hp": 44, "intent": "ATTACK"},
                    ],
                    "turn": 1,
                }
            }
        }

        state = GameState.from_mod_response(response)
        assert state.room_phase == RoomPhase.COMBAT
        assert state.floor == 1
        assert state.is_combat is True
        assert state.is_ready_for_combat is True

    def test_is_combat(self):
        """测试战斗判断"""
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=CombatState(
                hand=[],
                player=Player(energy=3, max_energy=3, current_hp=70, max_hp=70),
                monsters=[],
                turn=1
            )
        )
        assert state.is_combat is True

        state.room_phase = RoomPhase.EVENT
        assert state.is_combat is False


class TestAction:
    """动作测试"""

    def test_play_card_command(self):
        """测试出牌命令转换"""
        # 无目标出牌（target=0 时不包含在命令中）
        action = Action.play_card(0)  # 内部 0-based
        cmd = action.to_command()
        assert cmd == "play 1"  # Mod 1-based，无目标时省略

        # 带目标出牌（内部 1-based，Mod 0-based）
        action = Action.play_card(0, target_idx=1)
        cmd = action.to_command()
        assert cmd == "play 1 0"  # 敌人1 → Mod target 0

    def test_end_turn_command(self):
        """测试结束回合命令"""
        action = Action.end_turn()
        assert action.to_command() == "end"

    def test_from_command(self):
        """测试从命令解析（Mod target 0-based → 内部 1-based）"""
        action = Action.from_command("play 2 0")
        assert action.type == ActionType.PLAY_CARD
        assert action.card_index == 1  # 1-based → 0-based
        assert action.target_index == 1  # Mod 0 → 内部敌人1

        action = Action.from_command("play 2 1")
        assert action.target_index == 2  # Mod 1 → 内部敌人2

    def test_action_id(self):
        """测试动作 ID 转换（133维动作空间）"""
        action = Action.play_card(3)
        assert action.to_id() == 3

        action = Action.end_turn()
        assert action.to_id() == 170  # 173维空间中，结束回合 ID 为 170

    def test_from_id(self):
        """测试从 ID 创建（133维动作空间）"""
        action = Action.from_id(5)
        assert action.type == ActionType.PLAY_CARD
        assert action.card_index == 5

        action = Action.from_id(170)  # 173维空间中，结束回合 ID 为 170
        assert action.type == ActionType.END_TURN

    def test_potion_commands(self):
        """测试药水命令"""
        # 使用药水（无目标）
        action = Action.use_potion(0)
        assert action.to_command() == "potion use 1"

        # 使用药水（带目标，敌人1 → Mod target 0）
        action = Action.use_potion(0, target_idx=1)
        assert action.to_command() == "potion use 1 0"

        # 丢弃药水
        action = Action.discard_potion(0)
        assert action.to_command() == "potion discard 1"

    def test_new_commands(self):
        """测试新增命令"""
        # 取消
        action = Action.cancel()
        assert action.to_command() == "cancel"

        # 前进
        action = Action.proceed()
        assert action.to_command() == "proceed"

        # 按名称选择
        action = Action.choose_by_name("shop")
        assert action.to_command() == "choose shop"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
