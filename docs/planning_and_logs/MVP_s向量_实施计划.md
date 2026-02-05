# MVP s 向量实施计划

> **目的**：用最小可跑通的 s 向量验证「数据收集 → 编码 → 训练 → 推理」全流程，不追求决策质量。

---

## 一、MVP s 向量规格（31 维）

| 区块 | 维度 | 来源 | 编码方式 |
|------|------|------|----------|
| 全局 | 5 | game_state: floor, act, gold, current_hp, max_hp | 标量 / max 归一化到 0~1 |
| 场景 | 15 | room_phase (4) + screen_type (11) | one-hot |
| 可用命令 | 3 | available_commands 含 play/end、choose、proceed | 3 个 0/1 |
| 战斗（有 combat_state 时） | 7 | player.energy, player.block, hand 数, draw 数, discard 数, monsters 数, 存活怪物总 hp 占比 | 标量归一化 |
| 选择 | 1 | len(choice_list) | min(len,60)/60 |
| **合计** | **31** | | |

**归一化常量**：MAX_HP=999, MAX_BLOCK=99, MAX_ENERGY=10, MAX_GOLD=999, MAX_HAND=10, MAX_DRAW=80, MAX_MONSTERS=6

---

## 二、Mod log → s 向量 映射表（核心）

> **关键**：每一维 s 必须明确对应 Mod log 的字段路径与转换公式。

### 2.1 输入结构（Mod log 一帧）

```json
{
  "available_commands": ["play", "end", "choose", ...],
  "ready_for_command": true,
  "in_game": true,
  "game_state": {
    "floor": 1,
    "act": 1,
    "gold": 99,
    "current_hp": 70,
    "max_hp": 70,
    "room_phase": "COMBAT",
    "screen_type": "NONE",
    "choice_list": ["x=1", "x=2"],
    "combat_state": { ... }   // 仅战斗时存在
  }
}
```

### 2.2 逐维映射与转换公式

| s 索引 | 区块 | Mod log 路径 | 类型 | 转换公式 | 缺失/异常处理 |
|--------|------|--------------|------|----------|---------------|
| 0 | 全局 | `game_state.floor` | int | `min(v, 15) / 15` | 缺则 0 |
| 1 | 全局 | `game_state.act` | int | `min(v, 3) / 3` | 缺则 0 |
| 2 | 全局 | `game_state.gold` | int | `min(v, 999) / 999` | 缺则 0 |
| 3 | 全局 | `game_state.current_hp` 或 `combat_state.player.current_hp` | int | `min(v, max_hp) / max(1, max_hp)` | 缺则 0；max_hp 缺则 70 |
| 4 | 全局 | `game_state.max_hp` 或 `combat_state.player.max_hp` | int | `min(v, 999) / 999` | 缺则 1 |
| 5 | 场景 | `game_state.room_phase` | str | one-hot | EVENT→[1,0,0,0], COMBAT→[0,1,0,0], COMPLETE→[0,0,1,0], INCOMPLETE→[0,0,0,1] |
| 6 | 场景 | 同上 | | | |
| 7 | 场景 | 同上 | | | |
| 8 | 场景 | 同上 | | | |
| 9 | 场景 | `game_state.screen_type` | str | one-hot | 见下表 2.3 |
| ... | 场景 | 同上 | | | |
| 19 | 场景 | 同上 | | | |
| 20 | 命令 | `available_commands` | list | `1 if "play" in cmds or "end" in cmds else 0` | 缺则 0 |
| 21 | 命令 | 同上 | | `1 if "choose" in cmds else 0` | |
| 22 | 命令 | 同上 | | `1 if "proceed" in cmds else 0` | |
| 23 | 战斗 | `combat_state.player.energy` | int | `min(v, 10) / 10` | 无 combat_state 则 0 |
| 24 | 战斗 | `combat_state.player.block` | int | `min(v, 99) / 99` | 无 combat_state 则 0 |
| 25 | 战斗 | `len(combat_state.hand)` | int | `min(v, 10) / 10` | 无 combat_state 则 0 |
| 26 | 战斗 | `len(combat_state.draw_pile)` | int | `min(v, 80) / 80` | 无 combat_state 则 0 |
| 27 | 战斗 | `len(combat_state.discard_pile)` | int | `min(v, 80) / 80` | 无 combat_state 则 0 |
| 28 | 战斗 | `len([m for m in combat_state.monsters if not m.get("is_gone")])` | int | `min(v, 6) / 6` | 无 combat_state 则 0 |
| 29 | 战斗 | 存活怪物总 hp / 存活怪物总 max_hp | float | `sum(cur_hp)/max(1, sum(max_hp))` | 无怪物则 0 |
| 30 | 选择 | `game_state.choice_list` | list | `min(len(v), 60) / 60` | None 或缺则 0 |

