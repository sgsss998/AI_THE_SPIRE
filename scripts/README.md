# AI_THE_SPIRE 训练脚本

本文档介绍新的统一训练脚本。

## 新版训练脚本（推荐）

### 1. train_sl.py - 监督学习训练

从标记数据训练 SL 模型。

```bash
# 基本用法
python scripts/train_sl.py --data-dir combat_logs/sessions

# 使用 PyTorch 后端
python scripts/train_sl.py --data-dir combat_logs/sessions --model-type pytorch

# 自定义参数
python scripts/train_sl.py \
    --data-dir combat_logs/sessions \
    --model-type pytorch \
    --hidden-layers 128 64 \
    --epochs 200 \
    --batch-size 64 \
    --learning-rate 0.0001 \
    --output models/my_sl_model.pkl
```

**参数说明：**
- `--data-dir`: 训练数据目录（JSONL 格式）
- `--model-type`: sklearn 或 pytorch（默认: sklearn）
- `--hidden-layers`: 隐藏层大小（默认: 64 32）
- `--epochs`: 训练轮数（默认: 100）
- `--batch-size`: 批次大小（默认: 32）
- `--learning-rate`: 学习率（默认: 0.001）
- `--val-split`: 验证集比例（默认: 0.2）
- `--output`: 模型输出路径

### 2. train_rl.py - 强化学习训练

使用 Gymnasium 环境训练 RL Agent。

```bash
# 基本用法
python scripts/train_rl.py --timesteps 100000

# Warm Start 从 SL 模型
python scripts/train_rl.py \
    --timesteps 500000 \
    --sl-model models/sl_model.pkl \
    --n-envs 4

# 自定义参数
python scripts/train_rl.py \
    --algorithm ppo \
    --timesteps 1000000 \
    --n-envs 8 \
    --learning-rate 0.0001 \
    --hidden-layers 256 256 \
    --output models/my_rl_model.zip
```

**参数说明：**
- `--algorithm`: ppo、a2c 或 dqn（默认: ppo）
- `--sl-model`: SL 模型路径（用于 Warm Start）
- `--timesteps`: 总训练步数（默认: 100000）
- `--n-envs`: 并行环境数量（默认: 1）
- `--learning-rate`: 学习率（默认: 3e-4）
- `--gamma`: 折扣因子（默认: 0.99）
- `--n-steps`: 每次更新步数（默认: 2048）
- `--batch-size`: 批次大小（默认: 64）
- `--hidden-layers`: 策略网络隐藏层（默认: 128 128）
- `--character`: 角色（默认: silent）
- `--ascension`: Ascension 等级（默认: 0）

### 3. evaluate.py - 模型评估

评估训练好的 Agent 性能。

```bash
# 评估规则 Agent
python scripts/evaluate.py \
    --agent-type rule \
    --episodes 10

# 评估 SL Agent
python scripts/evaluate.py \
    --agent-type supervised \
    --model models/sl_model.pkl \
    --episodes 100 \
    --output results/eval_results.json

# 评估 RL Agent
python scripts/evaluate.py \
    --agent-type rl \
    --model models/rl_model.zip \
    --episodes 100 \
    --verbose
```

**参数说明：**
- `--agent-type`: Agent 类型（rule/supervised/rl）
- `--model`: 模型路径（supervised/rl 需要）
- `--episodes`: 评估回合数（默认: 10）
- `--character`: 角色（默认: silent）
- `--ascension`: Ascension 等级（默认: 0）
- `--output`: 结果输出路径（JSON 格式）
- `--verbose`: 详细输出

### 4. interactive.py - 交互式测试

手动运行 Agent 并观察其行为。

```bash
# 规则 Agent（无需模型）
python scripts/interactive.py --agent-type rule

# SL Agent
python scripts/interactive.py \
    --agent-type supervised \
    --model models/sl_model.pkl

# RL Agent
python scripts/interactive.py \
    --agent-type rl \
    --model models/rl_model.zip \
    --render human \
    --delay 1.0
```

**参数说明：**
- `--agent-type`: Agent 类型（默认: rule）
- `--model`: 模型路径（supervised/rl 需要）
- `--render`: 渲染模式（human/ansi/none，默认: human）
- `--delay`: 每步延迟（秒，默认: 0.5）
- `--max-steps`: 最大步数（默认无限制）
- `--character`: 角色（默认: silent）
- `--ascension`: Ascension 等级（默认: 0）

## 完整训练流程示例

### SL → RL Warm Start 流程

```bash
# 1. 用规则 Agent 收集数据
# （运行游戏，数据自动保存到 combat_logs/sessions/）

# 2. 训练 SL 模型
python scripts/train_sl.py \
    --data-dir combat_logs/sessions \
    --model-type pytorch \
    --epochs 200 \
    --output models/sl_base.pkl

# 3. 用 SL 模型 Warm Start RL
python scripts/train_rl.py \
    --sl-model models/sl_base.pkl \
    --timesteps 1000000 \
    --n-envs 8 \
    --output models/rl_final.zip

# 4. 评估最终模型
python scripts/evaluate.py \
    --agent-type rl \
    --model models/rl_final.zip \
    --episodes 100 \
    --output results/final_eval.json

# 5. 交互式测试
python scripts/interactive.py \
    --agent-type rl \
    --model models/rl_final.zip
```

## 工厂函数

所有脚本都支持通过工厂函数创建 Agent：

```python
from src.agents import create_agent

# 规则 Agent
agent = create_agent("rule", "MyRule")

# 监督学习 Agent
agent = create_agent("supervised", "MySL", config={"model_type": "pytorch"})

# 强化学习 Agent
agent = create_agent("rl", "MyRL", config={"algorithm": "ppo"})
```

## 旧版脚本（保留兼容）

以下旧版脚本保留用于兼容性，但建议使用新版脚本：

- `train_model_sklearn.py`: 旧版 sklearn 训练
- `test_model_inference.py`: 旧版推理测试
- `read_state.py` / `read_state_rule_based.py`: 状态读取
- `strategy.py` / `game_rules.py`: 旧版策略
- `encode_state.py`: 状态编码
- `prepare_step_data.py`: 数据准备
- `convert_raw_to_turns.py`: 数据转换
- `load_data.py`: 数据加载
- `replay_test.py`: 日志回放测试
- `track_progress.py`: 进度追踪
- `send_input.py`: 测试输入
