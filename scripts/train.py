#!/usr/bin/env python3
"""
统一训练入口

支持监督学习和强化学习的完整训练流程。
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径，以便正确解析 from src.xxx 导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="AI_THE_SPIRE 统一训练入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 收集数据
  python scripts/train.py collect --games 100

  # 训练 SL 模型
  python scripts/train.py sl --data-dir combat_logs/sessions

  # 训练 RL 模型（从 SL Warm Start）
  python scripts/train.py rl --sl-model models/sl.pkl --timesteps 1M

  # 完整流程：收集 → 训练 SL → 训练 RL
  python scripts/train.py pipeline --collect-games 100 --sl-epochs 200 --rl-timesteps 1M

  # 评估模型
  python scripts/train.py eval --agent-type rl --model models/rl.zip

  # 交互测试
  python scripts/train.py interactive --agent-type rl --model models/rl.zip
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # collect 命令
    collect_parser = subparsers.add_parser('collect', help='收集训练数据')
    collect_parser.add_argument('--games', type=int, default=10, help='收集游戏局数')
    collect_parser.add_argument('--agent-type', type=str, default='rule', choices=['rule', 'supervised', 'rl'])
    collect_parser.add_argument('--model', type=str, default=None, help='模型路径（supervised/rl）')
    collect_parser.add_argument('--character', type=str, default='silent', help='角色')
    collect_parser.add_argument('--ascension', type=int, default=0, help='Ascension 等级')
    collect_parser.add_argument('--min-floors', type=int, default=0, help='最小楼层过滤')
    collect_parser.add_argument('--only-wins', action='store_true', help='只保存胜利对局')

    # sl 命令
    sl_parser = subparsers.add_parser('sl', help='训练监督学习模型')
    sl_parser.add_argument('--data-dir', type=str, required=True, help='训练数据目录')
    sl_parser.add_argument('--model-type', type=str, default='sklearn', choices=['sklearn', 'pytorch'])
    sl_parser.add_argument('--hidden-layers', type=int, nargs='+', default=[64, 32])
    sl_parser.add_argument('--epochs', type=int, default=100)
    sl_parser.add_argument('--batch-size', type=int, default=32)
    sl_parser.add_argument('--learning-rate', type=float, default=0.001)
    sl_parser.add_argument('--output', type=str, default=None, help='输出路径')

    # rl 命令
    rl_parser = subparsers.add_parser('rl', help='训练强化学习模型')
    rl_parser.add_argument('--algorithm', type=str, default='ppo', choices=['ppo', 'a2c', 'dqn'])
    rl_parser.add_argument('--sl-model', type=str, default=None, help='SL 模型路径（Warm Start）')
    rl_parser.add_argument('--timesteps', type=int, default=100000, help='训练步数')
    rl_parser.add_argument('--n-envs', type=int, default=1, help='并行环境数')
    rl_parser.add_argument('--learning-rate', type=float, default=3e-4)
    rl_parser.add_argument('--hidden-layers', type=int, nargs='+', default=[128, 128])
    rl_parser.add_argument('--character', type=str, default='silent', help='角色')
    rl_parser.add_argument('--ascension', type=int, default=0, help='Ascension 等级')
    rl_parser.add_argument('--output', type=str, default=None, help='输出路径')

    # pipeline 命令
    pipeline_parser = subparsers.add_parser('pipeline', help='完整训练流程')
    pipeline_parser.add_argument('--collect-games', type=int, default=50, help='收集游戏局数')
    pipeline_parser.add_argument('--data-dir', type=str, default='data/A20_Silent/Raw_Data_json_FORSL', help='数据目录（collect 输出 / SL 输入）')
    pipeline_parser.add_argument('--model-type', type=str, default='pytorch', choices=['sklearn', 'pytorch'])
    pipeline_parser.add_argument('--sl-epochs', type=int, default=100, help='SL 训练轮数')
    pipeline_parser.add_argument('--rl-timesteps', type=int, default=100000, help='RL 训练步数')
    pipeline_parser.add_argument('--n-envs', type=int, default=1, help='RL 并行环境数')
    pipeline_parser.add_argument('--character', type=str, default='silent', help='角色')
    pipeline_parser.add_argument('--ascension', type=int, default=0, help='Ascension 等级')
    pipeline_parser.add_argument('--skip-collect', action='store_true', help='跳过数据收集')
    pipeline_parser.add_argument('--skip-sl', action='store_true', help='跳过 SL 训练')
    pipeline_parser.add_argument('--skip-rl', action='store_true', help='跳过 RL 训练')

    # eval 命令
    eval_parser = subparsers.add_parser('eval', help='评估模型')
    eval_parser.add_argument('--agent-type', type=str, required=True, choices=['rule', 'supervised', 'rl'])
    eval_parser.add_argument('--model', type=str, required=True, help='模型路径')
    eval_parser.add_argument('--episodes', type=int, default=10, help='评估回合数')
    eval_parser.add_argument('--character', type=str, default='silent', help='角色')
    eval_parser.add_argument('--ascension', type=int, default=0, help='Ascension 等级')
    eval_parser.add_argument('--output', type=str, default='data/A20_Silent/eval_results.json', help='结果输出路径')

    # interactive 命令
    interactive_parser = subparsers.add_parser('interactive', help='交互式测试')
    interactive_parser.add_argument('--agent-type', type=str, default='rule', choices=['rule', 'supervised', 'rl'])
    interactive_parser.add_argument('--model', type=str, default=None, help='模型路径')
    interactive_parser.add_argument('--character', type=str, default='silent', help='角色')
    interactive_parser.add_argument('--ascension', type=int, default=0, help='Ascension 等级')
    interactive_parser.add_argument('--render', type=str, default='human', choices=['human', 'ansi', 'none'])
    interactive_parser.add_argument('--delay', type=float, default=0.5, help='每步延迟（秒）')

    return parser.parse_args()


def cmd_collect(args):
    """收集数据"""
    from scripts.collect_data import main as collect_main
    import sys

    # 修改命令行参数
    sys.argv = [
        'collect_data.py',
        '--agent-type', args.agent_type,
        '--games', str(args.games),
        '--character', args.character,
        '--ascension', str(args.ascension),
    ]

    if args.model:
        sys.argv.extend(['--model', args.model])
    if args.min_floors > 0:
        sys.argv.extend(['--min-floors', str(args.min_floors)])
    if args.only_wins:
        sys.argv.append('--only-wins')

    collect_main()


def cmd_sl(args):
    """训练 SL 模型"""
    from scripts.train_sl import main as sl_main
    import sys

    sys.argv = [
        'train_sl.py',
        '--data-dir', args.data_dir,
        '--model-type', args.model_type,
        '--hidden-layers'] + [str(x) for x in args.hidden_layers] + [
        '--epochs', str(args.epochs),
        '--batch-size', str(args.batch_size),
        '--learning-rate', str(args.learning_rate),
    ]

    if args.output:
        sys.argv.extend(['--output', args.output])

    sl_main()


def cmd_rl(args):
    """训练 RL 模型"""
    from scripts.train_rl import main as rl_main
    import sys

    sys.argv = [
        'train_rl.py',
        '--algorithm', args.algorithm,
        '--timesteps', str(args.timesteps),
        '--n-envs', str(args.n_envs),
        '--learning-rate', str(args.learning_rate),
        '--hidden-layers'] + [str(x) for x in args.hidden_layers] + [
        '--character', args.character,
        '--ascension', str(args.ascension),
    ]

    if args.sl_model:
        sys.argv.extend(['--sl-model', args.sl_model])
    if args.output:
        sys.argv.extend(['--output', args.output])

    rl_main()


def cmd_pipeline(args):
    """完整训练流程"""
    from scripts.collect_data import main as collect_main
    from scripts.train_sl import main as sl_main
    from scripts.train_rl import main as rl_main
    import sys

    logger.info("=" * 60)
    logger.info("完整训练流程")
    logger.info("=" * 60)
    logger.info(f"收集局数: {args.collect_games}")
    logger.info(f"SL 轮数: {args.sl_epochs}")
    logger.info(f"RL 步数: {args.rl_timesteps}")
    logger.info("=" * 60)

    sl_model_path = None

    # 1. 收集数据
    if not args.skip_collect:
        logger.info("\n[Step 1/3] 收集数据")
        logger.info("-" * 40)

        sys.argv = [
            'collect_data.py',
            '--agent-type', 'rule',
            '--games', str(args.collect_games),
            '--character', args.character,
            '--ascension', str(args.ascension),
            '--output-dir', args.data_dir,
        ]

        collect_main()
    else:
        logger.info("\n[Step 1/3] 跳过数据收集")

    # 2. 训练 SL
    if not args.skip_sl:
        logger.info("\n[Step 2/3] 训练 SL 模型")
        logger.info("-" * 40)

        # 自动生成 SL 模型路径
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sl_model_path = f"data/A20_Silent/models/sl_{timestamp}.pkl"

        sys.argv = [
            'train_sl.py',
            '--data-dir', args.data_dir,
            '--model-type', args.model_type,
            '--epochs', str(args.sl_epochs),
            '--output', sl_model_path,
        ]

        sl_main()
    else:
        logger.info("\n[Step 2/3] 跳过 SL 训练")
        sl_model_path = args.sl_model  # 使用指定的模型

    # 3. 训练 RL
    if not args.skip_rl:
        logger.info("\n[Step 3/3] 训练 RL 模型")
        logger.info("-" * 40)

        sys.argv = [
            'train_rl.py',
            '--timesteps', str(args.rl_timesteps),
            '--n-envs', str(args.n_envs),
            '--character', args.character,
            '--ascension', str(args.ascension),
        ]

        if sl_model_path:
            sys.argv.extend(['--sl-model', sl_model_path])

        rl_main()
    else:
        logger.info("\n[Step 3/3] 跳过 RL 训练")

    logger.info("\n" + "=" * 60)
    logger.info("完整流程完成!")
    logger.info("=" * 60)


def cmd_eval(args):
    """评估模型"""
    from scripts.evaluate import main as eval_main
    import sys

    sys.argv = [
        'evaluate.py',
        '--agent-type', args.agent_type,
        '--model', args.model,
        '--episodes', str(args.episodes),
        '--character', args.character,
        '--ascension', str(args.ascension),
    ]

    if args.output:
        sys.argv.extend(['--output', args.output])

    eval_main()


def cmd_interactive(args):
    """交互式测试"""
    from scripts.interactive import main as interactive_main
    import sys

    sys.argv = [
        'interactive.py',
        '--agent-type', args.agent_type,
        '--character', args.character,
        '--ascension', str(args.ascension),
        '--render', args.render,
        '--delay', str(args.delay),
    ]

    if args.model:
        sys.argv.extend(['--model', args.model])

    interactive_main()


def main():
    """主函数"""
    args = parse_args()

    if args.command is None:
        parse_args().print_help()
        return

    # 执行对应命令
    if args.command == 'collect':
        cmd_collect(args)
    elif args.command == 'sl':
        cmd_sl(args)
    elif args.command == 'rl':
        cmd_rl(args)
    elif args.command == 'pipeline':
        cmd_pipeline(args)
    elif args.command == 'eval':
        cmd_eval(args)
    elif args.command == 'interactive':
        cmd_interactive(args)
    else:
        logger.error(f"未知命令: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
