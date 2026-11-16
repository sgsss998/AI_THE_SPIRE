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

## 当前进度（2026-11-16 核验）

**真实游戏采集、控制与可复现证据链已有本地实验实现；全游戏状态充分性及训练准入仍未通过。**

累计15局实机实验已结束：首批8局、新增2局探索、最后5局新种子冻结验收。不同版本累计2993个测试驾驶员动作；新冻结5局841步、881帧，精确配对881，歧义0、未匹配0。已比较字段差异0，保存状态重放差异0。 详见[本轮S/A验收结果](docs/2026-11-15_SA_VALIDATION_RESULTS.md)。

当前本地冻结表示为`silent-observable-v6`（143337维），动作契约为`communicationmod-179-v2`（179编号槽）。S6新增公开手牌费用与有来源约束的牌堆位置记忆；采样采用独立编号精确绑定。最后5局固定同一游戏实例、源码、Mod、采集会话和实际加载类变体。新冻结5局没有实际触发Setup/Forethought放牌场景；空位置记忆来源通过不能算该场景实机验收通过。

| 范围 | 已确认状态 |
| --- | --- |
| 本地验证副本 | 真实step、状态/动作快照绑定、有限延迟结果确认、独立原生对照与保存记录重放已接通 |
| 动作见证 | 新5局478次入口匹配、363次未覆盖；不能由调用记录推导全部最终效果 |
| 训练工程 | 旧SL31维、RL2945维及预处理250动作路线尚未统一迁移；S6不能直接送入旧网络 |
| GitHub | 本次仅更新三份文档；验证源码、Mod、存档及原始对局数据不随文档上传 |

143337维是便于逐字段审计的固定槽表示，尚非最终高效训练输入。179编号含174/175两个保留槽；最多支持10张手牌、6个敌人槽、5个药水槽及60个选择，超容量明确拒绝。当前`training_eligible=false`，禁止通过截断、补零或混用标签迁就旧接口。

项目目标仍为静默猎手A20、NoSL条件下自主完成整局。此处使用规则测试驾驶员，不能把其实验终局当成神经网络胜率。下一步应优先补实际机制场景及效果证据，再迁移训练输入和数据；继续堆相似局数不能替代未出现机制的验证。

本次文档基于先前已发布的`66141af8f0ea8535606daeada8e9bd2dc8494878`。原8局的S5结果和对时歧义仍作为历史证据保留，不按S6结果追改。首次单场战斗发现见[上一轮实机审计](docs/2026-11-15_LIVE_AUDIT.md)。

---

## 目录

- [当前进度](#当前进度2026-11-16-核验)
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
- 📊 **状态编码器**：仓库保留旧2945维路线；本地S6审计版为143337维，验收与训练准入分开
- 🎯 **动作空间**：本地验证链采用179动作的版本化协议；旧250动作标签尚未迁移
- 🔄 **训练框架**：已有采集、预处理、训练与评估模块，端到端训练尚未验收
- 🛡️ **Action Masking**：本地已修确认、跳过及药水目标口径；实机覆盖范围见验收报告

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 游戏通信 | [CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod) | JSON 协议 |
| 状态编码 | 自定义编码器 | 仓库旧2945维；本地S6审计版143337维 |
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

> 下列2945维布局保留为历史路线，不能当作本地S6的字段索引，也不能接收S6验收记录。现行语义范围见[验收结果](docs/2026-11-15_SA_VALIDATION_RESULTS.md)。

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
当前本地映射表：144 个条目（含 UNKNOWN 占位符）
类别统计及完整覆盖情况仍需复核；映射项数不等于已验收的有效卡牌数。
```

---

## 动作空间

> 以下为仓库历史说明；本地验证链的协议版本为 `communicationmod-179-v2`。同为179维不保证各版命令、目标槽位与掩码兼容，使用时必须核对版本。

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

> 以下是保留的历史启动命令，不适用于S6验收记录。旧网络布局和预处理动作定义尚未迁移；在数据契约与训练接口单独验收前，不应使用本批记录启动训练。

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

- [2026-11-15 S/A分层验收、有限范围与训练阻断](docs/2026-11-15_SA_VALIDATION_RESULTS.md)
- [2026-11-15 实机审计、版本差异与验收顺序](docs/2026-11-15_LIVE_AUDIT.md)
- [S 向量历史设计方案](docs/S_VECTOR_DETAILED_PLAN.md)（设计意图不等于当前实现已通过验收）

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


