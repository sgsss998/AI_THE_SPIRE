#!/usr/bin/env python3
"""
监督学习 Agent

从标记数据中学习策略的 Agent。
支持 sklearn 和 PyTorch 后端。
"""
import os
import pickle
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime

import numpy as np

from src.agents.base import SupervisedAgent
from src.core.game_state import GameState
from src.core.action import Action
from src.core.config import get_config

logger = logging.getLogger(__name__)


def _create_policy_net(input_dim, hidden_layers, output_dim):
    """创建 PyTorch 策略网络（模块级函数，便于 pickle）"""
    import torch.nn as nn
    layers = []
    prev_dim = input_dim
    for dim in hidden_layers:
        layers.append(nn.Linear(prev_dim, dim))
        layers.append(nn.ReLU())
        prev_dim = dim
    layers.append(nn.Linear(prev_dim, output_dim))
    return nn.Sequential(*layers)


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
        self._encoder_encode_fn = None
        self._encoder_output_dim = None

        # 训练历史
        self._training_history = []

        # 加载编码器
        self._load_encoder()

    def _load_encoder(self):
        """加载 MVP 状态编码器"""
        from src.training.encoder_mvp import encode, get_output_dim
        self._encoder_encode_fn = encode
        self._encoder_output_dim = get_output_dim()

    def _encoder_encode(self, state_or_dict: Union[GameState, Dict]) -> np.ndarray:
        """编码状态为向量，支持 GameState 或 Mod 格式 dict。"""
        if isinstance(state_or_dict, dict):
            return self._encoder_encode_fn(state_or_dict)
        return self._encoder_encode_fn(state_or_dict.to_mod_response())

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

    def _encode_states(self, states) -> np.ndarray:
        """编码状态为向量"""
        encoded = []
        for state in states:
            vec = self._encoder_encode(state)
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

        # 划分训练/验证集（纯 numpy，避免 sklearn 的 NumPy 2.x 兼容性问题）
        n = len(X)
        np.random.seed(42)
        indices = np.random.permutation(n)
        n_val = int(n * val_split)
        val_idx = indices[:n_val]
        train_idx = indices[n_val:]
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        # 转换为 Tensor
        X_train_t = torch.FloatTensor(X_train)
        y_train_t = torch.LongTensor(y_train)
        X_val_t = torch.FloatTensor(X_val)
        y_val_t = torch.LongTensor(y_val)

        # 创建 DataLoader
        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        # 定义模型（使用模块级函数，便于 pickle）
        from src.core.action import ACTION_SPACE_SIZE

        model = _create_policy_net(
            input_dim=X.shape[1],
            hidden_layers=hidden_layers,
            output_dim=ACTION_SPACE_SIZE,
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

            # 验证（避免 .numpy() 在 NumPy 2.x 下的兼容性问题）
            model.eval()
            with torch.no_grad():
                val_outputs = model(X_val_t)
                val_pred = val_outputs.argmax(dim=1).tolist()
                val_acc = sum(1 for p, t in zip(val_pred, y_val) if p == t) / len(y_val) if len(y_val) > 0 else 0.0

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

    def predict_proba(self, state) -> np.ndarray:
        """
        预测动作概率分布

        Args:
            state: 游戏状态（GameState 或 Mod 格式 dict）

        Returns:
            动作概率数组，shape=(179,)
        """
        from src.core.action import ACTION_SPACE_SIZE

        if self._model is None:
            return np.ones(ACTION_SPACE_SIZE, dtype=np.float32) / ACTION_SPACE_SIZE

        state_vec = self._encoder_encode(state)
        state_vec = state_vec.reshape(1, -1)

        if self.model_type == "sklearn":
            proba = self._model.predict_proba(state_vec)[0]
        else:
            try:
                import torch
                with torch.no_grad():
                    output = self._model(torch.FloatTensor(state_vec))
                    proba = torch.softmax(output, dim=1).numpy()[0]
            except Exception as e:
                logger.error(f"[{self.name}] PyTorch prediction error: {e}")
                return np.ones(ACTION_SPACE_SIZE, dtype=np.float32) / ACTION_SPACE_SIZE

        return proba.astype(np.float32)

    def save(self, path: str):
        """保存模型"""
        logger.info(f"[{self.name}] Saving model to {path}")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        from src.training.encoder_mvp import encode
        save_data = {
            "model": self._model,
            "model_type": self.model_type,
            "config": self.config,
            "training_history": self._training_history,
            "encoder_module": "encoder_mvp",
            "encoder_encode": encode,
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
        self._encoder_encode_fn = save_data.get("encoder_encode")
        if self._encoder_encode_fn is None:
            from src.training.encoder_mvp import encode, get_output_dim
            self._encoder_encode_fn = encode
            self._encoder_output_dim = get_output_dim()
        else:
            from src.training.encoder_mvp import get_output_dim
            self._encoder_output_dim = get_output_dim()

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

    # 扫描数据文件：支持 Raw_Data_json_FORSL 的 .json（JSON 数组）和 session.jsonl
    data_path = Path(data_dir)
    json_files = sorted(data_path.glob("**/*.json"))
    jsonl_files = sorted(data_path.glob("**/*.jsonl"))

    logger.info(f"[load_training_data] Found {len(json_files)} .json, {len(jsonl_files)} .jsonl files")

    def _parse_record(record: dict):
        """从 record 解析 state 和 action。record 可能是 {state, action} 或 {mod_fields, action}"""
        mod_data = record.get("state", record)
        action_str = record.get("action", "")
        if not action_str or action_str in ("state", "wait"):
            return None, None  # 跳过无决策帧
        state = GameState.from_mod_response(mod_data)
        action = Action.from_command(action_str)
        return state, action

    for f in json_files:
        logger.info(f"[load_training_data] Loading {f.name}")
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                arr = json.load(fp)
            if not isinstance(arr, list):
                continue
            for record in arr:
                try:
                    s, a = _parse_record(record)
                    if s is not None and a is not None:
                        states.append(s)
                        actions.append(a)
                except Exception as e:
                    logger.warning(f"Failed to parse record: {e}")
        except Exception as e:
            logger.warning(f"Failed to load {f}: {e}")

    for jsonl_file in jsonl_files:
        logger.info(f"[load_training_data] Loading {jsonl_file.name}")
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    s, a = _parse_record(record)
                    if s is not None and a is not None:
                        states.append(s)
                        actions.append(a)
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
