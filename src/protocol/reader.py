#!/usr/bin/env python3
"""
协议读取层 - 从 stdin 读取 Mod 响应

负责从 CommunicationMod 的 stdout 读取 JSON 状态数据。
"""
import sys
import json
import logging
from typing import Optional, Dict, Any

from src.core.game_state import GameState

logger = logging.getLogger(__name__)


class ModReader:
    """CommunicationMod 协议读取器

    从 stdin 读取 Mod 发送的 JSON 状态数据。

    协议说明：
    - Mod 每次发送一行 JSON
    - 我们必须每次都回复，否则 Mod 会阻塞
    - 空行应被忽略
    """

    def __init__(self, input_stream=None):
        """
        初始化读取器

        Args:
            input_stream: 输入流，默认为 stdin
        """
        self.input_stream = input_stream or sys.stdin
        self._line_count = 0
        self._error_count = 0

    def read_state(self) -> Optional[Dict[str, Any]]:
        """
        读取一行 JSON 状态

        Returns:
            解析后的字典，None 表示 EOF 或解析失败
        """
        line = self.input_stream.readline()

        # EOF
        if not line:
            logger.debug("[Reader] EOF reached")
            return None

        line = line.strip()

        # 空行跳过
        if not line:
            return None

        self._line_count += 1

        try:
            data = json.loads(line)
            if logger.isEnabledFor(logging.DEBUG):
                preview = json.dumps(data, ensure_ascii=False)[:200]
                logger.debug(f"[Reader] Line {self._line_count}: {preview}...")
            return data
        except json.JSONDecodeError as e:
            self._error_count += 1
            logger.warning(f"[Reader] JSON decode error at line {self._line_count}: {e}")
            logger.debug(f"[Reader] Problematic line: {line[:200]}")
            return None

    def read_game_state(self) -> Optional[GameState]:
        """
        读取并解析为 GameState

        Returns:
            GameState 对象，None 表示 EOF 或解析失败
        """
        data = self.read_state()
        if data is None:
            return None

        try:
            return GameState.from_mod_response(data)
        except Exception as e:
            logger.error(f"[Reader] Failed to parse GameState: {e}")
            return None

    @property
    def line_count(self) -> int:
        """已读取的行数"""
        return self._line_count

    @property
    def error_count(self) -> int:
        """解析错误的行数"""
        return self._error_count


class InteractiveReader(ModReader):
    """交互式读取器（用于启动和测试）

    在首次使用时发送 "ready" 信号给 Mod。
    """

    def __init__(self, input_stream=None, output_stream=None):
        super().__init__(input_stream)
        self.output_stream = output_stream or sys.stdout
        self.sent_ready = False

    def start(self):
        """发送 ready 信号给 Mod

        根据协议，启动后应立即发送 "ready\\n"
        """
        if not self.sent_ready:
            self.output_stream.write("ready\n")
            self.output_stream.flush()
            self.sent_ready = True
            logger.info("[Reader] Sent ready signal")

    def read_game_state(self) -> Optional[GameState]:
        """确保已发送 ready 信号后再读取"""
        if not self.sent_ready:
            self.start()
        return super().read_game_state()


# 便捷函数
def create_reader(interactive: bool = True) -> ModReader:
    """
    创建读取器

    Args:
        interactive: 是否使用交互式读取器（自动发送 ready）

    Returns:
        ModReader 实例
    """
    if interactive:
        return InteractiveReader()
    return ModReader()
