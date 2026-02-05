# 状态向量 s 穷尽计划 — 详细技术规范

> **模式**：计划模式（详细版）  
> **原则**：穷尽每一个与 action 有关的决策参考点；维数多不要紧，后续 embedding 降维。  
> **目标**：Mod 日志每一条 → 标准化 1×1840 维 s → embedding 层 → 训练。

---

## 一、Mod 输入数据结构（完整路径）

```
mod_response (顶层)
├── in_game: bool
├── ready_for_command: bool
├── available_commands: List[str]   # ["play","end"], ["choose","proceed"], 等
├── game_state: dict
│   ├── floor: int
│   ├── act: int
│   ├── room_phase: str              # COMBAT, EVENT, MAP, SHOP, REST, BOSS, NONE, CARD_REWARD, ...
│   ├── screen_type: str             # 可能与 room_phase 等价或补充
│   ├── gold: int
│   ├── current_hp: int              # 非战斗时
│   ├── max_hp: int                  # 非战斗时
│   ├── relics: List[{id, name?, counter?}]
│   ├── potions: List[{id, name?, can_use, can_discard?, requires_target?}]
│   ├── screen_state: dict           # 非战斗时：event_id, next_nodes, options, 等
│   └── combat_state: dict | null    # 战斗时存在
│       ├── hand: List[{id, name?, cost, type, upgrades?, ethereal?, exhausts?, has_target?, is_playable, rarity?}]
│       ├── draw_pile: List[同 hand 元素]
│       ├── discard_pile: List[同 hand 元素]
│       ├── exhaust_pile: List[同 hand 元素]
│       ├── monsters: List[{id, name?, current_hp, max_hp, block, intent, move_id?, move_base_damage?, move_adjusted_damage?, move_hits?, is_gone, half_dead?, powers:[{id, amount}]}]
│       ├── player: {energy, current_hp, max_hp, block, orbs?, powers:[{id, amount}]}
│       ├── turn: int
│       ├── cards_discarded_this_turn: int
│       └── times_damaged: int
```

**缺失字段处理**：任一路径缺失时，使用默认值（见各区块）。

---

## 二、encoder_ids.yaml 穷尽规格

### 2.1 cards 段（271 条）

**顺序**：UNKNOWN(0) → 诅咒(14) → 状态(12) → 铁甲(73) → 静默(73) → 缺陷(73) → 观者(75) → 无色(47)。

**索引 0**：UNKNOWN（未知卡牌映射到此）

**索引 1–14**：诅咒（按穷尽清单文档 1.7 节顺序）

**索引 15–26**：状态（Burn, Dazed, Slimed, Void, Wound 等，按穷尽清单 1.8）

**索引 27–99**：铁甲战士 73 张（Basic 3 + Common 19 + Uncommon 27 + Rare 16）

**索引 100–172**：静默猎人 73 张

**索引 173–245**：缺陷机器人 73 张

**索引 246–320**：观者 75 张

**索引 321–367**：无色 47 张

**文件路径**：`/Volumes/T7/AI_THE_SPIRE/configs/encoder_ids.yaml`

### 2.2 relics 段（180 条）

**顺序**：UNKNOWN(0) → 起始(4) → 普通(43) → 稀有(43) → 稀有(33) → Boss(34) → 商店(24) → 事件(22)。

**文件路径**：同上

### 2.3 potions 段（45 条）

**顺序**：UNKNOWN(0) → 按 Wiki Potions List 穷尽约 44 种。

**文件路径**：同上

### 2.4 powers 段（80 条）

**顺序**：UNKNOWN(0) → 玩家 Buffs（Strength, Dexterity, Anger, Flex 等）→ Debuffs（Weakened, Vulnerable, Frail）→ 怪物 Powers（Poison, Curl Up, Thorns 等）→ 其他（按 Wiki Buffs and Debuffs 穷尽）。

**文件路径**：同上

### 2.5 intents 段（13 条）

**顺序**：UNKNOWN, ATTACK, DEFEND, BUFF, DEBUFF, ATTACK_BUFF, ATTACK_DEBUFF, STRONG_DEBUFF, DEFEND_BUFF, SLEEP, STUN, DEBUG, NONE。

**文件路径**：同上

---

