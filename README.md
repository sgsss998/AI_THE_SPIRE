# AI_THE_SPIRE

![AI_THE_SPIRE 封面](./cover-ai-the-spire-v1.png)

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)](https://pytorch.org/)
[![RL](https://img.shields.io/badge/RL-stable--baselines3-green.svg)](https://github.com/DLR-RM/stable-baselines3)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)

### 基于 Reinforcement Learning 的《Slay the Spire》AI 项目

**目标**：在 Ascension 20 难度下，使用静默猎手挑战 NoSL 模式

**技术路线**：规则基线 → 监督学习（从人类数据） → 强化学习（自我优化）

</div>

---

## 目录

- [项目简介](#项目简介)
- [系统架构](#系统架构)
- [状态编码器 V2](#状态编码器-v2)
- [动作空间](#动作空间)
- [数据流程](#数据流程)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [开发文档](#开发文档)
- [更新日志](#更新日志)

---

## 项目简介

本项目使用**强化学习技术**训练 AI 自主学习《杀戮尖塔》的游戏策略。

### 核心特性

- 🎮 **静默猎手专用**：针对 A20 难度 + 静默职业优化
- 📊 **状态编码器**：2945 维 S 向量，覆盖完整游戏状态
- 🎯 **动作空间**：179 维离散动作，支持所有游戏操作
- 🔄 **完整训练流程**：从 Mod Log → 预处理 → 训练 → 评估
- 🛡️ **Action Masking**：只选择当前合法动作

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 游戏通信 | [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod) | JSON 协议 |
| 状态编码 | 自定义编码器 | 2945 维 S 向量 |
| RL 框架 | Gymnasium + Stable-Baselines3 | PPO/A2C 算法 |
| 神经网络 | PyTorch | 策略网络 + 价值网络 |
| 配置管理 | YAML | 灵活的配置系统 |

---

## 系统架构

### 训练流程

```
┌─────────────┐
│  Mod Log    │  真实游戏数据
└──────┬──────┘
       ↓
┌─────────────┐
│  预处理     │  (s, a) 对生成
└──────┬──────┘
       ↓
┌─────────────┐
│ 监督学习    │  行为克隆
└──────┬──────┘
       ↓
┌─────────────┐
│ 强化学习    │  PPO/A2C 优化
└──────┬──────┘
       ↓
┌─────────────┐
│   评估      │  性能测试
└─────────────┘
```

### 组件架构

```
┌───────────────────────────────────────────────────────────────┐
│                        训练入口                            │
│                    scripts/train.py                         │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ pipeline │ collect │ sl │ rl │ eval │ interactive │   │
│  └────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│                      核心模块层                              │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────┐  ┌─────────┐  │
│  │  核心    │  │    训练      │  │    智能体     │  │  环境   │  │
│  │          │  │              │  │              │  │         │  │
│  │ action.py│  │ encoder.py  │  │supervised.py │ │sts_env.py│ │
│  │config.py │  │encoder_dims.py│  │  rl_agent.py │  │         │  │
│  │game_state│  │encoder_utils│  │rule_based.py │  │         │  │
│  └──────────┘  │power_parser│  └──────────────┘  └─────────┘  │
│  └──────────┘  └─────────────┘  └──────────────┘  └─────────┘  │
└───────────────────────────────────────────────────────────────┘
                              ↓
┌───────────────────────────────────────────────────────────────┐
│                      数据层                                  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │          Mod Log 原始数据                              │  │
│  │  data/A20_Silent/Raw_Data_json_FORSL/*.json             │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │          预处理后的训练数据                            │  │
│  │  data/training_data_*.json                             │  │
│  │  data/s_vectors.npy / data/actions.npy                   │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 状态编码器 V2

### 总览

**总维度**：2945 维
**设计原则**：静默猎手专用（A20 固定难度）
**数据来源**：100% 基于 Mod 日志字段

### 区块结构

```
┌────────────────────────────────────────────────────────────────────┐
│ 区块          | 范围        | 维度  | 内容                              │
├────────────────────────────────────────────────────────────────────┤
│ 玩家核心      │ [0-16]      │  17  │ HP/能量/护甲/金币/钥匙               │
│ 手牌         │ [17-406]    │ 390  │ 144 multi-hot + 21×10 + 统计        │
│ 抽牌堆       │ [407-746]   │ 340  │ 144 multi-hot + 详细统计             │
│ 弃牌堆       │ [747-1086]  │ 340  │ 同上                               │
│ 消耗堆       │ [1087-1326] │ 240  │ 同上                               │
│ 玩家Powers  │ [1327-1426] │ 100  │ Power效果                           │
│ 怪物         │ [1427-2045] │ 618  │ 6怪物×103维                        │
│ 遗物         │ [2045-2244] │ 200  │ 180 multi-hot + 统计                  │
│ 药水         │ [2245-2444] │ 200  │ 45 multi-hot + 槽位信息               │
│ 全局         │ [2445-2944] │ 500  │ 楼层/事件/地图/战斗动态/牌组变化      │
└────────────────────────────────────────────────────────────────────┘
```

### 区块10：全局状态详细结构（新增功能）

```
[0-22]      基础信息（楼层、章节、房间阶段、可用命令）
[23-72]     事件ID one-hot (50维)
[73-87]     房间细分类型 one-hot (15维)
[88-112]    地图路径信息 (25维)
[113-136]   更多buff/debuff状态 (24维)
[137-200]   地图编码 (64维)
[201-209]   重要字段 (9维)
            ├── 商店删牌信息 (2维)
            ├── 正在打出的牌 (2维)
            ├── 受击次数 (1维)
            └── 奖励类型 (4维)
[210-320]   ⭐ 战斗动态信息 (111维) - 新增
            ├── limbo牌信息 (3维)
            ├── 怪物行为模式 (8维)
            ├── 预计伤害来源 (10维)
            └── 本回合动态 (20维)
[321-400]   ⭐ 牌组变化统计 (80维) - 新增
            ├── 牌组构成变化 (15维)
            ├── 已消耗牌统计 (35维)
            └── 升级牌统计 (15维)
[401-499]   预留 (99维)
```

### 新增功能（2026-02-07）

| 功能 | 说明 | Mod 日志来源 |
|------|------|---------------|
| **战斗动态** | limbo 牌、怪物行为模式、预计伤害 | `combat_state.limbo`, `monsters[].last_move_id` |
| **牌组变化** | 牌组构成、已消耗牌、升级牌统计 | `game_state.deck`, `combat_state.exhaust_pile` |

### 静默专用优化

| 删除项 | 原因 |
|--------|------|
| 角色编码 (3维) | 固定静默猎手 |
| 难度编码 (1维) | 固定 A20 |
| Orbs 编码 (15维) | 静默不用能量球 |
| 其他职业卡牌 | 只保留静默 75 张 |

### 卡牌池

```
总卡牌数：144 张
├── UNKNOWN     1 张（占位符）
├── 诅咒        14 张
├── 状态        5 张
├── 静默职业    75 张
└── 无色        47 种（事件/商店/遗物获得）
```

---

## 动作空间

### 179 维离散动作

```
┌───────────────────────────────────────────────────────────────┐
│ 动作类型      | ID 范围      | 数量  | 说明                           │
├──────────────────────────────────────────────────────────────┤
│ 出牌动作      | 0-69         | 70   │ 10张牌 × 7个目标              │
│ 使用药水      | 70-74        | 5    │ 不指定目标                     │
│ 使用药水(目标) | 75-104       | 30   │ 对敌人1-6                     │
│ 丢弃药水      | 105-109      | 5    │                                 │
│ 选择选项      | 110-169      | 60   │ 事件/商店/卡牌奖励            │
│ 结束回合      | 170          | 1    │ ACTION_END_ID                  │
│ 确认/前进    | 171          | 1    │                                 │
│ 确认按钮      | 172          | 1    │                                 │
│ 其他控制      | 173-178      | 6    │ cancel/key/click/return/skip/leave│
└──────────────────────────────────────────────────────────────┘
```

### 动作掩码 (Action Masking)

每一步返回当前可用的动作掩码，AI 只需从可用动作中选择：

```python
# 示例：战斗中有 6 张可打出的牌
action_mask = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 100: 1}

# 示例：事件选择
action_mask = {110: 1, 111: 1, 112: 1}  # 3个选项可用
```

---

## 数据流程

### 完整数据处理流程

```
1. Mod Log 原始数据
   data/A20_Silent/Raw_Data_json_FORSL/*.json
   ↓
2. 预处理 (scripts/preprocess_training_data.py)
   ├── encode(): 生成 S 向量 (2945维)
   ├── create_action_mask(): 生成动作掩码
   └── infer_actual_action(): 推断实际执行的动作
   ↓
3. 训练数据文件
   ├── training_data_*.json    # 完整数据 (含元数据)
   ├── s_vectors.npy           # 状态矩阵 (N × 2945)
   └── actions.npy             # 动作标签 (N,)
   ↓
4. 训练
   ├── 监督学习：从 (s, a) 学习策略
   └── 强化学习：用 (s, action_mask) 优化策略
```

### 预处理脚本功能

**脚本**：`scripts/preprocess_training_data.py`

**功能**：
- 从 Mod Log 生成 (s, a) 训练对
- 支持单文件和批量处理
- 自动推断实际执行的动作
- 生成 JSON 和 NumPy 两种格式

**使用方法**：

```bash
# 单文件处理
python scripts/preprocess_training_data.py \
    -i data/A20_Silent/Raw_Data_json_FORSL/file.json \
    -o data/training_data.json

# 批量处理
python scripts/preprocess_training_data.py -b \
    -i data/A20_Silent/Raw_Data_json_FORSL \
    -o data/processed/
```

---

## 项目结构

```
AI_THE_SPIRE/
├── src/                           # 源代码
│   ├── core/                       # 核心模块
│   │   ├── action.py              # 动作空间定义 (179维)
│   │   ├── config.py              # 配置管理
│   │   └── game_state.py          # 游戏状态类
│   │
│   ├── training/                   # 训练模块
│   │   ├── encoder.py             # ⭐ 状态编码器 (2945维)
│   │   ├── encoder_dims.py        # ⭐ 维度常量定义
│   │   ├── encoder_utils.py       # ID 映射工具
│   │   └── power_parser.py         # Power 解析
│   │
│   ├── agents/                    # 智能体
│   │   ├── base.py                # Agent 基类
│   │   ├── supervised.py          # 监督学习 Agent
│   │   ├── rl_agent.py            # 强化学习 Agent
│   │   └── rule_based.py          # 基于规则的 Agent
│   │
│   └── env/                       # 环境模块
│       └── sts_env.py             # Gymnasium 环境接口
│
├── scripts/                       # 训练脚本
│   ├── train.py                   # ⭐ 统一训练入口
│   ├── train_sl.py                # 监督学习训练
│   ├── train_rl.py                # 强化学习训练
│   ├── evaluate.py                # 模型评估
│   └── preprocess_training_data.py # ⭐ 数据预处理
│
├── configs/                       # 配置文件
│   ├── encoder_ids.yaml          # ⭐ 卡牌/遗物/药水 ID 映射表
│   └── default.yaml              # 默认配置
│
├── data/                          # 数据目录
│   ├── A20_Silent/                # 静默猎手数据
│   │   └── Raw_Data_json_FORSL/  # Mod Log 原始数据
│   ├── training_data_*.json       # 预处理后的训练数据
│   ├── s_vectors.npy              # 状态矩阵 (PyTorch 训练用)
│   └── actions.npy                # 动作标签 (PyTorch 训练用)
│
├── docs/                          # 文档
│   └── MOD_LOG_PARAMETERS.md      # Mod 协议文档
│
├── rules_for_all.md               # 全局规则
└── README.md                      # 本文件
```

---

## 快速开始

### 环境要求

- Python 3.14+
- 《杀戮尖塔》游戏本体
- [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod)（可选，用于真实游戏）

### 安装依赖

```bash
pip install numpy==1.26.4
pip install scipy scikit-learn pyyaml
pip install torch torchvision torchaudio
pip install gymnasium stable-baselines3
```

### 数据预处理

```bash
# 将 Mod Log 转换为训练数据
python scripts/preprocess_training_data.py \
    -i data/A20_Silent/Raw_Data_json_FORSL/Silent_A20_HUMAN_20260205_233501.json \
    -o data/training_data.json
```

输出文件：
- `training_data.json` - 完整训练数据（JSON 格式）
- `s_vectors.npy` - 状态矩阵
- `actions.npy` - 动作标签

### 训练模型

```bash
# 完整训练流程
python scripts/train.py pipeline \
    --data-dir data/A20_Silent/Raw_Data_json_FORSL \
    --collect-games 50 \
    --sl-epochs 100 \
    --rl-timesteps 100000

# 单独步骤
python scripts/train.py sl --data-dir data/    # 监督学习
python scripts/train.py rl --sl-model models/sl.pkl  # 强化学习
python scripts/train.py eval --agent-type rl       # 评估
```

---

## 开发文档

### 编码器使用

```python
from src.training.encoder import encode, get_output_dim

# 从 Mod 响应生成 S 向量
mod_response = {
    "game_state": {...},
    "available_commands": [...],
    ...
}

s_vector = encode(mod_response)
print(f"S 向量维度: {len(s_vector)}")  # 2945
print(f"非零元素: {(s_vector != 0).sum()}")
```

### ID 映射使用

```python
from src.training.encoder_utils import card_id_to_index

# 卡牌 ID → 索引
index = card_id_to_index("Backflip")  # 静默卡牌
print(f"Backflip 索引: {index}")  # 0-143
```

### 自定义训练

参考：
- `scripts/train_sl.py` - 监督学习实现
- `scripts/train_rl.py` - 强化学习实现
- `src/agents/supervised.py` - Agent 实现

---

## 更新日志

### 2026-02-07：编码器 V2 + 数据预处理

**状态编码器更新**
- ✅ 总维度：2945 维（静默专用）
- ✅ 新增：战斗动态信息（111维）
- ✅ 新增：牌组变化统计（80维）
- ✅ 删除：角色/难度/Orbs 编码（静默不用）
- ✅ 卡牌池：144 张（静默75 + 诅咒14 + 状态5 + 无色47）

**新增功能**
- ✅ 数据预处理脚本 `scripts/preprocess_training_data.py`
- ✅ 动作掩码生成（支持 choose/play/end 等所有命令）
- ✅ 实际动作推断（从相邻记录推断）
- ✅ 批量处理支持

**数据处理**
- ✅ 从 Mod Log 生成 (s, a) 训练对
- ✅ 支持 JSON 和 NumPy 两种输出格式
- ✅ 完整的元数据记录

### 2026-02-06：静默专用编码器完善

- 完善卡牌池：144 张卡牌
- 删除冗余编码：角色/难度/Orbs
- 调整参数上限：MAX_HP=200, MAX_BLOCK=999, MAX_ENERGY=20

### 2026-02-05：初始版本

- 动作空间定义（179 维）
- S 向量编码器实现
- 基础训练框架

---

## 参考资源

- [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod) - 游戏通信协议
- [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3) - RL 框架
- [Gymnasium](https://github.com/Farama-Foundation/Gymnasium) - RL 环境标准

---

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

---

微信号：`soplaoming`  
| 微信二维码 | 收款码 |
|---|---|
| ![微信二维码](./wechat-qrcode.jpg) | ![收款码](./wechat-pay-qrcode.jpg) |
