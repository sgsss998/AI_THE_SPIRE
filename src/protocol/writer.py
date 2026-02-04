#!/usr/bin/env python3
"""
协议写入层 - 向 stdout 发送命令

负责向 CommunicationMod 的 stdin 发送命令。
"""
import sys
import logging
from typing import Optional

from src.core.action import Action

logger = logging.getLogger(__name__)


class ModWriter:
    """CommunicationMod 协议写入器

    向 stdout 发送命令给 Mod。

    命令格式：
    - "play X Y" - 出第 X 张牌（1-based），目标 Y
    - "end" - 结束回合
    - "choose X" - 选择选项 X
    - "key X" - 按键 X（Confirm/Cancel）
    - "proceed" - 前进
    - "wait" - 等待
    - "state" - 请求状态
    """

    def __init__(self, output_stream=None):
        """
        初始化写入器

        Args:
            output_stream: 输出流，默认为 stdout
        """
        self.output_stream = output_stream or sys.stdout
        self._command_count = 0
        self._last_command: Optional[str] = None

    def send(self, command: str):
        """
        发送命令到 Mod

        Args:
            command: 命令字符串（如 "play 1 0", "end"）

        注意：
        - 命令必须以换行符结尾
        - 发送后必须 flush，否则 Mod 收不到
        """
        self._command_count += 1
        self._last_command = command

        self.output_stream.write(command + "\n")
        self.output_stream.flush()

        logger.debug(f"[Writer] Sent #{self._command_count}: {command}")

    def send_action(self, action: Action):
        """
        发送动作

        Args:
            action: Action 对象
        """
        cmd = action.to_command()
        self.send(cmd)

    def send_state(self):
        """发送状态请求（当无其他命令时使用）"""
        self.send("state")

    def send_play(self, card_index: int, target_index: int = 0):
        """
        发送出牌命令

        Args:
            card_index: 卡牌索引（0-based，内部使用）
            target_index: 目标索引（0=无目标, 1+=怪物1-based）
        """
        cmd = f"play {card_index + 1}"
        if target_index > 0:
            cmd += f" {target_index - 1}"  # Mod target 为 0-based
        self.send(cmd)

    def send_end(self):
        """发送结束回合命令"""
        self.send("end")

    def send_choose(self, choice_index: int):
        """
        发送选择命令

        Args:
            choice_index: 选项索引（0-based）
        """
        cmd = f"choose {choice_index}"
        self.send(cmd)

    def send_key(self, key_name: str):
        """
        发送按键命令

        Args:
            key_name: 按键名称（Confirm, Cancel 等）
        """
        cmd = f"key {key_name}"
        self.send(cmd)

    def send_proceed(self):
        """发送前进命令"""
        self.send("proceed")

    def send_wait(self):
        """发送等待命令"""
        self.send("wait")

    def send_click(self):
        """发送点击命令"""
        self.send("click")

    @property
    def command_count(self) -> int:
        """已发送的命令数"""
        return self._command_count

    @property
    def last_command(self) -> Optional[str]:
        """最后发送的命令"""
        return self._last_command


# 便捷函数
def create_writer() -> ModWriter:
    """创建写入器"""
    return ModWriter()
