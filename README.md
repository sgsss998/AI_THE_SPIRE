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

## 当前进度（2026-11-20）

静默猎手 A20 使用 **3,118 个公开状态值（S3118）和 193 个动作编号（A193）**。第 61 至 64 个选牌位置已在原版逐个操作。高速模拟器保留 1,761 项主体观测、146 个内部动作，适配层把模型选择翻译成游戏操作。

本地用同一个模型入口重放了一局原版游戏的 82 次操作，双方都在第 4 层阵亡。按下令时的实际记录，78 次在可独立核验的字段上一致，三次采集程序用到了旧快照，一次模拟器提前清除了死亡动画中怪物的虚弱。

同一批 320 个种子上，走到游戏判定阵亡的局数从 89 升到 117，接口中断从 231 降至 203。新版共执行 23,085 次决策。另测 128 个不同种子，最后一批 64 个全新留出种子有 23 局阵亡、41 局中断。原版已逐一核对涅奥六种付费选稀有牌组合，也核对了两张同名牌中只有指定的那一张升级。

当前在验收环境。正式训练与 A20 平均楼层评估须等完整对局验证通过。[本轮复核与历史基线](docs/2026-11-20_SILENT_A20_ENV_VALIDATION.md) · [S 向量说明](docs/S_VECTOR_DETAILED_PLAN.md) · [前期实机核验](docs/2026-11-19_COMPACT_SA_VALIDATION.md)

### 2026-11-16 的实机基线

此前 15 局实机实验使用过 S5 和 S6。最后 5 局冻结验收有 841 个动作、881 个精确配对的观察帧。S6 的 143,337 维属于当时的逐字段审计表示，动作协议有 179 个编号槽。这批记录和更早的 2,945 维训练设计保留原有版本，不能直接作为 S3118/A193 的训练样本。[历史分层验收](docs/2026-11-15_SA_VALIDATION_RESULTS.md) · [首次战斗审计](docs/2026-11-15_LIVE_AUDIT.md)

---

## 目录

- [当前进度](#当前进度2026-11-20)
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
- 📊 **状态编码器**：本地紧凑候选 S3118，历史 2945 维与 S6 审计数据按版本保留
- 🎯 **动作空间**：本地紧凑模型使用 A193，旧训练动作标签仍需显式转换
- 🔄 **训练框架**：已有采集、预处理、训练与评估模块，端到端训练尚未验收
- 🛡️ **Action Masking**：本地已修确认、跳过及药水目标口径；实机覆盖范围见验收报告

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 游戏通信 | [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod) | JSON 协议 |
| 状态编码 | 自定义编码器 | 本地候选 S3118，仓库历史训练路线 2945 维 |
| RL 框架 | Gymnasium + Stable-Baselines3 | PPO/A2C 算法 |
| 神经网络 | PyTorch | 策略网络 + 价值网络 |
| 配置管理 | YAML | 灵活的配置系统 |

---

## 系统架构

### 训练流程

以下为目标流程；各模块存在不代表整条链已运行正确，当前阻断见上方进度与实机审计。

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

> 下表是历史 2945 维布局。当前本地紧凑模型的字段与验收范围见[本轮报告](docs/2026-11-19_COMPACT_SA_VALIDATION.md)。

### 总览

**总维度**：2945 维
**设计原则**：静默猎手专用（A20 固定难度）
**数据来源**：Mod JSON 字段与派生统计。2945 是输出长度，不代表全部决策信息已保留；具体缺项见实机审计。

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
│ 怪物         │ [1427-2044] │ 618  │ 6怪物×103维                        │
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
该历史编码表：144 个条目（含 UNKNOWN 占位符）
类别统计及完整覆盖情况仍需复核；映射项数不等于已验收的有效卡牌数。
```

---

## 动作空间

> 下表描述历史 179 槽方案。本地紧凑模型采用 A193，新增的 189 至 192 分别选择第 61 至 64 行。各版命令、目标槽和掩码须按对应版本解释。

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

设计上每一步应返回合法动作掩码。当前实现仍有缺漏，下面仅说明编号用法，不代表已通过真机合法性验收：

```python
# 示例：战斗中有 6 张可打出的牌
action_mask = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 170: 1}

