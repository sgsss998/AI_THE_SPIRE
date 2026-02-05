#!/usr/bin/env python3
"""
强化学习训练脚本

使用 Gymnasium 环境和 Stable-Baselines3 训练 RL Agent。
支持 Warm Start 从 SL 模型初始化。
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径，以便正确解析 from src.xxx 导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents import RLAgentImpl, SupervisedAgentImpl, create_agent
from src.env import StsEnvWrapper
from src.core.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="训练强化学习 Agent")

    # 算法参数
    parser.add_argument(
        "--algorithm",
        type=str,
        choices=["ppo", "a2c", "dqn"],
        default="ppo",
        help="RL 算法（默认: ppo）"
    )

    # Warm Start 参数
    parser.add_argument(
        "--sl-model",
        type=str,
        default=None,
        help="SL 模型路径，用于 Warm Start"
    )

    # 环境参数
    parser.add_argument(
        "--character",
        type=str,
        default="silent",
        help="角色（默认: silent）"
    )
    parser.add_argument(
        "--ascension",
        type=int,
        default=0,
        help=" Ascension 等级（默认: 0）"
    )

    # 训练参数
    parser.add_argument(
        "--timesteps",
        type=int,
        default=100000,
        help="总训练步数（默认: 100000）"
    )
    parser.add_argument(
        "--n-envs",
        type=int,
        default=1,
        help="并行环境数量（默认: 1）"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=3e-4,
        help="学习率（默认: 3e-4）"
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.99,
        help="折扣因子（默认: 0.99）"
    )
    parser.add_argument(
        "--n-steps",
        type=int,
        default=2048,
        help="每次更新步数（PPO/A2C，默认: 2048）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="批次大小（默认: 64）"
    )
    parser.add_argument(
        "--hidden-layers",
        type=int,
        nargs="+",
        default=[128, 128],
        help="策略网络隐藏层（默认: 128 128）"
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
        default="RL_Model",
        help="模型名称（默认: RL_Model）"
    )

    # 其他
    parser.add_argument(
        "--no-train",
        action="store_true",
        help="不训练，仅创建环境测试"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    config = get_config()

    logger.info("=" * 60)
    logger.info("强化学习训练")
    logger.info("=" * 60)
    logger.info(f"算法: {args.algorithm.upper()}")
    logger.info(f"训练步数: {args.timesteps}")
    logger.info(f"并行环境: {args.n_envs}")
    logger.info(f"学习率: {args.learning_rate}")
    logger.info(f"折扣因子: {args.gamma}")
    logger.info(f"隐藏层: {args.hidden_layers}")
    logger.info("=" * 60)

    # 创建环境
    logger.info("创建环境...")
    env = StsEnvWrapper(
        character=args.character,
        ascension=args.ascension,
    )

    logger.info(f"观察空间: {env.observation_space}")
    logger.info(f"动作空间: {env.action_space}")

    # 创建 Agent
    agent = RLAgentImpl(
        args.name,
        config={
            "algorithm": args.algorithm,
        }
    )

    # 设置环境
    agent.set_environment(env)

    # Warm Start
    if args.sl_model:
        logger.info(f"从 SL 模型加载: {args.sl_model}")
        sl_agent = SupervisedAgentImpl("SL_For_WarmStart")
        sl_agent.load(args.sl_model)
        agent.load_sl_model(sl_agent)

    # 训练
    if not args.no_train:
        logger.info("开始训练...")
        result = agent.train(
            total_timesteps=args.timesteps,
            n_envs=args.n_envs,
            learning_rate=args.learning_rate,
            gamma=args.gamma,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            policy_kwargs={
                "net_arch": args.hidden_layers,
            }
        )

        # 输出结果
        logger.info("=" * 60)
        logger.info("训练完成!")
        logger.info("=" * 60)
        logger.info(f"总训练步数: {result['total_timesteps']}")
        logger.info(f"算法: {result['algorithm']}")
        logger.info(f"并行环境: {result['n_envs']}")
        logger.info("=" * 60)

        # 保存模型
        output_path = args.output or agent.get_model_path()
        logger.info(f"保存模型到: {output_path}")
        agent.save(output_path)

        logger.info("完成!")
    else:
        logger.info("跳过训练（--no-train）")

    # 关闭环境
    env.close()


if __name__ == "__main__":
    main()
