# 状态向量 s 表达式与 Mod 转换 — 技术计划

> **模式**：计划模式  
> **任务**：① 写出 s 向量每个维度的精确表达式；② 建立 Mod 日志 → s 向量的精准转换方法。

---

## 一、s 向量完整表达式（723 维）

### 1.1 索引与维度总表

| 区块 | 起始索引 | 结束索引 | 维度 | 累计 |
|------|----------|----------|------|------|
| 1. 玩家核心 | 0 | 17 | 18 | 18 |
| 2. 手牌 | 18 | 247 | 230 | 248 |
| 3. 牌库摘要 | 248 | 255 | 8 | 256 |
| 4. 玩家 Powers | 256 | 315 | 60 | 316 |
| 5. 怪物 | 316 | 453 | 138 | 454 |
| 6. 遗物 | 454 | 653 | 200 | 654 |
| 7. 药水 | 654 | 708 | 55 | 709 |
| 8. 全局 | 709 | 722 | 14 | 723 |

---

### 1.2 区块 1：玩家核心 (s[0]–s[17])

| 索引 | 名称 | 表达式 | 类型 | 备注 |
|------|------|--------|------|------|
| 0 | hp_ratio | clamp(player.current_hp / max(player.max_hp, 1), 0, 1) | float | max_hp=0 时取 0 |
| 1 | max_hp_norm | min(player.max_hp, 999) / 999 | float | |
| 2 | block_norm | min(player.block, 50) / 50 | float | |
| 3 | energy_norm | min(player.energy, 10) / 10 | float | |
| 4 | max_energy_norm | min(max_energy, 10) / 10 | float | 从遗物推断，默认 3 |
| 5 | gold_norm | min(game_state.gold, 999) / 999 | float | |
| 6 | strength_norm | min(parse_strength(player.powers), 30) / 30 | float | 从 powers 解析 |
| 7 | dexterity_norm | min(parse_dexterity(player.powers), 30) / 30 | float | 从 powers 解析 |
| 8 | weak_norm | min(parse_weak(player.powers), 10) / 10 | float | Weakened |
| 9 | vulnerable_norm | min(parse_vulnerable(player.powers), 10) / 10 | float | Vulnerable |
| 10 | frail_norm | min(parse_frail(player.powers), 10) / 10 | float | Frail |
| 11 | focus_norm | min(parse_focus(player.powers), 10) / 10 | float | Focus（缺陷） |
| 12 | hand_count_norm | min(len(hand), 10) / 10 | float | |
| 13 | draw_count_norm | min(len(draw_pile), 50) / 50 | float | |
| 14 | discard_count_norm | min(len(discard_pile), 50) / 50 | float | |
| 15 | exhaust_count_norm | min(len(exhaust_pile), 30) / 30 | float | |
| 16 | cards_discarded_norm | min(cards_discarded_this_turn, 10) / 10 | float | |
| 17 | times_damaged_norm | min(times_damaged, 50) / 50 | float | |

**Power 解析映射**：Strength→strength, Dexterity→dexterity, Weakened→weak, Vulnerable→vulnerable, Frail→frail, Bias→focus（缺陷用）

---

### 1.3 区块 2：手牌 (s[18]–s[247])

#### 2a. multi-hot (s[18]–s[217])

| 索引 | 表达式 | 说明 |
|------|--------|------|
| 18 + k | 1 若 hand 中存在 card.id 在 encoder_v2_ids.cards 中索引为 k 的卡牌，否则 0；同 ID 多张则累加 | k ∈ [0, 199] |

**公式**：s[18+k] = sum(1 for c in hand if card_id_to_index(c.id) == k)

#### 2b. 每槽详情 (s[218]–s[247])

每槽 3 维，共 10 槽。槽位 i ∈ [0, 9]：

| 子索引 | 表达式 | 说明 |
|--------|--------|------|
| 218 + i*3 + 0 | cost_norm | min(max(cost, 0), 3) / 3；cost<0 时为 0 |
| 218 + i*3 + 1 | type_embed | ATTACK=0.1, SKILL=0.3, POWER=0.5, STATUS=0.0, CURSE=0.0 |
| 218 + i*3 + 2 | is_playable | 1 或 0 |

