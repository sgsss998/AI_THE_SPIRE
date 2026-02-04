# AI_THE_SPIRE — 杀戮尖塔 AI 开发项目

本地开发针对 Slay the Spire 的小型 AI 模型（Mac Mini M4 16GB），从「能自动玩一局」到「可训练、可扩展」，最终可冲击 A20 连胜。**终极目标：NoSL 盗贼（静默猎手）28 连胜，超越人类 NoSL 盗贼 27 连胜纪录。**

---

## 项目概述

AI_THE_SPIRE 是一个基于 Python 的杀戮尖塔 AI 项目，采用模块化架构设计，支持：

- **规则驱动 AI**：基于预定义规则的决策系统
- **监督学习 (SL)**：从游戏数据中学习策略
- **强化学习 (RL)**：通过环境交互优化策略
- **SL → RL Warm Start**：用 SL 模型初始化 RL 训练

### 技术栈

- **通信**：CommunicationMod (stdin/stdout JSON 协议)
- **环境**：Gymnasium (OpenAI Gym 标准)
- **SL 后端**：sklearn / PyTorch
- **RL 框架**：Stable-Baselines3 (PPO, A2C, DQN)
- **实验管理**：内置实验跟踪系统

---

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 运行规则 Agent

```bash
# 使用规则 Agent 自动玩一局
python scripts/train.py interactive --agent-type rule
```

### 3. 训练你的第一个模型

```bash
# 完整训练流程：收集数据 → 训练 SL → 训练 RL
python scripts/train.py pipeline \
    --collect-games 50 \
    --sl-epochs 100 \
    --rl-timesteps 100000
```

---

## 项目结构

```
AI_THE_SPIRE/
├── src/                    # 新架构源代码（推荐使用）
│   ├── core/               # 核心数据结构
│   │   ├── game_state.py   # GameState, Card, Monster 等
│   │   ├── action.py       # Action 数据类
│   │   └── config.py       # 配置管理
│   ├── protocol/           # Mod 通信协议
│   │   ├── reader.py       # stdin JSON 读取
│   │   ├── writer.py       # stdout 命令发送
│   │   └── parser.py       # 协议解析器
│   ├── env/                # Gymnasium 环境
│   │   └── sts_env.py      # StsEnvironment
│   ├── agents/             # AI Agent
│   │   ├── base.py         # Agent 基类
│   │   ├── rule_based.py   # 规则 Agent
│   │   ├── supervised.py   # 监督学习 Agent
│   │   └── rl_agent.py     # 强化学习 Agent
│   └── training/           # 训练模块
│       ├── encoder.py      # 状态编码器
│       └── experiment.py   # 实验管理
│
├── scripts/                # 训练和测试脚本
│   ├── train.py            # ⭐ 统一训练入口
│   ├── collect_data.py     # 数据收集
│   ├── train_sl.py         # SL 训练
│   ├── train_rl.py         # RL 训练
│   ├── evaluate.py         # 模型评估
│   ├── interactive.py      # 交互测试
│   └── README.md           # 脚本详细文档
│
├── tests/                  # 单元测试（104 个测试）
│   ├── test_core/          # 核心模块测试
│   ├── test_protocol/      # 协议层测试
│   ├── test_env/           # 环境测试
│   ├── test_agents/        # Agent 测试
│   └── test_training/      # 训练模块测试
│
├── configs/                # 配置文件
│   └── default.yaml        # 默认配置
│
├── combat_logs/            # 游戏日志
│   └── sessions/           # 会话数据（用于训练）
│
├── experiments/            # 实验记录
│   └── index.json          # 实验索引
│
├── models/                 # 训练好的模型
│
├── docs/                   # 文档
│   ├── rules/              # 游戏规则文档
│   └── phase4-plan.md      # SL+RL 计划
│
├── DEVELOPMENT_LOG.md      # ⚠️ 开发日志（不可删除）
└── README.md               # 本文件
```

---

## 统一训练入口

所有训练操作通过 `scripts/train.py` 进行：

