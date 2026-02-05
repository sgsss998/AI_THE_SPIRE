# MVP s 向量 完整实施计划

> **模式**：计划模式（完整版）  
> **目的**：最小可跑通 s 向量，验证「Mod log → 编码 → 训练 → 推理」全流程。  
> **原则**：每个动作为原子操作，含确切文件路径、行号、函数名。  
> **关联**：Mod log → s 映射表见 `MVP_s向量_实施计划.md` 第二节。

---

## 阶段划分

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 1 | GameState 扩展（gold、to_mod_response、from_mod_response 兼容 choice_list） | 无 |
| 2 | encoder_mvp 实现 | 无 |
| 3 | supervised.py 改造 | 阶段 1、2 |
| 4 | collect_data 改造 | 阶段 1 |
| 5 | 验证脚本 | 阶段 2 |
| 6 | 端到端验证 | 阶段 1–5 |

---

## 阶段 1：GameState 扩展

### 1.1 新增 gold 字段

**文件**：`/Volumes/T7/AI_THE_SPIRE/src/core/game_state.py`

**位置**：GameState 类字段定义（约第 343–348 行）

**操作**：在 `choice_list` 后新增 `gold: int = 0`

**修改前**：
```python
    choice_list: List[Any] = field(default_factory=list)  # 选择列表（商店/奖励/事件）
    draw: int = 0  # 抽牌数
```

**修改后**：
```python
    choice_list: List[Any] = field(default_factory=list)  # 选择列表（商店/奖励/事件）
    gold: int = 0  # 金币（encoder 需要）
    draw: int = 0  # 抽牌数
```

### 1.2 from_mod_response 解析 gold、choice_list、current_hp、max_hp

**文件**：`/Volumes/T7/AI_THE_SPIRE/src/core/game_state.py`

**位置**：`from_mod_response` 方法内（约第 376–407 行）

**操作**：
1. 将 `choice_list = gs.get("choices", gs.get("cards", gs.get("event", [])))` 改为  
   `choice_list = gs.get("choice_list", gs.get("choices", gs.get("cards", gs.get("event", []))))`
2. 在 `return cls(...)` 之前计算：  
   `cur_hp = combat.player.current_hp if combat else gs.get("current_hp", 0)`  
   `mx_hp = combat.player.max_hp if combat else gs.get("max_hp", 70)`
3. 在 `return cls(...)` 中新增参数：`gold=gs.get("gold", 0)`、`current_hp=cur_hp`、`max_hp=mx_hp`

**修改后 return**：
```python
        cur_hp = combat.player.current_hp if combat else gs.get("current_hp", 0)
        mx_hp = combat.player.max_hp if combat else gs.get("max_hp", 70)
        return cls(
            room_phase=room_phase,
            floor=gs.get("floor", 0),
            act=gs.get("act", 1),
            combat=combat,
            screen_type=gs.get("screen_type"),
            in_game=response.get("in_game", True),
            available_commands=response.get("available_commands", []),
            ready_for_command=response.get("ready_for_command", False),
            relics=relics,
            choice_list=choice_list,
            gold=gs.get("gold", 0),
            current_hp=cur_hp,
            max_hp=mx_hp,
        )
```

### 1.3 新增 to_mod_response 方法

**文件**：`/Volumes/T7/AI_THE_SPIRE/src/core/game_state.py`

**位置**：在 `to_dict` 方法之后（约第 427 行后）

**操作**：新增方法 `to_mod_response(self) -> Dict[str, Any]`，输出与《MVP_s向量_实施计划》第二节 2.1 一致的 Mod 格式。

**实现规格**：
```python
def to_mod_response(self) -> Dict[str, Any]:
    """转为 encoder 所需的 Mod 格式，与 configs/Mod日志_参数清单 结构一致。"""
    phase = self.room_phase.value if hasattr(self.room_phase, "value") else str(self.room_phase)
    cur_hp = self.combat.player.current_hp if self.combat else self.current_hp
    mx_hp = self.combat.player.max_hp if self.combat else self.max_hp
    gs = {
        "floor": self.floor,
        "act": self.act,
        "room_phase": phase,
        "screen_type": self.screen_type or "",
        "choice_list": self.choice_list,
        "choices": self.choice_list,  # from_mod_response 兼容
        "current_hp": cur_hp,
        "max_hp": mx_hp,
        "gold": self.gold,
    }
    if self.combat:
        cs = self.combat
        gs["combat_state"] = {
            "hand": [c.to_dict() for c in cs.hand],
            "draw_pile": [{}] * cs.draw_pile_count,
            "discard_pile": [{}] * cs.discard_pile_count,
            "monsters": [m.to_dict() for m in cs.monsters],
            "player": cs.player.to_dict(),
        }
    else:
        gs["combat_state"] = None
    return {
        "game_state": gs,
        "available_commands": self.available_commands,
        "ready_for_command": self.ready_for_command,
        "in_game": self.in_game,
    }
```