## 三、区块 1：玩家核心 — 逐维规格（20 维）

| 索引 | 名称 | Mod 路径 | 表达式 | 缺省 |
|------|------|----------|--------|------|
| 0 | hp_ratio | combat_state.player.current_hp, max_hp；无则 game_state | current_hp / max(max_hp, 1)，clamp(0,1) | 0 |
| 1 | max_hp_norm | player.max_hp 或 game_state.max_hp | min(v, 999) / 999 | 70/999 |
| 2 | block_norm | combat_state.player.block | min(v, 99) / 99 | 0 |
| 3 | energy_norm | combat_state.player.energy | min(v, 10) / 10 | 0（非战斗） |
| 4 | max_energy_norm | 从 relics 推断（Coffee Dripper=1, Boss 遗物等） | min(v, 10) / 10 | 3/10 |
| 5 | gold_norm | game_state.gold | min(v, 999) / 999 | 0 |
| 6 | strength_norm | player.powers 解析 | min(parse_strength, 50) / 50 | 0 |
| 7 | dexterity_norm | player.powers 解析 | min(parse_dexterity, 30) / 30 | 0 |
| 8 | weak_norm | player.powers 解析 | min(parse_weak, 15) / 15 | 0 |
| 9 | vulnerable_norm | player.powers 解析 | min(parse_vulnerable, 15) / 15 | 0 |
| 10 | frail_norm | player.powers 解析 | min(parse_frail, 15) / 15 | 0 |
| 11 | focus_norm | player.powers 解析 | min(parse_focus, 15) / 15 | 0 |
| 12 | hand_count_norm | len(combat_state.hand) | min(v, 10) / 10 | 0（非战斗） |
| 13 | draw_count_norm | len(combat_state.draw_pile) | min(v, 80) / 80 | 0（非战斗） |
| 14 | discard_count_norm | len(combat_state.discard_pile) | min(v, 80) / 80 | 0（非战斗） |
| 15 | exhaust_count_norm | len(combat_state.exhaust_pile) | min(v, 50) / 50 | 0（非战斗） |
| 16 | cards_discarded_norm | combat_state.cards_discarded_this_turn | min(v, 15) / 15 | 0 |
| 17 | times_damaged_norm | combat_state.times_damaged | min(v, 50) / 50 | 0 |
| 18 | orb_slots_norm | player.orbs 当前 orb 数（**缺陷机器人**专属，槽位上限 **10**） | min(len(orbs), 10) / 10 | 0 |
| 19 | turn_norm | combat_state.turn | min(v, 50) / 50 | 0（非战斗） |

**实现函数**：`_encode_block1_player_core(mod_response: dict) -> np.ndarray`，输出 shape=(20,)，dtype=float32。

**文件**：`src/training/encoder_v2.py`

---

## 四、区块 2：手牌 — 逐维规格（331 维）

### 4.1 手牌 multi-hot（s[20]–s[290]，271 维）

| 索引范围 | 表达式 |
|----------|--------|
| 20 + k, k∈[0,270] | 对 hand 中每张卡 c：idx=card_id_to_index(normalize_id(c.id))；s[20+idx] += 1 |

**缺省**：无 combat_state 或 hand 为空时，s[20:291] 全 0。

### 4.2 每槽详情（s[291]–s[350]，60 维）

槽位 i ∈ [0, 9]，每槽 6 维：

| 子索引 | 名称 | Mod 路径 | 表达式 | 空槽 |
|--------|------|----------|--------|------|
| 291+i*6+0 | cost_norm | hand[i].cost | min(max(cost,0), 5) / 5 | 0 |
| 291+i*6+1 | type_embed | hand[i].type | ATTACK=0.2, SKILL=0.4, POWER=0.6, STATUS=0.0, CURSE=0.0, 其他=0 | 0 |
| 291+i*6+2 | is_playable | hand[i].is_playable | 1 if True else 0 | 0 |
| 291+i*6+3 | has_target | hand[i].has_target | 1 if True else 0 | 0 |
| 291+i*6+4 | upgrades_norm | hand[i].upgrades | min(v, 2) / 2，缺省 0 | 0 |
| 291+i*6+5 | ethereal_or_exhaust | hand[i].ethereal, exhausts | 1 若 ethereal 或 exhausts 为 True  else 0 | 0 |

