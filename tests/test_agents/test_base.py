#!/usr/bin/env python3
"""
Agent 基类单元测试
"""
import pytest
import sys
import os
import numpy as np

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.agents.base import Agent, RuleBasedAgent, SupervisedAgent, RLAgent
from src.core.game_state import GameState, RoomPhase
from src.core.action import Action, ACTION_SPACE_SIZE, ACTION_END_ID


class DummyAgent(Agent):
    """测试用的简单 Agent 实现"""

    def select_action(self, state: GameState) -> Action:
        return Action.end_turn()


class TestAgent:
    """Agent 基类测试"""

    def test_create_agent(self):
        """测试创建 Agent"""
        agent = DummyAgent("TestAgent")
        assert agent.name == "TestAgent"
        assert agent._episode_id == 0
        assert agent.is_training is False

    def test_select_action(self):
        """测试选择动作"""
        agent = DummyAgent("TestAgent")
        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)
        action = agent.select_action(state)
        assert action.to_command() == "end"

    def test_get_action_probabilities(self):
        """测试获取动作概率"""
        agent = DummyAgent("TestAgent")
        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)

        probs = agent.get_action_probabilities(state)
        assert probs.shape == (ACTION_SPACE_SIZE,)
        assert probs.sum() == pytest.approx(1.0)
        # end 是 action_id 70 (ACTION_END_ID)
        assert probs[ACTION_END_ID] == 1.0
        assert probs[0] == 0.0

    def test_on_episode_start(self):
        """测试回合开始回调"""
        agent = DummyAgent("TestAgent")
        agent.on_episode_start(1)
        assert agent._episode_id == 1
        assert agent._step_count == 0

    def test_on_step(self):
        """测试每步回调"""
        agent = DummyAgent("TestAgent")
        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)

        agent.on_episode_start(1)
        agent.on_step(Action.end_turn(), reward=0.0, next_state=state, done=False)
        assert agent._step_count == 1
        assert agent._total_steps == 1

        agent.on_step(Action.end_turn(), reward=1.0, next_state=state, done=True)
        assert agent._step_count == 2
        assert agent._total_steps == 2

    def test_on_episode_end(self):
        """测试回合结束回调"""
        agent = DummyAgent("TestAgent")
        agent.on_episode_start(1)
        agent.on_episode_end(reward=100.0)
        assert agent._total_episodes == 1

    def test_set_training_mode(self):
        """测试设置训练模式"""
        agent = DummyAgent("TestAgent")
        assert agent.is_training is False

        agent.set_training_mode(True)
        assert agent.is_training is True

        agent.set_training_mode(False)
        assert agent.is_training is False

    def test_get_metrics(self):
        """测试获取指标"""
        agent = DummyAgent("TestAgent")
        metrics = agent.get_metrics()

        assert metrics["name"] == "TestAgent"
        assert metrics["episode_id"] == 0
        assert metrics["step_count"] == 0
        assert metrics["total_steps"] == 0
        assert metrics["total_episodes"] == 0
        assert metrics["training_mode"] is False

    def test_reset_metrics(self):
        """测试重置指标"""
        agent = DummyAgent("TestAgent")
        agent.on_episode_start(1)
        agent.on_step(Action.end_turn(), 0.0, None, False)

        agent.reset_metrics()
        assert agent._episode_id == 0
        assert agent._total_steps == 0

    def test_repr(self):
        """测试字符串表示"""
        agent = DummyAgent("TestAgent")
        repr_str = repr(agent)
        assert "TestAgent" in repr_str
        assert "training=False" in repr_str