### 2.3 screen_type one-hot 映射（s[9]~s[19]）

| 索引 | screen_type 值 | s 中对应位 |
|------|----------------|------------|
| 0 | EVENT | s[9]=1 |
| 1 | MAP | s[10]=1 |
| 2 | NONE | s[11]=1 |
| 3 | COMBAT_REWARD | s[12]=1 |
| 4 | CARD_REWARD | s[13]=1 |
| 5 | SHOP_ROOM | s[14]=1 |
| 6 | SHOP_SCREEN | s[15]=1 |
| 7 | GRID | s[16]=1 |
| 8 | REST | s[17]=1 |
| 9 | CHEST | s[18]=1 |
| 10 | HAND_SELECT | s[19]=1 |
| - | 未知/其他 | 全 0 |

### 2.4 转换逻辑伪代码

```python
def encode(mod_response):
    gs = mod_response.get("game_state") or {}
    cs = gs.get("combat_state")
    cmds = mod_response.get("available_commands") or []
    s = np.zeros(31, dtype=np.float32)

    # 0-4: 全局
    s[0] = min(gs.get("floor", 0), 15) / 15
    s[1] = min(gs.get("act", 1), 3) / 3
    s[2] = min(gs.get("gold", 0), 999) / 999
    cur_hp = (cs.get("player") or {}).get("current_hp", gs.get("current_hp", 0))
    max_hp = max((cs.get("player") or {}).get("max_hp", gs.get("max_hp", 70)), 1)
    s[3] = min(cur_hp, max_hp) / max_hp
    s[4] = min(max_hp, 999) / 999

    # 5-8: room_phase one-hot
    rp = gs.get("room_phase", "")
    for i, v in enumerate(["EVENT", "COMBAT", "COMPLETE", "INCOMPLETE"]):
        s[5 + i] = 1.0 if rp == v else 0.0

    # 9-19: screen_type one-hot
    st = gs.get("screen_type", "")
    for i, v in enumerate(["EVENT","MAP","NONE","COMBAT_REWARD","CARD_REWARD","SHOP_ROOM","SHOP_SCREEN","GRID","REST","CHEST","HAND_SELECT"]):
        s[9 + i] = 1.0 if st == v else 0.0

    # 20-22: 可用命令
    s[20] = 1.0 if ("play" in cmds or "end" in cmds) else 0.0
    s[21] = 1.0 if "choose" in cmds else 0.0
    s[22] = 1.0 if "proceed" in cmds else 0.0

    # 23-29: 战斗（无 combat_state 则全 0）
    if cs:
        s[23] = min((cs.get("player") or {}).get("energy", 0), 10) / 10
        s[24] = min((cs.get("player") or {}).get("block", 0), 99) / 99
        s[25] = min(len(cs.get("hand") or []), 10) / 10
        s[26] = min(len(cs.get("draw_pile") or []), 80) / 80
        s[27] = min(len(cs.get("discard_pile") or []), 80) / 80
        monsters = [m for m in (cs.get("monsters") or []) if not m.get("is_gone")]
        s[28] = min(len(monsters), 6) / 6
        total_cur = sum(m.get("current_hp", 0) for m in monsters)
        total_max = sum(m.get("max_hp", 1) for m in monsters)
        s[29] = total_cur / max(1, total_max)

    # 30: choice_list
    cl = gs.get("choice_list") or []
    s[30] = min(len(cl), 60) / 60

    return s
```

