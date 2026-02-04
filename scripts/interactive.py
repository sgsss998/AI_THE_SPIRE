#!/usr/bin/env python3
"""
交互式测试脚本

手动运行 Agent 并观察其行为。
"""
import os
import sys
import argparse
import logging

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.agents import create_agent
from src.env import StsEnvWrapper
from src.core.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="交互式测试 Agent")

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
        help="Ascension 等级（默认: 0）"
    )

    # 渲染参数
    parser.add_argument(
        "--render",
        choices=["human", "ansi", "none"],
        default="human",
        help="渲染模式（默认: human）"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="每步延迟（秒，默认: 0.5）"
    )

    # 其他
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="最大步数（默认无限制）"
    )

    return parser.parse_args()


def print_state(state, action=None):
    """打印状态信息"""
    from src.core.game_state import RoomPhase

    print(f"\n{'='*50}")
    print(f"房间阶段: {state.room_phase.value}")
    print(f"楼层: {state.floor} | Act: {state.act}")

    if state.combat:
        combat = state.combat
        print(f"\n[战斗信息]")
        print(f"  回合: {combat.turn}")
        print(f"  能量: {combat.player.energy}/{combat.player.max_energy}")
        print(f"  生命: {combat.player.current_hp}/{combat.player.max_hp}")

        if combat.hand:
            print(f"\n[手牌] ({len(combat.hand)} 张)")
            for i, card in enumerate(combat.hand):
                playable = "可" if card.is_playable else "不可"
                print(f"  {i}. {card.name} ({card.cost}费) - {playable}玩")

        if combat.monsters:
            print(f"\n[敌人] ({len(combat.monsters)} 个)")
            for i, monster in enumerate(combat.monsters):
                if monster.current_hp > 0:
                    print(f"  {i}. {monster.name}: {monster.current_hp}/{monster.max_hp} HP - 意图: {monster.intent.value}")

    print(f"\n[可用命令]: {', '.join(state.available_commands)}")

    if action:
        print(f"\n[选择动作]: {action.to_command()}")

    print(f"{'='*50}\n")


def main():
    """主函数"""
    args = parse_args()

    logger.info("=" * 60)
    logger.info("交互式测试")
    logger.info("=" * 60)
    logger.info(f"Agent 类型: {args.agent_type}")
    logger.info(f"渲染模式: {args.render}")
    logger.info("=" * 60)

    # 创建环境
    logger.info("创建环境...")
    env = StsEnvWrapper(
        character=args.character,
        ascension=args.ascension,
    )

    # 创建 Agent
    logger.info(f"创建 {args.agent_type} Agent...")
    agent = create_agent(args.agent_type, "Interactive")

    if args.model:
        logger.info(f"加载模型: {args.model}")
        agent.load(args.model)
        agent.set_training_mode(False)  # 推理模式

    # 运行
    logger.info("开始运行...")
    logger.info("按 Ctrl+C 停止\n")

    try:
        # 重置环境
        state, info = env.reset()
        agent.on_episode_start(1)

        step = 0
        done = False
        truncated = False

        while not done and not truncated:
            # 渲染
            if args.render == "human":
                env.render()

            # 打印状态
            print_state(state)

            # 选择动作
            action = agent.select_action(state)

            # 执行动作
            logger.info(f"执行: {action.to_command()}")
            next_state, reward, done, truncated, info = env.step(action)

            # 打印结果
            logger.info(f"奖励: {reward:.2f}")

            if args.render == "human":
                if reward > 0:
                    logger.info(f"  ↑ +{reward:.2f}")
                elif reward < 0:
                    logger.info(f"  ↓ {reward:.2f}")

            # 回调
            agent.on_step(action, reward, next_state, done or truncated)

            # 更新状态
            state = next_state
            step += 1

            # 检查最大步数
            if args.max_steps and step >= args.max_steps:
                logger.info(f"达到最大步数: {args.max_steps}")
                break

            # 延迟
            if args.delay > 0:
                import time
                time.sleep(args.delay)

        # 回合结束
        agent.on_episode_end(info.get("reward", 0), info)

        logger.info("=" * 60)
        logger.info("游戏结束")
        logger.info("=" * 60)
        logger.info(f"总步数: {step}")
        logger.info(f"最终楼层: {info.get('floor', 'N/A')}")
        logger.info(f"胜利: {'是' if info.get('won', False) else '否'}")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\n用户中断")

    # 关闭环境
    env.close()
    logger.info("环境已关闭")


if __name__ == "__main__":
    main()
