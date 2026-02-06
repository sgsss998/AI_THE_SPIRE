# AI_THE_SPIRE

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)](https://pytorch.org/)
[![RL](https://img.shields.io/badge/RL-stable--baselines3-green.svg)](https://github.com/DLR-RM/stable-baselines3)

基于强化学习的《杀戮尖塔》AI 项目

</div>

---

## 项目简介

本项目使用强化学习技术，让 AI 自主学习《杀戮尖塔》的游戏策略。

**目标**：在进阶20难度下，使用静默猎手角色，挑战 NoSL（No Save & Loading，不存读档）模式的人类纪录（当前27场连胜）。

**技术路线**：规则基线 → 监督学习（从人类数据学习）→ 强化学习（自我对弈优化）

---

## 系统架构

### 训练流程

```
规则基线 (数据收集)
       ↓
监督学习 (热启动)
       ↓
强化学习 (PPO/A2C)
       ↓
    自我对弈优化
```

### 技术栈

| 组件 | 技术 |
|------|------|
| 游戏通信 | CommunicationMod (JSON) |
| 状态编码 | 自定义 ~2900维 S-向量 |
| 动作空间 | 179维离散空间 |
| RL框架 | Gymnasium + Stable-Baselines3 |
| 神经网络 | PyTorch |

---

## 状态编码 (S-向量)

游戏状态编码为 **2900维向量**，分为10个区块：

```
┌─────────────────────────────────────────────────────────────┐
│  区块          范围          维度    内容                    │
├─────────────────────────────────────────────────────────────┤
│  玩家核心    [0-49]        50     HP、能量、金币、护甲等     │
│  手牌        [50-449]      400    手牌详情                  │
│  抽牌堆      [450-849]     400    牌库组成                  │
│  弃牌堆      [850-1249]    400                            │
│  消耗堆      [1250-1549]   300                            │
│  能力效果    [1550-1649]   100    Power 状态               │
│  怪物        [1650-2249]   600    怪物状态、意图            │
│  遗物        [2250-2449]   200                            │
│  药水        [2450-2649]   200                            │
│  全局状态    [2650-2899]   250    楼层、房间类型等          │
└─────────────────────────────────────────────────────────────┘
```

### 编码原则

1. 所有参数来源于 Mod 日志（无外部信息）
2. 单个游戏参数可映射到多个向量维度
3. 非战斗状态使用零填充

---

## 动作空间 (179维)

| 类别 | 数量 | 说明 |
|------|------|------|
| 出牌 | 70 | 每张牌 × 6目标 |
| 使用药水 | 20 | |
| 丢弃药水 | 20 | |
| 屏幕选择 | 60 | 事件/商店/奖励 |
| 控制动作 | 9 | 结束回合、确认等 |

---

## 项目结构

```
AI_THE_SPIRE/
├── src/
│   ├── core/                      # 数据结构
│   │   ├── game_state.py          # GameState, Card, Monster
│   │   ├── action.py              # 动作空间定义
│   │   └── config.py
│   ├── env/
│   │   └── sts_env.py             # Gymnasium 环境
│   ├── agents/                    # AI 实现
│   │   ├── base.py
│   │   ├── rule_based.py          # 规则 AI
│   │   ├── supervised.py          # 监督学习
│   │   └── rl_agent.py            # 强化学习
│   └── training/
│       ├── encoder.py             # S-向量编码器
│       ├── encoder_utils.py
│       └── power_parser.py
├── scripts/
│   ├── train.py                   # 主入口
│   ├── collect_data.py
│   ├── train_sl.py
│   ├── train_rl.py
│   └── evaluate.py
├── configs/
│   ├── default.yaml
│   └── encoder_ids.yaml
└── docs/
    └── MOD_LOG_PARAMETERS.md
```

---

## 快速开始

### 前置要求

- 《杀戮尖塔》游戏本体
- [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod)
- Python 3.14+

### 安装

```bash
pip install "numpy<2.0" "scipy<2.0" scikit-learn pyyaml
pip install torch torchvision torchaudio
pip install stable-baselines3 gymnasium
```

### 使用

```bash
# 观看规则 AI 玩一局
python scripts/train.py interactive --agent-type rule

# 完整训练流程
python scripts/train.py pipeline --collect-games 50 --sl-epochs 100 --rl-timesteps 100000

# 单独执行
python scripts/train.py collect   # 收集数据
python scripts/train.py sl        # 监督学习
python scripts/train.py rl        # 强化学习
python scripts/train.py eval      # 评估
```

---

## 技术特性

- **防卡死机制**：命令重复检测、状态哈希检测、命令黑名单
- **热启动**：使用监督学习模型初始化 RL，加速收敛
- **动作掩码**：只选择当前合法动作
- **模块化设计**：核心层/环境层/智能体层分离

---

## 已知问题

**NumPy 2.0 兼容性**：`sklearn + numpy 2.0` 会报错

```bash
pip install "numpy<2.0" "scipy<2.0"
```

---

## 开发记录

### 2026-02-04：S-向量设计共识

- S-向量参数是 Mod 日志的子集
- 维度远大于原始参数数量（多 hot 编码）
- 参数选择是最关键的设计决策

### 进度

| 时间      | 里程碑                |
| ------- | ------------------ |
| 2026-01 | 动作空间定义完成 (179)     |
| 2026-02 | S-向量编码器完成 (~2900维) |
| 待定      | 监督学习训练             |
| 待定      | 强化学习训练             |

---

## 参考资源

- [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod)
- [Stable-Baselines3](https://github.com/DLR-RM/stable-Baselines3)
- [Gymnasium](https://github.com/Farama-Foundation/Gymnasium)
---

AI_THE_SPIRE 项目完整分析报告

  项目概述

  AI_THE_SPIRE 是一个基于强化学习的《杀戮尖塔》(Slay the Spire) AI 项目，目标是让 AI 自主学习游戏策略，挑战进阶20难度的 NoSL 模式人类纪录（27场连胜）。

  技术路线: 规则基线 → 监督学习（SL）→ 强化学习（RL）

  ---
  核心架构

  1. 目录结构

  AI_THE_SPIRE/
  ├── src/
  │   ├── core/              # 核心数据结构
  │   │   ├── game_state.py  # 游戏状态定义
  │   │   ├── action.py      # 动作空间定义 (179维)
  │   │   └── config.py      # 配置管理
  │   ├── env/
  │   │   └── sts_env.py     # Gymnasium RL环境
  │   ├── agents/
  │   │   ├── base.py        # Agent基类
  │   │   ├── rule_based.py  # 规则AI
  │   │   ├── supervised.py  # 监督学习
  │   │   └── rl_agent.py    # 强化学习
  │   └── training/
  │       ├── encoder.py     # S向量编码器 (~3126维)
  │       ├── encoder_utils.py
  │       └── power_parser.py
  ├── scripts/               # 训练脚本
  ├── configs/               # 配置文件
  └── data/                  # 数据存储

  2. 核心数据结构 (game_state.py)

  类层次结构:
  GameState (游戏总状态)
  ├── RoomPhase (房间阶段枚举)
  ├── CardType (卡牌类型枚举)
  ├── IntentType (怪物意图枚举)
  ├── Card (卡牌 - frozen dataclass)
  ├── Player (玩家状态)
  ├── Monster (怪物状态)
  ├── CombatState (战斗状态)
  └── GameState (完整游戏状态)

  关键方法:
  - GameState.from_mod_response(): 从 CommunicationMod JSON 创建状态
  - GameState.to_mod_response(): 转换为 Mod 格式用于编码

  3. 动作空间 (action.py)

  179维离散动作空间:
  - 0-69: 出牌 (10张牌 × 7个目标)
  - 70-109: 药水 (使用/丢弃)
  - 110-169: 选择选项
  - 170-178: 控制动作 (end/proceed/confirm/cancel等)

  关键方法:
  - Action.to_command(): 转换为 Mod 命令字符串
  - Action.from_command(): 从命令解析
  - Action.to_id(): 转换为训练标签
  - Action.from_id(): 从模型预测创建

  4. 状态编码 (encoder.py)

  S向量 V2: ~3126维，分10个区块
  ┌───────────────┬──────┬─────────────────────────────────────────┐
  │     区块      │ 维度 │                  内容                   │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 1. 玩家核心   │ 58   │ HP/能量/护甲/金币/钥匙/Orbs等           │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 2. 手牌       │ 500  │ 271维卡牌multi-hot + 21×10牌属性 + 统计 │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 3. 抽牌堆     │ 450  │ 卡牌multi-hot + 详细统计                │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 4. 弃牌堆     │ 450  │ 同上                                    │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 5. 消耗堆     │ 350  │ 同上                                    │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 6. 玩家Powers │ 100  │ Power效果one-hot                        │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 7. 怪物       │ 618  │ 6怪物×103维 (ID/HP/意图/类型等)         │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 8. 遗物       │ 200  │ 180维multi-hot + 统计                   │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 9. 药水       │ 200  │ 45维multi-hot + 每槽5×5 + 统计          │
  ├───────────────┼──────┼─────────────────────────────────────────┤
  │ 10. 全局      │ 500  │ 楼层/事件ID/地图/房间细分等             │
  └───────────────┴──────┴─────────────────────────────────────────┘
  5. RL环境 (sts_env.py)

  StsEnvironment 类:
  - 观察空间: ~3126维连续向量
  - 动作空间: Discrete(179)
  - Action Masking: 返回合法动作列表
  - 奖励函数: 基于伤害、击杀、HP变化等
  - 终止条件: 游戏结束/战斗结束/死亡/胜利

  ---
  训练流程

  完整Pipeline

  1. 数据收集 (collect_data.py)
     ↓ 真实游戏数据
  2. 监督学习 (train_sl.py)
     ↓ 初始化RL策略
  3. 强化学习 (train_rl.py)
     ↓ PPO/A2C优化
  4. 评估 (evaluate.py)

  脚本说明

  train.py: 统一训练入口
  - pipeline: 完整流程
  - collect: 数据收集
  - sl: 监督学习
  - rl: 强化学习
  - eval: 评估
  - interactive: 交互测试

  train_rl.py: RL训练专用
  - 支持 PPO/A2C/DQN 算法
  - Warm Start 从 SL 模型初始化
  - 支持并行环境训练

  ---
  设计特点

  1. 防卡死机制: 命令重复检测、状态哈希检测、命令黑名单
  2. 热启动: 使用 SL 模型初始化 RL，加速收敛
  3. 动作掩码: 只选择当前合法动作
  4. 模块化设计: 核心层/环境层/智能体层分离
  5. 完整训练流程: 从数据收集到 RL 训练的完整 pipeline

  ---
  技术栈
  ┌──────────┬───────────────────────────────┐
  │   组件   │             技术              │
  ├──────────┼───────────────────────────────┤
  │ 游戏通信 │ CommunicationMod (JSON)       │
  ├──────────┼───────────────────────────────┤
  │ 状态编码 │ 自定义 ~3126维 S-向量         │
  ├──────────┼───────────────────────────────┤
  │ 动作空间 │ 179维离散空间                 │
  ├──────────┼───────────────────────────────┤
  │ RL框架   │ Gymnasium + Stable-Baselines3 │
  ├──────────┼───────────────────────────────┤
  │ 神经网络 │ PyTorch + sklearn             │
  ├──────────┼───────────────────────────────┤
  │ 配置管理 │ YAML                          │
  └──────────┴───────────────────────────────┘
  ---
  已知问题

  1. NumPy 2.0兼容性: sklearn + numpy 2.0 会报错
  2. CommunicationMod依赖: 需要安装 Mod 才能与真实游戏通信
  3. 数据收集: 真实游戏数据收集需要配置 Mod 的 command 参数