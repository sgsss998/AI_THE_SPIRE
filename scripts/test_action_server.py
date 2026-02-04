#!/usr/bin/env python3
"""
Action 测试 - Server 端（由 Mod 启动）

Mod 会启动本脚本，stdin/stdout 与 Mod 通信。本脚本同时监听本地端口，
等待 test_action_client 连接。当游戏到达决策点时，将状态转发给 client，
等待 client 输入 action_id，再转发给 Mod。

config.properties 中应配置：
  command=/Volumes/T7/AI_THE_SPIRE/venv/bin/python -u /Volumes/T7/AI_THE_SPIRE/scripts/test_action_server.py

用户需在终端单独运行 test_action_client.py 进行交互。
"""
import sys
import json
import socket
import threading
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


def _run_server(port: int):
    """在后台线程运行 TCP 服务器，返回 (sock, client_response_queue)"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    sock.settimeout(0.5)  # 便于主循环检查

    client_conn = [None]  # 用 list 以便在闭包中修改
    client_response = [None]  # client 的响应

    def accept_loop():
        while True:
            try:
                conn, _ = sock.accept()
                conn.settimeout(None)
                if client_conn[0] is not None:
                    try:
                        client_conn[0].close()
                    except Exception:
                        pass
                client_conn[0] = conn
                recv_buf[0] = b""  # 新连接，清空缓冲区
            except (socket.timeout, OSError):
                continue

    recv_buf = [b""]  # 接收缓冲区

    def wait_for_client_response():
        """阻塞直到 client 发送一行响应"""
        conn = client_conn[0]
        if conn is None:
            return None
        try:
            while b"\n" not in recv_buf[0]:
                chunk = conn.recv(4096)
                if not chunk:
                    client_conn[0] = None
                    return None
                recv_buf[0] += chunk
            line, rest = recv_buf[0].split(b"\n", 1)
            recv_buf[0] = rest
            return line.decode("utf-8", errors="replace").strip()
        except Exception:
            return None

    t = threading.Thread(target=accept_loop, daemon=True)
    t.start()
    return sock, client_conn, wait_for_client_response


def main():
    port = int(os.environ.get("TEST_ACTION_PORT", DEFAULT_PORT))
    sock, client_conn, wait_for_response = _run_server(port)

    # 协议要求：启动后先发送 ready
    print("ready", flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            print("state", flush=True)
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            print("state", flush=True)
            continue

        if msg.get("in_game") is False:
            print("state", flush=True)
            continue

        gs = msg.get("game_state")
        if gs and gs.get("action_phase") != "WAITING_ON_USER":
            print("state", flush=True)
            continue
        # 临时移除 ready_for_command 过滤，排查 Survivor 弃牌等子界面
        # if msg.get("ready_for_command") is False:
        #     print("state", flush=True)
        #     continue

        # 决策点：转发给 client，等待响应
        conn = client_conn[0]
        if conn is None:
            # 无 client 连接，发送 state 保持通信（游戏会卡住直到 client 连接）
            print("state", flush=True)
            continue

        try:
            conn.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception:
            print("state", flush=True)
            continue

        # 阻塞等待 client 响应
        user_input = None
        while user_input is None:
            user_input = wait_for_response()
            if user_input is None:
                # 连接可能断开
                if client_conn[0] is None:
                    print("state", flush=True)
                    break
                continue

        if user_input is None:
            continue

        if user_input.lower() == "q":
            print("state", flush=True)
            continue

        if user_input.lower() in ("state", "wait", ""):
            print("state", flush=True)
            continue

        try:
            action_id = int(user_input)
        except ValueError:
            print("state", flush=True)
            continue

        if not 0 <= action_id < ACTION_SPACE_SIZE:
            print("state", flush=True)
            continue

        action = Action.from_id(action_id)
        cmd = action.to_command()
        print(cmd, flush=True)


if __name__ == "__main__":
    main()
