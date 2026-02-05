#!/usr/bin/env python3
"""
Mod 连接脚本 - 仅用 stdlib，无项目依赖

既能自动玩，又能收集 (s, a) 键值对到 session.jsonl。
当 collect_data 在 Mod 下无法连接时，用本脚本替代。

用法：
  config.properties 的 command 设为：
  command=/Volumes/T7/AI_THE_SPIRE/venv/bin/python -u /Volumes/T7/AI_THE_SPIRE/scripts/mod_diagnose.py
"""
import sys
import os
import json
from datetime import datetime

PROJECT_ROOT = "/Volumes/T7/AI_THE_SPIRE"
LOG_PATH = f"{PROJECT_ROOT}/mod_diagnose.log"
SESSION_DIR = f"{PROJECT_ROOT}/combat_logs/sessions"


def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")


def _first_alive_monster_index(data: dict) -> int:
    """返回第一个存活怪物的数组索引（0-based），无则返回 0"""
    gs = data.get("game_state") or {}
    cs = gs.get("combat_state") or {}
    monsters = cs.get("monsters") or []
    for i, m in enumerate(monsters):
        if not m.get("is_gone", True):
            return i
    return 0


def main():
    # 第一行：证明脚本被启动
    log("=== mod_diagnose 启动（含数据收集）===")

    # 立即发送 ready（Mod 超时约 10 秒）
    try:
        sys.stdout.write("ready\n")
        sys.stdout.flush()
        log("已发送 ready")
    except Exception as e:
        log(f"发送 ready 失败: {e}")
        return

    # 准备 session.jsonl 用于收集 (s, a)
    os.makedirs(SESSION_DIR, exist_ok=True)
    session_name = datetime.now().strftime("mod_collect_%Y%m%d_%H%M%S")
    session_file = os.path.join(SESSION_DIR, session_name, "session.jsonl")
    os.makedirs(os.path.dirname(session_file), exist_ok=True)
    log(f"数据将保存到: {session_file}")

    # 读取并记录 Mod 发来的内容
    line_count = 0
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                log("stdin EOF，退出")
                break
            line = line.strip()
            if not line:
                log("收到空行，跳过")
                continue
            line_count += 1
            # 只记录前 200 字符，避免日志过大
            preview = line[:200] + ("..." if len(line) > 200 else "")
            log(f"收到第 {line_count} 行 ({len(line)} 字符): {preview}")

            # 尝试解析 JSON 并响应
            try:
                import json
                data = json.loads(line)
                cmds = data.get("available_commands", [])
                ready = data.get("ready_for_command", False)
                in_game = data.get("in_game", False)
                log(f"  -> in_game={in_game}, ready_for_command={ready}, commands={cmds[:5]}...")
                # 协议要求必须回复，否则 Mod 阻塞
                response = "state"
                if ready:
                    if "play" in cmds:
                        # 目标必须为活着的怪物，否则打死一只后 target 0 指向尸体会导致卡住
                        target = _first_alive_monster_index(data)
                        response = f"play 1 {target}" if target >= 0 else "play 1 0"
                    elif "end" in cmds:
                        response = "end"
                    elif "choose" in cmds:
                        response = "choose 0"
                    elif "proceed" in cmds:
                        response = "proceed"
                    else:
                        response = "state"
                else:
                    # 动画/过渡阶段（如怪物死亡）：发 wait 让 Mod 推进，否则会卡住
                    response = "wait" if "wait" in cmds else "state"
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
                log("  已发送响应")
                # 收集 (s, a)：仅记录真实决策，跳过 state/wait 轮询
                if response not in ("state", "wait"):
                    try:
                        record = {"state": data, "action": response, "step": line_count}
                        with open(session_file, "a", encoding="utf-8") as sf:
                            sf.write(json.dumps(record, ensure_ascii=False) + "\n")
                    except Exception as e:
                        log(f"  写入 session 失败: {e}")
            except Exception as e:
                log(f"  解析/响应异常: {e}")
    except KeyboardInterrupt:
        log("用户中断")
    except Exception as e:
        log(f"异常退出: {e}")

    log(f"=== 结束，共收到 {line_count} 行 ===")


if __name__ == "__main__":
    main()