### 2.5 数据来源一致性

| 场景 | combat_state | current_hp / max_hp 取法 |
|------|--------------|--------------------------|
| 战斗 | 有 | 优先 `combat_state.player`，否则 `game_state` |
| 事件/地图/商店等 | 无 | 仅 `game_state.current_hp` / `game_state.max_hp` |

---

## 三、涉及文件与修改点

### 3.1 新增：MVP 编码器

**文件**：`src/training/encoder_mvp.py`

**内容**：
- `encode(mod_response: Dict[str, Any]) -> np.ndarray`，输出 shape=(31,), dtype=float32
- **实现必须严格遵循第二节「Mod log → s 向量映射表」**：每维 s 的取值、路径、转换公式、缺失处理均按表执行
- `get_output_dim() -> int` 返回 31
- 不依赖 `encoder_utils`、`power_parser`、`encoder_ids.yaml`
- 从 `mod_response` 直接读取：`game_state`、`available_commands`、`combat_state`（可选）

**room_phase one-hot 顺序**：EVENT=0, COMBAT=1, COMPLETE=2, INCOMPLETE=3

**screen_type one-hot 顺序**：EVENT, MAP, NONE, COMBAT_REWARD, CARD_REWARD, SHOP_ROOM, SHOP_SCREEN, GRID, REST, CHEST, HAND_SELECT（共 11，未知填 0）

### 3.2 修改：数据保存格式

**文件**：`src/core/game_state.py`

**修改**：
- 新增 `GameState.to_mod_response() -> Dict`：将 GameState 转成 encoder 所需的 Mod 格式
- 输出结构：`{"game_state": {...}, "available_commands": [...], "ready_for_command": bool, "in_game": bool}`
- `game_state` 需含：floor, act, room_phase, screen_type, choice_list, combat_state, current_hp, max_hp, gold（从 combat.player 或默认值补齐）
- **结构必须与第二节 2.1 的 Mod log 输入结构一致**，以便 `encode()` 能按映射表正确读取
- 若 `GameState` 无 `gold` 字段：在 `GameState` 中新增 `gold: int = 0`，在 `from_mod_response` 中解析 `gs.get("gold", 0)` 并赋值

**文件**：`scripts/collect_data.py`

**修改**：
- 第 178 行附近：`episode_data["states"].append(state.to_dict())` 改为 `episode_data["states"].append(state.to_mod_response())`
- 确保写入 jsonl 的 `state` 为 Mod 格式

### 3.3 修改：数据加载与监督学习 Agent

**文件**：`src/agents/supervised.py`

**修改**：
1. `_load_encoder()`：改为 `from src.training.encoder_mvp import encode, get_output_dim`，不再使用 `StateEncoder`
2. 新增 `_encoder_encode(state_or_dict)`：
   - 若为 `dict`（Mod 格式），直接调用 `encode(state_or_dict)`
   - 若为 `GameState`，先调用 `state.to_mod_response()` 再 `encode(...)`
3. `_encode_states(states)`：遍历 states，对每条调用 `_encoder_encode`，得到 `np.ndarray`
4. `load_training_data` / `load_data_from_sessions`：
   - 解析 `record["state"]` 时，若为 Mod 格式（含 `game_state` 键），不解析为 GameState，直接保留 dict 传给 encoder
   - 为兼容 `Action.from_command(record["action"])`，保留原有 action 解析逻辑
