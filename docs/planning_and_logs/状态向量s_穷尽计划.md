# 状态向量 s 穷尽计划

> **原则**：维数多不要紧，后面用 embedding 降维；**穷尽每一个与 action 有关的决策参考点**。
>
> **目标**：Mod 日志每一条 → 标准化 1×n 维 s → embedding 层 → 训练。

---

## 一、决策上下文与 Action 映射

| 决策上下文 | Action ID 范围 | 关键决策参考点 |
|------------|----------------|----------------|
| **战斗出牌** | 0–69, 170 | 手牌、能量、怪物、遗物、药水、牌库、Powers |
| **战斗药水** | 70–109 | 同上 + 药水 can_use、requires_target |
| **选择（事件/地图/奖励/商店/涅奥/火堆）** | 110–169 | screen_type、选项列表、当前资源、牌组、遗物 |
| **确认/前进** | 171 | 结算界面、是否胜利/失败 |
| **取消** | 172 | 覆盖层状态 |

**穷尽原则**：任一决策上下文可能用到的 state，全部纳入 s；该上下文不适用时对应维度填 0。

---

## 二、s 向量区块穷尽设计

### 2.1 总维度估算

| 区块 | 维度 | 说明 |
|------|------|------|
| 1. 玩家核心 | 20 | 扩展 max_energy 推断、orb 相关（缺陷） |
| 2. 手牌 | 10×(3+271) = 2740 | 每槽：cost/type/playable + 卡牌 multi-hot 271 |
| 2'. 手牌简化 | 271+10×6 = 331 | multi-hot 271 + 每槽 6 维详情 |
| 3. 抽牌堆 | 271+8 | full multi-hot 271 + 类型占比 8 |
| 4. 弃牌堆 | 271+8 | full multi-hot 271 + 类型占比 8 |
| 5. 消耗堆 | 271 | full multi-hot |
| 6. 玩家 Powers | 80 | 穷尽 Power ID，含 amount |
| 7. 怪物 | 6×50 | 每怪：hp/block/intent/damage/alive + powers 等 |
| 8. 遗物 | 180 | multi-hot 179 + UNKNOWN |
| 9. 药水 | 45+5×4 | multi-hot 45 + 每槽 can_use/can_discard/requires_target |
| 10. 全局/房间 | 30 | floor/act/room_phase/turn/available_commands 等 |
| 11. 非战斗：地图 | 50 | next_nodes 类型、距离、精英标记等 |
| 12. 非战斗：奖励 | 5×271+20 | 卡牌奖励 5 张×271 + 遗物/药水槽 |
| 13. 非战斗：商店 | 15×271+30 | 卡牌/遗物/药水在售、价格、删牌费 |
| 14. 非战斗：事件 | 60 | event_id、options 数量与类型 |

**简化版（优先实现）**：合并 2'、3 摘要、4 摘要、5 摘要，先不做 11–14 的完整编码，用 room_phase one-hot 区分；非战斗时 2–9 填 0。

---

## 三、穷尽区块详细规格

### 区块 1：玩家核心（20 维）

| 索引 | 名称 | 来源 | 表达式 |
|------|------|------|--------|
| 0 | hp_ratio | player | current_hp / max(max_hp, 1) |
| 1 | max_hp_norm | player | min(max_hp, 999) / 999 |
| 2 | block_norm | player | min(block, 99) / 99 |
| 3 | energy_norm | player | min(energy, 10) / 10 |
| 4 | max_energy_norm | 遗物推断 | min(max_energy, 10) / 10 |
| 5 | gold_norm | game_state | min(gold, 999) / 999 |
| 6 | strength_norm | powers | min(parse_strength, 50) / 50 |
| 7 | dexterity_norm | powers | min(parse_dexterity, 30) / 30 |
| 8 | weak_norm | powers | min(parse_weak, 15) / 15 |
| 9 | vulnerable_norm | powers | min(parse_vulnerable, 15) / 15 |
| 10 | frail_norm | powers | min(parse_frail, 15) / 15 |
| 11 | focus_norm | powers | min(parse_focus, 15) / 15 |
| 12 | hand_count_norm | hand | min(len(hand), 10) / 10 |
| 13 | draw_count_norm | draw_pile | min(len, 80) / 80 |
| 14 | discard_count_norm | discard_pile | min(len, 80) / 80 |
| 15 | exhaust_count_norm | exhaust_pile | min(len, 50) / 50 |
| 16 | cards_discarded_norm | combat | min(cards_discarded_this_turn, 15) / 15 |
| 17 | times_damaged_norm | combat | min(times_damaged, 50) / 50 |
| 18 | orb_slots_norm | orbs | min(orb_slots, 10) / 10（缺陷） |
| 19 | turn_norm | combat | min(turn, 50) / 50 |

