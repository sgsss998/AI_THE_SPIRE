#!/usr/bin/env python3
"""
监督学习训练脚本

从标记数据训练 SL 模型，用于 RL Warm Start 或直接部署。
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径，以便正确解析 from src.xxx 导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents import SupervisedAgentImpl, load_data_from_sessions
from src.core.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="训练监督学习 Agent")

    # 数据参数
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="训练数据目录（默认使用配置文件中的值）"
    )

    # 模型参数
    parser.add_argument(
        "--model-type",
        type=str,
        choices=["sklearn", "pytorch"],
        default="sklearn",
        help="模型类型（默认: sklearn）"
    )
    parser.add_argument(
        "--hidden-layers",
        type=int,
        nargs="+",
        default=[64, 32],
        help="隐藏层大小（默认: 64 32）"
    )

    # 训练参数
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.2,
        help="验证集比例（默认: 0.2）"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="训练轮数（默认: 100）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="批次大小（默认: 32）"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.001,
        help="学习率（默认: 0.001）"
    )

    # 输出参数
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="模型输出路径（默认自动生成）"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="SL_Model",
        help="模型名称（默认: SL_Model）"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    config = get_config()

    # 数据目录
    data_dir = args.data_dir or config.training.data_dir
    if data_dir is None:
        logger.error("请指定 --data-dir 或在配置文件中设置 training.data_dir")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("监督学习训练")
    logger.info("=" * 60)
    logger.info(f"数据目录: {data_dir}")
    logger.info(f"模型类型: {args.model_type}")
    logger.info(f"隐藏层: {args.hidden_layers}")
    logger.info(f"训练轮数: {args.epochs}")
    logger.info(f"批次大小: {args.batch_size}")
    logger.info(f"学习率: {args.learning_rate}")
    logger.info(f"验证集比例: {args.val_split}")
    logger.info("=" * 60)

    # 创建 Agent
    agent = SupervisedAgentImpl(
        args.name,
        config={
            "model_type": args.model_type,
        }
    )

    # 加载数据
    logger.info("正在加载数据...")
    states, actions = load_data_from_sessions(data_dir)

    if len(states) == 0:
        logger.error(f"未找到训练数据: {data_dir}")
        sys.exit(1)

    logger.info(f"加载了 {len(states)} 条样本")

    # 训练
    logger.info("开始训练...")
    result = agent.train(
        states,
        actions,
        val_split=args.val_split,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        hidden_layers=tuple(args.hidden_layers),
    )

    # 输出结果
    logger.info("=" * 60)
    logger.info("训练完成!")
    logger.info("=" * 60)
    acc = result.get('accuracy')
    train_acc = result.get('train_accuracy')
    logger.info(f"验证集准确率: {acc:.4f}" if acc is not None else "验证集准确率: N/A")
    logger.info(f"训练集准确率: {train_acc:.4f}" if train_acc is not None else "训练集准确率: N/A")
    logger.info(f"模型类型: {result.get('model_type')}")
    logger.info(f"隐藏层: {result.get('hidden_layers')}")
    logger.info("=" * 60)

    # 保存模型
    output_path = args.output or agent.get_model_path()
    logger.info(f"保存模型到: {output_path}")
    agent.save(output_path)

    logger.info("完成!")


if __name__ == "__main__":
    main()