class TestSupervisedAgent:
    """SupervisedAgent 基类测试"""

    class TestSupervisedAgentImpl(SupervisedAgent):
        """测试用实现"""

        def train(self, states, actions, **kwargs):
            self._model = "trained"

        def predict_proba(self, state):
            from src.core.action import ACTION_SPACE_SIZE, ACTION_END_ID
            if self._model is None:
                return np.ones(ACTION_SPACE_SIZE, dtype=np.float32) / ACTION_SPACE_SIZE
            # 返回偏向 end 动作的概率（确保和为 1）
            # 173个动作，172个*0.004 + 0.312 = 1.0，end 概率 >= 0.2
            probs = np.ones(ACTION_SPACE_SIZE, dtype=np.float32) * 0.004
            probs[ACTION_END_ID] = 0.312  # end，总和 = 0.004*172 + 0.312 = 1.0
            return probs

    def test_create_supervised_agent(self):
        """测试创建监督学习 Agent"""
        agent = self.TestSupervisedAgentImpl("TestSL")
        assert agent.name == "TestSL"
        assert agent._model is None

    def test_select_action_without_model(self):
        """测试未训练模型时选择动作"""
        agent = self.TestSupervisedAgentImpl("TestSL")
        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)

        action = agent.select_action(state)
        # 没有模型时返回 state 动作
        assert action.to_command() == "state"

    def test_select_action_with_model_inference_mode(self):
        """测试推理模式下选择动作"""
        agent = self.TestSupervisedAgentImpl("TestSL")
        agent.train([], [])  # 设置模型
        agent.set_training_mode(False)

        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)
        action = agent.select_action(state)

        # 推理模式选择概率最高的动作（end，ID=70）
        assert action.to_id() == ACTION_END_ID

    def test_select_action_with_model_training_mode(self):
        """测试训练模式下选择动作"""
        agent = self.TestSupervisedAgentImpl("TestSL")
        agent.train([], [])
        agent.set_training_mode(True)

        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)

        # 多次采样，最终应该能采样到不同动作
        actions = set()
        for _ in range(100):
            action = agent.select_action(state)
            actions.add(action.to_id())

        # 训练模式会采样，但概率主要集中在 end（ID=70）
        assert ACTION_END_ID in actions

    def test_get_action_probabilities(self):
        """测试获取动作概率"""
        from src.core.action import ACTION_SPACE_SIZE, ACTION_END_ID
        agent = self.TestSupervisedAgentImpl("TestSL")
        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)

        # 没有模型时返回均匀分布
        probs = agent.get_action_probabilities(state)
        assert probs.shape == (ACTION_SPACE_SIZE,)
        assert np.allclose(probs.sum(), 1.0)

        # 有模型时返回预测概率
        agent.train([], [])
        probs = agent.get_action_probabilities(state)
        assert probs[ACTION_END_ID] >= 0.2  # end 的概率应该很高


class TestRLAgent:
    """RLAgent 基类测试"""

    class TestRLAgentImpl(RLAgent):
        """测试用实现"""

        def set_environment(self, env):
            self._env = env

        def train(self, total_timesteps, **kwargs):
            self._policy = "trained"

        def learn_from_experience(self, experience):
            pass

        def select_action(self, state):
            if self._policy is None:
                return Action.state()
            return Action.end_turn()

    def test_create_rl_agent(self):
        """测试创建 RL Agent"""
        agent = self.TestRLAgentImpl("TestRL")
        assert agent.name == "TestRL"
        assert agent._policy is None

    def test_set_environment(self):
        """测试设置环境"""
        agent = self.TestRLAgentImpl("TestRL")
        env = "fake_env"
        agent.set_environment(env)
        assert agent._env == env

    def test_select_action_without_policy(self):
        """测试没有策略时选择动作"""
        agent = self.TestRLAgentImpl("TestRL")
        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)

        action = agent.select_action(state)
        assert action.to_command() == "state"

    def test_select_action_with_policy(self):
        """测试有策略时选择动作"""
        agent = self.TestRLAgentImpl("TestRL")
        agent.train(1000)  # 设置策略

        state = GameState(room_phase=RoomPhase.COMBAT, floor=1, act=1)
        action = agent.select_action(state)
        assert action.to_command() == "end"

    def test_load_sl_model_not_implemented(self):
        """测试加载 SL 模型（默认未实现）"""
        agent = self.TestRLAgentImpl("TestRL")
        sl_agent = None

        with pytest.raises(NotImplementedError):
            agent.load_sl_model(sl_agent)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