**依赖**：GameState 需有 `current_hp`、`max_hp`、`gold` 字段，`from_mod_response` 需解析并传入。

### 1.4 可选：CombatState.from_dict 兼容 draw_pile/discard_pile 为 list

**文件**：`/Volumes/T7/AI_THE_SPIRE/src/core/game_state.py`

**位置**：CombatState.from_dict（约第 313–314 行）

**说明**：Mod 格式中 `draw_pile`、`discard_pile` 为数组，`d.get("draw_pile", 0)` 会返回 list。若 env 解析报错，需改为：  
`draw_pile_count=len(d.get("draw_pile", [])) if isinstance(d.get("draw_pile"), list) else d.get("draw_pile_count", 0)`，  
`discard_pile_count` 同理（Mod 键为 `discard_pile`）。

---

## 阶段 2：encoder_mvp 实现

### 2.1 新建 encoder_mvp.py

**文件**：`/Volumes/T7/AI_THE_SPIRE/src/training/encoder_mvp.py`（新建）

**内容**：完整实现，严格按《MVP_s向量_实施计划》第二节 2.2–2.4 映射表。

**必须包含**：
- `encode(mod_response: Dict[str, Any]) -> np.ndarray`，输出 shape=(31,), dtype=np.float32
- `get_output_dim() -> int` 返回 31
- 不 import `encoder_utils`、`power_parser`
- 仅 import：`numpy`、`typing`

**实现**：直接采用《MVP_s向量_实施计划》2.4 节伪代码，补全类型与边界处理。

---

## 阶段 3：supervised.py 改造

### 3.1 修改 _load_encoder

**文件**：`/Volumes/T7/AI_THE_SPIRE/src/agents/supervised.py`

**位置**：第 49–52 行

**修改前**：
```python
    def _load_encoder(self):
        """加载状态编码器"""
        from src.training.encoder import StateEncoder
        self._encoder = StateEncoder(mode="extended")  # 使用扩展模式
```

**修改后**：
```python
    def _load_encoder(self):
        """加载 MVP 状态编码器"""
        from src.training.encoder_mvp import encode, get_output_dim
        self._encoder_encode_fn = encode
        self._encoder_output_dim = get_output_dim()
```

### 3.2 新增 _encoder_encode 方法

**文件**：同上

**位置**：在 `_load_encoder` 之后

**操作**：新增方法
```python
def _encoder_encode(self, state_or_dict):  # Union[GameState, Dict]
    """编码状态为向量，支持 GameState 或 Mod 格式 dict。"""
    if isinstance(state_or_dict, dict):
        return self._encoder_encode_fn(state_or_dict)
    return self._encoder_encode_fn(state_or_dict.to_mod_response())
```

### 3.3 修改 _encode_states

**文件**：同上

**位置**：第 96–102 行

**修改前**：
```python
    def _encode_states(self, states: List[GameState]) -> np.ndarray:
        """编码状态为向量"""
        encoded = []
        for state in states:
            vec = self._encoder.encode_state(state)
            encoded.append(vec)
        return np.array(encoded)
```

**修改后**：
```python
    def _encode_states(self, states) -> np.ndarray:
        """编码状态为向量"""
        encoded = []
        for state in states:
            vec = self._encoder_encode(state)
            encoded.append(vec)
        return np.array(encoded)
```

### 3.4 修改 _train_sklearn 的 n_classes

**文件**：同上

**位置**：第 144–155 行，MLPClassifier 创建

**操作**：MLPClassifier 的 `hidden_layer_sizes` 最后一层输出需为 173。sklearn 的 MLPClassifier 根据 `y` 自动推断 `n_classes`，只要 `y` 为 0–172 的 action_id 即可，无需改 `output_dim`。**确认**：`_encode_actions` 返回 `[a.to_id() for a in actions]`，已为 0–172，无需修改。

### 3.5 修改 _train_pytorch 的 PolicyNet output_dim

**文件**：同上

**位置**：第 231–252 行

**修改**：`PolicyNet` 的 `output_dim` 从 11 改为 `ACTION_SPACE_SIZE`（173）。需 `from src.core.action import ACTION_SPACE_SIZE`，并将 `output_dim=11` 改为 `output_dim=ACTION_SPACE_SIZE`。同时 `input_dim` 从 30 改为 `X.shape[1]`（即 31）。

### 3.6 修改 predict_proba

**文件**：同上

**位置**：第 291–322 行

**修改**：
1. 未训练时返回 `np.ones(173, dtype=np.float32) / 173`，不再用 11
2. 编码调用 `self._encoder_encode(state)` 替代 `self._encoder.encode_state(state)`
3. sklearn 的 `predict_proba` 输出 shape 由 `y` 的类别数决定，已为 173
4. PyTorch 的 `output_dim` 改为 173 后，`proba` shape 为 (173,)

