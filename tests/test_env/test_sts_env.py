#!/usr/bin/env python3
"""
Gymnasium 环境测试

支持扩展模式（80维动作空间，~252维观察空间）
"""
import pytest
import sys
import os
import numpy as np

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.env.sts_env import StsEnvironment
from src.core.game_state import GameState, CombatState, RoomPhase, Card, Player, Monster, IntentType, CardType
from src.core.action import ACTION_SPACE_SIZE, ACTION_END_ID


class TestStsEnvironment:
    """StsEnvironment 测试（扩展模式）"""

    def test_create_env(self):
        """测试创建环境（扩展模式）"""
        env = StsEnvironment(mode="extended")
        assert env is not None
        assert env.action_space.n == ACTION_SPACE_SIZE  # 80
        # 观察维度取决于编码器输出
        assert env.observation_space.shape[0] >= 200  # 扩展模式至少200维

    def test_create_env_simple(self):
        """测试创建环境（简单模式）"""
        env = StsEnvironment(mode="simple", observation_dim=30)
        assert env is not None
        assert env.action_space.n == ACTION_SPACE_SIZE  # 80（动作空间统一）
        assert env.observation_space.shape == (30,)

    def test_reset(self):
        """测试重置环境（扩展模式）"""
        env = StsEnvironment(mode="extended")
        obs, info = env.reset()
        assert obs is not None
        assert obs.shape[0] >= 200  # 扩展模式至少200维
        assert "action_mask" in info
        assert "valid_actions" in info
        assert info["action_mask"].shape == (ACTION_SPACE_SIZE,)

    def test_reset_simple(self):
        """测试重置环境（简单模式）"""
        env = StsEnvironment(mode="simple", observation_dim=30)
        obs, info = env.reset()
        assert obs is not None
        assert obs.shape == (30,)
        assert "action_mask" in info
        assert "valid_actions" in info
        assert info["action_mask"].shape == (ACTION_SPACE_SIZE,)

    def test_step_without_state(self):
        """测试无状态时的步骤"""
        env = StsEnvironment(mode="extended")
        obs, info = env.reset()
        obs, reward, terminated, truncated, info = env.step(0)
        assert obs.shape[0] >= 200  # 扩展模式至少200维
        assert not terminated
        assert not truncated

    def test_step_with_combat_state(self):
        """测试有战斗状态时的步骤"""
        env = StsEnvironment(mode="extended")

        # 创建战斗状态
        hand = [
            Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK, has_target=True),
            Card(id="Defend_G", name="防御", cost=1, card_type=CardType.SKILL, is_playable=False),
        ]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        monsters = [
            Monster(id="m1", name="Test", current_hp=40, max_hp=44, intent=IntentType.ATTACK),
        ]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)

        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["play", "end"],
            ready_for_command=True
        )

        env.set_state(state)

        # 执行步骤（无目标出第一张牌）
        obs, reward, terminated, truncated, info = env.step(0)

        assert obs.shape[0] >= 200  # 扩展模式至少200维
        assert "action_mask" in info
        assert "valid_actions" in info

    def test_get_valid_actions(self):
        """测试获取合法动作（扩展模式）"""
        env = StsEnvironment(mode="extended")

        # 创建有能量的状态
        hand = [
            Card(id="c1", name="C1", cost=1, card_type=CardType.ATTACK, has_target=True),
            Card(id="c2", name="C2", cost=3, card_type=CardType.ATTACK, has_target=True),
        ]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        monsters = [
            Monster(id="m1", name="M1", current_hp=40, max_hp=44, intent=IntentType.ATTACK),
        ]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["play", "end"],
            ready_for_command=True
        )
        env.set_state(state)

        valid = env._get_valid_actions()
        # 第一张牌可出（无目标：0，有目标：10）
        assert 0 in valid  # 无目标
        assert 10 in valid  # 目标怪物1
        # 第二张牌能量不够，不应该有相关动作
        assert 1 not in valid
        assert 11 not in valid
        # 结束回合可用（新ID是70）
        assert ACTION_END_ID in valid  # 170

    def test_action_mask(self):
        """测试动作掩码（扩展模式）"""
        env = StsEnvironment(mode="extended")

        hand = [
            Card(id="c1", name="C1", cost=0, card_type=CardType.ATTACK, has_target=True),
        ]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        monsters = [
            Monster(id="m1", name="M1", current_hp=40, max_hp=44, intent=IntentType.ATTACK),
        ]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["play", "end"],
            ready_for_command=True
        )
        env.set_state(state)

        valid = [0, 10, ACTION_END_ID]  # 无目标、目标怪物1、结束回合
        mask = env._get_action_mask(valid)

        assert mask.shape == (ACTION_SPACE_SIZE,)
        assert mask[0] == 1
        assert mask[10] == 1
        assert mask[ACTION_END_ID] == 1
        assert mask[1] == 0  # 不合法

    def test_reward_calculation(self):
        """测试奖励计算"""
        env = StsEnvironment()

        # 创建状态
        hand = [Card(id="c1", name="C1", cost=0, card_type=CardType.ATTACK)]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        monsters = [
            Monster(id="m1", name="M1", current_hp=40, max_hp=44, intent=IntentType.ATTACK),
        ]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["play", "end"],
            ready_for_command=True
        )
        env.set_state(state)

        # 怪物受伤 -> 正奖励
        reward = env._compute_reward()
        # 第一次调用没有变化，奖励为 0
        assert reward == 0.0

    def test_is_terminal(self):
        """测试终止判断"""
        env = StsEnvironment()

        # 不在游戏中
        state = GameState(
            room_phase=RoomPhase.NONE,
            floor=0,
            act=0,
            in_game=False
        )
        env.set_state(state)
        assert env._is_terminal() is True

        # 玩家死亡
        hand = []
        player = Player(energy=3, max_energy=3, current_hp=0, max_hp=70)
        combat = CombatState(hand=hand, player=player, monsters=[], turn=1)
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            in_game=True
        )
        env.set_state(state)
        assert env._is_terminal() is True

        # 正常战斗
        player = Player(energy=3, max_energy=3, current_hp=70, max_hp=70)
        combat = CombatState(hand=hand, player=player, monsters=[], turn=1)
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            in_game=True
        )
        env.set_state(state)
        # 没有怪物，也算结束（胜利）
        assert env._is_terminal() is True


class TestStateEncoder:
    """StateEncoder 测试"""

    def test_encode_basic_state(self):
        """测试基本状态编码"""
        from src.training.encoder import StateEncoder

        encoder = StateEncoder(mode="simple")  # 使用新 API

        hand = [
            Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK),
            Card(id="Defend_G", name="防御", cost=1, card_type=CardType.SKILL),
        ]
        player = Player(energy=3, max_energy=3, current_hp=70, max_hp=70)
        monsters = [
            Monster(id="m1", name="Test", current_hp=40, max_hp=44, intent=IntentType.ATTACK),
        ]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat
        )

        encoding = encoder.encode_state(state)
        assert encoding.shape == (30,)
        assert encoding.dtype == np.float32

    def test_encode_empty_state(self):
        """测试空状态编码"""
        from src.training.encoder import StateEncoder

        encoder = StateEncoder(mode="simple")  # 使用新 API
        state = GameState(room_phase=RoomPhase.NONE, floor=0, act=0)

        encoding = encoder.encode_state(state)
        assert encoding.shape == (30,)
        # 应该是全零
        assert np.all(encoding == 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
