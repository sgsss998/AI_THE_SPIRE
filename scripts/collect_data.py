#!/usr/bin/env python3
"""
数据收集脚本

使用规则 Agent 运行游戏并收集训练数据。
"""
import os
import sys
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.agents import create_agent
from src.env import StsEnvWrapper
from src.protocol import ModProtocol
from src.core.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="收集训练数据")

    # Agent 参数
    parser.add_argument(
        "--agent-type",
        type=str,
        choices=["rule", "supervised", "rl"],
        default="rule",
        help="Agent 类型（默认: rule）"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="模型路径（supervised/rl 需要）"
    )

    # 游戏参数
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

    # 收集参数
    parser.add_argument(
        "--games",
        type=int,
        default=10,
        help="收集游戏局数（默认: 10）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="输出目录（默认: combat_logs/sessions/）"
    )
    parser.add_argument(
        "--session-name",
        type=str,
        default=None,
        help="会话名称（默认自动生成）"
    )

    # 过滤参数
    parser.add_argument(
        "--min-floors",
        type=int,
        default=0,
        help="最小楼层过滤（默认: 0）"
    )
    parser.add_argument(
        "--only-wins",
        action="store_true",
        help="只保存胜利的对局"
    )

    return parser.parse_args()


class DataCollector:
    """数据收集器"""

    def __init__(
        self,
        agent,
        output_dir: str,
        session_name: str = None,
        min_floors: int = 0,
        only_wins: bool = False
    ):
        """
        初始化数据收集器

        Args:
            agent: Agent 实例
            output_dir: 输出目录
            session_name: 会话名称
            min_floors: 最小楼层过滤
            only_wins: 只保存胜利对局
        """
        self.agent = agent
        self.output_dir = Path(output_dir)
        self.min_floors = min_floors
        self.only_wins = only_wins

        # 创建会话
        self.session_name = session_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / self.session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 输出文件
        self.output_file = self.session_dir / "session.jsonl"

        # 统计
        self.games_collected = 0
        self.games_filtered = 0
        self.total_steps = 0

    def should_save(self, info: dict) -> bool:
        """判断是否应该保存这个对局"""
        floors = info.get("floor", 0)
        won = info.get("won", False)

        if floors < self.min_floors:
            return False

        if self.only_wins and not won:
            return False

        return True

    def collect_game(self, env, max_steps: int = 10000) -> dict:
        """
        收集一局游戏的数据

        Args:
            env: 环境
            max_steps: 最大步数

        Returns:
            收集结果
        """
        # 重置环境
        state, info = env.reset()
        self.agent.on_episode_start(self.games_collected + 1)

        episode_data = {
            "states": [],
            "actions": [],
            "rewards": [],
        }

        step = 0
        done = False
        truncated = False

        while not done and not truncated and step < max_steps:
            # 记录状态
            episode_data["states"].append(state.to_dict())

            # 选择动作
            action = self.agent.select_action(state)

            # 执行动作
            next_state, reward, done, truncated, info = env.step(action)

            # 记录动作和奖励
            episode_data["actions"].append(action.to_command())
            episode_data["rewards"].append(reward)

            # 回调
            self.agent.on_step(action, reward, next_state, done or truncated)

            # 更新状态
            state = next_state
            step += 1

        # 回合结束
        total_reward = sum(episode_data["rewards"])
        self.agent.on_episode_end(total_reward, info)

        # 检查是否保存
        should_save = self.should_save(info)

        result = {
            "steps": step,
            "floors": info.get("floor", 0),
            "won": info.get("won", False),
            "reward": total_reward,
            "saved": should_save,
        }

        if should_save:
            # 保存到文件
            for i, (s, a, r) in enumerate(zip(
                episode_data["states"],
                episode_data["actions"],
                episode_data["rewards"]
            )):
                record = {
                    "state": s,
                    "action": a,
                    "reward": r,
                    "step": i,
                    "game": self.games_collected,
                }
                self._write_record(record)

            self.games_collected += 1
            self.total_steps += step
        else:
            self.games_filtered += 1

        return result

    def _write_record(self, record: dict):
        """写入记录到文件"""
        with open(self.output_file, 'a', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False)
            f.write('\n')

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "games_collected": self.games_collected,
            "games_filtered": self.games_filtered,
            "total_steps": self.total_steps,
            "output_file": str(self.output_file),
        }


def main():
    """主函数"""
    args = parse_args()
    config = get_config()

    # 输出目录
    output_dir = args.output_dir or "combat_logs/sessions"

    logger.info("=" * 60)
    logger.info("数据收集")
    logger.info("=" * 60)
    logger.info(f"Agent 类型: {args.agent_type}")
    logger.info(f"收集局数: {args.games}")
    logger.info(f"角色: {args.character}")
    logger.info(f"Ascension: {args.ascension}")
    logger.info(f"最小楼层: {args.min_floors}")
    logger.info(f"只保存胜利: {args.only_wins}")
    logger.info(f"输出目录: {output_dir}")
    logger.info("=" * 60)

    # 创建环境
    logger.info("创建环境...")
    env = StsEnvWrapper(
        character=args.character,
        ascension=args.ascension,
    )

    # 创建 Agent
    logger.info(f"创建 {args.agent_type} Agent...")
    agent = create_agent(args.agent_type, "DataCollector")

    if args.model:
        logger.info(f"加载模型: {args.model}")
        agent.load(args.model)
        agent.set_training_mode(False)  # 推理模式

    # 创建收集器
    collector = DataCollector(
        agent=agent,
        output_dir=output_dir,
        session_name=args.session_name,
        min_floors=args.min_floors,
        only_wins=args.only_wins,
    )

    logger.info(f"会话: {collector.session_name}")
    logger.info("开始收集...\n")

    # 收集数据
    for game in range(args.games):
        logger.info(f"游戏 {game + 1}/{args.games}...")

        try:
            result = collector.collect_game(env)

            status = "保存" if result["saved"] else "过滤"
            logger.info(
                f"  {status} - 层数: {result['floors']}, "
                f"步数: {result['steps']}, "
                f"胜: {'是' if result['won'] else '否'}, "
                f"奖励: {result['reward']:.2f}"
            )

        except Exception as e:
            logger.error(f"  错误: {e}")
            continue

    # 输出统计
    stats = collector.get_stats()

    logger.info("\n" + "=" * 60)
    logger.info("收集完成!")
    logger.info("=" * 60)
    logger.info(f"收集对局: {stats['games_collected']}")
    logger.info(f"过滤对局: {stats['games_filtered']}")
    logger.info(f"总步数: {stats['total_steps']}")
    logger.info(f"输出文件: {stats['output_file']}")
    logger.info("=" * 60)

    # 关闭环境
    env.close()


if __name__ == "__main__":
    main()