5. `predict_proba(state)`：参数可为 `GameState` 或 `dict`，内部统一转为 dict 后调用 `encode`
6. `_train_sklearn`：`MLPClassifier` 的 `output_dim` 改为 `ACTION_SPACE_SIZE`（173），不再使用 11
7. `_train_pytorch`：`PolicyNet` 的 `output_dim` 改为 `ACTION_SPACE_SIZE`（173）
8. `predict_proba` 返回值 shape 改为 `(173,)`，不再 `(11,)`
9. 保存/加载时，`encoder` 字段存 `encoder_mvp` 的 `encode` 函数引用或模块路径，确保推理时使用 MVP 编码器

### 3.4 修改：动作 ID 与掩码

**文件**：`src/core/action.py`

**确认**：`to_id()` 已支持 0–172，`Action.from_id()` 已支持反向映射。无需修改。

### 3.5 可选：Raw_Data 编码验证脚本

**文件**：`scripts/verify_encoder_mvp.py`（新增）

**内容**：
- 读取 `data/A20_Slient/Raw_Data_json_FORSL/*.json`
- 对每帧调用 `encoder_mvp.encode(frame)`，检查无异常、shape=(31,)
- 打印前 5 帧的 s 向量摘要

---

## 四、数据流说明

1. **收集**：`python scripts/collect_data.py --games 5` → 输出 `combat_logs/sessions/<session>/session.jsonl`
2. **格式**：每行 `{"state": <Mod 格式 dict>, "action": "play 0 0", "reward": 0.1, ...}`
3. **加载**：`load_data_from_sessions(data_dir)` 读取 jsonl，返回 `(states: List[dict], actions: List[Action])`
4. **编码**：`X = [encode(s) for s in states]`，`y = [a.to_id() for a in actions]`
5. **训练**：`agent.train(states, actions)`，内部用 MVP encoder 编码
6. **推理**：`agent.predict_proba(state)` → 173 维概率，取 argmax 或按掩码采样

---

## 五、与现有组件的兼容

- **encoder.py**：保留不动，MVP 不替换 1840 维 encoder
- **sts_env.py、rl_agent.py**：仍引用 `StateEncoder`，会 ImportError；MVP 阶段不修复，仅验证 SL 流程
- **train.py**：`sl` 子命令调用 `train_sl.py`，传入 `--data-dir`，无需修改

---

## 六、实施检查清单

1. 在 `src/training/encoder_mvp.py` 中实现 `encode(mod_response)`，**严格按第二节 Mod log → s 映射表**逐维转换，输出 shape=(31,)、dtype=float32，并实现 `get_output_dim() -> 31`
2. 在 `src/core/game_state.py` 中实现 `GameState.to_mod_response() -> Dict`
3. 若 `GameState` 无 `gold`，在 `from_mod_response` 中解析 `gs.get("gold", 0)` 并存入新字段，或 `to_mod_response` 中从可用字段推断
4. 在 `scripts/collect_data.py` 中将 `state.to_dict()` 改为 `state.to_mod_response()`
5. 在 `src/agents/supervised.py` 中移除 `StateEncoder` 引用，改为使用 `encoder_mvp.encode`
6. 在 `src/agents/supervised.py` 中实现 `_encoder_encode(state_or_dict)`，支持 dict 与 GameState
7. 在 `src/agents/supervised.py` 中，`load_training_data` 保持解析为 GameState；`_encode_states` 对每个 GameState 调用 `state.to_mod_response()` 再 `encode(...)`
8. 在 `src/agents/supervised.py` 中将 sklearn 与 PyTorch 模型的 `output_dim` 改为 173
9. 在 `src/agents/supervised.py` 中将 `predict_proba` 返回 shape 改为 (173,)
10. 在 `src/agents/supervised.py` 的 save/load 中正确保存与加载 MVP encoder 引用
11. 新增 `scripts/verify_encoder_mvp.py`，对 Raw_Data 跑 encode 验证
12. 运行 `python scripts/collect_data.py --games 3` 生成 session.jsonl
13. 运行 `python scripts/train_sl.py --data-dir combat_logs/sessions/<session_dir> --model-type sklearn` 验证训练
14. 运行 `python scripts/train.py interactive --agent-type supervised --model <path>` 验证推理（若 interactive 支持 supervised）
