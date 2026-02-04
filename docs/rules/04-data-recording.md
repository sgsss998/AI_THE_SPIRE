# 04 - 数据记录规则

> **目的**：规定何时写入日志、写入什么，与 `read_state.py` 的 `_should_log` 逻辑对齐。  
> **存储格式**：见 [combat_logs/README.md](../../combat_logs/README.md)

---

## 记录原则

**仅当 (1) 发送决策命令 且 (2) `game_state` 实际变化 时记录。**

- Mod 可能在动画/轮询时多次推送相同状态，需去重。
- 实现：对 `game_state` 做哈希，`hash(current) != last_logged_hash` 时才写入。
- **决策点过滤**：仅当 `cmd` 为 `play *`、`end`、`choose *`、`proceed`、`return`、`skip`、`potion`、`key *` 时写入，过滤掉 `state` 等无意义轮询。
- **会话结束**：当 `in_game` 变为 `false`（死亡/胜利回到主页面）时，额外记录一条以标记会话终结。

---

## 战斗内记录点

| 逻辑点 | 说明 | 识别方式 |
|--------|------|----------|
| 回合开始 | 能量回满、抽牌完成 | `energy=3` 且与上次记录不同 |
| 每出一次牌 | 手牌/能量变化 | 状态指纹（hand+energy）与上次不同 |
| 回合结束 | 玩家发送 `end` | 命令为 `end` |

**状态指纹**：`(len(hand), energy, tuple(card_uuid for card in hand))`，用于去重。

---

## 非战斗记录

- 地图、事件、商店、涅奥等：**状态变化即记录**。
- 同样依赖 `game_state` 哈希去重。

---

## 存储格式（JSONL）

每行一条 JSON，**精简存储**以控制体积（约 1KB/条，完整 state 约 12KB/条）：

```json
{"ts": "2026-02-02T20:06:23.218194", "action": "play 0 0", "state": {...}}
```

- `ts`：时间戳（ISO）
- `action`：本轮发送的命令
- `state`：**精简后的**状态，仅保留训练/转换所需字段：
  - 战斗：`combat_state`（hand、player、monsters、turn），不含 map/deck/draw_pile 等
  - 非战斗：`screen_type`、`choice_list`、`screen_state.options`

---

## 与 read_state.py 的对应

- `_state_hash(data)`：对 `game_state` 做 SHA256。
- `_should_log(data, last_logged_hash)`：`hash != last_logged_hash` 且 `in_game`。
- 关闭记录：`AI_STS_NO_LOG=1` 或 `--no-log`。
