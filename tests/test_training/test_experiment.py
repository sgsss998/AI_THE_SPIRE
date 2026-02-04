#!/usr/bin/env python3
"""
实验管理模块单元测试
"""
import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.training.experiment import (
    ExperimentTracker,
    ExperimentConfig,
    ExperimentResult,
    get_tracker,
    create_experiment,
)


class TestExperimentConfig:
    """ExperimentConfig 测试"""

    def test_create_config(self):
        """测试创建配置"""
        config = ExperimentConfig(
            name="test_exp",
            agent_type="supervised",
            model_type="pytorch",
        )

        assert config.name == "test_exp"
        assert config.agent_type == "supervised"
        assert config.model_type == "pytorch"

    def test_config_hash(self):
        """测试配置哈希"""
        config1 = ExperimentConfig(name="test", agent_type="supervised")
        config2 = ExperimentConfig(name="test", agent_type="supervised")
        config3 = ExperimentConfig(name="test", agent_type="rl")

        hash1 = config1.to_hash()
        hash2 = config2.to_hash()
        hash3 = config3.to_hash()

        # 相同配置应该有相同哈希
        assert hash1 == hash2
        # 不同配置应该有不同哈希
        assert hash1 != hash3


class TestExperimentTracker:
    """ExperimentTracker 测试"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.tracker = ExperimentTracker(experiments_dir=self.temp_dir)

    def teardown_method(self):
        """每个测试后清理临时目录"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_experiment(self):
        """测试创建实验"""
        config = ExperimentConfig(
            name="test_exp",
            agent_type="supervised",
        )

        exp_id = self.tracker.create_experiment(config)

        assert exp_id is not None
        assert exp_id in self.tracker._index

    def test_save_and_get_result(self):
        """测试保存和获取结果"""
        config = ExperimentConfig(name="test")
        exp_id = self.tracker.create_experiment(config, experiment_id="test_001")

        result = ExperimentResult(
            experiment_id=exp_id,
            config_hash=config.to_hash(),
            created_at="2024-01-01T00:00:00",
            eval_win_rate=0.5,
        )

        self.tracker.save_result(exp_id, result)

        retrieved = self.tracker.get_result(exp_id)

        assert retrieved is not None
        assert retrieved.experiment_id == exp_id
        assert retrieved.eval_win_rate == 0.5

    def test_update_result(self):
        """测试更新结果"""
        config = ExperimentConfig(name="test")
        exp_id = self.tracker.create_experiment(config)

        self.tracker.update_result(
            exp_id,
            eval_win_rate=0.75,
            total_steps=1000,
        )

        result = self.tracker.get_result(exp_id)

        assert result.eval_win_rate == 0.75
        assert result.total_steps == 1000

    def test_complete_experiment(self):
        """测试完成实验"""
        config = ExperimentConfig(name="test")
        exp_id = self.tracker.create_experiment(config)

        self.tracker.complete_experiment(
            exp_id,
            model_path="models/test.pkl",
            notes="Test completed"
        )

        result = self.tracker.get_result(exp_id)

        assert result.status == "completed"
        assert result.model_path == "models/test.pkl"
        assert result.notes == "Test completed"

    def test_fail_experiment(self):
        """测试失败实验"""
        config = ExperimentConfig(name="test")
        exp_id = self.tracker.create_experiment(config)

        self.tracker.fail_experiment(exp_id, error="Test error")

        result = self.tracker.get_result(exp_id)

        assert result.status == "failed"
        assert "Test error" in result.notes

    def test_list_experiments(self):
        """测试列出实验"""
        config1 = ExperimentConfig(name="exp1", agent_type="supervised")
        config2 = ExperimentConfig(name="exp2", agent_type="rl")

        exp_id1 = self.tracker.create_experiment(config1, experiment_id="exp_001")
        exp_id2 = self.tracker.create_experiment(config2, experiment_id="exp_002")

        # 完成一个
        self.tracker.complete_experiment(exp_id1)

        # 列出所有
        all_exps = self.tracker.list_experiments()
        assert len(all_exps) == 2

        # 过滤状态
        completed = self.tracker.list_experiments(status="completed")
        assert len(completed) == 1
        assert completed[0]["id"] == exp_id1

    def test_get_best_experiment(self):
        """测试获取最佳实验"""
        config1 = ExperimentConfig(name="exp1", agent_type="supervised")
        config2 = ExperimentConfig(name="exp2", agent_type="supervised")

        exp_id1 = self.tracker.create_experiment(config1, experiment_id="exp_001")
        exp_id2 = self.tracker.create_experiment(config2, experiment_id="exp_002")

        # 设置不同的胜率
        self.tracker.update_result(exp_id1, eval_win_rate=0.5, status="completed")
        self.tracker.update_result(exp_id2, eval_win_rate=0.75, status="completed")

        best = self.tracker.get_best_experiment(metric="eval_win_rate")

        assert best is not None
        assert best["id"] == exp_id2
        assert best["value"] == 0.75

    def test_delete_experiment(self):
        """测试删除实验"""
        config = ExperimentConfig(name="test")
        exp_id = self.tracker.create_experiment(config, experiment_id="exp_001")

        assert exp_id in self.tracker._index

        self.tracker.delete_experiment(exp_id)

        assert exp_id not in self.tracker._index

    def test_compare_experiments(self):
        """测试比较实验"""
        config1 = ExperimentConfig(name="exp1", agent_type="supervised")
        config2 = ExperimentConfig(name="exp2", agent_type="supervised")

        exp_id1 = self.tracker.create_experiment(config1, experiment_id="exp_001")
        exp_id2 = self.tracker.create_experiment(config2, experiment_id="exp_002")

        comparison = self.tracker.compare_experiments([exp_id1, exp_id2])

        assert exp_id1 in comparison
        assert exp_id2 in comparison
        assert comparison[exp_id1]["name"] == "exp1"
        assert comparison[exp_id2]["name"] == "exp2"


class TestGlobalFunctions:
    """测试全局函数"""

    def test_create_experimentShortcut(self):
        """测试快捷创建实验"""
        with tempfile.TemporaryDirectory() as temp_dir:
            import src.training.experiment as exp_module
            original_tracker = exp_module._tracker

            try:
                # 使用临时目录
                exp_module._tracker = ExperimentTracker(experiments_dir=temp_dir)

                exp_id = create_experiment(
                    name="test_exp",
                    agent_type="supervised",
                    model_type="pytorch",
                )

                assert exp_id is not None

            finally:
                exp_module._tracker = original_tracker


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
