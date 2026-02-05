# AI_THE_SPIRE 训练脚本

本文档介绍新的统一训练脚本。

## 新版训练脚本（推荐）

### 1. train_sl.py - 监督学习训练

从标记数据训练 SL 模型。

```bash
# 基本用法
python scripts/train_sl.py --data-dir data/A20_Slient/Raw_Data_json_FORSL

# 使用 PyTorch 后端
python scripts/train_sl.py --data-dir data/A20_Slient/Raw_Data_json_FORSL --model-type pytorch

# 自定义参数
python scripts/train_sl.py \
    --data-dir data/A20_Slient/Raw_Data_json_FORSL \
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

## 真实游戏数据采集（--real-game）

在**真实游戏环境**中打一局并记录每个 (s, a) 键值对，用于监督学习训练。

### 前置条件

1. **Slay the Spire** + **ModTheSpire** + **CommunicationMod** 已安装
2. 配置 CommunicationMod 的 `config.properties`（Mac: `~/Library/Preferences/ModTheSpire/CommunicationMod/config.properties`），将 `command` 设为：
   ```
   command=python3 -u <项目根目录>/scripts/collect_data.py --real-game --agent-type rule --games 1 --session-name real_session
   runAtGameStart=true
   ```
3. 启动游戏，开始新局（选择角色后 Mod 会自动启动脚本）

### 运行方式

**方式 A：由游戏 Mod 自动启动**（推荐）

- 按上述配置好 `command` 后，在游戏中开始新局即可
- 脚本通过 stdin/stdout 与 Mod 通信，自动发送 `ready` 握手
- 规则 Agent 全程自动决策，记录每个 (s, a) 到 `combat_logs/sessions/<session_name>/session.jsonl`

**方式 B：手动测试**（需游戏已启动且 Mod 已连接）

```bash
# 在项目根目录
PYTHONPATH=. python -u scripts/collect_data.py --real-game --games 1 --session-name real_session
```

### 参数说明

- `--real-game`: 启用真实游戏模式（stdin/stdout 连接 CommunicationMod）
- `--games 1`: 采集 1 局（真实游戏通常一次一局）
- `--session-name`: 会话名称，数据保存到 `combat_logs/sessions/<name>/session.jsonl`

### 排查：Mod 无反应 / 游戏不能自己玩

1. **触发时机**：`runAtGameStart=true` 表示在**开始新局**时启动脚本，不是主菜单。需：启动游戏 → 点击 Play → 选择角色（铁甲/静默/故障）→ 进入第一层后 Mod 才会启动脚本。

2. **config 示例**（使用 venv 的 python 和完整路径）：
   ```
   command=/Volumes/T7/AI_THE_SPIRE/venv/bin/python -u /Volumes/T7/AI_THE_SPIRE/scripts/collect_data.py --real-game --agent-type rule --games 1 --session-name real_game_001
   runAtGameStart=true
   ```

3. **验证脚本能启动**：在项目根目录执行 `./venv/bin/python -u scripts/collect_data.py --real-game --games 1`，若出现「环境未返回有效状态」属正常（无游戏连接时）。若出现 ImportError 则说明依赖或路径有问题。

4. **调试日志**：真实游戏模式下会写入 `collect_data.log`（项目根目录），可查看运行情况。

5. **部分 Mod 版本**：若 `runAtGameStart` 无效，尝试在游戏内 Mod 菜单中手动点击「Start External Process」或类似按钮启动脚本。

6. **collect_data 修复说明**：Mod 发送首帧后会等待响应，若脚本在创建 env（含 StateEncoder）时耗时过长，Mod 可能超时。collect_data 已改为：先建 protocol、agent → 立即读首帧并响应 → 再建 env，从而避免超时。

7. **诊断脚本**：若仍无反应，用 `mod_diagnose.py` 排查：
   - 临时修改 config 的 command 为：`.../venv/bin/python -u .../scripts/mod_diagnose.py`
   - 进游戏开始新局
   - 查看 `mod_diagnose.log`：若有「启动」记录说明 Mod 启动了脚本；若有「收到第 N 行」说明通信正常

---

## 完整训练流程示例

### SL → RL Warm Start 流程

```bash
# 1. 用规则 Agent 收集数据
# （运行游戏，数据自动保存到 data/）

# 2. 训练 SL 模型
python scripts/train_sl.py \
    --data-dir data/A20_Slient/Raw_Data_json_FORSL \
    --model-type pytorch \
    --epochs 200 \
    --output data/models/sl_base.pkl

# 3. 用 SL 模型 Warm Start RL
python scripts/train_rl.py \
    --sl-model data/models/sl_base.pkl \
    --timesteps 1000000 \
    --n-envs 8 \
    --output data/models/rl_final.zip

# 4. 评估最终模型
python scripts/evaluate.py \
    --agent-type rl \
    --model data/models/rl_final.zip \
    --episodes 100 \
    --output results/final_eval.json

# 5. 交互式测试
python scripts/interactive.py \
    --agent-type rl \
    --model data/models/rl_final.zip
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

## 其他脚本

| 脚本 | 说明 |
|------|------|
| `read_state.py` | 状态读取与调试 |
| `extract_mod_schema.py` | 从 Mod 日志提取参数完整清单 |
| `extract_ids_from_raw.py` | 从 Raw JSON 提取卡牌/遗物 ID |
| `test_action_client.py` | 动作客户端测试 |
| `test_action_server.py` | 动作服务端测试 |
