#!/usr/bin/env python3
"""
协议解析器 - 桥接协议层和核心数据层

提供高级接口，组合 reader 和 writer 的功能。
"""
import logging
from typing import Optional, Tuple

from src.core.game_state import GameState
from src.core.action import Action
from src.core.config import get_config
from src.protocol.reader import ModReader
from src.protocol.writer import ModWriter

logger = logging.getLogger(__name__)


class ModProtocol:
    """CommunicationMod 协议处理器

    组合读取器和写入器，提供完整的协议交互功能。
    """

    def __init__(
        self,
        reader: Optional[ModReader] = None,
        writer: Optional[ModWriter] = None,
    ):
        """
        初始化协议处理器

        Args:
            reader: 读取器，默认创建新的
            writer: 写入器，默认创建新的
        """
        self.reader = reader or ModReader()
        self.writer = writer or ModWriter()
        self.config = get_config()

        # 状态跟踪
        self._last_state_hash: Optional[str] = None
        self._null_stuck_start: Optional[float] = None

    def read_state(self) -> Optional[GameState]:
        """
        读取游戏状态

        Returns:
            GameState 对象，None 表示 EOF
        """
        return self.reader.read_game_state()

    def send_action(self, action: Action):
        """
        发送动作

        Args:
            action: 要发送的动作
        """
        self.writer.send_action(action)

    def send_command(self, command: str):
        """
        发送原始命令

        Args:
            command: 命令字符串
        """
        self.writer.send(command)

    def is_null_state(self, state: GameState) -> bool:
        """
        判断是否为无效状态

        Mod 解析失败时可能返回空状态。

        Args:
            state: 游戏状态

        Returns:
            True 表示无效状态
        """
        if state is None:
            return True

        # 检查关键字段是否都为空/None
        # 兼容枚举和字符串
        phase = state.room_phase
        if hasattr(phase, "value"):
            phase = phase.value

        return (
            phase == "NONE"
            and state.combat is None
            and state.screen_type is None
        )

    def has_state_changed(self, state: GameState) -> bool:
        """
        判断状态是否变化（用于去重）

        Args:
            state: 当前状态

        Returns:
            True 表示状态已变化
        """
        current_hash = state.hash()
        if current_hash != self._last_state_hash:
            self._last_state_hash = current_hash
            return True
        return False

    def should_log_state(self, state: GameState) -> bool:
        """
        判断是否应该记录此状态

        规则：
        - 必须在游戏中
        - 状态必须实际变化（去重）
        - 排除轮询状态

        Args:
            state: 游戏状态

        Returns:
            True 表示应该记录
        """
        if not state.in_game:
            return False

        return self.has_state_changed(state)

    def get_fallback_action(self, state: GameState) -> Action:
        """
        获取回退动作（当无法正常决策时）

        根据当前状态返回一个安全的默认动作。

        Args:
            state: 当前游戏状态

        Returns:
            回退动作
        """
        # 1. 优先处理 proceed
        if "proceed" in state.available_commands and state.ready_for_command:
            return Action.proceed()

        # 2. 未就绪且有 wait，等待
        if not state.ready_for_command and "wait" in state.available_commands:
            return Action.wait()

        # 3. 有 key 命令，尝试 Confirm
        if state.ready_for_command and "key" in state.available_commands:
            # 战斗中可能需要确认
            if state.is_combat:
                return Action.key("Confirm")
            # 其他情况确认
            return Action.key("Confirm")

        # 4. 默认返回 state
        return Action.state()

    def handle_null_state(
        self,
        time_stuck: float,
    ) -> Action:
        """
        处理 null 状态（Mod 解析失败）

        Args:
            time_stuck: 已卡住的秒数

        Returns:
            要尝试的回退命令
        """
        config = self.config.protocol
        fallback_cmds = config.fallback_commands

        # 超时后扩展命令列表
        if time_stuck > config.null_stuck_timeout:
            # 使用完整列表循环
            idx = int(time_stuck) % len(fallback_cmds)
        else:
            # 仅使用前两个命令（key Confirm, wait）
            idx = int(time_stuck) % 2

        cmd = fallback_cmds[idx]
        return Action.from_command(cmd)

    def get_stats(self) -> dict:
        """
        获取协议统计信息

        Returns:
            统计信息字典
        """
        return {
            "lines_read": self.reader.line_count,
            "errors": self.reader.error_count,
            "commands_sent": self.writer.command_count,
            "last_command": self.writer.last_command,
        }

    def log_stats(self):
        """记录统计信息到日志"""
        stats = self.get_stats()
        logger.info(
            f"[Protocol] Stats: "
            f"{stats['lines_read']} lines read, "
            f"{stats['errors']} errors, "
            f"{stats['commands_sent']} commands sent"
        )


# 便捷函数
def create_protocol() -> ModProtocol:
    """创建协议处理器"""
    return ModProtocol()
