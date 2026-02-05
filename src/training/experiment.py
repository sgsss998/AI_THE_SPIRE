#!/usr/bin/env python3
"""
实验管理模块

提供实验跟踪、记录、比较功能。
"""
import os
import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """实验配置"""

    # 实验基本信息
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)

    # Agent 配置
    agent_type: str = "rule"  # rule, supervised, rl
    model_type: str = "sklearn"  # sklearn, pytorch
    algorithm: str = "ppo"  # ppo, a2c, dqn

    # 训练配置
    data_dir: str = ""
    total_games: int = 0
    total_timesteps: int = 0
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    hidden_layers: List[int] = field(default_factory=list)

    # 环境配置
    character: str = "silent"
    ascension: int = 0

    # 其他
    sl_model_path: str = ""  # Warm Start 模型路径

    def to_hash(self) -> str:
        """生成配置哈希"""
        config_str = json.dumps(asdict(self), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]


@dataclass
class ExperimentResult:
    """实验结果"""

    # 实验标识
    experiment_id: str
    config_hash: str

    # 时间信息
    created_at: str
    completed_at: str = ""

    # 训练结果
    training_time: float = 0.0  # 秒
    total_steps: int = 0
    total_episodes: int = 0

    # 模型指标
    train_accuracy: float = 0.0
    val_accuracy: float = 0.0

    # 评估结果
    eval_episodes: int = 0
    eval_wins: int = 0
    eval_win_rate: float = 0.0
    eval_avg_reward: float = 0.0
    eval_avg_floors: float = 0.0

    # 模型路径
    model_path: str = ""

    # 状态
    status: str = "running"  # running, completed, failed

    # 额外信息
    metrics: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""


