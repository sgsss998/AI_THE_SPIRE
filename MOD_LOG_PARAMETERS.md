# Slay the Spire Mod 日志完整参数清单

> 基于 CommunicationMod 协议的完整游戏状态参数
> 生成时间: 2025-02-05
> 数据来源: `data/A20_Silent/Raw_Data_json_FORSL/`

---

## 目录

- [一、顶层字段](#一顶层字段)
- [二、game_state 基础字段](#二game_state-基础字段)
- [三、combat_state 战斗字段](#三combat_state-战斗字段)
- [四、screen_state 屏幕详情字段](#四screen_state-屏幕详情字段)
- [五、嵌套对象字段](#五嵌套对象字段)

---

## 一、顶层字段

每个日志记录的最外层结构。

| 字段路径                 | 类型     | 示例值                          | 说明                        | 优先级 |
| -------------------- | ------ | ---------------------------- | ------------------------- | --- |
| `action`             | string | `"play"`, `"end"`, `"state"` | 当前/上一条执行的动作               | ⭐⭐⭐ |
| `available_commands` | list   | `["play", "end", "key"...]`  | 可用命令列表（Action Masking 依据） | ⭐⭐⭐ |
| `ready_for_command`  | bool   | `true`, `false`              | 是否准备好接收新命令                | ⭐⭐⭐ |
| `in_game`            | bool   | `true`, `false`              | 是否在游戏中                    | ⭐⭐  |
| `error`              | string | 错误信息                         | 错误描述（正常情况下为空）             | ⭐   |

```json
{
  "action": "play",
  "available_commands": ["play", "end", "key", "click", "wait", "state"],
  "ready_for_command": true,
  "in_game": true
}
```

---

## 二、game_state 基础字段

### 2.1 游戏进度信息

| 字段路径                        | 类型     | 示例值                                                                                                      | 说明          | 优先级 |
| --------------------------- | ------ | -------------------------------------------------------------------------------------------------------- | ----------- | --- |
| `game_state.act`            | int    | `1`, `2`, `3`, `4`                                                                                       | 当前章节（第1-4章） | ⭐⭐⭐ |
| `game_state.floor`          | int    | `0-60+`                                                                                                  | 当前楼层        | ⭐⭐⭐ |
| `game_state.room_phase`     | string | `"COMBAT"`, `"EVENT"`, `"MAP"`<br>`"SHOP"`, `"REST"`, `"BOSS"`<br>`"CARD_REWARD"`, `"NONE"`, `"UNKNOWN"` | 房间阶段        | ⭐⭐⭐ |
| `game_state.room_type`      | string | `"MonsterRoom"`, `"EventRoom"`<br>`"ShopRoom"`, `"RestRoom"`<br>`"TreasureRoom"`                         | 房间类型        | ⭐⭐  |
| `game_state.screen_type`    | string | `"NONE"`, `"EVENT"`, `"SHOP"`<br>`"CARD_REWARD"`, `"HAND_SELECT"`                                        | 当前屏幕类型      | ⭐⭐⭐ |
| `game_state.screen_name`    | string | `"NONE"`                                                                                                 | 屏幕名称        | ⭐   |
| `game_state.is_screen_up`   | bool   | `true`, `false`                                                                                          | 是否有弹窗       | ⭐   |
| `game_state.action_phase`   | string | `"WAITING_ON_USER"`                                                                                      | 动作阶段        | ⭐⭐  |
| `game_state.current_action` | string | 当前动作                                                                                                     | ⭐⭐          |     |

### 2.2 玩家基础状态

| 字段路径                         | 类型     | 示例值                                                | 说明        | 优先级 |
| ---------------------------- | ------ | -------------------------------------------------- | --------- | --- |
| `game_state.class`           | string | `"THE_SILENT"`, `"THE_IRONCLAD"`<br>`"THE_DEFECT"` | 角色类       | ⭐⭐⭐ |
| `game_state.ascension_level` | int    | `0-20`                                             | 逆飞（难易度）等级 | ⭐⭐  |
| `game_state.max_hp`          | int    | `70-80+`                                           | 最大生命值     | ⭐⭐⭐ |
| `game_state.current_hp`      | int    | 当前生命值（非战斗时）                                        | ⭐⭐⭐       |     |
| `game_state.gold`            | int    | 金币数量                                               | ⭐⭐⭐       |     |
| `game_state.act_boss`        | string | `"Slime Boss"`                                     | 当前章节Boss名 | ⭐   |

### 2.3 牌组与资源

| 字段路径                 | 类型    | 说明         | 优先级 |
| -------------------- | ----- | ---------- | --- |
| `game_state.deck`    | array | 完整牌组（所有卡牌） | ⭐⭐⭐ |
| `game_state.relics`  | array | 遗物列表       | ⭐⭐⭐ |
| `game_state.potions` | array | 药水栏（最多3格）  | ⭐⭐⭐ |

### 2.4 地图与选择

| 字段路径                      | 类型     | 说明                   | 优先级 |
| ------------------------- | ------ | -------------------- | --- |
| `game_state.map`          | array  | 地图节点列表（树结构）          | ⭐⭐  |
| `game_state.choice_list`  | array  | 选择列表（商店商品/事件选项/卡牌奖励） | ⭐⭐⭐ |
| `game_state.screen_state` | object | 屏幕详情（见第四节）           | ⭐⭐⭐ |

### 2.5 系统字段

| 字段路径              | 类型  | 说明            | 优先级 |
| ----------------- | --- | ------------- | --- |
| `game_state.seed` | int | 随机种子（对AI决策无用） | ❌   |

---

## 三、combat_state 战斗字段

战斗时才存在的字段，位于 `game_state.combat_state` 下。

### 3.1 战斗基础

| 字段路径                                                | 类型     | 示例值                | 说明    | 优先级 |
| --------------------------------------------------- | ------ | ------------------ | ----- | --- |
| `game_state.combat_state.turn`                      | int    | `1, 2, 3...`       | 当前回合数 | ⭐⭐⭐ |
| `game_state.combat_state.hand`                      | array  | 手牌列表（最多10张）        | ⭐⭐⭐   |     |
| `game_state.combat_state.draw_pile`                 | array  | 抽牌堆（未知顺序的背面牌）      | ⭐⭐⭐   |     |
| `game_state.combat_state.discard_pile`              | array  | 弃牌堆                | ⭐⭐⭐   |     |
| `game_state.combat_state.exhaust_pile`              | array  | 消耗堆                | ⭐⭐    |     |
| `game_state.combat_state.limbo`                     | array  | 虚空牌（打出中）           | ⭐     |     |
| `game_state.combat_state.card_in_play`              | object | **正在打出的牌**（等待效果结算） | ⭐⭐    |     |
| `game_state.combat_state.cards_discarded_this_turn` | int    | 本回合已弃牌数            | ⭐     |     |
| `game_state.combat_state.times_damaged`             | int    | 本局受击次数             | ⭐     |     |

### 3.2 玩家战斗状态

| 字段路径                                        | 类型     | 示例值        | 说明   | 优先级 |
| ------------------------------------------- | ------ | ---------- | ---- | --- |
| `game_state.combat_state.player`            | object | 玩家状态对象     | ⭐⭐⭐  |     |
| `game_state.combat_state.player.energy`     | int    | `0-3+`     | 当前能量 | ⭐⭐⭐ |
| `game_state.combat_state.player.max_hp`     | int    | 最大生命       | ⭐⭐⭐  |     |
| `game_state.combat_state.player.current_hp` | int    | 当前生命       | ⭐⭐⭐  |     |
| `game_state.combat_state.player.block`      | int    | 当前护甲       | ⭐⭐⭐  |     |
| `game_state.combat_state.player.powers`     | array  | Powers效果列表 | ⭐⭐⭐  |     |
| `game_state.combat_state.player.orbs`       | array  | 能量球（缺陷角色）  | ⭐⭐   |     |

### 3.3 怪物状态

| 字段路径                               | 类型    | 示例值        | 说明  | 优先级 |
| ---------------------------------- | ----- | ---------- | --- | --- |
| `game_state.combat_state.monsters` | array | 怪物列表（1-3个） | ⭐⭐⭐ |     |

#### 单个怪物字段

| 字段路径                              | 类型     | 示例值                                                                                                         | 说明     | 优先级 |
| --------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------- | ------ | --- |
| `monsters[].id`                   | string | `"SpikeSlime_S"`                                                                                            | 怪物唯一ID | ⭐⭐  |
| `monsters[].name`                 | string | `"尖刺史莱姆（小）"`                                                                                                | 怪物名称   | ⭐⭐⭐ |
| `monsters[].current_hp`           | int    | 当前血量                                                                                                        | ⭐⭐⭐    |     |
| `monsters[].max_hp`               | int    | 最大血量                                                                                                        | ⭐⭐⭐    |     |
| `monsters[].block`                | int    | 当前护甲                                                                                                        | ⭐⭐⭐    |     |
| `monsters[].intent`               | string | `"ATTACK"`, `"DEFEND"`, `"BUFF"`<br>`"DEBUFF"`, `"ATTACK_BUFF"`<br>`"ATTACK_DEBUFF"`, `"UNKNOWN"`, `"NONE"` | 怪物意图   | ⭐⭐⭐ |
| `monsters[].move_id`              | int    | 当前招式ID                                                                                                      | ⭐⭐⭐    |     |
| `monsters[].last_move_id`         | int    | 上一招式ID                                                                                                      | ⭐⭐     |     |
| `monsters[].second_last_move_id`  | int    | 上上个招式ID                                                                                                     | ⭐      |     |
| `monsters[].move_base_damage`     | int    | 基础伤害                                                                                                        | ⭐⭐     |     |
| `monsters[].move_adjusted_damage` | int    | 调整后伤害（考虑Powers）                                                                                             | ⭐⭐     |     |
| `monsters[].move_hits`            | int    | 打击次数                                                                                                        | ⭐      |     |
| `monsters[].is_gone`              | bool   | 是否死亡/消失                                                                                                     | ⭐⭐⭐    |     |
| `monsters[].half_dead`            | bool   | 是否半死状态（小史莱姆分裂后）                                                                                             | ⭐⭐     |     |
| `monsters[].powers`               | array  | 怪物Powers效果                                                                                                  | ⭐⭐⭐    |     |

---

## 四、screen_state 屏幕详情字段

`game_state.screen_state` 是一个动态对象，根据当前屏幕类型包含不同字段。

### 4.1 事件屏幕 (EVENT)

| 字段路径                      | 类型     | 说明     | 优先级 |
| ------------------------- | ------ | ------ | --- |
| `screen_state.event_id`   | string | 事件ID   | ⭐⭐⭐ |
| `screen_state.event_name` | string | 事件名称   | ⭐⭐⭐ |
| `screen_state.body_text`  | string | 事件正文文本 | ⭐   |
| `screen_state.options`    | array  | 事件选项列表 | ⭐⭐⭐ |

#### 选项字段 (screen_state.options[])

| 字段             | 类型     | 说明                   | 优先级 |
| -------------- | ------ | -------------------- | --- |
| `choice_index` | int    | 选项索引（对应动作ID 110-169） | ⭐⭐⭐ |
| `text`         | string | 选项描述文本               | ⭐⭐  |
| `label`        | string | 选项标签                 | ⭐   |
| `disabled`     | bool   | 是否禁用（不可选）            | ⭐⭐  |

### 4.2 商店屏幕 (SHOP)

| 字段路径                           | 类型    | 说明          | 优先级 |
| ------------------------------ | ----- | ----------- | --- |
| `screen_state.any_number`      | bool  | 是否可选任意数量    | ⭐   |
| `screen_state.can_pick_zero`   | bool  | 是否可以不选      | ⭐   |
| `screen_state.boss_available`  | bool  | 是否有Boss遗物可买 | ⭐⭐  |
| `screen_state.cards`           | array | 在售卡牌列表      | ⭐⭐⭐ |
| `screen_state.relics`          | array | 在售遗物列表      | ⭐⭐⭐ |
| `screen_state.potions`         | array | 在售药水列表      | ⭐⭐  |
| `screen_state.purge_available` | bool  | 是否可删牌       | ⭐⭐  |
| `screen_state.purge_cost`      | int   | 删牌价格        | ⭐⭐  |

### 4.3 卡牌奖励屏幕 (CARD_REWARD)

| 字段路径                       | 类型     | 说明              | 优先级 |
| -------------------------- | ------ | --------------- | --- |
| `screen_state.cards`       | array  | 可选卡牌列表          | ⭐⭐⭐ |
| `screen_state.rewards`     | array  | 奖励列表（含金币/药水/卡牌） | ⭐⭐⭐ |
| `screen_state.screen_type` | string | `"CARD_REWARD"` | ⭐⭐  |
| `screen_state.boss_relic`  | object | Boss遗物选择        | ⭐⭐  |

### 4.4 地图屏幕 (MAP)

| 字段路径                             | 类型     | 说明                  | 优先级 |
| -------------------------------- | ------ | ------------------- | --- |
| `screen_state.current_node`      | object | 当前节点 {x, y, symbol} | ⭐⭐⭐ |
| `screen_state.next_nodes`        | array  | 下一层可选节点             | ⭐⭐⭐ |
| `screen_state.first_node_chosen` | bool   | 是否已选首节点             | ⭐   |

### 4.5 手牌选择屏幕 (HAND_SELECT)

| 字段路径                          | 类型    | 说明     | 优先级 |
| ----------------------------- | ----- | ------ | --- |
| `screen_state.hand`           | array | 可选手牌   | ⭐⭐⭐ |
| `screen_state.selected`       | array | 已选中卡牌  | ⭐⭐⭐ |
| `screen_state.selected_cards` | array | 已选卡牌列表 | ⭐⭐  |
| `screen_state.num_cards`      | int   | 需要选择数量 | ⭐⭐⭐ |
| `screen_state.max_cards`      | int   | 最大可选数量 | ⭐⭐  |
| `screen_state.for_upgrade`    | bool  | 是否用于升级 | ⭐⭐  |
| `screen_state.for_transform`  | bool  | 是否用于转化 | ⭐⭐  |
| `screen_state.for_purge`      | bool  | 是否用于删除 | ⭐⭐  |

### 4.6 宝箱屏幕 (CHEST)

| 字段路径                      | 类型     | 说明    | 优先级 |
| ------------------------- | ------ | ----- | --- |
| `screen_state.chest_type` | string | 宝箱类型  | ⭐⭐  |
| `screen_state.chest_open` | bool   | 是否已打开 | ⭐   |
| `screen_state.rewards`    | array  | 奖励列表  | ⭐⭐⭐ |

### 4.7 通用屏幕字段

| 字段路径                      | 类型   | 说明     | 优先级 |
| ------------------------- | ---- | ------ | --- |
| `screen_state.confirm_up` | bool | 确认按钮位置 | ⭐   |
| `screen_state.score`      | int  | 分数     | ⭐   |
| `screen_state.victory`    | bool | 是否胜利   | ⭐⭐  |

---

## 五、嵌套对象字段

### 5.1 Card（卡牌）

卡牌对象出现在：`deck`, `hand`, `draw_pile`, `discard_pile`, `exhaust_pile`, `screen_state.cards`, `screen_state.selected`

| 字段            | 类型     | 示例值                                                          | 说明                | 优先级 |
| ------------- | ------ | ------------------------------------------------------------ | ----------------- | --- |
| `id`          | string | `"Strike_G"`, `"Defend_G"`<br>`"Neutralize"`, `"Survivor"`   | 卡牌唯一ID            | ⭐⭐⭐ |
| `name`        | string | `"打击"`, `"防御"`, `"中和"`                                       | 卡牌名称（中文）          | ⭐⭐  |
| `cost`        | int    | `-2, 0, 1, 2, 3`                                             | 能量费用（-2为X/诅咒）     | ⭐⭐⭐ |
| `type`        | string | `"ATTACK"`, `"SKILL"`<br>`"POWER"`, `"STATUS"`, `"CURSE"`    | 卡牌类型              | ⭐⭐⭐ |
| `is_playable` | bool   | `true`, `false`                                              | 当前是否可打出           | ⭐⭐⭐ |
| `has_target`  | bool   | `true`, `false`                                              | 是否需要选择目标          | ⭐⭐⭐ |
| `upgrades`    | int    | `0, 1`                                                       | 升级次数（0=普通, 1=升级+） | ⭐⭐  |
| `rarity`      | string | `"BASIC"`, `"COMMON"`<br>`"UNCOMMON"`, `"RARE"`, `"SPECIAL"` | 稀有度               | ⭐   |
| `ethereal`    | bool   | `true`, `false`                                              | 是否虚无牌（回合结束消失）     | ⭐⭐  |
| `exhausts`    | bool   | `true`, `false`                                              | 是否消耗（打出后移除）       | ⭐⭐  |
| `uuid`        | string | `"7663481f-4122-4eef-8f5e..."`                               | 唯一标识（对AI无用）       | ❌   |

```json
{
  "id": "Strike_G",
  "name": "打击",
  "cost": 1,
  "type": "ATTACK",
  "is_playable": true,
  "has_target": true,
  "upgrades": 0,
  "rarity": "BASIC",
  "ethereal": false,
  "exhausts": false,
  "uuid": "7663481f-..."
}
```

### 5.2 Relic（遗物）

遗物对象出现在：`game_state.relics`, `screen_state.relics`

| 字段        | 类型     | 示例值                                             | 说明       | 优先级 |
| --------- | ------ | ----------------------------------------------- | -------- | --- |
| `id`      | string | `"Ring of the Snake"`<br>`"Bag of Preparation"` | 遗物唯一ID   | ⭐⭐⭐ |
| `name`    | string | `"蛇之戒指"`                                        | 遗物名称（中文） | ⭐⭐  |
| `counter` | int    | 计数器值（某些遗物有计数）                                   | ⭐⭐       |     |

```json
{
  "id": "Ring of the Snake",
  "name": "蛇之戒指",
  "counter": -1
}
```

### 5.3 Potion（药水）

药水对象出现在：`game_state.potions`, `screen_state.potions`, `screen_state.rewards[].potion`

| 字段                | 类型     | 示例值                               | 说明       | 优先级 |
| ----------------- | ------ | --------------------------------- | -------- | --- |
| `id`              | string | `"AttackPotion"`, `"BlockPotion"` | 药水唯一ID   | ⭐⭐⭐ |
| `name`            | string | `"攻击药水"`                          | 药水名称（中文） | ⭐⭐  |
| `requires_target` | bool   | `true`, `false`                   | 是否需要选择目标 | ⭐⭐  |
| `can_use`         | bool   | `true`, `false`                   | 当前是否可用   | ⭐⭐  |
| `can_discard`     | bool   | `true`, `false`                   | 当前是否可丢弃  | ⭐⭐  |

```json
{
  "id": "AttackPotion",
  "name": "攻击药水",
  "requires_target": true,
  "can_use": true,
  "can_discard": false
}
```

### 5.4 Power（Powers效果）

Power对象出现在：`player.powers`, `monsters[].powers`

| 字段             | 类型     | 示例值                                                 | 说明        | 优先级 |
| -------------- | ------ | --------------------------------------------------- | --------- | --- |
| `id`           | string | `"Strength"`, `"Weak"`<br>`"Vulnerable"`, `"Frail"` | Power唯一ID | ⭐⭐⭐ |
| `name`         | string | `"力量"`, `"虚弱"`                                      | Power名称   | ⭐⭐  |
| `amount`       | int    | 数值（如力量层数）                                           | ⭐⭐⭐       |     |
| `just_applied` | bool   | 是否刚施加                                               | ⭐         |     |
|                |        |                                                     |           |     |

```json
{
  "id": "Weak",
  "name": "虚弱",
  "amount": 2,
  "just_applied": false
}
```

### 5.5 Orb（能量球）

Orb对象仅出现在：`player.orbs`（缺陷角色）

| 字段                   | 类型     | 说明     | 优先级 |     |
| -------------------- | ------ | ------ | --- | --- |
| `id`                 | string | 能量球类型  | ⭐⭐  |     |
| `amount`             | int    | 被动层数   | ⭐⭐  |     |
| `focus_evoke_amount` | int    | 激活时的数值 | ⭐   |     |
|                      |        |        |     |     |

### 5.6 Map Node（地图节点）

地图节点出现在：`game_state.map`, `screen_state.current_node`, `screen_state.next_nodes`

| 字段         | 类型     | 示例值                                                            | 说明   | 优先级 |
| ---------- | ------ | -------------------------------------------------------------- | ---- | --- |
| `x`        | int    | `0-15`                                                         | X坐标  | ⭐⭐  |
| `y`        | int    | `0-15`                                                         | Y坐标  | ⭐⭐  |
| `symbol`   | string | `"M"`=怪物, `"?"`=问号<br>`"$"`=商店, `"E"`=精英<br>`"R"`=休息, `"T"`=宝箱 | 节点类型 | ⭐⭐⭐ |
| `parents`  | array  | 父节点列表                                                          | ⭐    |     |
| `children` | array  | 子节点列表                                                          | ⭐    |     |

```json
{
  "x": 3,
  "y": 1,
  "symbol": "M",
  "parents": [],
  "children": [{"x": 2, "y": 2}, {"x": 3, "y": 2}]
}
```

### 5.7 Reward（奖励）

奖励对象出现在：`screen_state.rewards`

| 字段            | 类型     | 说明                                          | 优先级  |     |
| ------------- | ------ | ------------------------------------------- | ---- | --- |
| `reward_type` | string | `"CARD"`, `"POTION"`, `"GOLD"`<br>`"RELIC"` | 奖励类型 | ⭐⭐⭐ |
| `gold`        | int    | 金币数量                                        | ⭐⭐   |     |
| `potion`      | object | 药水对象                                        | ⭐⭐   |     |
| `cards`       | array  | 卡牌对象                                        | ⭐⭐   |     |

---

## 六、优先级说明

| 优先级 | 说明 |
|--------|------|
| ⭐⭐⭐ | **必须包含** - 对决策至关重要 |
| ⭐⭐ | **重要** - 对有明显帮助 |
| ⭐ | **可选** - 有一定帮助 |
| ❌ | **不包含** - 对AI决策无用 |

---

## 七、数据结构示例

### 7.1 完整战斗状态示例

```json
{
  "available_commands": ["play", "end", "key", "click", "wait", "state"],
  "ready_for_command": true,
  "in_game": true,
  "action": "play",
  "game_state": {
    "screen_type": "NONE",
    "screen_state": {},
    "room_phase": "COMBAT",
    "floor": 5,
    "act": 1,
    "class": "THE_SILENT",
    "max_hp": 66,
    "current_hp": 59,
    "gold": 150,
    "relics": [{"id": "Ring of the Snake", "name": "蛇之戒指", "counter": -1}],
    "potions": [
      {"id": "AttackPotion", "name": "攻击药水", "requires_target": true, "can_use": true}
    ],
    "combat_state": {
      "turn": 3,
      "hand": [
        {
          "id": "Strike_G",
          "name": "打击",
          "cost": 1,
          "type": "ATTACK",
          "is_playable": true,
          "has_target": true,
          "upgrades": 0,
          "rarity": "BASIC"
        }
      ],
      "draw_pile": [...],
      "discard_pile": [...],
      "monsters": [
        {
          "id": "SpikeSlime_S",
          "name": "尖刺史莱姆（小）",
          "current_hp": 8,
          "max_hp": 13,
          "block": 0,
          "intent": "ATTACK",
          "move_id": 1,
          "move_base_damage": 6,
          "move_adjusted_damage": 6,
          "move_hits": 1,
          "is_gone": false,
          "powers": []
        }
      ],
      "player": {
        "energy": 3,
        "max_hp": 66,
        "current_hp": 59,
        "block": 5,
        "powers": [{"id": "Weak", "name": "虚弱", "amount": 1}]
      }
    }
  }
}
```

### 7.2 事件状态示例

```json
{
  "game_state": {
    "room_phase": "EVENT",
    "screen_type": "EVENT",
    "screen_state": {
      "event_id": "The Shrine",
      "event_name": "神殿",
      "body_text": "你发现了一座古老的神殿...",
      "options": [
        {"choice_index": 0, "text": "祈祷 (获得10点护甲)", "disabled": false},
        {"choice_index": 1, "text": "离开", "disabled": false}
      ]
    }
  }
}
```

### 7.3 商店状态示例

```json
{
  "game_state": {
    "room_phase": "SHOP",
    "screen_type": "SHOP",
    "screen_state": {
      "any_number": true,
      "can_pick_zero": true,
      "cards": [
        {"id": "PiercingWail", "name": "哀号之箭", "cost": 1, "type": "SKILL"}
      ],
      "relics": [
        {"id": "Bag of Preparation", "name": "备战背包", "counter": 0}
      ],
      "purge_available": true,
      "purge_cost": 100
    }
  }
}
```

---

## 八、字段汇总统计

| 类别 | 字段数量 | 说明 |
|------|----------|------|
| 顶层控制字段 | 5 | action, available_commands, ready_for_command, in_game, error |
| game_state 基础 | 25 | 游戏进度、玩家状态、牌组、地图等 |
| combat_state 战斗 | 13 | 回合、手牌、牌堆、玩家、怪物 |
| player 子字段 | 6 | hp, energy, block, powers, orbs |
| monster 子字段 | 17 | hp, block, intent, move, powers |
| screen_state 详情 | ~60 | 事件、商店、地图、奖励等屏幕详情 |
| Card 字段 | 11 | 卡牌属性 |
| Relic 字段 | 3 | 遗物属性 |
| Potion 字段 | 5 | 药水属性 |
| Power 字段 | 4 | Power属性 |
| Map Node 字段 | 5 | 地图节点 |
| Reward 字段 | 4 | 奖励 |
| **总计** | **~225** | 所有唯一字段路径 |

---

## 九、编码建议

### 9.1 必须编码（⭐⭐⭐）

1. **玩家战斗状态**: energy, hp, block, powers
2. **手牌**: 每张卡的 id, cost, type, is_playable, has_target
3. **怪物状态**: hp, block, intent, powers（最多3个怪物）
4. **可用命令**: available_commands（用于 Action Masking）
5. **选择列表**: choice_list/options（商店/事件/奖励）

### 9.2 重要编码（⭐⭐）

1. **牌库统计**: deck, draw_pile, discard_pile 的卡牌构成
2. **遗物**: relics 列表
3. **药水**: potions 列表及可用性
4. **怪物历史**: last_move_id, second_last_move_id
5. **地图信息**: 当前层、可选节点

### 9.3 可选编码（⭐）

1. **游戏进度**: floor, act, ascension_level
2. **详细屏幕信息**: body_text, confirm_up 等
3. **卡牌详细属性**: rarity, ethereal, exhausts
4. **计数器**: counter, cards_discarded_this_turn

### 9.4 不编码（❌）

1. **UUID**: 所有 xxx.uuid 字段
2. **随机种子**: seed
3. **名称文本**: name（中文），用 id 代替
4. **label**: 选项标签

---

*文档版本: 1.0*
*最后更新: 2025-02-05*