**实现函数**：`_encode_block2_hand(mod_response) -> np.ndarray`，输出 shape=(331,)。

**文件**：`src/training/encoder_v2.py`

---

## 五、区块 3：抽牌堆 — 逐维规格（279 维）

### 5.1 full multi-hot（s[351]–s[621]，271 维）

| 索引范围 | 表达式 |
|----------|--------|
| 351 + k, k∈[0,270] | 对 draw_pile 中每张卡 c：idx=card_id_to_index(...)；s[351+idx] += 1 |

### 5.2 类型占比（s[622]–s[629]，8 维）

| 索引 | 名称 | 表达式 |
|------|------|--------|
| 622 | draw_attack_ratio | count(draw_pile, type=ATTACK) / max(len(draw_pile), 1) |
| 623 | draw_skill_ratio | 同上 SKILL |
| 624 | draw_power_ratio | 同上 POWER |
| 625 | draw_status_curse_ratio | 同上 type in (STATUS, CURSE) |
| 626 | discard_attack_ratio | 同上，discard_pile |
| 627 | discard_skill_ratio | 同上 |
| 628 | discard_power_ratio | 同上 |
| 629 | discard_status_curse_ratio | 同上 |

**缺省**：空堆时比值为 0。

**实现函数**：`_encode_block3_draw_pile(mod_response) -> np.ndarray`，输出 shape=(279,)。

**文件**：`src/training/encoder_v2.py`

---

## 六、区块 4：弃牌堆 — 逐维规格（279 维）

与区块 3 结构相同，数据来源为 discard_pile。

| 索引范围 | 数据来源 |
|----------|----------|
| 630 + k, k∈[0,270] | discard_pile multi-hot |
| 901–908 | 类型占比（draw 的 622–625 对应 discard 的 901–904；905–908 为 discard 的 attack/skill/power/status_curse） |

**注**：与区块 3 的 622–629 重复了 discard 的类型占比。为保持一致性，区块 4 的 901–908 定义为：discard multi-hot 271 维 + discard 类型占比 8 维（与区块 3 中 626–629 一致，即 discard 的 4 个 ratio 重复一次；或 901–908 为 discard 的 8 维：attack, skill, power, status_curse × 2 无意义）。**简化**：区块 4 仅 271 维 multi-hot，类型占比已在区块 3 的 626–629 覆盖。修正：区块 3 含 draw 4 维 + discard 4 维 = 8 维；区块 4 仅 discard 的 full multi-hot 271 维。则区块 4 为 271 维，s[630]–s[900]。

**修正后**：
- 区块 3：351–621（271）+ 622–629（8）= 279 维。其中 622–625 为 draw，626–629 为 discard。
- 区块 4：630–900，271 维，仅 discard_pile 的 full multi-hot。

**实现函数**：`_encode_block4_discard_pile(mod_response) -> np.ndarray`，输出 shape=(271,)。

---

## 七、区块 5：消耗堆 — 逐维规格（271 维）

| 索引范围 | 表达式 |
|----------|--------|
| 901 + k, k∈[0,270] | exhaust_pile 中 card.id 在 cards 中索引 k 的张数 |

**实现函数**：`_encode_block5_exhaust_pile(mod_response) -> np.ndarray`，输出 shape=(271,)。

**索引修正**：区块 4 结束于 900，区块 5 起始于 901，结束于 1171。

---

## 八、区块 6：玩家 Powers — 逐维规格（80 维）

| 索引范围 | 表达式 |
|----------|--------|
| 1172 + k, k∈[0,79] | sum(p.amount for p in player.powers if power_id_to_index(p.id)==k) |

**实现函数**：`_encode_block6_player_powers(mod_response) -> np.ndarray`，输出 shape=(80,)。

**依赖**：`encoder_utils.power_id_to_index(id: str) -> int`，未找到返回 0。

**文件**：`src/training/encoder_utils.py` 需新增 `power_id_to_index`。

---

## 九、区块 7：怪物 — 逐维规格（300 维，6×50）

每怪物 50 维，怪物槽位 m ∈ [0, 5]。基础索引 base = 1252 + m*50。