不足 10 张时，空槽位填 (0, 0, 0)。

---

### 1.4 区块 3：牌库摘要 (s[248]–s[255])

| 索引 | 名称 | 表达式 |
|------|------|--------|
| 248 | draw_attack_ratio | count(draw_pile, type=ATTACK) / max(len(draw_pile), 1) |
| 249 | draw_skill_ratio | count(draw_pile, type=SKILL) / max(len(draw_pile), 1) |
| 250 | draw_power_ratio | count(draw_pile, type=POWER) / max(len(draw_pile), 1) |
| 251 | draw_status_curse_ratio | count(draw_pile, type∈{STATUS,CURSE}) / max(len(draw_pile), 1) |
| 252 | discard_attack_ratio | 同上，discard_pile |
| 253 | discard_skill_ratio | 同上 |
| 254 | discard_power_ratio | 同上 |
| 255 | discard_status_curse_ratio | 同上 |

空堆时对应填 0。

---

### 1.5 区块 4：玩家 Powers (s[256]–s[315])

| 索引 | 表达式 |
|------|--------|
| 256 + k | sum(p.amount for p in player.powers if power_id_to_index(p.id) == k)，k ∈ [0, 59] |

同一 power 多段可累加；或约定取 max，由实现固定。

---

### 1.6 区块 5：怪物 (s[316]–s[453])

每怪物 23 维 × 6 槽。怪物槽位 m ∈ [0, 5]：

| 子索引 | 名称 | 表达式 |
|--------|------|--------|
| 316+m*23+0 | hp_ratio | current_hp / max(max_hp, 1) |
| 316+m*23+1 | block_norm | min(block, 50) / 50 |
| 316+m*23+2 ~ +14 | intent_onehot | 13 维，intent 在 encoder_v2_ids.intents 中索引处为 1 |
| 316+m*23+15 | damage_norm | min(move_adjusted_damage * move_hits, 50) / 50，负值取 0 |
| 316+m*23+16 | alive | 1 - is_gone（0 或 1） |
| 316+m*23+17 | strength_norm | 从 powers 提取 Strength |
| 316+m*23+18 | vulnerable_norm | 从 powers 提取 Vulnerable |
| 316+m*23+19 | weak_norm | 从 powers 提取 Weak |
| 316+m*23+20 | poison_norm | 从 powers 提取 Poison |
| 316+m*23+21 | curl_up_norm | 从 powers 提取 Curl Up |
| 316+m*23+22 | other_powers_count_norm | min(len(powers) - 上述5种数量, 10) / 10 |

不足 6 个怪物时，空槽位填 0。意图 one-hot 顺序与 encoder_v2_ids.intents 一致。

---

### 1.7 区块 6：遗物 (s[454]–s[653])

| 索引 | 表达式 |
|------|--------|
| 454 + k | 1 若 relics 中存在 relic.id 在 encoder_v2_ids.relics 中索引为 k，否则 0；同 ID 多张累加 | k ∈ [0, 199] |

---

### 1.8 区块 7：药水 (s[654]–s[708])

| 索引 | 表达式 |
|------|--------|
| 654 + k | 1 若 potions 中存在 potion.id 在 encoder_v2_ids.potions 中索引为 k，否则 0 | k ∈ [0, 49] |
| 704 | potions[0].can_use ? 1 : 0 |
| 705 | potions[1].can_use ? 1 : 0 |
| 706 | potions[2].can_use ? 1 : 0 |
| 707 | potions[3].can_use ? 1 : 0 |
| 708 | potions[4].can_use ? 1 : 0 |

不足 5 个药水槽时，对应 slot 填 0。

---

### 1.9 区块 8：全局 (s[709]–s[722])

