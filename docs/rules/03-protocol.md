# 03 - CommunicationMod 协议

> **核心规则**：Mod 通信约定与关键状态字段，供 `read_state.py` 及后续脚本解析。  
> **参考**：[CommunicationMod](https://github.com/ForgottenArbiter/CommunicationMod)、[spirecomm](https://github.com/banjtheman/spirecomm)

---

## 协议要点

1. **Mod 发状态** → **等待响应** → **必须回复**，否则阻塞。
2. 建议用 `python -u` 启动，关闭 I/O 缓冲。
3. 启动后脚本立即输出 `ready\n`。

---

## 响应命令

| 命令 | 使用场景 |
|------|----------|
| `state` | 无可执行命令时，让 Mod 立即回传当前状态 |
| `play <i> <t>` | 战斗出牌阶段，打出第 `i` 张牌（1-based：1=第一张），目标 `t` |
| `end` | 战斗出牌阶段，结束回合 |
| `choose` | 事件/涅奥/地图等需要选择时 |
| `proceed` | 结算界面「前进」、死亡/胜利画面点击继续时 |
| `return` | 从子界面返回（如地图、回到主页面） |
| `skip` | 卡牌奖励界面选择跳过（不拿牌） |
| `potion` | 使用药水 |
| `wait` | 动画/过渡阶段（如战斗开始），让 Mod 推进游戏 |
| `key Confirm` | 弃牌确认、弹窗确认等需按确认键的界面 |
| `key Cancel` | 有 cancel 时关闭覆盖层（如药水选择） |
| `key` / `click` | 其他底层操作，一般由 Mod 根据场景提供 |

---

## 状态字段

### 顶层

| 字段 | 类型 | 说明 |
|------|------|------|
| `in_game` | bool | 是否在游戏中 |
| `ready_for_command` | bool | 是否等待命令（`false` 时多为动画/过渡） |
| `available_commands` | list | 当前可用命令，如 `["play","end","state"]` |

### game_state

| 字段 | 说明 |
|------|------|
| `screen_type` | `EVENT` / `MAP` / `NONE` 等，当前界面类型 |
| `screen_state` | 界面相关数据（事件选项、地图节点等） |
| `room_phase` | `COMBAT` 表示战斗 |
| `combat_state` | 战斗状态，非战斗时可能为空 |
| `deck` | 牌组（全局） |
| `seed` | 本局种子 |

### combat_state（战斗时）

| 字段 | 说明 |
|------|------|
| `hand` | 手牌列表，每张含 `id`、`name`、`cost`、`uuid`、`is_playable` 等 |
| `draw_pile` | 抽牌堆 |
| `discard_pile` | 弃牌堆 |
| `player` | `energy`、`current_hp`、`block` 等 |
| `monsters` | 敌人列表，含意图、血量等 |
| `turn` | 当前回合数（若有） |

---

## 决策逻辑（read_state.py）

- `ready_for_command=true` 且 `choose` 在 `available_commands` → 发送 `choose`。
- `ready_for_command=true` 且 `proceed` 在 `available_commands` → 发送 `proceed`（结算界面前进）。
- `ready_for_command=true` 且 `play` 或 `end` 在 `available_commands` → 发送 `play` 或 `end`。
- 否则 → 发送 `state`。