# 示例：事件选择
action_mask = {110: 1, 111: 1, 112: 1}  # 3个选项可用
```

---

## 数据流程

### 现有数据处理支路（尚未贯通验收）

```
1. Mod Log 原始数据
   data/A20_Silent/Raw_Data_json_FORSL/*.json
   ↓
2. 预处理 (scripts/preprocess_training_data.py)
   ├── encode(): 生成 S 向量 (2945维)
   ├── create_action_mask(): 生成动作掩码
   └── infer_actual_action(): 推断实际执行的动作
   ↓
3. 既有训练相关文件（并非此脚本一次生成）
   ├── training_data_*.json    # 完整数据 (含元数据)
   ├── s_vectors.npy           # 状态矩阵 (N × 2945)
   └── actions.npy             # 动作标签 (N,)
   ↓
4. 训练
   ├── 监督学习：从 (s, a) 学习策略
   └── 强化学习：用 (s, action_mask) 优化策略
```

旧预处理生成的 78 条标签含 27 个编号100，与当前“结束回合”170不兼容。当前本地 SL loader 读取带动作字符串的原始数组记录，不会自动消费这些预处理 JSON 或 NumPy 文件。详见审计中的数据范围与计数。

### 预处理脚本功能

**脚本**：`scripts/preprocess_training_data.py`

**功能**：
- 从 Mod Log 生成 (s, a) 训练对
- 支持单文件和批量处理
- 自动推断实际执行的动作
- 该预处理脚本写出 JSON；现有 NumPy 文件是另外的历史产物，不能当成这条命令的输出

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

> 此结构说明现有仓库；本地隔离验证模块尚未随本次文档发布合入。

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
│   ├── s_vectors.npy              # 历史状态矩阵产物（需验收）
│   └── actions.npy                # 历史动作标签（编号有冲突）
│
├── docs/                          # 文档
│   └── MOD_LOG_PARAMETERS.md      # Mod 协议文档
│
├── rules_for_all.md               # 全局规则
└── README.md                      # 本文件
```

---

## 快速开始

> 这些命令对应仓库旧训练代码。S3118/A193 的训练入口、标签和奖励仍需单独验收。

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

该命令输出 `training_data.json`。仓库已有的 `s_vectors.npy` 和 `actions.npy` 不由这条命令自动生成，其生成流程与标签兼容性需另外核对。

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

- [2026-11-19 紧凑 S3118/A193 实机与模拟验收](docs/2026-11-19_COMPACT_SA_VALIDATION.md)
- [2026-11-15 S/A分层验收、有限范围与训练阻断](docs/2026-11-15_SA_VALIDATION_RESULTS.md)
- [2026-11-15 实机审计、版本差异与验收顺序](docs/2026-11-15_LIVE_AUDIT.md)
- [S 向量历史设计方案](docs/S_VECTOR_DETAILED_PLAN.md)（设计意图不等于当前实现已通过验收）

### 旧 2945 维编码器使用

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

### 2026-11-19 紧凑环境验收

- 记录 16 个真机与模拟同局面、四个高位选牌动作，以及 64 个固定种子的进展与未验停点。

### 2026-11-16 文档续报

- 记录累计15局与新冻结5局的分层结果；保留原8局历史证据。
- 更新S6公开费用、公开牌堆记忆、精确采样绑定及实际加载变体边界。
- 明确仍未覆盖的机制、动作效果和训练迁移，不将回放一致写成全游戏准确。


### 2026-11-15：本地S/A分层验证进展（文档草稿）

- 记录S5/A179/真实step隔离验证链及五局冻结验收范围。
- 区分传输、实际调用、最终效果和状态充分性，保留对时歧义与未观测前提。
- 明确114906维属于审计表示，旧31/2945/250训练体系尚未迁移。
- 本次更新仅含文档；源码、Mod及原始对局数据不随文档发布。

### 2026-11-15：实机验证与现状校正（文档）

- 记录本地一次战斗的动作、换回合与奖励采集验证。
- 区分 GitHub 31 维 SL 入口与本地已改为2945维的开发副本。
- 记录状态丢失、动作协议/掩码、奖励和训练环境阻断；移除完整覆盖/流程已贯通的表述。
- 重新界定旧数据数量与标签质量，明确后续验收顺序。
- 以下旧日志保留为历史开发记录，其中的勾选不代表本次重新验收通过。

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


