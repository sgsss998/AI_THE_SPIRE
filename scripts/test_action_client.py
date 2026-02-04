#!/usr/bin/env python3
"""
Action 测试 - Client 端（用户在终端运行）

在终端运行本脚本，连接 test_action_server，在每次决策点显示状态并输入 action_id。

用法：
  cd /Volumes/T7/AI_THE_SPIRE
  ./venv/bin/python scripts/test_action_client.py

或指定端口（默认 5555）：
  TEST_ACTION_PORT=5556 ./venv/bin/python scripts/test_action_client.py
"""
import sys
import json
import socket
import os

# 添加项目根目录到路径
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
try:
    from src.core.action import Action, ACTION_SPACE_SIZE
except ImportError:
    sys.path.insert(0, ".")
    from src.core.action import Action, ACTION_SPACE_SIZE

DEFAULT_PORT = 5555


def _print_state_summary(msg: dict) -> None:
    """打印状态摘要"""
    gs = msg.get("game_state") or {}
    cmds = msg.get("available_commands") or []
    st = gs.get("screen_type", "N/A")
    print(f"\n--- screen_type={st} | available_commands={cmds} ---")
    if gs.get("combat_state"):
        cs = gs["combat_state"]
        hand = cs.get("hand", [])
        monsters = cs.get("monsters", [])
        player = cs.get("player", {})
        print(f"  手牌: {len(hand)} 张 | 能量: {player.get('energy')} | 敌人: {len([m for m in monsters if not m.get('is_gone')])} 个")
    print(f"  输入 action_id (0-{ACTION_SPACE_SIZE-1}) 或 state/wait/q: ", end="", flush=True)


def main():
    port = int(os.environ.get("TEST_ACTION_PORT", DEFAULT_PORT))
    host = os.environ.get("TEST_ACTION_HOST", "127.0.0.1")

    print(f"正在连接 {host}:{port} ...", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
    except (socket.error, OSError) as e:
        print(f"连接失败: {e}", file=sys.stderr)
        print("请确保：1) 游戏已启动（Mod 会启动 server） 2) 端口未被占用", file=sys.stderr)
        sys.exit(1)

    print("已连接，等待游戏决策点...", flush=True)
    recv_buf = b""

    try:
        while True:
            # 读取一行 JSON
            while b"\n" not in recv_buf:
                chunk = sock.recv(4096)
                if not chunk:
                    print("\n连接已断开", flush=True)
                    return
                recv_buf += chunk
            line, recv_buf = recv_buf.split(b"\n", 1)
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            try:
                msg = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            _print_state_summary(msg)

            try:
                user_input = input().strip()
            except (EOFError, KeyboardInterrupt):
                sock.sendall(b"q\n")
                print("\n已退出", flush=True)
                return

            if user_input.lower() == "q":
                sock.sendall(b"q\n")
                print("已退出", flush=True)
                return

            if user_input.lower() in ("state", "wait", ""):
                sock.sendall(b"state\n")
                continue

            try:
                action_id = int(user_input)
            except ValueError:
                print(f"  无效输入，发送 state", flush=True)
                sock.sendall(b"state\n")
                continue

            if not 0 <= action_id < ACTION_SPACE_SIZE:
                print(f"  action_id 应在 0-{ACTION_SPACE_SIZE-1}，发送 state", flush=True)
                sock.sendall(b"state\n")
                continue

            action = Action.from_id(action_id)
            cmd = action.to_command()
            print(f"  -> 发送: {cmd}", flush=True)
            sock.sendall((user_input + "\n").encode("utf-8"))
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
