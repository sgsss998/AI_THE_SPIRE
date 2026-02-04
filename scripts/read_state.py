#!/usr/bin/env python3
import sys
import json
import os
import hashlib
from datetime import datetime

# 一局一文件：每次开新局（Neow Event）新建一个 JSON 文件
# 局结束判定：仅基于 GAME_OVER（死亡/胜利），主动放弃不纳入
DATA_DIR = "/Volumes/T7/AI_THE_SPIRE/data/A20_Slient/Raw_Data_json_FORSL"
os.makedirs(DATA_DIR, exist_ok=True)


def _canonical_state(msg: dict) -> dict:
    """
    构造用于去重的状态视图：
    - 只依赖真正描述状态的字段
    - 排除任何时间戳/日志辅助信息
    """
    return {
        "available_commands": msg.get("available_commands"),
        "ready_for_command": msg.get("ready_for_command"),
        "in_game": msg.get("in_game"),
        "game_state": msg.get("game_state"),
    }


def _state_hash(msg: dict) -> str:
    """对 canonical_state 生成稳定哈希，用于去重"""
    canonical = _canonical_state(msg)
    dumped = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def _make_filename() -> str:
    """
    为本次进程生成一个文件名：
    - 仍沿用 Silent_A20_HUMAN 前缀
    - 用时间戳避免冲突
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"Silent_A20_HUMAN_{ts}.json"
    return os.path.join(DATA_DIR, name)


def _flush_states(states: list, filename: str) -> None:
    """将 states 写入文件（进程被强制终止时也能保留已收集的数据）"""
    if not states:
        return
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(states, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def main():
    # 本进程对应的一局（或一段会话）的所有状态
    states = []
    last_state_hash = None
    filename = _make_filename()
    last_game_ended = True  # 初始为 True，首次 Neow Event 时创建新文件

    # 协议要求：启动后先发送 ready
    print("ready")
    sys.stdout.flush()

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                # 保持通信
                print("state")
                sys.stdout.flush()
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # 解析失败时跳过，但仍保持通信
                print("state")
                sys.stdout.flush()
                continue

            # 主菜单（in_game=false）不记录，不视为局结束
            if msg.get("in_game") is False:
                print("state")
                sys.stdout.flush()
                continue

            gs = msg.get("game_state")
            # 局结束：GAME_OVER（死亡或胜利）
            if gs is not None and gs.get("screen_type") == "GAME_OVER":
                last_game_ended = True

            # 新局开始：Neow Event 且上一局已结束
            ss = (gs or {}).get("screen_state") or {}
            if (
                gs is not None
                and ss.get("event_id") == "Neow Event"
                and last_game_ended
            ):
                if states:
                    _flush_states(states, filename)
                filename = _make_filename()
                states = []
                last_state_hash = None
                last_game_ended = False

            # 仅保存「等待玩家决策」的状态，跳过执行中的帧（EXECUTING_ACTIONS 等）
            if gs is not None:
                ap = gs.get("action_phase")
                if ap is not None and ap != "WAITING_ON_USER":
                    # 动画/执行中，不记录
                    print("state")
                    sys.stdout.flush()
                    continue

            # 不再过滤 ready_for_command，以包含 Survivor 弃牌等子界面（其可能为 false）
            # if msg.get("ready_for_command") is False:
            #     print("state")
            #     sys.stdout.flush()
            #     continue

            # 去重：仅当状态内容发生变化时才记录
            try:
                h = _state_hash(msg)
            except Exception:
                # 意外情况时退回到不过滤，以免丢数据
                h = None

            if h is None or h != last_state_hash:
                states.append(msg)
                last_state_hash = h
                # 每 50 条新状态写一次盘，避免进程被强制终止时丢失全部数据
                if len(states) % 50 == 0:
                    _flush_states(states, filename)

            # 当前实现不做决策，只请求下一帧状态
            print("state")
            sys.stdout.flush()

    except KeyboardInterrupt:
        # 用户中断时，尽量落盘
        pass
    finally:
        if states:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(states, f, ensure_ascii=False, indent=2)
            except OSError:
                # 写盘失败时不干扰游戏/通信
                pass


if __name__ == "__main__":
    main()


