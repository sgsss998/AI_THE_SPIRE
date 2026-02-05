#!/usr/bin/env python3
"""
数据收集脚本

使用规则 Agent 运行游戏并收集训练数据。
"""
import os
import sys

# 真实游戏模式：必须在 import 项目模块之前发送 ready，否则 Mod 超时（约 10 秒）会终止进程
if "--real-game" in sys.argv:
    try:
        sys.stdout.write("ready\n")
        sys.stdout.flush()
    except Exception:
        pass

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径，以便正确解析 from src.xxx 导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents import create_agent
from src.core.game_state import GameState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="收集训练数据")

    parser.add_argument("--agent-type", type=str, choices=["rule", "supervised", "rl"], default="rule")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--character", type=str, default="silent")
    parser.add_argument("--ascension", type=int, default=0)
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--session-name", type=str, default=None)
    parser.add_argument("--min-floors", type=int, default=0)
    parser.add_argument("--only-wins", action="store_true")
    parser.add_argument("--real-game", action="store_true", help="真实游戏模式：stdin/stdout 连接 CommunicationMod")

    return parser.parse_args()


def _run_real_game_loop(args):
    """
    真实游戏模式：完全抄袭 mod_diagnose 的通信逻辑
    - 直接 sys.stdin.readline() / sys.stdout.write()
    - 不依赖 ModProtocol、StsEnvWrapper 等
    """
    output_dir = Path(args.output_dir or "combat_logs/sessions")
    session_name = args.session_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = output_dir / session_name
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "session.jsonl"

    log_file = output_dir.resolve().parent.parent / "collect_data.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(fh)

    logger.info("真实游戏模式：使用 mod_diagnose 风格通信（stdin/stdout 直连）")
    logger.info(f"数据保存: {session_file}")

    # 创建 Agent（仅 rule 类型，不加载 StateEncoder）
    agent = create_agent(args.agent_type, "DataCollector")
    if args.model:
        agent.load(args.model)
        agent.set_training_mode(False)

    step = 0
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                logger.info("stdin EOF，退出")
                break
            line = line.strip()
            if not line:
                continue
            step += 1

            try:
                data = json.loads(line)
                state = GameState.from_mod_response(data)
                action = agent.select_action(state)
                response = action.to_command()

                sys.stdout.write(response + "\n")
                sys.stdout.flush()

                if response not in ("state", "wait"):
                    record = {"state": data, "action": response, "step": step}
                    with open(session_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.exception(f"解析/响应异常: {e}")
                sys.stdout.write("state\n")
                sys.stdout.flush()

    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.exception(f"异常退出: {e}")

    logger.info(f"收集结束，共 {step} 步")


def main():
    args = parse_args()

    if not args.real_game:
        logger.error("数据收集需使用 --real-game 连接 CommunicationMod。示例：")
        logger.error("  python scripts/collect_data.py --real-game --games 1 --session-name my_session")
        sys.exit(1)

    _run_real_game_loop(args)


if __name__ == "__main__":
    main()