| 子索引 | 名称 | Mod 路径 | 表达式 | 空槽 |
|--------|------|----------|--------|------|
| base+0 | hp_ratio | monsters[m].current_hp, max_hp | current_hp / max(max_hp, 1) | 0 |
| base+1 | block_norm | monsters[m].block | min(block, 99) / 99 | 0 |
| base+2 ~ base+14 | intent_onehot | monsters[m].intent | 13 维，intent_to_index 得到 k，s[base+2+k]=1 | 全 0 |
| base+15 | damage_norm | move_adjusted_damage, move_hits | min(max(0, adj_dmg * hits), 99) / 99 | 0 |
| base+16 | alive | monsters[m].is_gone | 1 - int(is_gone) | 0 |
| base+17 | half_dead | monsters[m].half_dead | 1 if half_dead else 0 | 0 |
| base+18 | strength_norm | monsters[m].powers 解析 | min(Strength amount, 30) / 30 | 0 |
| base+19 | vulnerable_norm | 同上 | min(Vulnerable amount, 15) / 15 | 0 |
| base+20 | weak_norm | 同上 | min(Weak amount, 15) / 15 | 0 |
| base+21 | poison_norm | 同上 | min(Poison amount, 99) / 99 | 0 |
| base+22 | curl_up_norm | 同上 | min(Curl Up amount, 10) / 10 | 0 |
| base+23 | monster_id_hash | monsters[m].id | hash(id) % 1000 / 1000（或 monster_id_to_index 若穷尽） | 0 |
| base+24 ~ base+49 | monster_powers_multi | monsters[m].powers | 26 维，power_id_to_index 映射，amount 累加 | 全 0 |

**注**：monster_powers 若超过 26 维，可截断或合并到 other；或扩展为 80 维与玩家 powers 对齐。**简化**：base+24~base+49 为 26 维，对应 encoder_ids 中「怪物常见 powers」子集；或与玩家 powers 共用 80 维，取前 26。**约定**：base+24~base+49 为怪物 powers 的 26 维 multi-hot（amount 值，非 0/1），power 索引与 encoder_ids.powers 前 26 个对应；其余 powers 合并到 other_powers_count_norm 放入 base+22 或新增一维。为简化，base+24~base+49 填 0，仅用 base+18~22 的 5 种关键 power；base+23 保留 monster_id_hash。

**最终约定**：每怪物 50 维 = hp_ratio(1) + block_norm(1) + intent_onehot(13) + damage_norm(1) + alive(1) + half_dead(1) + strength(1) + vulnerable(1) + weak(1) + poison(1) + curl_up(1) + monster_id_hash(1) + 预留(26)。

**实现函数**：`_encode_block7_monsters(mod_response) -> np.ndarray`，输出 shape=(300,)。

**依赖**：`encoder_utils.intent_to_index(intent: str) -> int`。

---

## 十、区块 8：遗物 — 逐维规格（180 维）

| 索引范围 | 表达式 |
|----------|--------|
| 1552 + k, k∈[0,179] | 对 relics 中每个 r：idx=relic_id_to_index(r.id)；s[1552+idx] += 1 |

**实现函数**：`_encode_block8_relics(mod_response) -> np.ndarray`，输出 shape=(180,)。

**依赖**：`encoder_utils.relic_id_to_index(id: str) -> int`。

---

## 十一、区块 9：药水 — 逐维规格（65 维）

### 11.1 multi-hot（45 维）

| 索引范围 | 表达式 |
|----------|--------|
| 1732 + k, k∈[0,44] | 对 potions 中每个 p：idx=potion_id_to_index(p.id)；s[1732+idx] += 1 |

### 11.2 每槽 4 维（20 维）

| 索引 | 名称 | 表达式 |
|------|------|--------|
| 1777 + i*4 + 0 | can_use[i] | potions[i].can_use ? 1 : 0 |
| 1777 + i*4 + 1 | can_discard[i] | potions[i].can_discard ? 1 : 0 |
| 1777 + i*4 + 2 | requires_target[i] | potions[i].requires_target ? 1 : 0 |
| 1777 + i*4 + 3 | slot_filled[i] | 1 若 potions[i] 存在 else 0 |

i ∈ [0, 4]，共 5 槽。

**实现函数**：`_encode_block9_potions(mod_response) -> np.ndarray`，输出 shape=(65,)。

