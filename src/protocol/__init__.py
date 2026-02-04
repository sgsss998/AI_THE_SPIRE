#!/usr/bin/env python3
"""
协议层模块

处理与 CommunicationMod 的 stdin/stdout 通信。
"""
from .reader import ModReader, InteractiveReader, create_reader
from .writer import ModWriter, create_writer
from .parser import ModProtocol, create_protocol

__all__ = [
    # reader
    "ModReader",
    "InteractiveReader",
    "create_reader",
    # writer
    "ModWriter",
    "create_writer",
    # parser
    "ModProtocol",
    "create_protocol",
]
