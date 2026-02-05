# Mod 日志参数清单

> 数据来源：`data/A20_Silent/Raw_Data_json_FORSL/Silent_A20_HUMAN_20260203_220221.json`  
> **核验日期**：2025-02，已对原始 JSON 逐项实测，以下内容与 Mod 实际返回一致。

---

## 核验报告（实测 vs 文档）

| 项目 | 实测结果 | 说明 |
|------|----------|------|
| 顶层 keys | available_commands, game_state, in_game, ready_for_command | ✓ 一致 |
| available_commands 全集 | cancel, choose, click, confirm, end, key, leave, play, potion, proceed, return, skip, state, wait | 共 14 种，非仅 5 种 |
| choice_list | 地图/事件/商店/休息/选牌/宝箱等**多场景均有** | 格式随 screen_type 变化，见下表 |
| 卡牌对象 | deck: 无 is_playable；hand/CARD_REWARD: 有 is_playable；商店卡: 多 price | ✓ |
| 商店遗物/药水 | 多 price 字段 | ✓ |

**choice_list 格式（按 screen_type）**：MAP→`['x=1','x=2']`；EVENT→选项文本；CARD_REWARD→卡牌名；COMBAT_REWARD→`['gold','card']`；REST→`['rest','smith']`；CHEST→`['open']`；SHOP_ROOM→`['shop']`；SHOP_SCREEN→`['purge', 卡牌名]`；GRID→卡牌名列表。

**与 action_id 的对应**：choice_list 中每一项（无论格式）对应一次「选择」动作；在 action 空间里统一映射为 `choose` 的 id（110–169，共 60 个），即 `choose 0` ~ `choose 59`。choice_list[i] 对应 action_id = 110 + i。

---

## 验证说明（三种场景对比）

**实测帧索引**：事件=帧0，地图=帧5，战斗=帧8（来自同一日志文件）

| 场景 | room_phase | screen_type | combat_state | choice_list | screen_state 结构 |
|------|------------|-------------|--------------|-------------|-------------------|
| 事件 | EVENT | EVENT | 无 | 无 | event_id, event_name, body_text, options |
| 地图 | COMPLETE | MAP | 无 | 有（节点坐标列表） | first_node_chosen, current_node, next_nodes, boss_available |
| 战斗 | COMBAT | NONE | 有 | 无 | {} 空对象 |

**game_state 参数差异**：
- **战斗独有**：`combat_state`
- **choice_list**：地图、事件、商店、休息、选牌等多场景均有，格式随 screen_type 不同（见上表）
- **事件**：无 combat_state；choice_list 在有待选项时存在

**结论**：参数**不完全相同**。战斗时有 combat_state；choice_list 多场景存在但格式各异；screen_state 随 screen_type 变化。

---

## 全场景枚举（screen_type × room_phase × room_type）

> 数据来源：三份日志文件 `Silent_A20_HUMAN_*.json` 并集

### screen_type 全集（11 种）

| screen_type | room_phase | room_type | 说明 | combat_state | choice_list | screen_state 关键字段 |
|-------------|------------|-----------|------|--------------|-------------|----------------------|
| EVENT | EVENT | NeowRoom / EventRoom | 事件对话 | 无 | 无 | event_id, event_name, body_text, options |
| MAP | COMPLETE | 多种 | 地图选路 | 无 | 有 | boss_available, current_node, first_node_chosen, next_nodes |
| NONE | COMBAT | MonsterRoom / Elite / Boss | 战斗中 | 有 | 无 | {} 空 |
| NONE | COMPLETE | MonsterRoomElite | 精英战后（过渡） | 无 | 无 | {} 空 |
| COMBAT_REWARD | COMPLETE | MonsterRoom / Elite / TreasureRoom | 战斗奖励（金/遗物/药水） | 无 | 有 | rewards |
| CARD_REWARD | COMPLETE | MonsterRoom / Elite | 选牌奖励 | 无 | 有 | bowl_available, cards, skip_available |
| **SHOP_ROOM** | COMPLETE | ShopRoom | 商店房间（进入） | 无 | 有 | {} 空 |
| **SHOP_SCREEN** | COMPLETE | ShopRoom | 商店主界面 | 无 | 有 | cards, potions, purge_available, purge_cost, relics |
| **GRID** | COMPLETE | ShopRoom | 商店选牌（删牌/升级等） | 无 | 有 | any_number, cards, confirm_up, for_purge, for_transform, for_upgrade, num_cards, selected_cards |
| **GRID** | EVENT / INCOMPLETE | EventRoom / RestRoom | 事件/休息选牌 | 无 | 有 | 同上（for_purge/for_transform 等为 false） |
| REST | INCOMPLETE | RestRoom | 休息选择（休息/铁匠/回忆） | 无 | 有 | has_rested, rest_options |
| REST | COMPLETE | RestRoom | 休息完成 | 无 | 无 | has_rested, rest_options |
| **CHEST** | COMPLETE | TreasureRoom | 宝箱房间 | 无 | 有 | chest_open, chest_type |
| HAND_SELECT | COMBAT | MonsterRoomElite 等 | 战斗中选牌（如弃牌） | 有 | - | can_pick_zero, hand, max_cards, selected |

