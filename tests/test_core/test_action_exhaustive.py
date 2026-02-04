#!/usr/bin/env python3
"""
Action ID 穷尽性测试

验证 action.py 的 133 个 action_id 能否正确往返转换：
- from_id(id) -> Action -> to_command() 产生合法 Mod 命令
- from_id(id) -> Action -> to_id() 应等于 id（对策略空间内动作）
"""
import pytest
from src.core.action import Action, ActionType, ACTION_SPACE_SIZE


class TestActionExhaustive:
    """穷尽测试 0-172 所有 action_id"""

    def test_from_id_to_command_roundtrip(self):
        """每个 action_id 都能转为合法 Mod 命令"""
        for action_id in range(ACTION_SPACE_SIZE):
            action = Action.from_id(action_id)
            cmd = action.to_command()
            assert isinstance(cmd, str), f"action_id={action_id} -> cmd 应为 str"
            assert len(cmd) > 0, f"action_id={action_id} -> 空命令"
            # 命令应可被 from_command 解析
            parsed = Action.from_command(cmd)
            assert parsed.type == action.type, f"action_id={action_id} 往返类型不一致"

    def test_from_id_to_id_roundtrip(self):
        """from_id -> to_id 应等于原 id"""
        for action_id in range(ACTION_SPACE_SIZE):
            action = Action.from_id(action_id)
            back_id = action.to_id()
            assert back_id == action_id, f"action_id={action_id} -> to_id()={back_id} 不一致"

    def test_command_format_by_range(self):
        """按区间验证命令格式"""
        # 出牌 0-69（Mod target 为 0-based：敌人1=0）
        assert Action.from_id(0).to_command() == "play 1"
        assert Action.from_id(9).to_command() == "play 10"
        assert Action.from_id(10).to_command() == "play 1 0"   # 敌人1 → target 0
        assert Action.from_id(69).to_command() == "play 10 5"   # 敌人6 → target 5

        # 药水 70-109（Mod target 为 0-based）
        assert Action.from_id(70).to_command() == "potion use 1"
        assert Action.from_id(74).to_command() == "potion use 5"
        assert Action.from_id(75).to_command() == "potion use 1 0"   # 敌人1 → target 0
        assert Action.from_id(104).to_command() == "potion use 5 5"  # 敌人6 → target 5
        assert Action.from_id(105).to_command() == "potion discard 1"
        assert Action.from_id(109).to_command() == "potion discard 5"

        # 选择 110-169
        assert Action.from_id(110).to_command() == "choose 0"
        assert Action.from_id(129).to_command() == "choose 19"
        assert Action.from_id(169).to_command() == "choose 59"

        # 控制 170-172
        assert Action.from_id(170).to_command() == "end"
        assert Action.from_id(171).to_command() == "proceed"
        assert Action.from_id(172).to_command() == "cancel"