| 索引 | 名称 | 表达式 |
|------|------|--------|
| 709 | floor_norm | min(floor, 60) / 60 |
| 710 | act_1 | 1 if act==1 else 0 |
| 711 | act_2 | 1 if act==2 else 0 |
| 712 | act_3 | 1 if act==3 else 0 |
| 713 | room_COMBAT | 1 if room_phase==COMBAT else 0 |
| 714 | room_EVENT | 1 if room_phase==EVENT else 0 |
| 715 | room_MAP | 1 if room_phase==MAP else 0 |
| 716 | room_SHOP | 1 if room_phase==SHOP else 0 |
| 717 | room_REST | 1 if room_phase==REST else 0 |
| 718 | room_BOSS | 1 if room_phase==BOSS else 0 |
| 719 | room_NONE | 1 if room_phase==NONE else 0 |
| 720 | room_CARD_REWARD | 1 if room_phase==CARD_REWARD else 0 |
| 721 | room_UNKNOWN | 1 if room_phase==UNKNOWN else 0 |
| 722 | turn_norm | min(turn, 30) / 30 |

room_phase 若为其他值，映射到 UNKNOWN。无 combat_state 时 turn 填 0。

---

## 二、Mod 日志 → s 向量 精准转换表

### 2.1 输入数据结构（Mod 单帧 JSON）

```
response
├── game_state
│   ├── floor (int)
│   ├── act (int)
│   ├── room_phase (str)
│   ├── gold (int)
│   ├── current_hp (int)        # 非战斗时
│   ├── max_hp (int)            # 非战斗时
│   ├── relics: [{id, counter}]
│   ├── potions: [{id, can_use, can_discard, requires_target}]
│   └── combat_state (可选)
│       ├── hand: [{id, cost, type, upgrades, ethereal, exhausts, has_target, is_playable, rarity}]
│       ├── draw_pile: [...]
│       ├── discard_pile: [...]
│       ├── exhaust_pile: [...]
│       ├── monsters: [{id, current_hp, max_hp, block, intent, move_id, move_base_damage, move_adjusted_damage, move_hits, is_gone, half_dead, powers:[{id, amount}]}]
│       ├── player: {energy, current_hp, max_hp, block, orbs, powers:[{id, amount}]}
│       ├── turn (int)
│       ├── cards_discarded_this_turn (int)
│       └── times_damaged (int)
```

### 2.2 字段 → s 索引 映射表

| Mod 路径 | 转换规则 | s 索引 |
|----------|----------|--------|
| game_state.gold | gold / 999, clamp | 5 |
| game_state.floor | floor / 60, clamp | 709 |
| game_state.act | one-hot | 710–712 |
| game_state.room_phase | one-hot | 713–721 |
| game_state.relics[].id | id→index, multi-hot | 454–653 |
| game_state.potions[].id | id→index, multi-hot | 654–703 |
| game_state.potions[i].can_use | 0/1 | 704–708 |
| combat_state.player.energy | energy / 10, clamp | 3 |
| combat_state.player.current_hp | 与 max_hp 计算比例 | 0 |
| combat_state.player.max_hp | max_hp / 999 | 1 |
| combat_state.player.block | block / 50, clamp | 2 |
| combat_state.player.powers | 解析 strength/weak 等 + multi-hot | 6–11, 256–315 |
| combat_state.hand | 见 2.3 | 18–247 |
| combat_state.draw_pile | len + type 统计 | 13, 248–251 |
| combat_state.discard_pile | len + type 统计 | 14, 252–255 |
| combat_state.exhaust_pile | len | 15 |
| combat_state.turn | turn / 30, clamp | 722 |
| combat_state.cards_discarded_this_turn | / 10, clamp | 16 |
| combat_state.times_damaged | / 50, clamp | 17 |
| combat_state.monsters | 见 2.4 | 316–453 |

### 2.3 手牌转换流程

1. 取 `combat_state.hand`，若无则 s[18:248]=0
2. 对每张卡 c：`idx = card_id_to_index(normalize_id(c.id))`，s[18+idx] += 1
3. 对前 10 张（不足补空）：
   - cost_norm = min(max(c.cost,0),3)/3
   - type_embed = TYPE_MAP.get(c.type, 0)
   - is_playable = 1 if c.is_playable else 0
4. 写入 s[218:248]

### 2.4 怪物转换流程