### room_type 全集（8 种）

NeowRoom, EventRoom, MonsterRoom, MonsterRoomElite, MonsterRoomBoss, RestRoom, ShopRoom, TreasureRoom

### room_phase 全集（4 种）

EVENT, COMBAT, COMPLETE, INCOMPLETE

---

## 一、顶层参数

| 参数 | 类型 | 说明 |
|------|------|------|
| available_commands | 数组 | 可用命令（实测 14 种）：key, click, wait, state, end, choose, proceed, play, potion, cancel, confirm, return, skip, leave |
| ready_for_command | 布尔 | 是否等待指令 |
| in_game | 布尔 | 是否在游戏中 |
| game_state | 对象 | 游戏状态 |

---

## 二、game_state 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| screen_type | 字符串 | 屏幕类型：EVENT, NONE 等 |
| screen_state | 对象 | 屏幕状态（事件时含 event_id, event_name 等） |
| seed | 整数 | 种子 |
| combat_state | 对象 | 战斗状态（仅战斗时存在） |
| deck | 数组 | 牌组（卡牌对象列表） |
| relics | 数组 | 遗物列表 |
| max_hp | 整数 | 最大生命 |
| act_boss | 字符串 | 本幕 Boss 名 |
| gold | 整数 | 金币 |
| action_phase | 字符串 | 行动阶段：WAITING_ON_USER 等 |
| act | 整数 | 当前幕 |
| screen_name | 字符串 | 屏幕名称 |
| room_phase | 字符串 | 房间阶段：EVENT, COMBAT, COMPLETE 等 |
| room_type | 字符串 | 房间类型：NeowRoom, MonsterRoom 等 |
| is_screen_up | 布尔 | 是否有弹窗 |
| potions | 数组 | 药水列表 |
| current_hp | 整数 | 当前生命 |
| floor | 整数 | 当前楼层 |
| ascension_level | 整数 | 爬塔等级 |
| class | 字符串 | 角色：THE_SILENT 等 |
| map | 数组 | 地图节点列表 |
| choice_list | 数组 | 可选动作列表（多场景存在，格式随 screen_type 变化：地图=`x=N`，事件=选项文本，选牌=卡牌名等） |

---

## 三、combat_state 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| draw_pile | 数组 | 抽牌堆 |
| discard_pile | 数组 | 弃牌堆 |
| exhaust_pile | 数组 | 消耗堆 |
| cards_discarded_this_turn | 整数 | 本回合已弃牌数 |
| times_damaged | 整数 | 本回合受伤次数 |
| monsters | 数组 | 怪物列表 |
| turn | 整数 | 回合数 |
| limbo | 数组 | 待处理卡牌 |
| hand | 数组 | 手牌 |
| player | 对象 | 玩家战斗状态 |

---

## 四、卡牌对象（deck / hand / draw_pile / discard_pile）

| 参数 | 类型 | 说明 |
|------|------|------|
| id | 字符串 | 卡牌 ID：Strike_G, AscendersBane 等 |
| name | 字符串 | 中文名 |
| cost | 整数 | 费用（-2 为不可打出） |
| type | 字符串 | 类型：ATTACK, SKILL, POWER, CURSE 等 |
| ethereal | 布尔 | 是否虚无 |
| exhausts | 布尔 | 是否消耗 |
| has_target | 布尔 | 是否需要目标 |
| uuid | 字符串 | 唯一标识 |
| upgrades | 整数 | 升级次数 |
| rarity | 字符串 | 稀有度：BASIC, COMMON 等 |
| is_playable | 布尔 | 是否可打出（仅 combat 时） |

---

## 五、怪物对象

| 参数 | 类型 | 说明 |
|------|------|------|
| id | 字符串 | 怪物 ID：FuzzyLouseDefensive 等 |
| name | 字符串 | 中文名 |
| current_hp | 整数 | 当前生命 |
| max_hp | 整数 | 最大生命 |
| block | 整数 | 格挡 |
| intent | 字符串 | 意图：ATTACK, DEBUG 等 |
| move_id | 整数 | 招式 ID |
| move_base_damage | 整数 | 招式基础伤害 |
| move_adjusted_damage | 整数 | 招式实际伤害 |
| move_hits | 整数 | 命中次数 |
| is_gone | 布尔 | 是否已死亡 |
| half_dead | 布尔 | 是否半死（分裂等） |
| powers | 数组 | 怪物身上的增益/减益 |