---

### 区块 2：手牌（331 维）

#### 2a. 手牌 multi-hot（271 维）

| 索引 | 表达式 |
|------|--------|
| 20 + k | hand 中 card.id 在 cards 列表索引 k 的张数，k ∈ [0, 270] |

**cards 穷尽**：270 卡 + UNKNOWN=271。按穷尽清单。

#### 2b. 每槽详情（10 槽 × 6 维 = 60 维）

| 子索引 | 名称 | 表达式 |
|--------|------|--------|
| 291 + i*6 + 0 | cost_norm | min(max(cost,0), 5) / 5 |
| 291 + i*6 + 1 | type_embed | ATTACK=0.2, SKILL=0.4, POWER=0.6, STATUS=0.0, CURSE=0.0 |
| 291 + i*6 + 2 | is_playable | 0/1 |
| 291 + i*6 + 3 | has_target | 0/1 |
| 291 + i*6 + 4 | upgrades_norm | min(upgrades, 2) / 2 |
| 291 + i*6 + 5 | ethereal_or_exhaust | 1 若 ethereal 或 exhausts  else 0 |

---

### 区块 3：抽牌堆（279 维）

| 索引 | 表达式 |
|------|--------|
| 351 + k | draw_pile 中 card.id 在 cards 中索引 k 的张数，k ∈ [0, 270] |
| 622–629 | draw_attack_ratio, draw_skill_ratio, draw_power_ratio, draw_status_curse_ratio, discard 同理 |

---

### 区块 4：弃牌堆（279 维）

同上，discard_pile 的 full multi-hot 271 + 类型占比 8。

---

### 区块 5：消耗堆（271 维）

exhaust_pile 的 full multi-hot 271。

---

### 区块 6：玩家 Powers（80 维）

| 索引 | 表达式 |
|------|--------|
| 1640 + k | sum(p.amount for p in player.powers if power_id_to_index(p.id)==k)，k ∈ [0, 79] |

**powers 穷尽**：按 Wiki + Raw_Data 补全至 80。

---

### 区块 7：怪物（6 × 50 = 300 维）

每怪物 50 维：

| 子索引 | 名称 | 表达式 |
|--------|------|--------|
| +0 | hp_ratio | current_hp / max(max_hp, 1) |
| +1 | block_norm | min(block, 99) / 99 |
| +2~+14 | intent_onehot | 13 维 |
| +15 | damage_norm | min(adjusted_damage*hits, 99) / 99 |
| +16 | alive | 1 - is_gone |
| +17 | half_dead | 0/1 |
| +18 | strength_norm | 从 powers |
| +19 | vulnerable_norm | 从 powers |
| +20 | weak_norm | 从 powers |
| +21 | poison_norm | 从 powers |
| +22 | curl_up_norm | 从 powers |
| +23 | monster_id_embed | monster.id → 0~1 归一化（或 one-hot 若怪物类型有限） |
| +24~+49 | powers_multi_hot | 怪物 powers 的 26 维 multi-hot |

---

### 区块 8：遗物（180 维）

| 索引 | 表达式 |
|------|--------|
| 1940 + k | relics 中 relic.id 在 relics 列表索引 k 的数量，k ∈ [0, 179] |

---

### 区块 9：药水（65 维）

| 索引 | 表达式 |
|------|--------|
| 2120 + k | potions 中 potion.id 在 potions 列表索引 k 的数量，k ∈ [0, 44] |
| 2165 + i*4 + 0 | potions[i].can_use |
| 2165 + i*4 + 1 | potions[i].can_discard |
| 2165 + i*4 + 2 | potions[i].requires_target |
| 2165 + i*4 + 3 | potions[i] 槽位是否为空 |

---

### 区块 10：全局/房间（35 维）

| 索引 | 名称 | 表达式 |
|------|------|--------|
| 2185 | floor_norm | min(floor, 60) / 60 |
| 2186–2188 | act_onehot | act 1/2/3 |
| 2189–2200 | room_phase_onehot | COMBAT, EVENT, MAP, SHOP, REST, BOSS, NONE, CARD_REWARD, BOSS_REWARD, SHOP_SCREEN, ... |
| 2201 | available_play | 1 if "play" in available_commands else 0 |
| 2202 | available_end | 1 if "end" in available_commands else 0 |
| 2203 | available_choose | 1 if "choose" in available_commands else 0 |
| 2204 | available_proceed | 1 if "proceed" in available_commands else 0 |
| 2205 | available_potion | 1 if "potion" in available_commands else 0 |
| 2206 | choice_count_norm | min(len(choice_list), 60) / 60 |
| 2207–2219 | 预留 | 扩展用 |