**依赖**：`encoder_utils.potion_id_to_index(id: str) -> int`。

---

## 十二、区块 10：全局/房间 — 逐维规格（35 维）

| 索引 | 名称 | Mod 路径 | 表达式 | 缺省 |
|------|------|----------|--------|------|
| 1797 | floor_norm | game_state.floor | min(floor, 60) / 60 | 0 |
| 1798 | act_1 | game_state.act | 1 if act==1 else 0 | 0 |
| 1799 | act_2 | 1 if act==2 else 0 | 0 |
| 1800 | act_3 | 1 if act==3 else 0 | 0 |
| 1801 | room_COMBAT | game_state.room_phase | 1 if == "COMBAT" else 0 | 0 |
| 1802 | room_EVENT | 1 if == "EVENT" else 0 | 0 |
| 1803 | room_MAP | 1 if == "MAP" else 0 | 0 |
| 1804 | room_SHOP | 1 if == "SHOP" else 0 | 0 |
| 1805 | room_REST | 1 if == "REST" else 0 | 0 |
| 1806 | room_BOSS | 1 if == "BOSS" else 0 | 0 |
| 1807 | room_NONE | 1 if == "NONE" else 0 | 0 |
| 1808 | room_CARD_REWARD | 1 if == "CARD_REWARD" else 0 | 0 |
| 1809 | room_UNKNOWN | 1 if 非上述 else 0 | 0 |
| 1810 | available_play | available_commands | 1 if "play" in cmds else 0 | 0 |
| 1811 | available_end | 1 if "end" in cmds else 0 | 0 |
| 1812 | available_choose | 1 if "choose" in cmds else 0 | 0 |
| 1813 | available_proceed | 1 if "proceed" in cmds else 0 | 0 |
| 1814 | available_potion | 1 if "potion" in cmds else 0 | 0 |
| 1815 | choice_count_norm | screen_state.options 或 choice_list | min(len, 60) / 60 | 0 |
| 1816–1839 | 预留 | — | 0 | 0 |

**实现函数**：`_encode_block10_global(mod_response) -> np.ndarray`，输出 shape=(43,)。

---

## 十三、索引与维度汇总（修正版）

| 区块 | 起始 | 结束 | 维度 |
|------|------|------|------|
| 1. 玩家核心 | 0 | 19 | 20 |
| 2. 手牌 | 20 | 350 | 331 |
| 3. 抽牌堆 | 351 | 629 | 279 |
| 4. 弃牌堆 | 630 | 900 | 271 |
| 5. 消耗堆 | 901 | 1171 | 271 |
| 6. 玩家 Powers | 1172 | 1251 | 80 |
| 7. 怪物 | 1252 | 1551 | 300 |
| 8. 遗物 | 1552 | 1731 | 180 |
| 9. 药水 | 1732 | 1796 | 65 |
| 10. 全局 | 1797 | 1839 | 43 |
| **合计** | | | **1840** |

**注**：区块 10 含 35 维有效 + 8 维预留 = 43 维，保证总维度 1840。

---

## 十四、encoder_utils.py 新增函数规格

**文件**：`/Volumes/T7/AI_THE_SPIRE/src/training/encoder_utils.py`

| 函数签名 | 输入 | 输出 | 未找到 |
|----------|------|------|--------|
| relic_id_to_index(relic_id: str) -> int | 遗物 id 字符串 | 0~179 | 0 |
| potion_id_to_index(potion_id: str) -> int | 药水 id 字符串 | 0~44 | 0 |
| power_id_to_index(power_id: str) -> int | Power id 字符串 | 0~79 | 0 |
| intent_to_index(intent: str) -> int | 意图字符串 | 0~12 | 0 |

**实现要点**：查表前对 id 调用 `normalize_id(raw)`；从 `_load_ids()` 加载 YAML，构建 id→index 字典，懒加载。

---

## 十五、max_energy 推断逻辑

**文件**：`src/training/encoder_v2.py` 或新建 `src/training/max_energy.py`

**规则**：
- 基础值 3
- 若有 Boss 遗物 Coffee Dripper / Fusion Hammer / Philosopher's Stone 等，按游戏规则调整
- 若有 Violet Lotus（观者），+1
- 若有 Slaver's Collar，A2+ 时 +1
- **Phase 1 简化**：固定 3，不实现推断。