---

## 六、怪物 powers 元素

| 参数 | 类型 | 说明 |
|------|------|------|
| id | 字符串 | 效果 ID：Curl Up 等 |
| name | 字符串 | 中文名 |
| amount | 整数 | 层数/数值 |

---

## 七、player（战斗内）

| 参数 | 类型 | 说明 |
|------|------|------|
| energy | 整数 | 当前能量 |
| current_hp | 整数 | 当前生命 |
| block | 整数 | 格挡 |
| max_hp | 整数 | 最大生命 |
| orbs | 数组 | 充能球（缺陷） |
| powers | 数组 | 玩家身上的增益 |

---

## 八、遗物对象

| 参数 | 类型 | 说明 |
|------|------|------|
| id | 字符串 | 遗物 ID：Ring of the Snake 等 |
| name | 字符串 | 中文名 |
| counter | 整数 | 计数器（-1 表示无） |

---

## 九、药水对象

| 参数 | 类型 | 说明 |
|------|------|------|
| id | 字符串 | 药水 ID：Potion Slot 为空槽 |
| name | 字符串 | 中文名 |
| can_use | 布尔 | 是否可使用 |
| can_discard | 布尔 | 是否可丢弃 |
| requires_target | 布尔 | 是否需要目标 |

---

## 十、地图节点对象

| 参数 | 类型 | 说明 |
|------|------|------|
| symbol | 字符串 | 类型：M=怪物, ?=事件, $=商店, R=休息, E=精英 等 |
| x | 整数 | 横坐标 |
| y | 整数 | 纵坐标 |
| children | 数组 | 子节点坐标 [{x,y}, ...] |
| parents | 数组 | 父节点 |

---

## 十一、screen_state（按 screen_type 分）

### EVENT 时

| 参数 | 类型 | 说明 |
|------|------|------|
| event_id | 字符串 | 事件 ID |
| event_name | 字符串 | 事件名 |
| body_text | 字符串 | 正文 |
| options | 数组 | 选项列表 |

### MAP 时

| 参数 | 类型 | 说明 |
|------|------|------|
| boss_available | 布尔 | 是否可打 Boss |
| current_node | 对象 | 当前节点 {x, y} |
| first_node_chosen | 布尔 | 是否已选过首节点 |
| next_nodes | 数组 | 可选下一节点 |

### COMBAT_REWARD 时

| 参数 | 类型 | 说明 |
|------|------|------|
| rewards | 数组 | 奖励列表，元素含 reward_type（GOLD/CARD/RELIC 等） |

### CARD_REWARD 时

| 参数 | 类型 | 说明 |
|------|------|------|
| bowl_available | 布尔 | 是否有遗忘壶 |
| cards | 数组 | 可选卡牌列表 |
| skip_available | 布尔 | 是否可跳过 |

### SHOP_SCREEN 时

| 参数 | 类型 | 说明 |
|------|------|------|
| cards | 数组 | 出售卡牌（含 price） |
| potions | 数组 | 出售药水（含 price） |
| purge_available | 布尔 | 是否可删牌 |
| purge_cost | 整数 | 删牌费用 |
| relics | 数组 | 出售遗物（含 price） |

### GRID 时（商店/事件/休息选牌）

| 参数 | 类型 | 说明 |
|------|------|------|
| any_number | 布尔 | 是否可选任意数量 |
| cards | 数组 | 可选卡牌列表 |
| confirm_up | 布尔 | 是否已确认 |
| for_purge | 布尔 | 是否删牌模式 |
| for_transform | 布尔 | 是否变形模式 |
| for_upgrade | 布尔 | 是否升级模式 |
| num_cards | 整数 | 需选数量 |
| selected_cards | 数组 | 已选卡牌 |

### REST 时

| 参数 | 类型 | 说明 |
|------|------|------|
| has_rested | 布尔 | 是否已休息 |
| rest_options | 数组 | 选项：rest, smith, recall |

### CHEST 时

| 参数 | 类型 | 说明 |
|------|------|------|
| chest_open | 布尔 | 是否已开箱 |
| chest_type | 字符串 | 宝箱类型：SmallChest, MediumChest, LargeChest |

### HAND_SELECT 时（战斗中选牌）

| 参数 | 类型 | 说明 |
|------|------|------|
| can_pick_zero | 布尔 | 是否可不选 |
| hand | 数组 | 手牌列表 |
| max_cards | 整数 | 最多可选数 |
| selected | 数组 | 已选卡牌 |