1. 取 `combat_state.monsters`，截断或补零至 6 个
2. 对每个怪物 m，i ∈ [0,5]：
   - hp_ratio, block_norm 直接计算
   - intent → one-hot 13 维（查 encoder_v2_ids.intents）
   - damage = max(0, move_adjusted_damage * move_hits)
   - alive = 1 - int(m.is_gone)
   - 从 m.powers 解析 Strength, Vulnerable, Weak, Poison, Curl Up
   - other_powers_count = len(powers) - 上述 5 种
3. 写入 s[316+i*23 : 316+(i+1)*23]

### 2.5 非战斗状态

- 无 `combat_state`：s[18:316]、s[454:709] 中与 combat 相关的填 0
- 区块 1 中 player 相关：用 game_state.current_hp, max_hp；len(hand) 等填 0
- 区块 6 遗物、区块 8 全局：仍从 game_state 读取

---

## 三、辅助函数规格

### 3.1 ID 归一化

```
normalize_id(raw: str) -> str:
  - 转小写
  - 空格 ↔ 下划线 互换（或统一为下划线）
  - 去除首尾空白
```

### 3.2 查表函数

| 函数 | 输入 | 输出 | 未找到 |
|------|------|------|--------|
| card_id_to_index(id) | str | int ∈ [0,199] | 0 |
| relic_id_to_index(id) | str | int ∈ [0,199] | 0 |
| potion_id_to_index(id) | str | int ∈ [0,49] | 0 |
| power_id_to_index(id) | str | int ∈ [0,59] | 0 |
| intent_to_index(intent) | str | int ∈ [0,12] | 0 |

查表前对 id 做 normalize_id；encoder_v2_ids 中列表顺序即 index。

### 3.3 Power 解析

| 目标 | Power ID | 解析逻辑 |
|------|-----------|----------|
| strength | Strength, Anger, Flex 等 | sum(amount) |
| dexterity | Dexterity | sum(amount) |
| weak | Weakened, Weak | sum(amount) |
| vulnerable | Vulnerable | sum(amount) |
| frail | Frail | sum(amount) |
| focus | Bias, Focus | sum(amount) |

---

## 四、实施检查清单

1. 在 `docs/状态向量s_技术规范.md` 中新增附录「s 向量完整表达式」，将本文档第一节内容合并或引用
2. 在 `docs/状态向量s_技术规范.md` 中新增附录「Mod → s 转换表」，将本文档第二节内容合并或引用
3. 创建 `src/training/encoder_utils.py`，实现 normalize_id、card_id_to_index、relic_id_to_index、potion_id_to_index、power_id_to_index、intent_to_index
4. 创建 `src/training/power_parser.py`，实现 parse_strength、parse_dexterity、parse_weak、parse_vulnerable、parse_frail、parse_focus，输入为 powers 列表，输出为 int
5. 创建 `src/training/encoder_v2.py`，实现 StateEncoderV2 类
6. 在 StateEncoderV2 中实现 _encode_block1_player_core，输出 18 维，严格按 s[0]–s[17] 表达式
7. 实现 _encode_block2_hand，输出 230 维，严格按 s[18]–s[247] 表达式
8. 实现 _encode_block3_deck_summary，输出 8 维，严格按 s[248]–s[255] 表达式
9. 实现 _encode_block4_player_powers，输出 60 维，严格按 s[256]–s[315] 表达式
10. 实现 _encode_block5_monsters，输出 138 维，严格按 s[316]–s[453] 表达式
11. 实现 _encode_block6_relics，输出 200 维，严格按 s[454]–s[653] 表达式
12. 实现 _encode_block7_potions，输出 55 维，严格按 s[654]–s[708] 表达式
13. 实现 _encode_block8_global，输出 14 维，严格按 s[709]–s[722] 表达式
14. 实现 encode(mod_response: dict) -> np.ndarray，按顺序拼接 8 区块，输出 shape=(723,)，dtype=np.float32
15. 实现 get_output_dim() -> int，返回 723
16. 处理缺失字段：combat_state 缺失时按非战斗逻辑；player 缺失时用 game_state 的 current_hp/max_hp；各 list 缺失时视为 []
17. 加载 encoder_v2_ids.yaml，在初始化时构建 id→index 字典，供查表使用
18. 编写单元测试，对单帧 Mod JSON 调用 encode，验证输出 shape、各区块范围、已知场景数值正确性