### 3.7 修改 save 方法

**文件**：同上

**位置**：第 324–338 行

**修改**：`save_data` 中 `"encoder"` 改为存 `"encoder_module": "encoder_mvp"`、`"encoder_encode": encode`（或通过模块路径 `src.training.encoder_mvp.encode` 在 load 时重新 import）。pickle 可序列化函数引用。

### 3.8 修改 load 方法

**文件**：同上

**位置**：第 340–355 行

**修改**：加载时若 `save_data` 含 `encoder_module`，则 `from src.training.encoder_mvp import encode` 并设置 `self._encoder_encode_fn = encode`；否则兼容旧格式。

---

## 阶段 4：collect_data 改造

### 4.1 修改状态保存

**文件**：`/Volumes/T7/AI_THE_SPIRE/scripts/collect_data.py`

**位置**：第 178 行

**修改前**：
```python
            episode_data["states"].append(state.to_dict())
```

**修改后**：
```python
            episode_data["states"].append(state.to_mod_response())
```

---

## 阶段 5：验证脚本

### 5.1 新建 verify_encoder_mvp.py

**文件**：`/Volumes/T7/AI_THE_SPIRE/scripts/verify_encoder_mvp.py`（新建）

**内容**：
- 读取 `data/A20_Slient/Raw_Data_json_FORSL/*.json`
- 对每帧调用 `encoder_mvp.encode(frame)`
- 断言 `shape == (31,)`、`dtype == np.float32`
- 打印前 5 帧的 s 向量

---

## 阶段 6：load_training_data 兼容性

### 6.1 确认 load_training_data 解析逻辑

**文件**：`/Volumes/T7/AI_THE_SPIRE/src/agents/supervised.py`

**位置**：`load_training_data` 函数（约第 378–410 行）

**确认**：`record["state"]` 若含 `game_state` 键，则 `GameState.from_mod_response(record["state"])` 能正确解析（因 `to_mod_response` 输出结构与之一致）。`from_mod_response` 已支持 `choice_list`、`gold`、`current_hp`、`max_hp`。**注意**：`to_mod_response` 输出的 `game_state` 含 `choices` 还是 `choice_list`？encoder 读 `choice_list`，`from_mod_response` 读 `choices` 或 `choice_list`。为兼容，`to_mod_response` 的 `game_state` 应同时含 `"choice_list": self.choice_list` 和 `"choices": self.choice_list`。

---

## 实施检查清单（按顺序执行）

1. 在 `src/core/game_state.py` 的 GameState 中新增字段 `gold: int = 0`、`current_hp: int = 0`、`max_hp: int = 70`
2. 在 `src/core/game_state.py` 的 `from_mod_response` 中解析 `gold`、`current_hp`、`max_hp`、`choice_list`（支持 `choice_list` 键），并传入 `cls(...)`
3. 在 `src/core/game_state.py` 中实现 `GameState.to_mod_response()`，输出与 Mod log 结构一致，含 `game_state`（含 `combat_state`、`choice_list`、`choices`）、`available_commands`、`ready_for_command`、`in_game`
4. 新建 `src/training/encoder_mvp.py`，实现 `encode(mod_response)` 与 `get_output_dim()`，严格按映射表
5. 在 `src/agents/supervised.py` 中修改 `_load_encoder`，改用 `encoder_mvp.encode`
6. 在 `src/agents/supervised.py` 中新增 `_encoder_encode(state_or_dict)`
7. 在 `src/agents/supervised.py` 中修改 `_encode_states`，调用 `_encoder_encode`
8. 在 `src/agents/supervised.py` 的 `_train_pytorch` 中，将 PolicyNet 的 `output_dim` 改为 `ACTION_SPACE_SIZE`，`input_dim` 改为 `X.shape[1]`
9. 在 `src/agents/supervised.py` 的 `predict_proba` 中，未训练时返回 173 维，编码调用 `_encoder_encode`
10. 在 `src/agents/supervised.py` 的 save/load 中，正确保存与加载 MVP encoder 引用
11. 在 `scripts/collect_data.py` 第 178 行，将 `state.to_dict()` 改为 `state.to_mod_response()`
12. 新建 `scripts/verify_encoder_mvp.py`，对 Raw_Data 跑 encode 验证
13. 运行 `python scripts/verify_encoder_mvp.py` 验证 encoder
14. 运行 `python scripts/collect_data.py --games 3` 生成数据
15. 运行 `python scripts/train_sl.py --data-dir combat_logs/sessions/<session_dir> --model-type sklearn` 验证训练
16. 运行 `python scripts/train.py interactive --agent-type supervised --model <path>` 验证推理
