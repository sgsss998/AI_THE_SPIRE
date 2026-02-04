# API 参考文档

本文档提供 AI_THE_SPIRE 的主要 API 参考。

---

## 目录

- [Agent API](#agent-api)
- [环境 API](#环境-api)
- [训练 API](#训练-api)
- [实验 API](#实验-api)
- [协议 API](#协议-api)
- [核心数据类](#核心数据类)

---

## Agent API

### 创建 Agent

```python
from src.agents import create_agent

# 规则 Agent
agent = create_agent("rule", "MyRule")

# 监督学习 Agent
agent = create_agent("supervised", "MySL", config={
    "model_type": "pytorch"  # or "sklearn"
})

# 强化学习 Agent
agent = create_agent("rl", "MyRL", config={
    "algorithm": "ppo"  # or "a2c", "dqn"
})
```

### Agent 基础接口

```python
from src.agents import Agent

class Agent(ABC):
    """Agent 基类"""

    @abstractmethod
    def select_action(self, state: GameState) -> Action:
        """选择动作"""
        pass

    def get_action_probabilities(self, state: GameState) -> np.ndarray:
        """获取动作概率分布，shape=(11,)"""
        pass

    def on_episode_start(self, episode_id: int):
        """回合开始回调"""
        pass

    def on_episode_end(self, reward: float, info: dict = None):
        """回合结束回调"""
        pass

    def set_training_mode(self, training: bool):
        """设置训练/推理模式"""
        pass

    def save(self, path: str):
        """保存模型"""
        pass

    def load(self, path: str):
        """加载模型"""
        pass
```

### 规则 Agent

```python
from src.agents import RuleBasedAgentImpl

agent = RuleBasedAgentImpl("MyRule")

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
result = agent.train(
    states,
    actions,
    val_split=0.2,
    epochs=200,
    batch_size=32,
    learning_rate=0.001,
    hidden_layers=(128, 64)
)

# 预测
probs = agent.predict_proba(state)  # 概率分布
action = agent.predict(state)       # 最佳动作

# 保存/加载
agent.save("models/my_sl.pkl")
agent.load("models/my_sl.pkl")
```

### 强化学习 Agent

```python
from src.agents import RLAgentImpl
from src.env import StsEnvWrapper

# 创建环境
env = StsEnvWrapper(character="silent", ascension=0)

# 创建 Agent
agent = RLAgentImpl("MyRL", config={"algorithm": "ppo"})

# 设置环境
agent.set_environment(env)

# Warm Start（可选）
agent.load_sl_model(sl_agent)

# 训练
result = agent.train(
    total_timesteps=1000000,
    n_envs=4,
    learning_rate=3e-4,
    gamma=0.99,
    n_steps=2048,
    batch_size=64
)

# 价值函数
q_value = agent.get_action_value(state, action)

# 保存/加载
agent.save("models/my_rl.zip")
agent.load("models/my_rl.zip")
```

---

## 环境 API

### StsEnvWrapper

```python
from src.env import StsEnvWrapper

# 创建环境
env = StsEnvWrapper(
    character="silent",  # ironclad, silent, defect, watcher
    ascension=0
)

# 重置环境
state, info = env.reset()

# 执行动作
next_state, reward, done, truncated, info = env.step(action)

# 关闭环境
env.close()

# 环境属性
env.observation_space  # Box(30,)
env.action_space       # Discrete(11)
```

### StsEnvironment（底层）

```python
from src.env import StsEnvironment

# 标准 Gymnasium 环境
env = StsEnvironment()

# 自定义奖励函数
env = StsEnvironment(
    damage_reward_scale=1.0,
    health_reward_scale=1.0,
    kill_reward=100.0,
    death_penalty=-100.0
)
```

---

## 训练 API

### StateEncoder

```python
from src.training import StateEncoder

# 创建编码器
encoder = StateEncoder(output_dim=30)

# 编码状态
state_vec = encoder.encode_state(state)  # shape=(30,)

# 编码动作
action_id = encoder.encode_action(action)  # 0-10
action = encoder.decode_action(action_id)
```

### 数据加载

```python
from src.agents import load_data_from_sessions, load_training_data

# 从会话目录加载
states, actions = load_data_from_sessions("combat_logs/sessions")

# 从任意目录加载
states, actions = load_training_data("data/raw")
```

---

## 实验 API

### ExperimentTracker

```python
from src.training import ExperimentTracker, ExperimentConfig

# 创建跟踪器
tracker = ExperimentTracker(experiments_dir="experiments")

# 创建实验
config = ExperimentConfig(
    name="ppo_baseline",
    agent_type="rl",
    algorithm="ppo",
    tags=["baseline", "a20"],
    learning_rate=3e-4,
    hidden_layers=[128, 128]
)
exp_id = tracker.create_experiment(config)

# 更新结果
tracker.update_result(
    exp_id,
    eval_win_rate=0.65,
    total_steps=1000000
)

# 完成实验
tracker.complete_experiment(
    exp_id,
    model_path="models/ppo.zip",
    notes="A20 胜率 65%"
)

# 失败实验
tracker.fail_experiment(exp_id, error="Out of memory")

# 获取结果
result = tracker.get_result(exp_id)
config = tracker.get_config(exp_id)

# 列出实验
all_exps = tracker.list_experiments()
completed = tracker.list_experiments(status="completed")

# 获取最佳实验
best = tracker.get_best_experiment(metric="eval_win_rate")

# 比较实验
comparison = tracker.compare_experiments([exp_id1, exp_id2])

# 删除实验
tracker.delete_experiment(exp_id)
```

### 快捷函数

```python
from src.training import create_experiment, get_tracker

# 创建实验
exp_id = create_experiment(
    name="my_experiment",
    agent_type="rl",
    algorithm="ppo"
)

# 获取全局跟踪器
tracker = get_tracker()
```

---

## 协议 API

### ModProtocol

```python
from src.protocol import ModProtocol

# 创建协议
protocol = ModProtocol()

# 读取状态
state = protocol.read_state()

# 发送命令
protocol.send_command("play 1 0")
protocol.send_action(Action.play_card(0, 0))
protocol.send_end()

# 检测状态变化
if protocol.has_state_changed(state):
    print("状态已变化")

# 检测 null 状态
if protocol.is_null_state(state):
    print("无效状态")

# 获取回退动作
action = protocol.get_fallback_action(state)

# 统计信息
stats = protocol.get_stats()
print(f"行数: {stats['line_count']}, 错误: {stats['error_count']}")
```

### ModReader

```python
from src.protocol.reader import ModReader

# 创建读取器
reader = ModReader()

# 读取状态
state = reader.read()

# 交互模式（自动发送 ready）
reader = ModReader(interactive=True)
```

### ModWriter

```python
from src.protocol.writer import ModWriter

# 创建写入器
writer = ModWriter()

# 发送命令
writer.send_command("play 1 0")
writer.send_end()
```

---

## 核心数据类

### GameState

```python
from src.core.game_state import GameState, RoomPhase

# 创建状态
state = GameState(
    room_phase=RoomPhase.COMBAT,
    floor=1,
    act=1,
    combat=combat_state,
    available_commands=["play", "end"],
    ready_for_command=True
)

# 转换
dict_data = state.to_dict()
state = GameState.from_mod_response(dict_data)

# 辅助方法
state.is_combat()  # 是否战斗中
state.is_ready_for_combat()  # 是否准备好战斗
```

### CombatState

```python
from src.core.game_state import CombatState, Card, Player, Monster

combat = CombatState(
    hand=[card1, card2],
    player=player,
    monsters=[monster1, monster2],
    turn=1
)

# 获取有效卡牌索引
valid_indices = combat.get_valid_card_indices()

# 获取存活怪物
living = combat.get_living_monsters()
```

### Card

```python
from src.core.game_state import Card, CardType

card = Card(
    id="Strike_G",
    name="打击",
    cost=1,
    card_type=CardType.ATTACK,
    is_playable=True,
    has_target=True,
    damage=6
)
```

### Monster

```python
from src.core.game_state import Monster, IntentType

monster = Monster(
    id="m1",
    name="Cultist",
    current_hp=40,
    max_hp=44,
    intent=IntentType.ATTACK,
    intent_damage=6
)
```

### Action

```python
from src.core.action import Action

# 工厂方法
action = Action.play_card(hand_index=0, target_index=0)
action = Action.end_turn()
action = Action.state()
action = Action.choose(choice_index=0)
action = Action.key(key_name="Confirm")

# 转换
command = action.to_command()  # "play 1 0"
action_id = action.to_id()     # 0-10
action = Action.from_id(5)
action = Action.from_command("play 1 0")
```

### Config

```python
from src.core.config import get_config

# 获取配置
config = get_config()

# 访问配置
data_dir = config.training.data_dir
models_dir = config.training.models_dir

# 环境变量覆盖
import os
os.environ["STS_MODELS_DIR"] = "/path/to/models"
config = get_config()
```

---

## 类型注解

```python
from typing import Dict, List, Optional, Tuple
import numpy as np
from src.core.game_state import GameState
from src.core.action import Action

# 函数签名示例
def select_action(state: GameState) -> Action:
    pass

def get_probabilities(state: GameState) -> np.ndarray:
    pass

def train(
    states: List[GameState],
    actions: List[Action],
    **kwargs
) -> Dict[str, float]:
    pass

def step(
    action: Action
) -> Tuple[np.ndarray, float, bool, bool, Dict]:
    pass
```

---

## 常量

### 动作空间

```python
ACTION_SPACE_SIZE = 11

# 动作 ID 映射
# 0-8: 出第 1-9 张牌
# 9: 查看状态
# 10: 结束回合
```

### 房间阶段

```python
class RoomPhase(Enum):
    EVENT = "event"
    SHOP = "shop"
    REST = "rest"
    COMBAT = "combat"
    MAP = "map"
    BOSS = "boss"
    CARD_REWARD = "card_reward"
    UNKNOWN = "unknown"
```

### 怪物意图

```python
class IntentType(Enum):
    ATTACK = "attack"
    DEFEND = "defend"
    BUFF = "buff"
    DEBUFF = "debuff"
    UNKNOWN = "unknown"
    NONE = "none"
```

### 卡牌类型

```python
class CardType(Enum):
    ATTACK = "attack"
    SKILL = "skill"
    POWER = "power"
    STATUS = "status"
    CURSE = "curse"
    UNKNOWN = "unknown"
```