```bash
# 查看帮助
python scripts/train.py --help

# 数据收集
python scripts/train.py collect --games 100

# 训练 SL 模型
python scripts/train.py sl --data-dir combat_logs/sessions

# 训练 RL 模型
python scripts/train.py rl --timesteps 1M

# 完整流程（推荐）
python scripts/train.py pipeline \
    --collect-games 100 \
    --sl-epochs 200 \
    --rl-timesteps 1000000

# 评估模型
python scripts/train.py eval \
    --agent-type rl \
    --model models/rl.zip \
    --episodes 100

# 交互测试
python scripts/train.py interactive --agent-type rl --model models/rl.zip
```

---

## Agent 使用示例

### 规则 Agent

```python
from src.agents import create_agent

# 创建规则 Agent
agent = create_agent("rule", "MyRule")

# 选择动作
action = agent.select_action(state)
```

### 监督学习 Agent

```python
from src.agents import SupervisedAgentImpl, load_data_from_sessions

# 创建 Agent
agent = SupervisedAgentImpl("MySL", config={"model_type": "pytorch"})

# 加载数据
states, actions = load_data_from_sessions("combat_logs/sessions")

# 训练
result = agent.train(states, actions, epochs=200)

# 保存
agent.save("models/my_sl.pkl")

# 使用
agent.set_training_mode(False)
action = agent.select_action(state)
```

### 强化学习 Agent

```python
from src.agents import RLAgentImpl
from src.env import StsEnvWrapper

# 创建环境
env = StsEnvWrapper(character="silent", ascension=0)

# 创建 Agent
agent = RLAgentImpl("MyRL", config={"algorithm": "ppo"})
agent.set_environment(env)

# Warm Start（可选）
# agent.load_sl_model(sl_agent)

# 训练
agent.train(total_timesteps=1000000, n_envs=4)

# 保存
agent.save("models/my_rl.zip")
```

---

## 实验管理

内置实验跟踪系统，方便管理多次训练：

```python
from src.training import create_experiment, get_tracker

# 创建实验
exp_id = create_experiment(
    name="ppo_baseline",
    agent_type="rl",
    algorithm="ppo",
    tags=["baseline", "a20"]
)

# 训练完成后更新
tracker = get_tracker()
tracker.complete_experiment(
    exp_id,
    model_path="models/ppo.zip",
    notes="A20 胜率 65%"
)

# 获取最佳实验
best = tracker.get_best_experiment(metric="eval_win_rate")
print(f"最佳实验: {best['id']}, 胜率: {best['value']}")

# 比较实验
comparison = tracker.compare_experiments([exp_id1, exp_id2])
```

---

## 配置文件

编辑 `configs/default.yaml` 自定义配置：

```yaml
training:
  data_dir: "combat_logs/sessions"
  models_dir: "models"
  train_val_split: 0.2
  epochs: 100
  batch_size: 32

game:
  character: "silent"  # ironclad, silent, defect, watcher
  ascension: 0

model:
  hidden_layers: [128, 128]
  learning_rate: 0.001
```

---

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定模块测试
python -m pytest tests/test_agents/ -v
python -m pytest tests/test_training/ -v
```

当前测试覆盖：**104 个测试通过**

---

## 依赖问题说明

### sklearn 与 numpy 2.0+ 兼容性

如果遇到 `AttributeError: _ARRAY_API not found` 错误：

**方案 1**：降级 numpy/scipy
```bash
pip install "numpy<2.0" "scipy<2.0"
```

**方案 2**（推荐）：使用 PyTorch 后端
```bash
python scripts/train.py sl --data-dir data/ --model-type pytorch
```

---

## 开发日志

所有项目改动记录在 [DEVELOPMENT_LOG.md](./DEVELOPMENT_LOG.md) 中，**不可删除**。

---

## 文档索引

- [DEVELOPMENT_LOG.md](./DEVELOPMENT_LOG.md) - 开发日志
- [scripts/README.md](./scripts/README.md) - 脚本详细文档
- [docs/phase4-plan.md](./docs/phase4-plan.md) - SL+RL 计划
- [docs/rules/](./docs/rules/) - 游戏规则文档

---

## 许可证

本项目仅供学习和研究使用。
