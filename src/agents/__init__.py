#!/usr/bin/env python3
"""
AI Agent 模块

提供统一的 Agent 接口，支持规则、监督学习、强化学习。
"""
from .base import (
    Agent,
    RuleBasedAgent,
    SupervisedAgent,
    RLAgent,
    create_agent,
)
from .rule_based import RuleBasedAgentImpl, decide_combat_action, decide_choice
from .supervised import SupervisedAgentImpl, load_training_data, load_data_from_sessions
from .rl_agent import RLAgentImpl

__all__ = [
    # 基类
    "Agent",
    "RuleBasedAgent",
    "SupervisedAgent",
    "RLAgent",
    # 实现
    "RuleBasedAgentImpl",
    "SupervisedAgentImpl",
    "RLAgentImpl",
    # 工厂
    "create_agent",
    # 数据加载
    "load_training_data",
    "load_data_from_sessions",
    # 兼容旧版
    "decide_combat_action",
    "decide_choice",
]
