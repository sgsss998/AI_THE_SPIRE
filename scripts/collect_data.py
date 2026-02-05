#!/usr/bin/env python3
"""
数据收集脚本

使用规则 Agent 运行游戏并收集训练数据。
"""
import os
import sys

# 项目根目录（用于绝对路径，避免 Mod 从游戏目录启动时路径错误）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))

def _early_log(msg: str):
    """尽早写入日志（不依赖 logging 模块）"""
    try:
        _log_dir = os.path.join(_PROJECT_ROOT, "data", "A20_Silent")
        os.makedirs(_log_dir, exist_ok=True)
        with open(os.path.join(_log_dir, "collect_data.log"), "a", encoding="utf-8") as _f:
            import time
            _f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} - {msg}\n")
    except Exception:
        pass

# 真实游戏模式：必须在 import 项目模块之前发送 ready，否则 Mod 超时（约 10 秒）会终止进程
if "--real-game" in sys.argv:
    try:
        sys.stdout.write("ready\n")
        sys.stdout.flush()
        _early_log("脚本已启动，已发送 ready")
    except Exception:
        pass

_early_log("开始 import")
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, _PROJECT_ROOT)
_early_log("import 完成")

# 延迟 import：在收到首帧并立即回复后再加载，避免 Mod 在 import 期间超时
# create_agent、GameState 在 _run_real_game_loop 内按需导入

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
    parser.add_argument("--output-dir", type=str, default=None, help="数据目录，默认 data/A20_Silent/Raw_Data_json_FORSL")
    parser.add_argument("--min-floors", type=int, default=0)
    parser.add_argument("--only-wins", action="store_true")
    parser.add_argument("--real-game", action="store_true", help="真实游戏模式：stdin/stdout 连接 CommunicationMod")
    parser.add_argument("--session-name", type=str, default=None, help="会话名称（预留参数，当前未使用）")

    return parser.parse_args()


def _make_raw_filename() -> str:
    """生成 Raw_Data_json_FORSL 文件名：Silent_A20_HUMAN_<timestamp>.json"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"Silent_A20_HUMAN_{ts}.json"


def _flush_frames(frames: list, filepath: Path) -> None:
    """将帧数据写入 JSON 文件"""
    if not frames:
        return
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(frames, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"写入失败: {e}")


def _run_real_game_loop(args):
    """
    真实游戏模式：stdin/stdout 直连 Mod 通信
    数据直接保存到 Raw_Data_json_FORSL，格式与现有原始 JSON 一致（每帧 = Mod 原始响应 + action）
    """
    _early_log("进入 _run_real_game_loop")
    base = Path(_PROJECT_ROOT)
    output_dir = Path(args.output_dir) if args.output_dir else base / "data" / "A20_Silent" / "Raw_Data_json_FORSL"
    output_dir.mkdir(parents=True, exist_ok=True)

    log_file = base / "data" / "A20_Silent" / "collect_data.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(fh)

    logger.info("真实游戏模式：stdin/stdout 直连 Mod 通信")
    logger.info(f"数据保存: {output_dir}")

    # 先读取首帧再导入 Agent，避免 import 期间 Mod 超时断开
    _early_log("等待 Mod 首帧...")
    first_line = sys.stdin.readline()
    _early_log(f"收到首帧，长度={len(first_line) if first_line else 0}")
    if not first_line:
        logger.info("stdin EOF（无首帧），退出")
        return

    # 首帧收到后再导入（此时 Mod 已发送数据，正在等待响应）
    try:
        from src.agents import create_agent
        from src.core.game_state import GameState
    except Exception as e:
        logger.exception(f"导入失败: {e}")
        sys.stdout.write("state\n")
        sys.stdout.flush()
        return

    agent = create_agent(args.agent_type, "DataCollector")
    if args.model:
        agent.load(args.model)
        agent.set_training_mode(False)

    frames = []
    current_file = output_dir / _make_raw_filename()
    last_game_ended = True
    step = 0

    def process_line(line: str) -> bool:
        """处理一帧，返回 False 表示应退出"""
        nonlocal step, frames, current_file, last_game_ended
        line = line.strip()
        if not line:
            return True
        step += 1
        try:
            data = json.loads(line)
            gs = data.get("game_state") or {}
            if gs.get("screen_type") == "GAME_OVER":
                last_game_ended = True
            ss = gs.get("screen_state") or {}
            if ss.get("event_id") == "Neow Event" and last_game_ended:
                if frames:
                    _flush_frames(frames, current_file)
                    logger.info(f"已写入: {current_file} ({len(frames)} 帧)")
                current_file = output_dir / _make_raw_filename()
                frames = []
                last_game_ended = False
            state = GameState.from_mod_response(data)
            action = agent.select_action(state)
            response = action.to_command()
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
            record = dict(data)
            record["action"] = response
            frames.append(record)
            _flush_frames(frames, current_file)
        except Exception as e:
            logger.exception(f"解析/响应异常: {e}")
            sys.stdout.write("state\n")
            sys.stdout.flush()
        return True

    # 处理首帧
    if not process_line(first_line):
        return

    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                logger.info("stdin EOF，退出")
                break
            if not process_line(line):
                break

    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.exception(f"异常退出: {e}")
    finally:
        if frames:
            _flush_frames(frames, current_file)
            logger.info(f"收集结束，共 {step} 步，已写入: {current_file} ({len(frames)} 帧)")


def main():
    _early_log("main() 开始")
    args = parse_args()
    _early_log("parse_args 完成")

    if not args.real_game:
        logger.error("数据收集需使用 --real-game 连接 CommunicationMod。示例：")
        logger.error("  python scripts/collect_data.py --real-game --games 1")
        sys.exit(1)

    _early_log("调用 _run_real_game_loop")
    _run_real_game_loop(args)


if __name__ == "__main__":
    if "--real-game" in sys.argv:
        try:
            main()
        except Exception as e:
            _early_log(f"崩溃: {type(e).__name__}: {e}")
            import traceback
            _early_log("".join(traceback.format_exc()))
            raise
    else:
        main()