---

## 十六、非战斗帧处理

**条件**：`game_state.combat_state` 为 null 或不存在。

**处理**：
- 区块 1：s[0]=current_hp/max_hp（从 game_state），s[1]=max_hp_norm，s[5]=gold_norm；s[3],s[4],s[12]~s[19] 填 0
- 区块 2–9：全 0
- 区块 10：正常从 game_state、available_commands 读取

---

## 十七、实施检查清单（原子操作）

### 17.1 配置更新

1. [x] 打开 `configs/encoder_ids.yaml`，将 cards 段按穷尽清单补全（诅咒 14、状态 12，去重 Shiv）
2. [x] 将 relics 段去重、按穷尽清单补全（Snake Skull→Snecko Skull，补 Anchor/Bag of Preparation/Vajra）
3. [x] 将 potions 段保持 45 条
4. [x] 将 powers 段补全至 80+ 条
5. [x] 确认 intents 段为 13 条且顺序正确

### 17.2 encoder_utils.py

6. [ ] 在 `src/training/encoder_utils.py` 中实现 `relic_id_to_index(relic_id: str) -> int`
7. [ ] 实现 `potion_id_to_index(potion_id: str) -> int`
8. [ ] 实现 `power_id_to_index(power_id: str) -> int`
9. [ ] 实现 `intent_to_index(intent: str) -> int`
10. [ ] 将 `card_id_to_index` 的容量从 200 改为 271（或保持兼容，YAML 有 271 条即可）

### 17.3 encoder_v2.py 常量与入口

11. [ ] 将 `OUTPUT_DIM` 从 723 改为 1840
12. [ ] 更新 `get_output_dim()` 返回 1840
13. [ ] 在 `encode()` 中分配 `s = np.zeros(1840, dtype=np.float32)`

### 17.4 encoder_v2.py 区块实现

14. [ ] 实现 `_encode_block1_player_core()`，输出 20 维，按第三节规格
15. [ ] 实现 `_encode_block2_hand()`，输出 331 维，按第四节规格
16. [ ] 实现 `_encode_block3_draw_pile()`，输出 279 维，按第五节规格
17. [ ] 实现 `_encode_block4_discard_pile()`，输出 271 维
18. [ ] 实现 `_encode_block5_exhaust_pile()`，输出 271 维
19. [ ] 实现 `_encode_block6_player_powers()`，输出 80 维
20. [ ] 实现 `_encode_block7_monsters()`，输出 300 维，按第九节规格
21. [ ] 实现 `_encode_block8_relics()`，输出 180 维
22. [ ] 实现 `_encode_block9_potions()`，输出 65 维
23. [ ] 实现 `_encode_block10_global()`，输出 43 维（35 有效 + 8 预留）
24. [ ] 在 `encode()` 中按顺序拼接 10 个区块，写入 s[0:1840]
25. [ ] 实现非战斗分支：无 combat_state 时区块 2–9 填 0，区块 1 部分字段从 game_state 取

### 17.5 power_parser.py 扩展（若需）

26. [ ] 若 power_parser 需支持更多 Power 解析，在 `src/training/power_parser.py` 中扩展

### 17.6 测试与文档

27. [ ] 在 `tests/test_training/` 中新增 `test_encoder_v2.py`，测试 encode 输出 shape=(1840,)
28. [ ] 测试已知 Mod JSON 各区块数值正确性
29. [ ] 用 `scripts/read_state.py` 或批量脚本对 `data/A20_Slient/Raw_Data_json_FORSL/` 跑 encode，验证无异常
30. [ ] 更新 `docs/状态向量s_技术规范.md`，将本详细计划作为附录引用

---

## 十八、文件变更清单

| 文件 | 变更类型 |
|------|----------|
| configs/encoder_ids.yaml | 修改：cards/relics/potions/powers 穷尽 |
| src/training/encoder_utils.py | 修改：新增 4 个查表函数 |
| src/training/encoder_v2.py | 修改：OUTPUT_DIM、10 个区块、encode 逻辑 |
| src/training/power_parser.py | 可选修改 |
| tests/test_training/test_encoder_v2.py | 新增 |
| docs/状态向量s_技术规范.md | 修改：附录引用 |
