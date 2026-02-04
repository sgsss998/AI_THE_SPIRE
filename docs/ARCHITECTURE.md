# AI_THE_SPIRE 项目架构

本文档详细描述项目的整体架构设计。

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI_THE_SPIRE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐    │
│  │   scripts/    │    │    src/       │    │   tests/      │    │
│  │  - train.py   │───▶│  - agents/    │───▶│  - unit tests │    │
│  │  - collect.py │    │  - env/       │    │               │    │
│  │  - eval.py    │    │  - training/  │    │               │    │
│  └───────────────┘    └───────────────┘    └───────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    CommunicationMod                      │   │
│  │                    (stdin/stdout JSON)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Slay the Spire                        │   │
│  │                    (Java Game)                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 模块分层

### 1. 协议层 (Protocol Layer)

**职责**：与 CommunicationMod 进行通信

```
src/protocol/
├── reader.py     # ModReader - stdin JSON 读取
├── writer.py     # ModWriter - stdout 命令发送
└── parser.py     # ModProtocol - 协议解析器
```

**关键类**：
- `ModReader`: 从 stdin 读取游戏状态
- `ModWriter`: 向 stdout 发送命令
- `ModProtocol`: 组合读写，提供高级接口

**数据流**：
```
Game State (JSON) ──▶ ModReader ──▶ GameState (dataclass)
                                            │
Action (dataclass) ◀── ModWriter ◀── Command (String)
```

### 2. 核心层 (Core Layer)

**职责**：定义数据结构和配置

```
src/core/
├── game_state.py   # GameState, Card, Monster, Player, CombatState
├── action.py       # Action 数据类
└── config.py       # 配置管理 (YAML)
```

**关键数据类**：
- `GameState`: 完整游戏状态
- `Card`: 卡牌信息（frozen dataclass）
- `Monster`: 怪物信息
- `CombatState`: 战斗状态
- `Action`: 动作封装

**设计原则**：
- 使用 `@dataclass(frozen=True)` 确保不可变性
- 提供 `from_dict()` 方法兼容旧版 JSON 格式
- 完整的类型注解

### 3. 环境层 (Environment Layer)

**职责**：提供标准 RL 环境接口

```
src/env/
└── sts_env.py
    ├── StsEnvironment      # gym.Env 实现
    └── StsEnvWrapper       # 连接实际 Mod
```

**关键特性**：
- 标准 Gymnasium 接口 (`reset`, `step`, `render`, `close`)
- 30 维观察空间
- Discrete(11) 动作空间
- **Action Masking**: 只允许合法动作
- 奖励函数：伤害+ / 受伤- / 击杀++ / 死亡--

### 4. Agent 层 (Agent Layer)

**职责**：AI 决策

```
src/agents/
├── base.py         # Agent 基类和抽象类
├── rule_based.py   # 规则 Agent
├── supervised.py   # 监督学习 Agent
└── rl_agent.py     # 强化学习 Agent
```

**统一接口**：
```python
class Agent(ABC):
    @abstractmethod
    def select_action(state: GameState) -> Action:
        pass

    def get_action_probabilities(state) -> np.ndarray:
        pass

    def on_episode_start(episode_id: int):
        pass

    def on_episode_end(reward: float, info: dict):
        pass

    def set_training_mode(training: bool):
        pass

    def save(path: str):
        pass

    def load(path: str):
        pass
```

**Agent 类型**：

| 类型 | 类名 | 用途 |
|------|------|------|
| 规则 | `RuleBasedAgentImpl` | 数据收集、基线对比 |
| 监督学习 | `SupervisedAgentImpl` | 从数据学习策略 |
| 强化学习 | `RLAgentImpl` | 大规模训练优化 |

### 5. 训练层 (Training Layer)

**职责**：训练支持和实验管理

```
src/training/
├── encoder.py     # StateEncoder - 状态编码
└── experiment.py  # 实验跟踪系统
```

**StateEncoder**：
- 将 GameState 编码为 30 维向量
- 手牌 one-hot 编码 (13 维)
- HP 归一化
- 怪物意图编码 (6 维)

**ExperimentTracker**：
- 实验配置和结果管理
- 自动哈希生成
- 实验比较和最佳实验查找

### 6. 脚本层 (Scripts Layer)

**职责**：用户接口

```
scripts/
├── train.py         # ⭐ 统一入口
├── collect_data.py  # 数据收集
├── train_sl.py      # SL 训练
├── train_rl.py      # RL 训练
├── evaluate.py      # 模型评估
└── interactive.py   # 交互测试
```

---

## 数据流

