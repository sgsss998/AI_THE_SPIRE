#!/usr/bin/env python3
"""
训练数据预处理脚本

从 Mod Log 数据生成 (s, a) 训练数据对

输出格式:
- s: 状态向量 (2945维)
- a: 动作掩码 (dict {action_id: 1})
- actual_action: 实际执行的动作 (如果有)
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.training.encoder import encode, get_output_dim
import numpy as np


# ============================================================
# 动作空间定义
# ============================================================

ACTION_SPACE_SIZE = 250  # 最大动作ID

def create_action_mask(mod_response: Dict[str, Any]) -> Dict[int, int]:
    """
    从 Mod 响应生成动作掩码

    返回: dict {action_id: 1} 表示可用动作
    """
    gs = mod_response.get('game_state', {})
    cmds = mod_response.get('available_commands', [])
    cs = gs.get('combat_state', {})
    ss = gs.get('screen_state', {})

    action_mask = {}
    phase = gs.get('room_phase') or gs.get('screen_type', '')

    # 1. 手牌动作 (战斗中) - 0-9
    if phase == 'COMBAT' and 'play' in cmds:
        hand = cs.get('hand', [])
        for i, card in enumerate(hand[:10]):  # 最多10张手牌
            if card.get('is_playable', False):
                action_mask[i] = 1

    # 2. 结束回合 - 100
    if 'end' in cmds:
        action_mask[100] = 1

    # 3. 选择动作 - 110-119 (事件/卡牌奖励)
    if 'choose' in cmds or 'confirm' in cmds:
        options = ss.get('options', [])
        screen_cards = ss.get('cards', [])

        # 事件选项或卡牌选择
        num_choices = max(len(options), len(screen_cards))
        for i in range(min(num_choices, 10)):  # 最多10个选项
            action_mask[110 + i] = 1

    # 4. 药水动作 - 170-172
    if 'potion' in cmds:
        potions = gs.get('potions', [])
        for i, potion in enumerate(potions[:3]):  # 最多3个药水槽
            if potion.get('can_use', False):
                action_mask[170 + i] = 1

    # 5. 地图动作 - 200-201
    if 'proceed' in cmds:
        action_mask[200] = 1

    if 'return' in cmds:
        action_mask[201] = 1

    return action_mask


def infer_actual_action(current_record: Dict[str, Any], next_record: Dict[str, Any]) -> Optional[int]:
    """
    从当前记录和下一条记录推断实际执行的动作

    返回: 动作ID 或 None
    """
    curr_gs = current_record.get('game_state', {})
    next_gs = next_record.get('game_state', {})

    curr_cmds = current_record.get('available_commands', [])
    curr_action = current_record.get('action', '')
    curr_cs = curr_gs.get('combat_state', {})
    next_cs = next_gs.get('combat_state', {})

    # 检查 action 字段
    if curr_action == 'end':
        return 100
    elif curr_action == 'choose':
        # 需要进一步分析选择了哪个选项
        return 110  # 默认返回第一个选项
    elif curr_action == 'potion':
        return 170

    # 从战斗状态变化推断
    if curr_cs and next_cs:
        curr_turn = curr_cs.get('turn', 0)
        next_turn = next_cs.get('turn', 0)

        # 回合数变化 -> 结束回合
        if next_turn > curr_turn:
            return 100

        # 手牌数量减少1 -> 打出了一张牌
        curr_hand = curr_cs.get('hand', [])
        next_hand = next_cs.get('hand', [])

        if len(curr_hand) > len(next_hand):
            # 找出哪张牌被打出了
            curr_card_ids = {c.get('id', ''): i for i, c in enumerate(curr_hand)}
            next_card_ids = {c.get('id', '') for c in next_hand}

            for card_id, idx in curr_card_ids.items():
                if card_id not in next_card_ids:
                    return idx  # 返回打出的牌的位置

    return None


# ============================================================
# 数据处理主函数
# ============================================================

def process_mod_log_file(
    input_path: str,
    output_path: str,
    max_records: Optional[int] = None,
    include_actual_actions: bool = True,
) -> Dict[str, Any]:
    """
    处理 Mod Log 文件，生成训练数据

    Args:
        input_path: 输入 Mod Log 文件路径
        output_path: 输出训练数据文件路径
        max_records: 最大处理记录数（None=全部）
        include_actual_actions: 是否包含实际执行的动作

    Returns:
        处理统计信息
    """
    print(f"处理文件: {input_path}")

    # 读取 Mod Log
    with open(input_path, 'r', encoding='utf-8') as f:
        records = json.load(f)

    total_records = len(records)
    if max_records:
        records = records[:max_records]

    print(f"  总记录数: {total_records}")
    print(f"  处理记录数: {len(records)}")

    # 生成训练数据
    training_data = []
    stats = {
        'total': len(records),
        'processed': 0,
        'with_combat': 0,
        'with_event': 0,
        'with_actual_action': 0,
        'errors': 0,
    }

    for i, record in enumerate(records):
        try:
            # 生成 S 向量
            s = encode(record)

            # 生成动作掩码
            action_mask = create_action_mask(record)

            # 推断实际动作（如果有下一条记录）
            actual_action = None
            if include_actual_actions and i < len(records) - 1:
                actual_action = infer_actual_action(record, records[i + 1])
                if actual_action is not None:
                    stats['with_actual_action'] += 1

            # 统计场景类型
            gs = record.get('game_state', {})
            phase = gs.get('room_phase') or gs.get('screen_type', '')
            if phase == 'COMBAT':
                stats['with_combat'] += 1
            elif phase == 'EVENT':
                stats['with_event'] += 1

            # 保存训练样本
            sample = {
                's': s.tolist(),  # 转换为列表以便JSON序列化
                'action_mask': action_mask,
            }

            if actual_action is not None:
                sample['actual_action'] = actual_action

            # 可选：保存原始记录的元数据
            sample['metadata'] = {
                'record_idx': i,
                'floor': gs.get('floor', -1),
                'phase': phase,
                'commands': record.get('available_commands', []),
            }

            training_data.append(sample)
            stats['processed'] += 1

        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] <= 5:  # 只打印前5个错误
                print(f"  警告: 记录{i}处理失败: {e}")

    # 保存训练数据
    output_data = {
        'metadata': {
            'source_file': input_path,
            's_dimension': get_output_dim(),
            'action_space_size': ACTION_SPACE_SIZE,
            'total_samples': len(training_data),
            'timestamp': datetime.now().isoformat(),
        },
        'statistics': stats,
        'samples': training_data,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n处理完成!")
    print(f"  输出文件: {output_path}")
    print(f"  训练样本数: {len(training_data)}")
    print(f"  包含实际动作: {stats['with_actual_action']}")
    print(f"  错误数: {stats['errors']}")

    return stats


# ============================================================
# 批量处理
# ============================================================

def batch_process_mod_logs(
    input_dir: str,
    output_dir: str,
    pattern: str = "*.json",
) -> Dict[str, Any]:
    """
    批量处理 Mod Log 文件
    """
    import glob

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files = list(input_path.glob(pattern))
    print(f"找到 {len(files)} 个文件")

    all_stats = {
        'total_files': len(files),
        'processed_files': 0,
        'total_samples': 0,
        'total_with_actual_action': 0,
    }

    for i, input_file in enumerate(files):
        print(f"\n[{i+1}/{len(files)}] {input_file.name}")

        output_file = output_path / f"{input_file.stem}_processed.json"

        try:
            stats = process_mod_log_file(
                str(input_file),
                str(output_file),
                include_actual_actions=True,
            )

            all_stats['processed_files'] += 1
            all_stats['total_samples'] += stats['processed']
            all_stats['total_with_actual_action'] += stats['with_actual_action']

        except Exception as e:
            print(f"  ❌ 处理失败: {e}")

    print(f"\n" + "=" * 60)
    print("批量处理完成!")
    print(f"  处理文件: {all_stats['processed_files']}/{all_stats['total_files']}")
    print(f"  总样本数: {all_stats['total_samples']}")
    print(f"  包含实际动作: {all_stats['total_with_actual_action']}")

    return all_stats


# ============================================================
# 命令行入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="预处理 Mod Log 数据生成训练数据")
    parser.add_argument("--input", "-i", help="输入文件或目录")
    parser.add_argument("--output", "-o", help="输出文件或目录")
    parser.add_argument("--batch", "-b", action="store_true", help="批量处理模式")
    parser.add_argument("--max-records", type=int, help="最大处理记录数")

    args = parser.parse_args()

    if args.batch:
        # 批量处理
        batch_process_mod_logs(
            args.input or "data/A20_Silent/Raw_Data_json_FORSL",
            args.output or "data/processed",
        )
    else:
        # 单文件处理
        process_mod_log_file(
            args.input or "data/A20_Silent/Raw_Data_json_FORSL/Silent_A20_HUMAN_20260205_233248.json",
            args.output or "data/training_data.json",
            max_records=args.max_records,
        )
