#!/usr/bin/env python3
"""
强化学习 Agent 单元测试
"""
import pytest
import sys
import os
import numpy as np
import tempfile
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.agents.rl_agent import RLAgentImpl
from src.agents.supervised import SupervisedAgentImpl
from src.core.game_state import (
    GameState, CombatState, RoomPhase, Card, Player, Monster, IntentType, CardType
)
from src.core.action import Action


class MockEnv:
    """模拟 Gymnasium 环境（扩展模式）"""

    def __init__(self):
        from src.core.action import ACTION_SPACE_SIZE
        self.action_space = type('obj', (object,), {'n': ACTION_SPACE_SIZE})()
        self.observation_space = type('obj', (object,), {'shape': (252,)})()

    def reset(self, **kwargs):
        return np.zeros(252), {}

    def step(self, action):
        return np.zeros(252), 0.0, False, False, {}


class TestRLAgentImpl:
    """RLAgentImpl 测试"""

    def test_create_agent(self):
        """测试创建 Agent"""
        agent = RLAgentImpl("TestRL")
        assert agent.name == "TestRL"
        assert agent.algorithm == "ppo"
        assert agent._model is None

    def test_create_agent_with_algorithm(self):
        """测试创建不同算法的 Agent"""
        for algo in ["ppo", "a2c", "dqn"]:
            agent = RLAgentImpl(f"TestRL_{algo}", config={"algorithm": algo})
            assert agent.algorithm == algo

    def test_set_environment(self):
        """测试设置环境"""
        agent = RLAgentImpl("TestRL")
        env = MockEnv()
        agent.set_environment(env)
        assert agent._env is not None

    def test_select_action_without_model(self):
        """测试无模型时选择动作"""
        agent = RLAgentImpl("TestRL")
        state = self._create_test_state()

        action = agent.select_action(state)
        # 无模型时返回默认动作（end）
        assert action.to_command() == "end"

    def test_select_action_with_valid_actions_masking(self):
        """测试 Action Masking"""
        from src.core.action import ACTION_END_ID
        agent = RLAgentImpl("TestRL")
        state = self._create_test_state()

        # 模拟有效动作列表（只能出第一张牌或结束）
        valid_actions = [0, ACTION_END_ID]  # play 0, end (70)

        action = agent.select_action(state, valid_actions=valid_actions)
        action_id = action.to_id()
        assert action_id in valid_actions

    def test_get_action_probabilities_without_model(self):
        """测试无模型时获取动作概率"""
        from src.core.action import ACTION_SPACE_SIZE
        agent = RLAgentImpl("TestRL")
        state = self._create_test_state()

        probs = agent.get_action_probabilities(state)
        assert probs.shape == (ACTION_SPACE_SIZE,)
        assert np.allclose(probs.sum(), 1.0)
        # 未训练时返回均匀分布
        assert np.allclose(probs, 1/ACTION_SPACE_SIZE)

    def test_get_action_value_without_model(self):
        """测试无模型时获取动作价值"""
        agent = RLAgentImpl("TestRL")
        state = self._create_test_state()
        action = Action.play_card(0, 0)

        value = agent.get_action_value(state, action)
        assert value == 0.0

    def test_set_training_mode(self):
        """测试设置训练模式"""
        agent = RLAgentImpl("TestRL")

        # 推理模式
        agent.set_training_mode(False)
        assert agent.is_training is False

        # 训练模式
        agent.set_training_mode(True)
        assert agent.is_training is True

    def test_on_episode_callbacks(self):
        """测试回合回调"""
        agent = RLAgentImpl("TestRL")

        # 回合开始
        agent.on_episode_start(1)
        assert agent._episode_id == 1
        assert agent._step_count == 0

        # 模拟一些步数
        agent._step_count = 5
        agent._current_episode_length = 5

        # 回合结束
        agent.on_episode_end(reward=100.0)
        assert len(agent._episode_rewards) == 1
        assert agent._episode_rewards[0] == 100.0

    def test_get_metrics(self):
        """测试获取训练指标"""
        agent = RLAgentImpl("TestRL")

        metrics = agent.get_metrics()
        assert "total_timesteps" in metrics
        assert "episode_rewards" in metrics
        assert "episode_lengths" in metrics
        assert "mean_reward" in metrics

    def test_get_model_path(self):
        """测试获取模型路径"""
        agent = RLAgentImpl("TestRL")
        path = agent.get_model_path()
        assert "models" in path
        assert path.endswith(".zip")

    def test_train_without_environment(self):
        """测试无环境时训练"""
        agent = RLAgentImpl("TestRL")

        with pytest.raises(ValueError, match="Environment not set"):
            agent.train(total_timesteps=100)

    def test_save_without_model(self):
        """测试无模型时保存"""
        agent = RLAgentImpl("TestRL")

        # 不应该抛出错误，只是警告
        agent.save("/tmp/test_model.zip")

    def test_load_sl_model_untrained(self):
        """测试从未训练的 SL 模型加载"""
        rl_agent = RLAgentImpl("TestRL")
        sl_agent = SupervisedAgentImpl("TestSL")

        # 不应该抛出错误，只是警告
        rl_agent.load_sl_model(sl_agent)

    def _create_test_state(self) -> GameState:
        """创建测试用游戏状态"""
        hand = [
            Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK, has_target=True),
            Card(id="Defend_G", name="防御", cost=1, card_type=CardType.SKILL),
        ]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        monsters = [
            Monster(id="m1", name="M1", current_hp=40, max_hp=44, intent=IntentType.ATTACK),
        ]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)

        return GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["play", "end"],
            ready_for_command=True
        )


class TestFactoryFunction:
    """测试工厂函数"""

    def test_create_rl_agent_via_factory(self):
        """测试通过工厂函数创建 RL Agent"""
        from src.agents.base import create_agent

        agent = create_agent("rl", "TestRL")
        assert agent.name == "TestRL"
        assert isinstance(agent, RLAgentImpl)


class TestActionMasking:
    """测试 Action Masking 功能"""

    def _create_test_state(self) -> GameState:
        """创建测试用游戏状态"""
        hand = [
            Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK, has_target=True),
            Card(id="Defend_G", name="防御", cost=1, card_type=CardType.SKILL),
        ]
        player = Player(energy=2, max_energy=3, current_hp=70, max_hp=70)
        monsters = [
            Monster(id="m1", name="M1", current_hp=40, max_hp=44, intent=IntentType.ATTACK),
        ]
        combat = CombatState(hand=hand, player=player, monsters=monsters, turn=1)

        return GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=combat,
            available_commands=["play", "end"],
            ready_for_command=True
        )

    def test_action_masking_with_restricted_actions(self):
        """测试受限动作列表"""
        from src.core.action import ACTION_END_ID
        agent = RLAgentImpl("TestRL")

        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            combat=None,
            available_commands=["end"],  # 只有 end 命令可用
            ready_for_command=True
        )

        # 只有 end 可用（action_id = 70）
        valid_actions = [ACTION_END_ID]
        action = agent.select_action(state, valid_actions=valid_actions)

        assert action.to_id() == ACTION_END_ID

    def test_action_masking_with_empty_list(self):
        """测试空动作列表"""
        agent = RLAgentImpl("TestRL")
        state = self._create_test_state()

        # 空列表时不应用 masking
        action = agent.select_action(state, valid_actions=None)
        assert action is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
