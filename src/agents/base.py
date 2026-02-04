#!/usr/bin/env python3
"""
Agent 基类

定义所有 AI Agent 的统一接口，支持监督学习和强化学习无缝切换。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import numpy as np
import logging

from src.core.game_state import GameState
from src.core.action import Action

logger = logging.getLogger(__name__)


class Agent(ABC):
    """
    Agent 基类

    所有 AI 决策模块的统一接口。
    设计原则：
    - 统一的 select_action 接口
    - 支持 save/load 用于模型持久化
    - 提供训练回调用于 RL 学习
    - 提供概率输出用于分析和探索
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化 Agent

        Args:
            name: Agent 名称
            config: 配置字典
        """
        self.name = name
        self.config = config or {}
        self._episode_id = 0
        self._step_count = 0
        self._total_steps = 0
        self._total_episodes = 0

        # 训练状态
        self._training_mode = False

    # ==================== 核心方法 ====================

    @abstractmethod
    def select_action(self, state: GameState) -> Action:
        """
        选择动作

        这是 Agent 的核心方法，给定状态返回要执行的动作。

        Args:
            state: 当前游戏状态

        Returns:
            要执行的动作
        """
        pass

    def get_action_probabilities(self, state: GameState) -> np.ndarray:
        """
        获取动作概率分布

        用于：
        - 分析 Agent 行为
        - 探索策略（如 epsilon-greedy）
        - 模型集成

        Args:
            state: 当前游戏状态

        Returns:
            动作概率数组，shape=(ACTION_SPACE_SIZE,)
        """
        from src.core.action import ACTION_SPACE_SIZE

        # 默认实现：确定性策略
        # 子类可以重写以返回概率分布
        probs = np.zeros(ACTION_SPACE_SIZE, dtype=np.float32)
        action = self.select_action(state)
        action_id = action.to_id()
        if 0 <= action_id < ACTION_SPACE_SIZE:
            probs[action_id] = 1.0
        return probs

    def get_action_value(self, state: GameState) -> np.ndarray:
        """
        获取动作价值 Q(s, a)

        用于价值函数分析。

        Args:
            state: 当前游戏状态

        Returns:
            动作价值数组，shape=(ACTION_SPACE_SIZE,)
        """
        # 默认实现：不支持
        return np.zeros(11, dtype=np.float32)

    # ==================== 训练相关 ====================

    def on_episode_start(self, episode_id: int):
        """
        回合开始回调

        Args:
            episode_id: 回合 ID
        """
        self._episode_id = episode_id
        self._step_count = 0
        logger.debug(f"[{self.name}] Episode {episode_id} started")

    def on_step(self, action: Action, reward: float, next_state: GameState, done: bool):
        """
        每步回调

        用于 RL Agent 记录经验。

        Args:
            action: 执行的动作
            reward: 获得的奖励
            next_state: 下一个状态
            done: 是否结束
        """
        self._step_count += 1
        self._total_steps += 1

    def on_episode_end(self, reward: float, info: Optional[Dict] = None):
        """
        回合结束回调

        Args:
            reward: 总奖励
            info: 额外信息
        """
        self._total_episodes += 1
        logger.debug(
            f"[{self.name}] Episode {self._episode_id} ended, "
            f"reward: {reward:.2f}, steps: {self._step_count}"
        )

    def set_training_mode(self, training: bool):
        """
        设置训练/推理模式

        训练模式下可能使用探索策略（如 epsilon-greedy），
        推理模式下使用确定性策略。

        Args:
            training: True 表示训练模式，False 表示推理模式
        """
        self._training_mode = training
        logger.debug(f"[{self.name}] Training mode: {training}")

    @property
    def is_training(self) -> bool:
        """是否在训练模式"""
        return self._training_mode

    # ==================== 模型管理 ====================

    def save(self, path: str):
        """
        保存模型

        Args:
            path: 保存路径
        """
        logger.info(f"[{self.name}] Saving model to {path}")
        # 子类实现具体保存逻辑

    def load(self, path: str):
        """
        加载模型

        Args:
            path: 模型路径
        """
        logger.info(f"[{self.name}] Loading model from {path}")
        # 子类实现具体加载逻辑

    def get_metrics(self) -> Dict[str, Any]:
        """
        获取训练指标

        Returns:
            指标字典
        """
        return {
            "name": self.name,
            "episode_id": self._episode_id,
            "step_count": self._step_count,
            "total_steps": self._total_steps,
            "total_episodes": self._total_episodes,
            "training_mode": self._training_mode,
        }

    def log_metrics(self):
        """记录指标到日志"""
        metrics = self.get_metrics()
        logger.info(
            f"[{self.name}] Metrics: "
            f"episodes={metrics['total_episodes']}, "
            f"steps={metrics['total_steps']}, "
            f"training={metrics['training_mode']}"
        )

    # ==================== 辅助方法 ====================

    def reset_metrics(self):
        """重置所有计数器"""
        self._episode_id = 0
        self._step_count = 0
        self._total_steps = 0
        self._total_episodes = 0
        logger.debug(f"[{self.name}] Metrics reset")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', training={self._training_mode})"


class RuleBasedAgent(Agent):
    """规则 AI 基类

    基于硬编码规则的 Agent。
    """

    def select_action(self, state: GameState) -> Action:
        """选择动作（由子类实现）"""
        raise NotImplementedError("RuleBasedAgent subclasses must implement select_action")

    def get_action_probabilities(self, state: GameState) -> np.ndarray:
        """规则 AI 总是返回确定性概率"""
        return super().get_action_probabilities(state)

    def set_training_mode(self, training: bool):
        """规则 AI 不受训练模式影响"""
        pass


class SupervisedAgent(Agent):
    """监督学习 AI 基类

    从标记数据中学习策略的 Agent。
    """

    def __init__(self, name: str = "SupervisedAgent", config: Optional[Dict] = None):
        super().__init__(name, config)
        self._model = None
        self._encoder = None

    @abstractmethod
    def train(self, states: List, actions: List, **kwargs):
        """
        训练模型

        Args:
            states: 状态列表
            actions: 动作列表
            **kwargs: 其他训练参数
        """
        pass

    @abstractmethod
    def predict_proba(self, state: GameState) -> np.ndarray:
        """
        预测动作概率分布

        Args:
            state: 游戏状态

        Returns:
            动作概率数组
        """
        pass

    def predict(self, state: GameState) -> Action:
        """
        预测最佳动作

        Args:
            state: 游戏状态

        Returns:
            预测的动作
        """
        probs = self.predict_proba(state)
        action_id = int(np.argmax(probs))
        return Action.from_id(action_id)

    def select_action(self, state: GameState) -> Action:
        """使用模型预测动作"""
        if self._model is None:
            # 模型未训练，返回随机动作
            logger.warning(f"[{self.name}] Model not trained, returning random action")
            return Action.state()

        if self._training_mode:
            # 训练模式：根据概率采样（探索）
            probs = self.predict_proba(state)
            action_id = np.random.choice(len(probs), p=probs)
        else:
            # 推理模式：选择概率最高的动作（利用）
            action_id = int(np.argmax(self.predict_proba(state)))

        return Action.from_id(action_id)

    def get_action_probabilities(self, state: GameState) -> np.ndarray:
        """返回模型预测的概率分布"""
        from src.core.action import ACTION_SPACE_SIZE

        if self._model is None:
            # 模型未训练，返回均匀分布
            return np.ones(ACTION_SPACE_SIZE, dtype=np.float32) / ACTION_SPACE_SIZE
        return self.predict_proba(state)


class RLAgent(Agent):
    """强化学习 AI 基类

    从环境交互中学习策略的 Agent。
    """

    def __init__(self, name: str = "RLAgent", config: Optional[Dict] = None):
        super().__init__(name, config)
        self._policy = None
        self._value_fn = None
        self._env = None

    @abstractmethod
    def set_environment(self, env):
        """
        设置训练环境

        Args:
            env: Gymnasium 环境
        """
        pass

    @abstractmethod
    def train(self, total_timesteps: int, **kwargs):
        """
        训练 RL 模型

        Args:
            total_timesteps: 总训练步数
            **kwargs: 其他参数
                - n_envs: 并行环境数
                - learning_rate: 学习率
                - batch_size: 批次大小
        """
        pass

    @abstractmethod
    def learn_from_experience(self, experience):
        """
        从经验中学习

        Args:
            experience: 经验元组 (state, action, reward, next_state, done)
        """
        pass

    def load_sl_model(self, sl_agent: SupervisedAgent):
        """
        从监督学习模型初始化（Warm Start）

        将 SL 模型的权重复制到 RL 策略网络，
        可以显著加速 RL 训练收敛。

        Args:
            sl_agent: 训练好的监督学习 Agent
        """
        logger.info(f"[{self.name}] Loading SL model for warm-start")
        # 子类实现具体的权重复制逻辑
        raise NotImplementedError(f"{self.name} does not support SL warm-start")

    def select_action(self, state: GameState) -> Action:
        """使用策略网络选择动作"""
        if self._policy is None:
            logger.warning(f"[{self.name}] Policy not trained, returning random action")
            return Action.state()

        # 编码状态
        # 获取动作概率或价值
        # 选择动作
        # 子类实现具体逻辑
        raise NotImplementedError("Subclasses must implement select_action")

    def get_action_value(self, state: GameState) -> np.ndarray:
        """获取动作价值 Q(s, a)"""
        if self._value_fn is None:
            return np.zeros(11, dtype=np.float32)
        # 子类实现具体逻辑
        raise NotImplementedError("Subclasses must implement get_action_value")


# ==================== 工厂函数 ====================

def create_agent(agent_type: str, name: str = None, **kwargs) -> Agent:
    """
    创建 Agent 工厂函数

    Args:
        agent_type: Agent 类型 ("rule", "supervised", "rl")
        name: Agent 名称
        **kwargs: 其他参数

    Returns:
        Agent 实例
    """
    if name is None:
        name = agent_type.capitalize()

    if agent_type == "rule":
        # 需要延迟导入避免循环
        from src.agents.rule_based import RuleBasedAgentImpl
        return RuleBasedAgentImpl(name, **kwargs)
    elif agent_type == "supervised":
        from src.agents.supervised import SupervisedAgentImpl
        return SupervisedAgentImpl(name, **kwargs)
    elif agent_type == "rl":
        from src.agents.rl_agent import RLAgentImpl
        return RLAgentImpl(name, **kwargs)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")
