#!/usr/bin/env python3
"""
规则 Agent 单元测试
"""
import pytest
import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.agents.rule_based import RuleBasedAgentImpl, decide_combat_action, decide_choice, DEFAULT_ATTACK_DMG, DEFAULT_BLOCK
from src.core.game_state import (
    GameState, CombatState, RoomPhase, Card, Player, Monster, IntentType, CardType
)
from src.core.action import Action


class TestRuleBasedAgentImpl:
    """RuleBasedAgentImpl 测试"""

    def test_create_agent(self):
        """测试创建 Agent"""
        agent = RuleBasedAgentImpl("TestRule")
        assert agent.name == "TestRule"
        assert agent._gold == 200

    def test_select_action_without_combat(self):
        """测试非战斗状态"""
        agent = RuleBasedAgentImpl("TestRule")
        state = GameState(room_phase=RoomPhase.EVENT, floor=1, act=1)

        action = agent.select_action(state)
        assert action.to_command() == "state"

    def test_decide_combat_no_energy_no_zero_cost(self):
        """测试无能量无 0 费牌"""
        agent = RuleBasedAgentImpl("TestRule")

        hand = [
            Card(id="c1", name="C1", cost=1, card_type=CardType.ATTACK),
            Card(id="c2", name="C2", cost=1, card_type=CardType.SKILL),
        ]
        player = Player(energy=0, max_energy=3, current_hp=70, max_hp=70)
        monsters = [Monster(id="m1", name="M1", current_hp=40, max_hp=44, intent=IntentType.DEFEND)]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)

        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["end"],
            ready_for_command=True
        )

        action = agent._decide_combat_action(state)
        assert action.to_command() == "end"

    def test_decide_combat_with_zero_cost(self):
        """测试有 0 费牌时优先出"""
        agent = RuleBasedAgentImpl("TestRule")

        hand = [
            Card(id="Neutralize", name="中和", cost=0, card_type=CardType.ATTACK),
            Card(id="c2", name="C2", cost=1, card_type=CardType.SKILL),
        ]
        player = Player(energy=1, max_energy=3, current_hp=70, max_hp=70)
        monsters = [Monster(id="m1", name="M1", current_hp=40, max_hp=44, intent=IntentType.ATTACK)]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)

        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["play", "end"],
            ready_for_command=True
        )

        action = agent._decide_combat_action(state)
        # 应该出 0 费攻击牌（Neutralize 需目标，敌人1 → Mod target 0）
        assert action.to_command() == "play 1 0"

    def test_decide_combat_enemy_attacking_cant_kill(self):
        """测试敌人攻击且不能秒杀时优先防御"""
        agent = RuleBasedAgentImpl("TestRule")

        hand = [
            Card(id="Defend_G", name="防御", cost=1, card_type=CardType.SKILL),
            Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK),
        ]
        player = Player(energy=1, max_energy=3, current_hp=70, max_hp=70)
        monsters = [Monster(id="m1", name="M1", current_hp=40, max_hp=44, intent=IntentType.ATTACK)]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)

        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["play", "end"],
            ready_for_command=True
        )

        action = agent._decide_combat_action(state)
        # 应该优先防御（无目标时不包含 target 0）
        assert action.to_command() == "play 1"

    def test_card_damage(self):
        """测试卡牌伤害计算"""
        agent = RuleBasedAgentImpl("TestRule")

        # 已知卡牌
        card1 = Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK)
        assert agent._card_damage(card1) == 6

        card2 = Card(id="Defend_G", name="防御", cost=1, card_type=CardType.SKILL)
        assert agent._card_damage(card2) == 0

        # 未知攻击牌
        card3 = Card(id="Unknown", name="未知攻击", cost=1, card_type=CardType.ATTACK)
        assert agent._card_damage(card3) == DEFAULT_ATTACK_DMG

    def test_card_block(self):
        """测试卡牌格挡计算"""
        agent = RuleBasedAgentImpl("TestRule")

        card1 = Card(id="Defend_G", name="防御", cost=1, card_type=CardType.SKILL)
        assert agent._card_block(card1) == 5

        card2 = Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK)
        assert agent._card_block(card2) == 0

    def test_is_block_or_buff(self):
        """测试判断是否格挡/增益牌"""
        agent = RuleBasedAgentImpl("TestRule")

        card1 = Card(id="Defend_G", name="防御", cost=1, card_type=CardType.SKILL)
        assert agent._is_block_or_buff(card1) is True

        card2 = Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK)
        assert agent._is_block_or_buff(card2) is False

    def test_is_card_selection_screen(self):
        """测试检测选牌界面"""
        agent = RuleBasedAgentImpl("TestRule")

        hand = [Card(id="c1", name="C1", cost=1, card_type=CardType.SKILL)]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        combat = CombatState(hand=hand, player=player, monsters=[], turn=1)

        # 战斗中 + choose + 无 play/end = 覆盖层
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["choose", "proceed"],
            ready_for_command=True
        )

        assert agent._is_card_selection_screen(state) is True

    def test_handle_card_selection(self):
        """测试处理选牌界面"""
        agent = RuleBasedAgentImpl("TestRule")

        hand = [Card(id="c1", name="C1", cost=1, card_type=CardType.SKILL)]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        combat = CombatState(hand=hand, player=player, monsters=[], turn=1)

        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["choose", "proceed"],
            ready_for_command=True
        )

        # 第一次应该 choose 0
        action1 = agent._handle_card_selection(state)
        assert action1.to_command() == "choose 0"
        assert agent._last_discard_step == "choose"

        # 第二次应该 proceed（确认）
        action2 = agent._handle_card_selection(state)
        assert action2.to_command() == "proceed"
        assert agent._last_discard_step == "confirm"

    def test_decide_choice_shop(self):
        """测试商店决策"""
        agent = RuleBasedAgentImpl("TestRule")
        agent._gold = 50  # 只有 50 金，买不起任何东西

        # 创建商店状态（使用属性模拟）
        state = GameState(
            room_phase=RoomPhase.SHOP,
            floor=1,
            act=1,
            screen_type="SHOP_SCREEN",
            available_commands=["choose"],
            ready_for_command=True
        )
        # 模拟 choice_list
        state.choice_list = ["purge", "Strike_G", "Defend_G"]

        action = agent._decide_choice(state)
        # 买不起任何东西，应该选择 0（离开）
        assert action.to_command() == "choose 0"


class TestCompatibilityFunctions:
    """测试兼容旧版的函数"""

    def test_decide_combat_action_compat(self):
        """测试兼容旧版 decide_combat_action 函数"""
        combat_state = {
            "hand": [{"id": "Strike_G", "name": "打击", "cost": 1, "type": "ATTACK"}],
            "player": {"energy": 1, "current_hp": 70},
            "monsters": [{"id": "m1", "name": "M1", "current_hp": 40, "max_hp": 44, "intent": "DEFEND"}],
            "turn": 1,
        }
        available_commands = ["play", "end"]

        result = decide_combat_action(combat_state, available_commands)
        # 应该出牌（攻击牌需目标，敌人1 → Mod target 0）
        assert result in ["play 1", "play 1 0"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
