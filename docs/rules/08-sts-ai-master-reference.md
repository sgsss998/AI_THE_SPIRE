# 08 - STS-AI-Master 参考：监督学习可借鉴规则

> **来源**：[GitHub - XlousMao/STS-AI-Master](https://github.com/XlousMao/STS-AI-Master)  
> **用途**：监督学习框架搭建时可直接借鉴的状态结构、动作掩码、特征设计等规则

---

## 策略确认

**监督学习先行 → 后期 RL 结合** 的路线是正确的。先搭建监督学习框架，打通数据采集、状态编码、动作预测流水线，为后续 PPO 提供：
- 预训练权重（模仿学习 warm start）
- 动作掩码与合法动作过滤
- 状态/动作空间设计参考

---

## 可借鉴规则一览

| 规则 | STS-AI-Master 做法 | 本项目现状 | 建议 |
|------|-------------------|------------|------|
| 动作掩码 | `CardState.is_playable` 直接作为动作掩码 | `get_valid_actions` 已过滤 `is_playable` | ✅ 已对齐 |
| 卡牌伤害/格挡 | 序列化时调用 `calculateCardDamage(null)` 获取**上下文相关**数值 | `encode_state` 用静态 `CARD_STATS` | 可增强：若 Mod 提供实时 damage/block 则使用 |
| 状态结构 | `PlayerState`、`MonsterState`、`CardState` 等强类型 | JSON 字典，字段类似 | 可参考 proto 字段完整性查漏 |
| 合法动作列表 | `valid_actions` 为合法动作 ID 列表 | `get_valid_actions` 返回 0-9 + 99 | ✅ 已对齐 |
| 动作空间 | `play_card` + `card_index` + `target_index` | `play i t` + `end` | 结构等价 |
| 游戏阶段 | `stage`: BATTLE, REWARD, SHOP | `screen_type`、`room_phase` | 等价 |

---

## 1. 卡牌状态：上下文相关 damage/block

**STS-AI-Master**：在手牌序列化时调用 `calculateCardDamage(null)`，导出**当前上下文下**的伤害/格挡（受力量、虚弱、易伤等影响）。

**本项目**：`encode_state` 使用静态 `CARD_STATS`（如 Strike_G=6 伤害），不考虑力量等 buff。

**建议**：
- 若 CommunicationMod 的 `hand` 中每张牌已提供 `damage`、`block` 等实时数值，优先使用。
- 若无，保持静态估算；后续 RL 阶段可考虑在 Mod 侧扩展该字段。

---

## 2. CardState 字段完整性（sts_state.proto）

```protobuf
message CardState {
  string id = 1;
  string name = 2;
  int32 cost = 3;
  string type = 4;
  int32 damage = 5;      // 上下文相关
  string target = 6;     // 单体/全体等
  int32 block = 7;       // 上下文相关
  bool is_upgraded = 8;
  int32 magic_number = 9;
  bool exhaust = 10;
  bool is_playable = 11;  // 动作掩码核心
  int32 price = 12;       // 商店用
}
```

**建议**：检查 `combat_state.hand` 中是否已有 `damage`、`block`、`target`；若有，在 `encode_state` 中纳入特征。

---

## 3. 动作掩码（Action Mask）

**STS-AI-Master**：`CardState.is_playable` 综合考虑能量、卡牌限制与 `cardPlayable`，**直接作为动作掩码**。

**本项目**：`get_valid_actions` 已过滤 `is_playable=false` 且 `cost <= energy`。

**建议**：训练时对非法动作做 **mask**，预测时只从 `valid_actions` 中采样，避免模型输出无效动作。若用 sklearn，可在 `predict_proba` 后对非法动作置 0 再 argmax。

---

## 4. 状态字段对照

| STS-AI-Master | 本项目 | 说明 |
|----------------|--------|------|
| PlayerState.hp, max_hp, energy, block, floor | player.current_hp, energy, block | 等价 |
| MonsterState.hp, max_hp, intent, block | monsters[].current_hp, intent, block | 等价 |
| hand (CardState[]) | combat_state.hand | 等价 |
| master_deck | deck | 等价 |
| screen_type | screen_type, room_phase | 等价 |
| GameOutcome (victory, score) | 若有 game_over 等 | 可扩展用于回合/对局级标签 |

---

## 5. 动作空间设计

**STS-AI-Master**：
```protobuf
message GameAction {
  string action_type = 1;   // play_card, end_turn, select_card...
  int32 card_index = 2;     // 0-based
  int32 target_index = 3;   // 目标怪物索引
}
```

**本项目**：`play {idx+1} {target}`（1-based）+ `end`。

**建议**：内部统一用 0-based（训练、编码），发送给 Mod 时转为 1-based。你们已在 `encode_action`/`decode_action` 中处理，保持即可。

---

## 6. 防死锁机制（可选）

**STS-AI-Master**：协议中 `sequence_id`、`is_waiting_for_input` 用于防指令错位。

**本项目**：Mod 发状态 → 等待响应 → 必须回复。若遇卡顿，可考虑在日志中记录 `sequence_id` 便于排查。

---

## 7. 监督学习特征增强建议

基于 STS-AI-Master 的观测设计，可考虑在 `encode_state` 中补充：

| 特征 | 说明 | 优先级 |
|------|------|--------|
| 每张手牌的实时 damage/block | 若 Mod 提供 | 高 |
| 怪物数量 | 多目标时影响出牌顺序 | 中 |
| 抽牌堆/弃牌堆数量 | 影响过牌价值 | 低 |
| floor / act | 长期策略 | 低（监督学习可先省略） |

---

## 8. 小结

- **已对齐**：动作掩码、合法动作过滤、动作空间（0-based 内部 / 1-based Mod）。
- **可增强**：卡牌 damage/block 若 Mod 提供则用实时值；训练时对非法动作做 mask。
- **可扩展**：参考 `sts_state.proto` 的 CardState、MonsterState 字段查漏补缺。

监督学习框架搭建完成后，这些设计可直接复用到 PPO 的观测空间与动作掩码中。