---

### 区块 11–14：非战斗决策（可选扩展）

当 room_phase = MAP / CARD_REWARD / SHOP / EVENT 时，screen_state 中有：

- **MAP**：next_nodes（类型、距离、是否精英、是否商店等）→ 编码为固定槽位
- **CARD_REWARD**：cards 列表（3–5 张）→ 每张 271 维 multi-hot + 稀有度
- **SHOP**：cards/relics/potions 在售、价格、删牌费
- **EVENT**：event_id、options 数量

**建议**：Phase 1 用 room_phase one-hot 区分，非战斗时 2–9 填 0；Phase 2 再补 11–14 的完整编码。

---

## 四、穷尽维度汇总（Phase 1）

| 区块 | 起始 | 结束 | 维度 |
|------|------|------|------|
| 1. 玩家核心 | 0 | 19 | 20 |
| 2. 手牌 | 20 | 350 | 331 |
| 3. 抽牌堆 | 351 | 629 | 279 |
| 4. 弃牌堆 | 630 | 908 | 279 |
| 5. 消耗堆 | 909 | 1179 | 271 |
| 6. 玩家 Powers | 1180 | 1259 | 80 |
| 7. 怪物 | 1260 | 1559 | 300 |
| 8. 遗物 | 1560 | 1739 | 180 |
| 9. 药水 | 1740 | 1804 | 65 |
| 10. 全局 | 1805 | 1839 | 35 |
| **合计** | | | **1840** |

**Phase 2 扩展**（含非战斗完整编码）：+500 ~ 1000 维，总计约 **2500**。

---

## 五、encoder_v2_ids 穷尽更新

| 项目 | 当前 | 穷尽目标 | 来源 |
|------|------|----------|------|
| cards | ~200 | **271** | 穷尽清单：270 + UNKNOWN |
| relics | ~180 有重复 | **180** | 穷尽清单：179 + UNKNOWN |
| potions | ~45 | **45** | Wiki 约 40 种 + UNKNOWN |
| powers | ~60 | **80** | Wiki Buffs/Debuffs 穷尽 |
| intents | 13 | **13** | 保持 |

---

## 六、实施检查清单

### 6.1 配置与 ID 映射

1. [ ] 按穷尽清单更新 `encoder_v2_ids.yaml`：cards 271、relics 180、potions 45、powers 80
2. [ ] 实现 `encoder_utils.py`：relic_id_to_index、power_id_to_index、potion_id_to_index、intent_to_index
3. [ ] 验证 Mod 实际发送的 ID 与 YAML 的覆盖（运行 extract_ids_from_raw 检查漏网）

### 6.2 编码器实现

4. [ ] 实现区块 1（20 维）
5. [ ] 实现区块 2（331 维）：手牌 multi-hot 271 + 每槽 6 维
6. [ ] 实现区块 3（279 维）：抽牌堆 full multi-hot + 类型占比
7. [ ] 实现区块 4（279 维）：弃牌堆 full multi-hot + 类型占比
8. [ ] 实现区块 5（271 维）：消耗堆 full multi-hot
9. [ ] 实现区块 6（80 维）：玩家 Powers multi-hot
10. [ ] 实现区块 7（300 维）：怪物 6×50
11. [ ] 实现区块 8（180 维）：遗物 multi-hot
12. [ ] 实现区块 9（65 维）：药水 multi-hot + 每槽 4 维
13. [ ] 实现区块 10（35 维）：全局/房间
14. [ ] 实现 `encode(mod_response) -> np.ndarray`，输出 shape=(1840,)
15. [ ] 非战斗帧：区块 2–9 填 0，区块 1 用 game_state 的 hp/gold，区块 10 正常

### 6.3 验证

16. [ ] 单元测试：已知 Mod JSON → 验证各区块数值
17. [ ] 用 Raw_Data 批量跑 encode，检查无异常、shape 正确
18. [ ] 更新 `状态向量s_技术规范.md`，将本计划作为附录

---

## 七、与 Embedding 的衔接

- **离散 ID 类**（卡牌、遗物、药水、Power、怪物 ID）：可做 embedding，vocab_size = 穷尽数 + 1
- **连续标量**（hp_ratio、energy_norm 等）：直接输入或简单线性层
- **one-hot**（room_phase、intent）：可 embedding 或保持

**后续**：在 `encoder_v2.encode()` 输出 1840 维后，接 `nn.Embedding` + 拼接，再进 MLP/Transformer。
