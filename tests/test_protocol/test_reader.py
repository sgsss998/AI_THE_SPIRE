#!/usr/bin/env python3
"""
协议层单元测试
"""
import pytest
import sys
import os
from io import StringIO

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.protocol.reader import ModReader, InteractiveReader
from src.protocol.writer import ModWriter
from src.protocol.parser import ModProtocol
from src.core.game_state import GameState, RoomPhase
from src.core.action import Action


class TestModReader:
    """ModReader 测试"""

    def test_read_empty_input(self):
        """测试空输入"""
        input_stream = StringIO("")
        reader = ModReader(input_stream)
        assert reader.read_state() is None

    def test_read_valid_json(self):
        """测试有效 JSON"""
        json_data = '{"in_game": true, "game_state": {"room_phase": "COMBAT"}}'
        input_stream = StringIO(json_data)
        reader = ModReader(input_stream)
        data = reader.read_state()
        assert data is not None
        assert data["in_game"] is True

    def test_read_invalid_json(self):
        """测试无效 JSON"""
        input_stream = StringIO("not a json")
        reader = ModReader(input_stream)
        data = reader.read_state()
        assert data is None
        assert reader.error_count == 1

    def test_read_game_state(self):
        """测试读取 GameState"""
        # 使用单行 JSON（模拟真实 Mod 输出）
        json_data = '{"in_game": true, "ready_for_command": true, "available_commands": ["play", "end"], "game_state": {"room_phase": "COMBAT", "floor": 1, "act": 1, "combat_state": {"hand": [{"id": "Strike", "name": "打击", "cost": 1, "type": "ATTACK"}], "player": {"energy": 3, "current_hp": 70}, "monsters": [], "turn": 1}}}'
        input_stream = StringIO(json_data)
        reader = ModReader(input_stream)
        state = reader.read_game_state()
        assert state is not None
        assert state.is_combat is True
        assert state.floor == 1


class TestModWriter:
    """ModWriter 测试"""

    def test_send_command(self):
        """测试发送命令"""
        output_stream = StringIO()
        writer = ModWriter(output_stream)
        writer.send("play 1 0")
        output = output_stream.getvalue()
        assert output == "play 1 0\n"
        assert writer.command_count == 1

    def test_send_action(self):
        """测试发送 Action"""
        output_stream = StringIO()
        writer = ModWriter(output_stream)
        action = Action.play_card(0)
        writer.send_action(action)
        output = output_stream.getvalue()
        # target=0 时省略目标参数（正确的行为）
        assert output == "play 1\n"

    def test_send_end(self):
        """测试发送结束回合"""
        output_stream = StringIO()
        writer = ModWriter(output_stream)
        writer.send_end()
        output = output_stream.getvalue()
        assert output == "end\n"

    def test_send_choose(self):
        """测试发送选择"""
        output_stream = StringIO()
        writer = ModWriter(output_stream)
        writer.send_choose(0)
        output = output_stream.getvalue()
        assert output == "choose 0\n"

    def test_send_key(self):
        """测试发送按键"""
        output_stream = StringIO()
        writer = ModWriter(output_stream)
        writer.send_key("Confirm")
        output = output_stream.getvalue()
        assert output == "key Confirm\n"


class TestModProtocol:
    """ModProtocol 测试"""

    def test_create_protocol(self):
        """测试创建协议"""
        protocol = ModProtocol()
        assert protocol.reader is not None
        assert protocol.writer is not None

    def test_is_null_state(self):
        """测试判断 null 状态"""
        protocol = ModProtocol()

        # None 是 null
        assert protocol.is_null_state(None) is True

        # 空状态是 null
        empty_state = GameState(
            room_phase=RoomPhase.NONE,
            floor=0,
            act=0
        )
        assert protocol.is_null_state(empty_state) is True

        # 正常状态不是 null
        normal_state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1
        )
        assert protocol.is_null_state(normal_state) is False

    def test_has_state_changed(self):
        """测试状态变化检测"""
        protocol = ModProtocol()

        state1 = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1
        )

        state2 = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1
        )

        state3 = GameState(
            room_phase=RoomPhase.EVENT,
            floor=2,
            act=1
        )

        # 第一次总是变化
        assert protocol.has_state_changed(state1) is True

        # 相同状态不变化
        assert protocol.has_state_changed(state2) is False

        # 不同状态变化
        assert protocol.has_state_changed(state3) is True

    def test_get_fallback_action(self):
        """测试获取回退动作"""
        protocol = ModProtocol()

        # 有 proceed 时返回 proceed
        state = GameState(
            room_phase=RoomPhase.COMBAT,
            floor=1,
            act=1,
            available_commands=["proceed"],
            ready_for_command=True
        )
        action = protocol.get_fallback_action(state)
        assert action.to_command() == "proceed"

        # 默认返回 state
        state = GameState(
            room_phase=RoomPhase.NONE,
            floor=0,
            act=0,
            available_commands=[],
            ready_for_command=False
        )
        action = protocol.get_fallback_action(state)
        assert action.to_command() == "state"

    def test_get_stats(self):
        """测试获取统计信息"""
        protocol = ModProtocol()
        stats = protocol.get_stats()
        assert "lines_read" in stats
        assert "errors" in stats
        assert "commands_sent" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