### 训练流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       训练流程                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. 数据收集                                                      │
│     ┌─────────────┐                                             │
│     │ RuleBased   │                                             │
│     │ Agent       │                                             │
│     └──────┬──────┘                                             │
│            │                                                    │
│            ▼                                                    │
│     ┌─────────────┐    ┌──────────────┐                        │
│     │ StsEnv      │───▶│ JSONL Files  │                        │
│     └─────────────┘    └──────────────┘                        │
│                                                                 │
│  2. 监督学习                                                      │
│     ┌──────────────┐    ┌──────────────┐                       │
│     │ JSONL Files  │───▶│ SL Agent     │                       │
│     └──────────────┘    │ (sklearn/    │                       │
│                          │  PyTorch)    │                       │
│                          └──────┬───────┘                       │
│                                 │                               │
│                                 ▼                               │
│                          ┌──────────────┐                       │
│                          │ SL Model     │                       │
│                          │ (.pkl)       │                       │
│                          └──────┬───────┘                       │
│                                                                 │
│  3. 强化学习 (Warm Start)                                         │
│     ┌──────────────┐    ┌──────────────┐                       │
│     │ SL Model     │───▶│ RL Agent     │                       │
│     └──────────────┘    │ (PPO/A2C/    │                       │
│                          │  DQN)        │                       │
│                          └──────┬───────┘                       │
│                                 │                               │
│                                 ▼                               │
│                          ┌──────────────┐                       │
│                          │ RL Model     │                       │
│                          │ (.zip)       │                       │
│                          └──────────────┘                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 推理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       推理流程                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Game (JSON)                                                      │
│      │                                                            │
│      ▼                                                            │
│  ┌─────────────┐                                                  │
│  │ ModReader   │                                                  │
│  └──────┬──────┘                                                  │
│         │                                                         │
│         ▼                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐        │
│  │ GameState   │───▶│ Agent        │───▶│ Action       │        │
│  │ (dataclass) │    │ (rule/SL/RL) │    │ (dataclass)  │        │
│  └─────────────┘    └──────────────┘    └──────┬───────┘        │
│                                                  │               │
│                                                  ▼               │
│                                          ┌──────────────┐       │
│                                          │ ModWriter    │       │
│                                          └──────┬───────┘       │
│                                                 │               │
│                                                 ▼               │
│                                          Command (String)       │
│                                                 │               │
│                                                 ▼               │
│                                          Game (stdin)           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 关键设计决策

### 1. 数据类 vs 字典

**选择**：使用 `@dataclass`

**原因**：
- 类型安全
- IDE 自动完成
- 不可变性 (`frozen=True`)
- 更好的文档

### 2. 工厂模式

**选择**：`create_agent(agent_type, name, **kwargs)`

**原因**：
- 统一创建接口
- 易于添加新 Agent 类型
- 配置驱动

### 3. Action Masking

**选择**：在环境层实现

**原因**：
- 防止无效动作
- 参考 STS-AI-Master 设计
- 加速训练收敛

### 4. 状态编码

**选择**：30 维固定向量

**组成**：
- 手牌 one-hot: 13 维
- 玩家状态: 4 维 (HP/能量/牌库/弃牌)
- 怪物状态: 7 维 (HP/意图/力量)

**原因**：
- 简单高效
- 适合神经网络
- 易于调试

### 5. Warm Start

**选择**：SL → RL 权重迁移

**原因**：
- 加速 RL 收敛
- 避免随机初始化
- 利用先验知识

---

## 扩展点

### 添加新 Agent

```python
# 1. 在 src/agents/base.py 添加抽象类
class NewAgentType(Agent):
    pass

# 2. 在 src/agents/new_agent.py 实现
class NewAgentImpl(NewAgentType):
    def select_action(self, state):
        pass

# 3. 在 src/agents/__init__.py 导出
from .new_agent import NewAgentImpl

# 4. 在工厂函数注册
def create_agent(agent_type, name, **kwargs):
    if agent_type == "new":
        return NewAgentImpl(name, **kwargs)
```

### 添加新 RL 算法

```python
# 在 src/agents/rl_agent.py 的 _create_model 中添加
elif self.algorithm == "new_algo":
    from stable_baselines3 import NewAlgo
    model = NewAlgo(...)
```

### 修改状态编码

```python
# 在 src/training/encoder.py 中修改 StateEncoder
class StateEncoder:
    def encode_state(self, state: GameState) -> np.ndarray:
        # 自定义编码逻辑
        pass
```

---

## 性能考虑

### 1. 状态编码缓存

对于频繁访问的状态，可以考虑缓存编码结果。

### 2. 批量预测

SL Agent 支持批量预测以提高推理速度。

### 3. 多环境并行

RL Agent 支持多环境并行训练 (`n_envs > 1`)。

---

## 测试策略

| 模块 | 测试文件 | 测试数量 |
|------|----------|----------|
| 核心数据 | `test_core/` | 15 |
| 协议层 | `test_protocol/` | 14 |
| 环境 | `test_env/` | 10 |
| Agent | `test_agents/` | 53 |
| 训练 | `test_training/` | 12 |
| **总计** | | **104** |

---

## 依赖关系

```
                    ┌──────────────┐
                    │   scripts/   │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │ agents/  │     │  env/    │     │training/ │
    └────┬─────┘     └────┬─────┘     └────┬─────┘
         │                │                │
         └────────┬───────┴────────────────┘
                  ▼
           ┌──────────────┐
           │    core/     │
           └──────┬───────┘
                  │
         ┌────────┴────────┐
         ▼                 ▼
    ┌──────────┐     ┌──────────┐
    │protocol/ │     │ config/  │
    └──────────┘     └──────────┘
```
