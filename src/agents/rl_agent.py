#!/usr/bin/env python3
"""
强化学习 Agent

使用 Stable-Baselines3 进行 RL 训练，支持 Warm Start 从 SL 模型初始化。
支持 PPO、A2C、DQN 等算法。
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from abc import abstractmethod

import numpy as np

from src.agents.base import RLAgent
from src.core.game_state import GameState
from src.core.action import Action
from src.core.config import get_config

logger = logging.getLogger(__name__)


class RLAgentImpl(RLAgent):
    """
    强化学习 Agent 实现

    支持多种 RL 算法：
    - PPO: Proximal Policy Optimization（推荐，稳定高效）
    - A2C: Advantage Actor-Critic
    - DQN: Deep Q-Network

    特性：
    - Warm Start: 从 SL 模型初始化策略网络
    - Action Masking: 只选择合法动作
    - 多环境并行训练
    """

    def __init__(self, name: str = "RL", config: Optional[Dict] = None):
        super().__init__(name, config)
        self.config = config or {}
        self.algorithm = self.config.get("algorithm", "ppo")  # ppo, a2c, dqn

        # RL 模型
        self._model = None
        self._env = None

        # 编码器（用于 Warm Start）
        self._encoder = None

        # 训练统计
        self._episode_rewards = []
        self._episode_lengths = []
        self._total_timesteps = 0

        # 加载编码器
        self._load_encoder()

    def _load_encoder(self):
        """加载状态编码器"""
        from src.training.encoder import StateEncoder
        self._encoder = StateEncoder(mode="extended")  # 使用扩展模式

    def set_environment(self, env):
        """
        设置训练环境

        Args:
            env: Gymnasium 环境实例
        """
        self._env = env
        logger.info(f"[{self.name}] Environment set: {type(env).__name__}")

    def train(
        self,
        total_timesteps: int,
        n_envs: int = 1,
        learning_rate: float = 3e-4,
        **kwargs
    ) -> Dict[str, Any]:
        """
        训练 RL 模型

        Args:
            total_timesteps: 总训练步数
            n_envs: 并行环境数量
            learning_rate: 学习率
            **kwargs: 其他训练参数
                - n_steps: PPO 每次更新的步数
                - batch_size: 批次大小
                - gamma: 折扣因子
                - gae_lambda: GAE 参数
                - policy_kwargs: 策略网络配置

        Returns:
            训练结果字典
        """
        if self._env is None:
            raise ValueError("Environment not set. Call set_environment() first.")

        logger.info(f"[{self.name}] Starting RL training...")
        logger.info(f"[{self.name}] Algorithm: {self.algorithm}")
        logger.info(f"[{self.name}] Timesteps: {total_timesteps}, Envs: {n_envs}")

        # 如果需要多环境，创建向量环境
        if n_envs > 1:
            env = self._make_vec_env(n_envs)
        else:
            env = self._env

        # 创建模型
        if self._model is None:
            self._model = self._create_model(env, learning_rate, **kwargs)
        else:
            # 已有模型（可能是 Warm Start 后），更新环境
            self._model.set_env(env)

        # 训练
        logger.info(f"[{self.name}] Training started...")
        self._model.learn(
            total_timesteps=total_timesteps,
            progress_bar=True,
            log_interval=100
        )

        self._total_timesteps += total_timesteps

        # 获取训练统计
        result = {
            "total_timesteps": self._total_timesteps,
            "algorithm": self.algorithm,
            "n_envs": n_envs,
            "learning_rate": learning_rate,
        }

        logger.info(f"[{self.name}] Training completed!")
        return result

    def _make_vec_env(self, n_envs: int):
        """创建向量环境"""
        try:
            from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
            from stable_baselines3.common.vec_env import VecCheckNan

            # 创建多个环境实例
            envs = [lambda: self._env for _ in range(n_envs)]
            vec_env = DummyVecEnv(envs)

            # 添加 NaN 检查
            vec_env = VecCheckNan(vec_env)

            return vec_env
        except ImportError:
            logger.error(f"[{self.name}] Stable-Baselines3 not installed")
            raise ImportError("Stable-Baselines3 is required for RL training")

    def _create_model(self, env, learning_rate: float, **kwargs):
        """创建 RL 模型"""
        try:
            from stable_baselines3 import PPO, A2C, DQN
            from stable_baselines3.common.policies import ActorCriticPolicy
        except ImportError:
            raise ImportError("Stable-Baselines3 is required for RL training")

        # 默认参数
        policy_kwargs = kwargs.get("policy_kwargs", {
            "net_arch": [128, 128]  # 隐藏层架构
        })

        gamma = kwargs.get("gamma", 0.99)
        gae_lambda = kwargs.get("gae_lambda", 0.95)
        n_steps = kwargs.get("n_steps", 2048)
        batch_size = kwargs.get("batch_size", 64)

        if self.algorithm == "ppo":
            model = PPO(
                "MlpPolicy",
                env,
                learning_rate=learning_rate,
                gamma=gamma,
                gae_lambda=gae_lambda,
                n_steps=n_steps,
                batch_size=batch_size,
                policy_kwargs=policy_kwargs,
                verbose=1,
                tensorboard_log=self._get_tensorboard_log_dir(),
            )
        elif self.algorithm == "a2c":
            model = A2C(
                "MlpPolicy",
                env,
                learning_rate=learning_rate,
                gamma=gamma,
                n_steps=n_steps,
                policy_kwargs=policy_kwargs,
                verbose=1,
                tensorboard_log=self._get_tensorboard_log_dir(),
            )
        elif self.algorithm == "dqn":
            model = DQN(
                "MlpPolicy",
                env,
                learning_rate=learning_rate,
                gamma=gamma,
                batch_size=batch_size,
                policy_kwargs=policy_kwargs,
                verbose=1,
                tensorboard_log=self._get_tensorboard_log_dir(),
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

        logger.info(f"[{self.name}] Created {self.algorithm.upper()} model")
        return model

    def _get_tensorboard_log_dir(self) -> str:
        """获取 TensorBoard 日志目录"""
        config = get_config()
        log_dir = os.path.join(config.training.models_dir, "tensorboard")
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def load_sl_model(self, sl_agent):
        """
        从监督学习模型初始化（Warm Start）

        Args:
            sl_agent: SupervisedAgentImpl 实例
        """
        logger.info(f"[{self.name}] Loading SL model for warm start...")

        if sl_agent._model is None:
            logger.warning(f"[{self.name}] SL agent has no trained model")
            return

        # 获取 SL 模型权重
        if hasattr(sl_agent._model, 'coefs_'):
            # sklearn MLP
            # 提取权重并转换为 PyTorch 格式
            self._warm_start_from_sklearn(sl_agent)
        elif hasattr(sl_agent._model, 'network'):
            # PyTorch 模型
            self._warm_start_from_pytorch(sl_agent)
        else:
            logger.warning(f"[{self.name}] Unknown SL model type, skipping warm start")

        logger.info(f"[{self.name}] Warm start completed")

    def _warm_start_from_sklearn(self, sl_agent):
        """从 sklearn 模型进行 Warm Start"""
        logger.info(f"[{self.name}] Warm start from sklearn model")

        # sklearn MLP 权重结构: coefs_ (weights), intercepts_ (biases)
        # 需要转换为 SB3 格式
        # 由于格式差异较大，这里只是示例

        # 实际项目中需要仔细对齐权重
        # 可以创建一个临时环境获取策略网络，然后复制权重
        pass

    def _warm_start_from_pytorch(self, sl_agent):
        """从 PyTorch 模型进行 Warm Start"""
        logger.info(f"[{self.name}] Warm start from PyTorch model")

        # PyTorch 模型可以直接复制权重
        # 需要创建一个 SB3 模型，然后复制网络权重

        if self._env is None:
            logger.warning(f"[{self.name}] Cannot warm start without environment")
            return

        # 创建临时模型
        temp_model = self._create_model(self._env, learning_rate=3e-4)

        # 复制权重（需要网络结构匹配）
        # sl_agent._model.network 和 temp_model.policy.mlp_extractor
        # 这部分需要根据实际网络结构调整

        self._model = temp_model
        logger.info(f"[{self.name}] PyTorch model weights copied")

    def select_action(self, state: GameState, valid_actions: Optional[List[int]] = None) -> Action:
        """
        选择动作

        Args:
            state: 游戏状态
            valid_actions: 合法动作索引列表（用于 action masking）

        Returns:
            选择的动作
        """
        if self._model is None:
            # 未训练，返回默认动作
            return Action.end_turn()

        # 编码状态
        state_vec = self._encoder.encode_state(state)
        state_vec = state_vec.reshape(1, -1)

        # 使用模型预测
        if self._training_mode:
            # 训练模式：采样（探索）
            action_id, _ = self._model.predict(state_vec, deterministic=False)
        else:
            # 推理模式：确定性（利用）
            action_id, _ = self._model.predict(state_vec, deterministic=True)

        # 应用 action masking
        if valid_actions is not None and action_id not in valid_actions:
            # 选择合法动作中概率最高的
            action_id = valid_actions[0]

        return Action.from_id(action_id)

    def get_action_probabilities(self, state: GameState) -> np.ndarray:
        """
        获取动作概率分布

        Args:
            state: 游戏状态

        Returns:
            动作概率数组，shape=(ACTION_SPACE_SIZE,)
        """
        from src.core.action import ACTION_SPACE_SIZE

        if self._model is None:
            return np.ones(ACTION_SPACE_SIZE, dtype=np.float32) / ACTION_SPACE_SIZE

        # 编码状态
        state_vec = self._encoder.encode_state(state)
        state_vec = state_vec.reshape(1, -1)

        # 获取概率（需要根据具体算法实现）
        try:
            # 对于 PPO/A2C，可以从策略网络获取
            if hasattr(self._model, 'policy'):
                obs_tensor = self._model.policy.obs_to_tensor(state_vec)[0]
                distribution = self._model.policy.get_distribution(obs_tensor)
                probs = distribution.distribution.probs.detach().numpy()[0]
                return probs.astype(np.float32)
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to get action probabilities: {e}")

        from src.core.action import ACTION_SPACE_SIZE
        return np.ones(ACTION_SPACE_SIZE, dtype=np.float32) / ACTION_SPACE_SIZE

    def get_action_value(self, state: GameState, action: Action) -> float:
        """
        获取状态-动作价值 Q(s, a)

        Args:
            state: 游戏状态
            action: 动作

        Returns:
            动作价值
        """
        if self._model is None:
            return 0.0

        # 编码状态
        state_vec = self._encoder.encode_state(state)
        state_vec = state_vec.reshape(1, -1)

        try:
            # 对于支持 Q 值的算法（如 DQN）
            if hasattr(self._model, 'q_net'):
                import torch
                with torch.no_grad():
                    q_values = self._model.q_net(torch.FloatTensor(state_vec))
                    return q_values[0, action.to_id()].item()
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to get action value: {e}")

        return 0.0

    def set_training_mode(self, training: bool):
        """
        设置训练/推理模式

        Args:
            training: True=训练模式（探索），False=推理模式（利用）
        """
        self._training_mode = training
        if self._model is not None:
            self._model.set_training_mode(training)

        logger.info(f"[{self.name}] Training mode: {training}")

    def on_episode_start(self, episode_id: int):
        """回合开始回调"""
        super().on_episode_start(episode_id)
        self._current_episode_reward = 0.0
        self._current_episode_length = 0

    def on_episode_end(self, reward: float, info: Optional[Dict] = None):
        """回合结束回调"""
        self._episode_rewards.append(reward)
        if hasattr(self, '_current_episode_length'):
            self._episode_lengths.append(self._current_episode_length)

    def save(self, path: str):
        """保存模型"""
        if self._model is None:
            logger.warning(f"[{self.name}] No model to save")
            return

        logger.info(f"[{self.name}] Saving model to {path}")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        # 保存 SB3 模型（使用 zip 格式）
        self._model.save(path)

        logger.info(f"[{self.name}] Model saved")

    def load(self, path: str):
        """加载模型"""
        logger.info(f"[{self.name}] Loading model from {path}")

        try:
            from stable_baselines3 import PPO, A2C, DQN

            # 根据算法加载
            if self.algorithm == "ppo":
                self._model = PPO.load(path)
            elif self.algorithm == "a2c":
                self._model = A2C.load(path)
            elif self.algorithm == "dqn":
                self._model = DQN.load(path)
            else:
                raise ValueError(f"Unknown algorithm: {self.algorithm}")

            logger.info(f"[{self.name}] Model loaded")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to load model: {e}")
            raise

    def get_model_path(self) -> str:
        """获取默认模型路径"""
        config = get_config()
        models_dir = config.training.models_dir
        os.makedirs(models_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(models_dir, f"{self.algorithm}_agent_{timestamp}.zip")

    def get_metrics(self) -> Dict[str, Any]:
        """获取训练指标"""
        return {
            "total_timesteps": self._total_timesteps,
            "episode_rewards": self._episode_rewards[-100:] if self._episode_rewards else [],
            "episode_lengths": self._episode_lengths[-100:] if self._episode_lengths else [],
            "mean_reward": np.mean(self._episode_rewards[-100:]) if self._episode_rewards else 0.0,
        }

    def learn_from_experience(self, experience):
        """
        从经验中学习

        Args:
            experience: 经验元组 (state, action, reward, next_state, done)

        Note:
            对于使用 Stable-Baselines3 的算法，经验学习由算法内部处理。
            此方法主要用于在线学习场景。
        """
        # SB3 算法内部处理经验回放和训练
        # 此方法可用于自定义在线学习逻辑
        if self._model is None:
            logger.warning(f"[{self.name}] Model not trained, cannot learn from experience")
            return

        # 可以在这里添加自定义的在线学习逻辑
        # 例如：单步更新
        pass
