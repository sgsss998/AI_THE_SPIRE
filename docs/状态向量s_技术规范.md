# 状态向量 s 技术规范

> 核心：s 里的信息只能来自 Mod 日志的 state；用 multi-hot、one-hot 等办法展开成 **1840 维**。与 Mod 日志数据互通，字段路径一致。

---

## 一、排除法：哪些不要、哪些要

**不要的**：uuid、name（有 id 就能查）、seed、screen_state、map、action_phase 等，跟战斗决策无关的、不能泛化的都扔。

**要的**：

| 数据从哪来 | 要的字段 |
|------------|----------|
| combat_state | hand（手牌）、draw_pile（抽牌堆）、discard_pile（弃牌堆）、exhaust_pile（消耗堆）、monsters（怪物）、player（玩家）、turn（回合）、cards_discarded_this_turn（本回合弃牌数）、times_damaged（本回合受伤次数） |
| game_state | floor（楼层）、act（章节）、room_phase（房间阶段）、gold（金币）、relics（遗物）、potions（药水） |
| 卡牌 | id、cost（费用）、type（类型）、upgrades（升级次数）、ethereal（虚无）、exhausts（消耗）、has_target（需目标）、is_playable（可出）、rarity（稀有度） |
| player | energy（能量）、current_hp（当前血）、max_hp（最大血）、block（格挡）、powers（增益/减益列表）、orbs（能量槽，缺陷用） |
| monsters | id、current_hp、max_hp、block、intent（意图）、move_*（招式相关）、is_gone（是否消失）、half_dead（半死）、powers |
| relics | id、counter（计数器，如香炉） |
| potions | id、can_use（能用）、can_discard（能丢）、requires_target（需选目标） |

**注意**：力量、虚弱、易伤等 Mod 不直接给，要从 `player.powers` 里解析；最大能量暂时默认 3，后面可从遗物推。

---

## 二、向量块设计（1840 维，见穷尽计划详细版）

| 区块 | 维度 | 从哪来 | 咋编码 |
|------|------|--------|--------|
| 1. 玩家核心 | 18 | player、手牌/抽牌/弃牌/消耗堆数量、本回合弃牌数、受伤次数、金币 | 标量除以最大值，压到 0~1 |
| 2. 手牌 | 230 | hand 的 id、cost、type、is_playable | multi-hot 200 维 + 10 槽×3 维 |
| 3. 牌库摘要 | 8 | draw_pile、discard_pile 的 type | 各堆攻击/技能/能力/状态诅咒占比 |
| 4. 玩家 Powers | 60 | player.powers 的 id、amount | multi-hot |
| 5. 怪物 | 138 | monsters 的保留字段 | 6 个怪物槽×23 维（血、格挡、意图、伤害、存活、powers 等） |
| 6. 遗物 | 200 | game_state.relics 的 id | multi-hot |
| 7. 药水 | 55 | game_state.potions 的 id、can_use | multi-hot 50 维 + 5 槽是否可用 |
| 8. 全局 | 14 | floor、act、room_phase、turn | 标量 + one-hot |

**multi-hot**：多热编码，一个 id 对应一个位置，有几个就填几。  
**one-hot**：独热编码，多个选项里只有一个为 1，其余为 0。

---

## 三、扩到 ~1500 维

| 扩展块 | 维度 | 从哪来 |
|--------|------|--------|
| 9. 抽牌堆 multi-hot | 200 | draw_pile 的 id |
| 10. 弃牌堆 multi-hot | 200 | discard_pile 的 id |
| 11. 怪物 Powers 完整 | 360 | 每个怪物 60 维 powers |

9+10 → 1123 维；9+10+11 → 1483 维。

---

## 四、ID 和归一化

- **ID 从哪来**：`configs/encoder_ids.yaml`，cards 271、relics 180、potions 45、powers 80、intents 13
- **Raw_Data**：`data/A20_Slient/Raw_Data_json_FORSL/`，脚本 `extract_mod_schema.py`、`extract_ids_from_raw.py`
- 未知 ID → 编号 0；编码前把 id 归一化（小写、空格和下划线统一）
- **非战斗**：没有 combat_state 时，区块 2~5、7 全 0；区块 1 只用 game_state 里能拿到的

---

## 五、实施清单

1. [ ] 确认 encoder_ids.yaml 的维度
2. [ ] 实现 StateEncoderV2，只从保留字段读
3. [ ] 实现 player.powers → 力量/虚弱/易伤 等解析
4. [x] 实现 10 个区块编码，拼成 1840 维（见 `docs/planning_and_logs/状态向量s_穷尽计划_详细版.md`）
5. [ ] 缺的字段用默认值

---

## 附录：穷尽计划

完整 1840 维规格、Mod 字段路径、实施检查清单见：
[状态向量s_穷尽计划_详细版](../planning_and_logs/状态向量s_穷尽计划_详细版.md)
