#!/usr/bin/env python3
"""
模型评估脚本

评估训练好的 Agent 性能。
"""
import os
import sys
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径，以便正确解析 from src.xxx 导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents import create_agent
from src.env import StsEnvWrapper
from src.core.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="评估训练好的 Agent")

    # 模型参数
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="模型路径"
    )
    parser.add_argument(
        "--agent-type",
        type=str,
        choices=["rule", "supervised", "rl"],
        required=True,
        help="Agent 类型"
    )

    # 评估参数
    parser.add_argument(
        "--episodes",
        type=int,
        default=10,
        help="评估回合数（默认: 10）"
    )
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
        help="Ascension 等级（默认: 0）"
    )

    # 输出参数
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="结果输出路径（JSON 格式）"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出"
    )

    return parser.parse_args()


def evaluate_agent(agent, env, n_episodes: int, verbose: bool = False):
    """
    评估 Agent

    Args:
        agent: Agent 实例
        env: 环境
        n_episodes: 评估回合数
        verbose: 是否详细输出

    Returns:
        评估结果字典
    """
    results = {
        "episodes": [],
        "total_episodes": n_episodes,
        "wins": 0,
        "total_reward": 0.0,
        "total_steps": 0,
        "floors_reached": [],
    }

    for episode in range(n_episodes):
        episode_result = {
            "episode": episode + 1,
            "reward": 0.0,
            "steps": 0,
            "floors": 0,
            "won": False,
        }

        # 重置环境
        state, info = env.reset()
        agent.on_episode_start(episode + 1)

        if verbose:
            logger.info(f"回合 {episode + 1}/{n_episodes} 开始")

        done = False
        truncated = False

        while not done and not truncated:
            # 选择动作
            action = agent.select_action(state)

            if verbose and episode < 3:  # 只显示前 3 个回合的详情
                logger.info(f"  动作: {action.to_command()}")

            # 执行动作
            next_state, reward, done, truncated, info = env.step(action)

            # 记录
            episode_result["reward"] += reward
            episode_result["steps"] += 1

            # 回调
            agent.on_step(action, reward, next_state, done or truncated)

            # 更新状态
            state = next_state

        # 回合结束
        agent.on_episode_end(episode_result["reward"], info)

        # 记录结果
        episode_result["floors"] = info.get("floor", 0)
        episode_result["won"] = info.get("won", False)

        results["episodes"].append(episode_result)
        results["total_reward"] += episode_result["reward"]
        results["total_steps"] += episode_result["steps"]
        results["floors_reached"].append(episode_result["floors"])

        if episode_result["won"]:
            results["wins"] += 1

        if verbose:
            logger.info(
                f"回合 {episode + 1}/{n_episodes} 结束: "
                f"奖励={episode_result['reward']:.2f}, "
                f"层数={episode_result['floors']}, "
                f"胜={'是' if episode_result['won'] else '否'}"
            )

    # 计算统计
    results["win_rate"] = results["wins"] / n_episodes
    results["avg_reward"] = results["total_reward"] / n_episodes
    results["avg_steps"] = results["total_steps"] / n_episodes
    results["avg_floors"] = sum(results["floors_reached"]) / n_episodes

    return results


def main():
    """主函数"""
    args = parse_args()
    config = get_config()

    logger.info("=" * 60)
    logger.info("模型评估")
    logger.info("=" * 60)
    logger.info(f"模型路径: {args.model}")
    logger.info(f"Agent 类型: {args.agent_type}")
    logger.info(f"评估回合数: {args.episodes}")
    logger.info("=" * 60)

    # 创建环境
    logger.info("创建环境...")
    env = StsEnvWrapper(
        character=args.character,
        ascension=args.ascension,
    )

    # 创建 Agent
    logger.info(f"加载 {args.agent_type} Agent...")
    agent = create_agent(args.agent_type, "EvalAgent")
    agent.load(args.model)
    agent.set_training_mode(False)  # 推理模式

    # 评估
    logger.info("开始评估...")
    results = evaluate_agent(agent, env, args.episodes, args.verbose)

    # 输出结果
    logger.info("=" * 60)
    logger.info("评估结果")
    logger.info("=" * 60)
    logger.info(f"总回合数: {results['total_episodes']}")
    logger.info(f"胜利回合: {results['wins']}")
    logger.info(f"胜率: {results['win_rate']:.2%}")
    logger.info(f"平均奖励: {results['avg_reward']:.2f}")
    logger.info(f"平均步数: {results['avg_steps']:.2f}")
    logger.info(f"平均层数: {results['avg_floors']:.2f}")
    logger.info("=" * 60)

    # 保存结果
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"结果已保存到: {args.output}")

    # 关闭环境
    env.close()


if __name__ == "__main__":
    main()
