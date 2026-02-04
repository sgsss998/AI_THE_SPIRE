#!/usr/bin/env python3
"""
监督学习 Agent

从标记数据中学习策略的 Agent。
支持 sklearn 和 PyTorch 后端。
"""
import os
import pickle
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

import numpy as np

from src.agents.base import SupervisedAgent
from src.core.game_state import GameState
from src.core.action import Action
from src.core.config import get_config

logger = logging.getLogger(__name__)


class SupervisedAgentImpl(SupervisedAgent):
    """
    监督学习 Agent 实现

    支持多种后端：
    - sklearn: 用于快速原型和小规模训练
    - pytorch: 用于大规模训练和生产部署
    """

    def __init__(self, name: str = "Supervised", config: Optional[Dict] = None):
        super().__init__(name, config)
        self.config = config or {}
        self.model_type = self.config.get("model_type", "sklearn")

        # 模型实例
        self._model = None
        self._encoder = None

        # 训练历史
        self._training_history = []

        # 加载编码器
        self._load_encoder()

    def _load_encoder(self):
        """加载状态编码器"""
        from src.training.encoder import StateEncoder
        self._encoder = StateEncoder(mode="extended")  # 使用扩展模式

    def train(
        self,
        states: List[GameState],
        actions: List[Action],
        **kwargs
    ) -> Dict[str, Any]:
        """
        训练模型

        Args:
            states: 状态列表
            actions: 动作列表
            **kwargs: 训练参数
                - val_split: 验证集比例
                - epochs: 训练轮数
                - batch_size: 批次大小
                - learning_rate: 学习率

        Returns:
            训练结果字典
        """
        logger.info(f"[{self.name}] Starting training with {len(states)} samples")

        # 编码状态和动作
        X = self._encode_states(states)
        y = self._encode_actions(actions)

        logger.info(f"[{self.name}] X shape: {X.shape}, y shape: {y.shape}")

        # 根据模型类型训练
        if self.model_type == "sklearn":
            result = self._train_sklearn(X, y, **kwargs)
        elif self.model_type == "pytorch":
            result = self._train_pytorch(X, y, **kwargs)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        self._model = result["model"]
        self._training_history.append(result)

        logger.info(f"[{self.name}] Training completed. Accuracy: {result.get('accuracy', 'N/A')}")
        return result

    def _encode_states(self, states: List[GameState]) -> np.ndarray:
        """编码状态为向量"""
        encoded = []
        for state in states:
            vec = self._encoder.encode_state(state)
            encoded.append(vec)
        return np.array(encoded)

    def _encode_actions(self, actions: List[Action]) -> np.ndarray:
        """编码动作为标签"""
        return np.array([a.to_id() for a in actions])

    def _train_sklearn(
        self,
        X: np.ndarray,
        y: np.ndarray,
        val_split: float = 0.2,
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        hidden_layers: tuple = (64, 32),
        **kwargs
    ) -> Dict[str, Any]:
        """
        使用 sklearn 训练 MLP 模型

        Args:
            X: 状态向量
            y: 动作标签
            val_split: 验证集比例
            epochs: 最大迭代次数
            batch_size: 批次大小
            learning_rate: 学习率
            hidden_layers: 隐藏层大小

        Returns:
            训练结果
        """
        from sklearn.neural_network import MLPClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, classification_report

        # 划分训练/验证集
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=val_split, random_state=42, stratify=y
        )

        # 创建模型
        model = MLPClassifier(
            hidden_layer_sizes=hidden_layers,
            activation='relu',
            solver='adam',
            learning_rate_init=learning_rate,
            max_iter=epochs,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=20,
            random_state=42,
            batch_size=batch_size,
        )

        # 训练
        logger.info(f"[{self.name}] Training sklearn MLP...")
        model.fit(X_train, y_train)

        # 评估
        train_pred = model.predict(X_train)
        val_pred = model.predict(X_val)

        train_acc = accuracy_score(y_train, train_pred)
        val_acc = accuracy_score(y_val, val_pred)

        logger.info(f"[{self.name}] Train accuracy: {train_acc:.4f}")
        logger.info(f"[{self.name}] Val accuracy: {val_acc:.4f}")

        return {
            "model": model,
            "accuracy": val_acc,
            "train_accuracy": train_acc,
            "model_type": "sklearn",
            "hidden_layers": hidden_layers,
        }

    def _train_pytorch(
        self,
        X: np.ndarray,
        y: np.ndarray,
        val_split: float = 0.2,
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        hidden_layers: tuple = (64, 32),
        **kwargs
    ) -> Dict[str, Any]:
        """
        使用 PyTorch 训练神经网络

        Args:
            X: 状态向量
            y: 动作标签
            val_split: 验证集比例
            epochs: 训练轮数
            batch_size: 批次大小
            learning_rate: 学习率
            hidden_layers: 隐藏层大小

        Returns:
            训练结果
        """
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from torch.utils.data import DataLoader, TensorDataset
        except ImportError:
            logger.error(f"[{self.name}] PyTorch not installed")
            raise ImportError("PyTorch is required for model_type='pytorch'")

        # 划分训练/验证集
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=val_split, random_state=42, stratify=y
        )

        # 转换为 Tensor
        X_train_t = torch.FloatTensor(X_train)
        y_train_t = torch.LongTensor(y_train)
        X_val_t = torch.FloatTensor(X_val)
        y_val_t = torch.LongTensor(y_val)

        # 创建 DataLoader
        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        # 定义模型
        class PolicyNet(nn.Module):
            def __init__(self, input_dim=30, hidden_layers=(64, 32), output_dim=11):
                super().__init__()
                layers = []
                prev_dim = input_dim
                for dim in hidden_layers:
                    layers.append(nn.Linear(prev_dim, dim))
                    layers.append(nn.ReLU())
                    prev_dim = dim
                layers.append(nn.Linear(prev_dim, output_dim))
                self.network = nn.Sequential(*layers)

            def forward(self, x):
                return self.network(x)

        model = PolicyNet(
            input_dim=X.shape[1],
            hidden_layers=hidden_layers,
            output_dim=11
        )

        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)

        # 训练循环
        logger.info(f"[{self.name}] Training PyTorch model...")
        for epoch in range(epochs):
            model.train()
            epoch_loss = 0.0
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            # 验证
            model.eval()
            with torch.no_grad():
                val_outputs = model(X_val_t)
                val_pred = val_outputs.argmax(dim=1).numpy()
                val_acc = (val_pred == y_val).mean()

            if (epoch + 1) % 20 == 0:
                logger.info(
                    f"[{self.name}] Epoch {epoch+1}/{epochs}, "
                    f"Loss: {epoch_loss/len(train_loader):.4f}, "
                    f"Val Acc: {val_acc:.4f}"
                )

        logger.info(f"[{self.name}] Training completed")
        return {
            "model": model,
            "accuracy": val_acc,
            "model_type": "pytorch",
            "hidden_layers": hidden_layers,
        }

    def predict_proba(self, state: GameState) -> np.ndarray:
        """
        预测动作概率分布

        Args:
            state: 游戏状态

        Returns:
            动作概率数组，shape=(11,)
        """
        if self._model is None:
            # 未训练，返回均匀分布
            return np.ones(11, dtype=np.float32) / 11

        # 编码状态
        state_vec = self._encoder.encode_state(state)
        state_vec = state_vec.reshape(1, -1)

        # 获取概率
        if self.model_type == "sklearn":
            proba = self._model.predict_proba(state_vec)[0]
        else:  # pytorch
            try:
                import torch
                with torch.no_grad():
                    output = self._model(torch.FloatTensor(state_vec))
                    proba = torch.softmax(output, dim=1).numpy()
            except Exception as e:
                logger.error(f"[{self.name}] PyTorch prediction error: {e}")
                return np.ones(11, dtype=np.float32) / 11

        return proba.astype(np.float32)

    def save(self, path: str):
        """保存模型"""
        logger.info(f"[{self.name}] Saving model to {path}")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        save_data = {
            "model": self._model,
            "model_type": self.model_type,
            "config": self.config,
            "training_history": self._training_history,
            "encoder": self._encoder,
        }

        with open(path, 'wb') as f:
            pickle.dump(save_data, f)

        logger.info(f"[{self.name}] Model saved")

    def load(self, path: str):
        """加载模型"""
        logger.info(f"[{self.name}] Loading model from {path}")

        with open(path, 'rb') as f:
            save_data = pickle.load(f)

        self._model = save_data["model"]
        self.model_type = save_data.get("model_type", "sklearn")
        self.config = save_data.get("config", {})
        self._training_history = save_data.get("training_history", [])
        self._encoder = save_data.get("encoder")

        logger.info(f"[{self.name}] Model loaded (type: {self.model_type})")

    def get_model_path(self) -> str:
        """获取默认模型路径"""
        config = get_config()
        models_dir = config.training.models_dir
        os.makedirs(models_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(models_dir, f"{self.model_type}_agent_{timestamp}.pkl")


# ==================== 数据加载辅助函数 ====================

def load_training_data(data_dir: str) -> tuple:
    """
    加载训练数据

    Args:
        data_dir: 数据目录路径

    Returns:
        (states, actions) 元组
    """
    import json
    from src.core.game_state import GameState

    states = []
    actions = []

    # 扫描数据文件
    data_path = Path(data_dir)
    jsonl_files = sorted(data_path.glob("*.jsonl"))

    logger.info(f"[load_training_data] Found {len(jsonl_files)} data files")

    for jsonl_file in jsonl_files:
        logger.info(f"[load_training_data] Loading {jsonl_file.name}")
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    # 解析状态
                    state = GameState.from_mod_response(record.get("state", record))
                    action_str = record.get("action", "")
                    action = Action.from_command(action_str)

                    states.append(state)
                    actions.append(action)
                except Exception as e:
                    logger.warning(f"Failed to parse record: {e}")

    logger.info(f"[load_training_data] Loaded {len(states)} samples")
    return states, actions


def load_data_from_sessions(data_dir: str) -> tuple:
    """
    从会话文件加载训练数据

    Args:
        data_dir: combat_logs/sessions 目录路径

    Returns:
        (states, actions) 元组
    """
    return load_training_data(data_dir)