class ExperimentTracker:
    """实验跟踪器"""

    def __init__(self, experiments_dir: str = "experiments"):
        """
        初始化实验跟踪器

        Args:
            experiments_dir: 实验数据目录
        """
        self.experiments_dir = Path(experiments_dir)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)

        # 索引文件
        self.index_file = self.experiments_dir / "index.json"
        self._index = self._load_index()

    def _load_index(self) -> Dict[str, Dict]:
        """加载实验索引"""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_index(self):
        """保存实验索引"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def create_experiment(
        self,
        config: ExperimentConfig,
        experiment_id: str = None
    ) -> str:
        """
        创建新实验

        Args:
            config: 实验配置
            experiment_id: 实验 ID（可选，自动生成）

        Returns:
            实验 ID
        """
        # 生成实验 ID
        if experiment_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            config_hash = config.to_hash()
            experiment_id = f"{timestamp}_{config_hash}"

        # 创建实验目录
        exp_dir = self.experiments_dir / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)

        # 保存配置
        config_file = exp_dir / "config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(config), f, indent=2, ensure_ascii=False)

        # 创建结果
        result = ExperimentResult(
            experiment_id=experiment_id,
            config_hash=config.to_hash(),
            created_at=datetime.now().isoformat(),
        )

        # 保存结果
        self.save_result(experiment_id, result)

        # 更新索引
        self._index[experiment_id] = {
            "id": experiment_id,
            "name": config.name,
            "config_hash": config.to_hash(),
            "created_at": result.created_at,
            "status": "running",
        }
        self._save_index()

        logger.info(f"[Experiment] 创建实验: {experiment_id}")
        logger.info(f"  名称: {config.name}")
        logger.info(f"  配置哈希: {config.to_hash()}")

        return experiment_id

    def save_result(self, experiment_id: str, result: ExperimentResult):
        """保存实验结果"""
        exp_dir = self.experiments_dir / experiment_id
        result_file = exp_dir / "result.json"

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)

    def update_result(
        self,
        experiment_id: str,
        **updates
    ):
        """
        更新实验结果

        Args:
            experiment_id: 实验 ID
            **updates: 要更新的字段
        """
        result = self.get_result(experiment_id)
        if result is None:
            logger.warning(f"[Experiment] 实验不存在: {experiment_id}")
            return

        # 更新字段
        for key, value in updates.items():
            if hasattr(result, key):
                setattr(result, key, value)

        self.save_result(experiment_id, result)

        # 更新索引状态
        if experiment_id in self._index:
            self._index[experiment_id]["status"] = result.status
            self._save_index()

    def complete_experiment(
        self,
        experiment_id: str,
        model_path: str = None,
        notes: str = ""
    ):
        """
        标记实验完成

        Args:
            experiment_id: 实验 ID
            model_path: 模型路径
            notes: 备注
        """
        updates = {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
        }

        if model_path:
            updates["model_path"] = model_path
        if notes:
            updates["notes"] = notes

        self.update_result(experiment_id, **updates)
        logger.info(f"[Experiment] 实验完成: {experiment_id}")

    def fail_experiment(
        self,
        experiment_id: str,
        error: str = ""
    ):
        """
        标记实验失败

        Args:
            experiment_id: 实验 ID
            error: 错误信息
        """
        self.update_result(
            experiment_id,
            status="failed",
            notes=f"Error: {error}"
        )
        logger.error(f"[Experiment] 实验失败: {experiment_id} - {error}")

    def get_result(self, experiment_id: str) -> Optional[ExperimentResult]:
        """获取实验结果"""
        exp_dir = self.experiments_dir / experiment_id
        result_file = exp_dir / "result.json"

        if not result_file.exists():
            return None

        with open(result_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ExperimentResult(**data)

    def get_config(self, experiment_id: str) -> Optional[ExperimentConfig]:
        """获取实验配置"""
        exp_dir = self.experiments_dir / experiment_id
        config_file = exp_dir / "config.json"

        if not config_file.exists():
            return None

        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ExperimentConfig(**data)

    def list_experiments(
        self,
        status: str = None,
        tag: str = None
    ) -> List[Dict]:
        """
        列出实验

        Args:
            status: 过滤状态
            tag: 过滤标签

        Returns:
            实验列表
        """
        experiments = []

        for exp_id, info in self._index.items():
            # 过滤
            if status and info.get("status") != status:
                continue
            if tag:
                config = self.get_config(exp_id)
                if config and tag not in config.tags:
                    continue

            experiments.append(info)

        # 按创建时间排序
        experiments.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return experiments

    def compare_experiments(
        self,
        experiment_ids: List[str]
    ) -> Dict[str, Dict]:
        """
        比较实验

        Args:
            experiment_ids: 实验 ID 列表

        Returns:
            比较结果
        """
        comparison = {}

        for exp_id in experiment_ids:
            result = self.get_result(exp_id)
            config = self.get_config(exp_id)

            if result and config:
                comparison[exp_id] = {
                    "name": config.name,
                    "config": asdict(config),
                    "result": asdict(result),
                }

        return comparison

    def get_best_experiment(
        self,
        metric: str = "eval_win_rate",
        agent_type: str = None,
        status: str = "completed"
    ) -> Optional[Dict]:
        """
        获取最佳实验

        Args:
            metric: 比较指标
            agent_type: Agent 类型过滤
            status: 状态过滤

        Returns:
            最佳实验信息
        """
        best_exp = None
        best_value = float('-inf')

        for exp_id in self._index.keys():
            result = self.get_result(exp_id)
            config = self.get_config(exp_id)

            if not result or not config:
                continue

            # 过滤
            if status and result.status != status:
                continue
            if agent_type and config.agent_type != agent_type:
                continue

            # 比较指标
            value = getattr(result, metric, None)
            if value is None:
                continue

            if value > best_value:
                best_value = value
                best_exp = {
                    "id": exp_id,
                    "name": config.name,
                    "value": value,
                    "result": asdict(result),
                }

        return best_exp

    def delete_experiment(self, experiment_id: str):
        """删除实验"""
        import shutil

        exp_dir = self.experiments_dir / experiment_id

        if exp_dir.exists():
            shutil.rmtree(exp_dir)

        if experiment_id in self._index:
            del self._index[experiment_id]
            self._save_index()

        logger.info(f"[Experiment] 删除实验: {experiment_id}")


# 全局实例
_tracker: Optional[ExperimentTracker] = None


def get_tracker() -> ExperimentTracker:
    """获取全局实验跟踪器"""
    global _tracker
    if _tracker is None:
        from src.core.config import get_config
        config = get_config()
        exp_dir = getattr(config.training, "experiments_dir", "data/A20_Silent/experiments")
        _tracker = ExperimentTracker(experiments_dir=exp_dir)
    return _tracker


def create_experiment(
    name: str,
    agent_type: str = "rule",
    **kwargs
) -> str:
    """
    快捷创建实验

    Args:
        name: 实验名称
        agent_type: Agent 类型
        **kwargs: 其他配置参数

    Returns:
        实验 ID
    """
    config = ExperimentConfig(
        name=name,
        agent_type=agent_type,
        **kwargs
    )

    return get_tracker().create_experiment(config)
