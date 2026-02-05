#!/usr/bin/env python3
"""
训练模块

包含状态编码、数据集处理、模型训练、实验跟踪等功能。
"""
from .encoder import encode, get_output_dim, OUTPUT_DIM
from .experiment import (
    ExperimentTracker,
    ExperimentConfig,
    ExperimentResult,
    get_tracker,
    create_experiment,
)

__all__ = [
    "encode",
    "get_output_dim",
    "OUTPUT_DIM",
    "ExperimentTracker",
    "ExperimentConfig",
    "ExperimentResult",
    "get_tracker",
    "create_experiment",
]
