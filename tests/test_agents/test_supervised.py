#!/usr/bin/env python3
"""
监督学习 Agent 单元测试
"""
import pytest
import sys
import os
import numpy as np
import pickle
from pathlib import Path
import tempfile

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.agents.supervised import SupervisedAgentImpl, load_training_data
from src.core.game_state import (
    GameState, CombatState, RoomPhase, Card, Player, Monster, IntentType, CardType
)
from src.core.action import Action


class TestSupervisedAgentImpl:
    """SupervisedAgentImpl 测试"""

    def test_create_agent(self):
        """测试创建 Agent"""
        agent = SupervisedAgentImpl("TestSL")
        assert agent.name == "TestSL"
        assert agent.model_type == "sklearn"
        assert agent._model is None

    def test_create_pytorch_agent(self):
        """测试创建 PyTorch Agent"""
        agent = SupervisedAgentImpl("TestSL_PyTorch", config={"model_type": "pytorch"})
        assert agent.model_type == "pytorch"

    def test_train_sklearn(self):
        """测试 sklearn 训练"""
        agent = SupervisedAgentImpl("TestSL")

        # 创建简单的训练数据
        states, actions = self._create_simple_data(50)

        # 训练
        result = agent.train(states, actions, epochs=50, batch_size=16)

        assert agent._model is not None
        assert "accuracy" in result
        assert result["accuracy"] > 0  # 应该至少有一些准确率

    def test_predict_proba_without_model(self):
        """测试未训练模型时的概率预测"""
        agent = SupervisedAgentImpl("TestSL")

        state = self._create_test_state()
        probs = agent.predict_proba(state)

        assert probs.shape == (11,)
        assert np.allclose(probs.sum(), 1.0)
        # 未训练时应该返回均匀分布
        assert np.allclose(probs, 1/11)

    def test_predict_proba_with_model(self):
        """测试训练模型后的概率预测"""
        agent = SupervisedAgentImpl("TestSL")

        # 训练模型
        states, actions = self._create_simple_data(100)
        agent.train(states, actions, epochs=50)

        # 预测
        state = self._create_test_state()
        probs = agent.predict_proba(state)

        assert probs.shape == (11,)
        assert np.allclose(probs.sum(), 1.0)

    def test_select_action_with_model(self):
        """测试使用模型选择动作"""
        agent = SupervisedAgentImpl("TestSL")

        # 训练模型
        states, actions = self._create_simple_data(100)
        agent.train(states, actions, epochs=50)

        # 推理模式选择动作
        agent.set_training_mode(False)
        action = agent.select_action(self._create_test_state())
        assert action.to_command() in ["play 1 0", "play 1 1", "end", "state"]

        # 训练模式应该探索（可能选择不同动作）
        agent.set_training_mode(True)
        actions = set()
        for _ in range(20):
            action = agent.select_action(self._create_test_state())
            actions.add(action.to_command())

    def test_save_load_model(self):
        """测试模型保存和加载"""
        agent = SupervisedAgentImpl("TestSL")

        # 训练模型
        states, actions = self._create_simple_data(50)
        agent.train(states, actions, epochs=20)

        # 保存到临时文件
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            save_path = f.name

        try:
            # 保存
            agent.save(save_path)

            # 创建新 Agent 并加载
            agent2 = SupervisedAgentImpl("TestSL2")
            agent2.load(save_path)

            # 验证模型已加载
            assert agent2._model is not None
            assert agent2.name == "TestSL2"

            # 验证预测结果一致
            state = self._create_test_state()
            probs1 = agent.predict_proba(state)
            probs2 = agent2.predict_proba(state)

            assert np.allclose(probs1, probs2, atol=1e-6)

        finally:
            # 清理
            Path(save_path).unlink(missing_ok=True)

    def test_get_model_path(self):
        """测试获取模型路径"""
        agent = SupervisedAgentImpl("TestSL")
        path = agent.get_model_path()
        assert "models" in path
        assert path.endswith(".pkl")

    def _create_simple_data(self, n: int) -> tuple:
        """创建简单的训练数据"""
        states = []
        actions = []

        for i in range(n):
            state = self._create_test_state()
            # 简单策略：如果能量>0 出牌，否则结束
            if state.combat and state.combat.player.energy > 0:
                action = Action.play_card(0, 0)  # 出第一张牌
            else:
                action = Action.end_turn()

            states.append(state)
            actions.append(action)

        return states, actions

    def _create_test_state(self) -> GameState:
        """创建测试用游戏状态"""
        hand = [
            Card(id="Strike_G", name="打击", cost=1, card_type=CardType.ATTACK),
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


class TestDataLoading:
    """数据加载测试"""

    def test_load_training_data(self):
        """测试加载训练数据"""
        # 这个测试需要真实数据文件，跳过如果没有
        data_dir = Path("data/raw")
        if not data_dir.exists():
            pytest.skip("No training data directory")

        states, actions = load_training_data(str(data_dir))

        # 验证数据
        assert len(states) > 0
        assert len(actions) == len(states)

        # 验证状态格式
        for state in states:
            assert isinstance(state, GameState)
            assert state.combat is not None or state.room_phase != RoomPhase.COMBAT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
