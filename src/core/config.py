#!/usr/bin/env python3
"""
配置管理

使用 YAML 配置文件，支持环境变量覆盖。
所有可配置的参数都集中在这里。
"""
import os
import yaml
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass
class ModelConfig:
    """模型配置"""
    type: str = "sklearn"  # sklearn, torch, tf
    hidden_layers: List[int] = field(default_factory=lambda: [64, 32])
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    max_iter: int = 500


@dataclass
class TrainingConfig:
    """训练配置"""
    # 数据路径
    data_dir: str = "data"
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    models_dir: str = "data/models"

    # 训练参数
    train_val_split: float = 0.2
    early_stopping_patience: int = 10

    # RL 参数
    rl_algorithm: str = "PPO"
    total_timesteps: int = 1_000_000
    n_envs: int = 1
    gamma: float = 0.99

    # 模型配置
    model: ModelConfig = field(default_factory=ModelConfig)


@dataclass
class GameConfig:
    """游戏配置"""
    character: str = "silent"  # silent, ironclad, defect
    ascension: int = 0
    max_hp: int = 70
    base_energy: int = 3

    # 卡牌定义
    card_library_path: str = "configs/cards/silent.yaml"

    # 怪物定义
    monster_library_path: str = "configs/monsters.yaml"


@dataclass
class LogConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    enable_slim_logging: bool = True  # 精简日志（仅保留训练所需字段）


@dataclass
class ProtocolConfig:
    """协议配置"""
    null_stuck_timeout: float = 10.0  # null 状态超时时间（秒）
    fallback_commands: List[str] = field(
        default_factory=lambda: ["key Confirm", "wait", "choose 0", "choose 1", "choose 2"]
    )


@dataclass
class Config:
    """总配置"""
    training: TrainingConfig = field(default_factory=TrainingConfig)
    game: GameConfig = field(default_factory=GameConfig)
    log: LogConfig = field(default_factory=LogConfig)
    protocol: ProtocolConfig = field(default_factory=ProtocolConfig)

    # 环境变量覆盖
    no_log: bool = False
    use_model: bool = False
    debug: bool = False

    @classmethod
    def load(cls, path: str = "configs/default.yaml") -> 'Config':
        """从 YAML 文件加载配置

        Args:
            path: 配置文件路径

        Returns:
            Config 对象
        """
        if not os.path.exists(path):
            return cls()

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """从字典创建"""
        training_data = data.get("training", {})
        game_data = data.get("game", {})
        log_data = data.get("log", {})
        protocol_data = data.get("protocol", {})

        return cls(
            training=TrainingConfig(
                **{k: v for k, v in training_data.items() if k != "model"},
                model=ModelConfig(**training_data.get("model", {}))
            ),
            game=GameConfig(**game_data),
            log=LogConfig(**log_data),
            protocol=ProtocolConfig(**protocol_data),
            no_log=os.getenv("AI_STS_NO_LOG", "").lower() == "1",
            use_model=os.getenv("AI_STS_USE_MODEL", "").lower() == "1",
            debug=os.getenv("AI_STS_DEBUG", "").lower() == "1",
        )

    def save(self, path: str):
        """保存配置到 YAML

        Args:
            path: 保存路径
        """
        data = {
            "training": {
                **{k: v for k, v in self.training.__dict__.items() if k != "model"},
                "model": self.training.model.__dict__,
            },
            "game": self.game.__dict__,
            "log": self.log.__dict__,
            "protocol": self.protocol.__dict__,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def get_model_path(self) -> str:
        """获取模型路径"""
        return os.path.join(self.training.models_dir, f"{self.training.model.type}_model.pkl")

    def get_session_path(self) -> str:
        """获取当前会话日志路径"""
        from datetime import datetime
        os.makedirs(self.training.raw_dir, exist_ok=True)
        name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jsonl"
        return os.path.join(self.training.raw_dir, name)


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def set_config(config: Config):
    """设置全局配置"""
    global _config
    _config = config


def reload_config(path: str = "configs/default.yaml"):
    """重新加载配置"""
    global _config
    _config = Config.load(path)
    return _config
