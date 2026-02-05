# AI_THE_SPIRE 完整 S 向量设计方案

> **设计原则**：s 向量信息量 = Mod 日志信息的子集，维度数远大于原始参数数量
> **设计目标**：穷尽所有游戏状态，建立权威、完整、可扩展的状态表示

---

## 目录
- [一、Mod 日志参数筛选](#一mod-日志参数筛选)
- [二、S 向量架构设计](#二s-向量架构设计)
- [三、各区块详细设计](#三各区块详细设计)
- [四、完整维度索引](#四完整维度索引)
- [五、编码器实现规范](# 五编码器实现规范)

---

## 一、Mod 日志参数筛选

### 1.1 排除的参数（不编码）

| 参数路径 | 原因 |
|---------|------|
| `in_game` | 对决策无价值（游戏内/外状态） |
| `error` | 错误状态，正常情况为空 |
| `game_state.screen_name` | 与 screen_type 功能重复 |
| `game_state.is_screen_up` | 可从 screen_state 推断 |
| `game_state.action_phase` | 可从 available_commands 推断 |
| `game_state.current_action` | 上一动作，对未来决策无直接价值 |
| `game_state.seed` | 随机性信息，对AI无意义 |
| `Card.uuid` | 唯一标识，对决策无意义 |
| `Reward.uuid` | 唯一标识，对决策无意义 |

### 1.2 保留的核心参数（全部编码）

```
顶层控制：
- action (上一动作，用于防卡住检测)
- available_commands (Action Masking 核心依据)
- ready_for_command

游戏进度：
- act, floor, room_phase, room_type, screen_type

玩家状态：
- class, ascension_level, max_hp, current_hp, gold

牌组资源：
- deck (完整牌组)
- relics (遗物列表)
- potions (药水栏，最多3格)

战斗状态：
- turn, hand, draw_pile, discard_pile, exhaust_pile
- card_in_play, cards_discarded_this_turn, times_damaged
- player (energy, max_hp, current_hp, block, powers, orbs)

怪物状态：
- monsters[] (1-3个怪物，含完整属性)

屏幕详情：
- screen_state (事件/商店/地图/奖励等)
```

---

## 二、S 向量架构设计

### 2.1 总体结构（10大区块）

```
┌─────────────────────────────────────────────────────────────┐
│                    S 向量 (总计: ~2500-3000 维)                │
├──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┤
│ 区块1 │ 区块2 │ 区块3 │ 区块4 │ 区块5 │ 区块6 │ 区块7 │ 区块8 │ 区块9 │ 区块10│
│ 玩家  │ 手牌  │抽牌堆 │ 弃牌堆 │ 消耗堆 │玩家Powers│ 怪物  │ 遗物  │ 药水  │ 全局  │
│ 核心  │      │      │      │      │       │       │       │       │       │
└──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┘
  ~50   ~400  ~400  ~400  ~300  ~100   ~600   ~200   ~100   ~2500维
```

### 2.2 设计原则

1. **Multi-Hot编码**：卡牌、遗物、药水等使用 one-hot/multi-hot
2. **比例特征**：HP、能量等使用原始值 + 比例值
3. **历史信息**：move_id, last_move_id, second_last_move_id
4. **扩展性预留**：为未来可能的新卡牌/遗物预留空间

---

## 三、各区块详细设计

### 区块1：玩家核心状态 (~50维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 0-1 | 当前/最大HP比例 | `current_hp / max_hp`, `max_hp / 200` | 标准化到0-1，200为假设最大值 |
| 2-3 | 能量状态 | `current_energy / 10`, `max_energy / 10` | 考虑能量球上限扩展 |
| 4-5 | 护甲 | `block / 100` (标准化), `block` (原始值) | 护甲也需要原始值用于计算 |
| 6-7 | 金币 | `gold / 1000` (标准化), `gold / 999` (截断) | 999为金量上限 |
| 8 | 角色类型 | one-hot 4维 | THE_SILENT, THE_IRONCLAD, THE_DEFECT, THE_WATCHER |
| 9-10 | 难度等级 | `ascension_level / 20`, `ascension_level` | 标准化 + 原始值 |
| 11-13 | 章节 one-hot | one-hot 4维 | act 1/2/3/4，包含"Beyond" |
| 14-18 | 核心状态 one-hot | one-hot 5维 | IN_GAME, EVENT, COMBAT, MAP, SHOP, REST, BOSS, NONE |
| 19-23 | Buff/Debuff计数 | `count(power_type) / 10` | 各类 power 的计数 |
| 24-25 | 回合信息 | `turn / 50`, `turn` (标准化) | 50为假设最大回合数 |
| 26-30 | 牌组统计 | `deck_size / 50`, `deck_size` | 牌组总卡牌数 |
| 31-35 | 本回合统计 | `cards_discarded_this_turn / 10`, `times_damaged` | 本回合弃牌/受击次数 |
| 36-40 | 预留扩展 | 全0 | 为未来状态预留 |
| **总计** | **50维** | | |

---

### 区块2：手牌状态 (~400维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 40-310 | 卡牌 Multi-Hot | multi-hot 271维 | 271张卡牌池 (详见下表) |
| 311-340 | 手牌属性 (10张牌×3) | 每张牌 3 维 × 10 | `[cost, is_playable, has_target]` × 10 |
| 341-350 | 手牌统计特征 | - | 见下表 |
| 351-390 | 预留扩展 | 全0 | 为未来卡牌预留 |

**手牌统计特征**：
| 特征 | 编码 |
|------|------|
| 手牌数量 | 原始值 |
| 0费牌数量 | 原始值 |
| 可出牌数量 | 原始值 |
| 攻击牌数量 | 原始值 |
| 技能牌数量 | 原始值 |
| 能量牌数量 | 原始值 |
| 虚无牌数量 | 原始值 |
| 升级牌数量 | 原始值 |
| 需目标牌数量 | 原始值 |
| 手牌总费用 | 原始值 |

---

### 区块3：抽牌堆状态 (~400维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 390-660 | 抽牌堆 Multi-Hot | multi-hot 271维 | 271张卡牌池 |
| 661-680 | 抽牌堆统计 | - | 见下表 |
| 681-690 | 牌堆构成比例 | one-hot 6维 | ATTACK/SKILL/POWER/STATUS/CURSE/Colorless |
| 691-700 | 预留扩展 | 全0 | 为未来功能预留 |

**抽牌堆统计特征**：
| 特征 | 编码 |
|------|------|
| 抽牌堆数量 | 原始值 |
| 0费牌数量 | 原始值 |
| 可用牌数(估算) | 原始值 |
| 稀有度分布 | [Common, Uncommon, Rare, Special] 计数 / 50 |

---

### 区块4：弃牌堆状态 (~400维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 700-970 | 弃牌堆 Multi-Hot | multi-hot 271维 | 271张卡牌池 |
| 971-990 | 弃牌堆统计 | - | 同抽牌堆 |
| 991-1000 | 弃牌堆构成比例 | one-hot 6维 | ATTACK/SKILL/POWER/STATUS/CURSE/Colorless |
| 1001-1010 | 本回合弃牌统计 | - | `cards_discarded_this_turn` 相关 |
| 1011-1020 | 预留扩展 | 全0 | |

---

### 区块5：消耗堆状态 (~300维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 1020-1290 | 消耗堆 Multi-Hot | multi-hot 271维 | 271张卡牌池 |
| 1291-1310 | 消耗堆统计 | - | 同抽牌堆 |
| 1311-1320 | 消耗堆构成比例 | one-hot 6维 | ATTACK/SKILL/POWER/STATUS/CURSE/Colorless |
| 1321-1330 | 预留扩展 | 全0 | |

---

### 区块6：玩家 Powers (~100维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 1330-1339 | 核心 Powers (10) | `amount / 10` (标准化) | Strength, Dexterity, Focus, Artifact, etc. |
| 1340-1419 | Buff/Debuff Pool (80) | `amount / 10` | 80种常见 Powers |
| 1420-1429 | 预留扩展 | 全0 | 为新 Power 预留 |

**核心 Powers (10)**：
1. Strength (力量)
2. Dexterity (敏捷)
3. Focus (专注 - Defect)
4. Artifact (人工造物 - 免疫 debuff)
5. Plated Armor (板甲 - 每回合+护甲)
6. Energized (充能 - 能量球相关)
7. Draw Reduction (抽牌减少)
8. Retain (保留 - 手牌保留)
9. Metallicize (金属化 - 回合结束+护甲)
10. Temporary HP (临时生命)

**Buff/Debuff Pool (80)**：
- **攻击性**：Vulnerable, Weak, Frail, Poison, Burn, etc.
- **防御性**：Block gain, Energy gain, Heal, etc.
- **特殊**：Intangible, No Draw, etc.

---

### 区块7：怪物状态 (~600维)

**单怪物编码 (50维 × 6 = 300维)**：

| 维度 | 特征 | 编码 |
|------|------|------|
| 0-2 | 怪物 ID one-hot | 3维 (小/中/大史莱姆等) |
| 3-4 | HP状态 | `current_hp / max_hp`, `max_hp / 300` |
| 5-6 | 护甲 | `block / 50` (标准化), `block` (原始) |
| 7-14 | Intent one-hot | 8维 (ATTACK/DEFEND/BUFF/DEBUFF/ATTACK_BUFF/ATTACK_DEBUFF/UNKNOWN/NONE) |
| 15 | 调整后伤害 | `move_adjusted_damage / 50` |
| 16 | 打击次数 | `move_hits / 10` |
| 17-18 | 死亡状态 | `is_gone`, `half_dead` |
| 19-20 | 历史意图 | `last_move_id / 100`, `second_last_move_id / 100` |
| 21-40 | Monster Powers (20) | `amount / 10` × 20 | 每个怪物最多20种 Powers |
| 41-49 | 预留扩展 | 全0 | 为复杂怪物机制预留 |

**怪物全局统计 (~50维)**：
- 存活怪物数量 (1-3)
- 总威胁度评估
- 总 HP 比例
- 主要意图分布
- 等

---

### 区块8：遗物状态 (~200维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 1650-1829 | 遗物 Multi-Hot | multi-hot 180维 | 180个遗物池 (详见下表) |
| 1830-1850 | 遗物统计 | - | 见下表 |
| 1851-1870 | 关键遗物组合标记 | binary | 特殊遗物组合效果 |

**遗物统计特征**：
| 特征 | 编码 |
|------|------|
| 遗物总数 | 原始值 |
| 稀有度分布 | [Common, Uncommon, Rare, Boss, Special] × 计数 |
| 能量球相关遗物数 | 原始值 |
| 伤害相关遗物数 | 原始值 |
| 等等 |

---

### 区块9：药水状态 (~200维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 1870-1904 | 药水槽位 (3×5) | 每个槽位 5 维 | `[id_one_hot(45), can_use, can_discard, requires_target, is_empty]` |
| 1905-1920 | 药水统计 | - | 见下表 |
| 1921-1970 | 预留扩展 | 全0 | 为新药水预留 |

**药水槽位编码**：
- 每个槽位：
  - 药水 ID one-hot (45维)
  - 可用性 (1维)
  - 可丢弃 (1维)
  - 需要目标 (1维)
  - 是否为空 (1维)

**药水统计特征**：
| 特征 | 编码 |
|------|------|
| 药水总数 | 原始值 |
| 可用药水数 | 原始值 |
| 战斗用药水数 | 原始值 |
| 稀有度分布 | [Common, Uncommon, Rare] × 计数 |

---

### 区块10：全局状态 (~250维)

| 维度索引 | 特征名称 | 编码方式 | 说明 |
|----------|---------|---------|------|
| 1971-1980 | 楼层/章节 | `floor / 60`, `act one-hot 4` | 当前楼层标准化/one-hot |
| 1981-2000 | 地图信息 | - | 当前节点坐标、可选节点数等 |
| 2001-2020 | 可用命令 | `available_commands` one-hot (20) | play, end, choose, proceed, confirm, etc. |
| 2021-2050 | 选择列表信息 | - | 选项数量、类型、价值等 |
| 2051-2100 | 屏幕状态详情 | - | 根据 screen_type 动态编码 |
| 2101-2150 | 防卡住检测 | - | 命令重复、状态重复历史 |
| 2151-2200 | 预留扩展 | 全0 | 为未来功能预留 |

---

## 四、完整维度索引

### 4.1 卡牌池 (271张)

**分类统计**：
- **诅咒卡牌**：14张
- **状态卡牌**：12张
- **角色卡牌**：4角色 × ~73 = ~292张 (实际去重后271张)
- **无色卡牌**：47张

**详细列表**（按类型分组）：

**Basic (基础卡)** - 每角色5张：
- Ironclad: Strike, Defend, Bash, Anger(+) → 实际4张
- Silent: Strike, Defend, Neutralize, Survivor
- Defect: Strike, Defend, Dualcast, Zap
- Watcher: Strike, Defend, Eruption, Vigilance

**Common (普通卡)**：~60张/角色

**Uncommon (稀有卡)**：~35张/角色

**Rare (史诗卡)**：~25张/角色

**Colorless (无色卡)**：47张
- Curse (诅咒)：12张
- Status (状态)：9张
- Skill (技能)：7张
- Attack (攻击)：8张
- Special (特殊)：11张

### 4.2 遗物池 (180个)

**Starter (起始遗物)** - 4角色各2个：
- Ironclad: Burning Blood, Black Blood
- Silent: Ring of the Snake, Ring of the Serpent
- Defect: Cracked Core, Frozen Core
- Watcher: Pure Water, Holy Water

**Boss (Boss遗物)** - 每章节11个，共44个：
- Act 1: 11个
- Act 2: 11个
- Act 3: 11个
- Act 4: 11个

**Common (普通遗物)**：~50个

**Uncommon (稀有遗物)**：~50个

**Rare (史诗遗物)**：~20个

**Special (特殊遗物)**：10个
- Ectoplasm, Tiny Chest, etc.

### 4.3 药水池 (45个)

**按角色分类**：
- 通用药水：~15个
  - Attack Potion, Block Potion, Fire Potion, etc.
- Ironclad 专属：3个
- Silent 专属：3个
- Defect 专属：3个
- Watcher 专属：3个

**按稀有度分类**：
- Common：~20个
- Uncommon：~15个
- Rare：~10个

### 4.4 Monster Pool (怪物ID)

**Act 1 怪物** (~20种)：
- Cultist, Jaw Worm, Louse (M/S), Slime (M/S/L), Gremlin variants, Slaver, Fungi Beast, Looter, etc.

**Act 2 怪物** (~30种)：
- Spheric Guardian, Chosen, Shelled Parasite, Byrd, Thieves, Sentry, Snake Plant, Snecko, Centurion, Mystic, etc.

**Act 3 怪物** (~25种)：
- Darkling, Orb Walker, Shapes (Repulsor/Exploder/Spiker), Maw, Transient, Jaw Worm Horde, Writhing Mass, etc.

### 4.5 Power Pool (80种)

**Buff (增益效果)** (~40种)：
- Strength, Dexterity, Focus, Artifact, Plated Armor, Energized, Metallicize, Draw Reduction, Retain, etc.

**Debuff (减益效果)** (~40种)：
- Weak, Vulnerable, Frail, Poison, Burn, Curse of Bell, Decay, Doubt, etc.

---

## 五、编码器实现规范

### 5.1 数据结构定义

```python
class SVectorConfig:
    """S 向量配置常量"""

    # 区块维度
    BLOCK1_PLAYER_CORE = 50
    BLOCK2_HAND = 400
    BLOCK3_DRAW_PILE = 400
    BLOCK4_DISCARD_PILE = 400
    BLOCK5_EXHAUST_PILE = 300
    BLOCK6_PLAYER_POWERS = 100
    BLOCK7_MONSTERS = 600
    BLOCK8_RELICS = 200
    BLOCK9_POTIONS = 200
    BLOCK10_GLOBAL = 250

    TOTAL_DIM = BLOCK1_PLAYER_CORE + BLOCK2_HAND + BLOCK3_DRAW_PILE + \
                 BLOCK4_DISCARD_PILE + BLOCK5_EXHAUST_PILE + BLOCK6_PLAYER_POWERS + \
                 BLOCK7_MONSTERS + BLOCK8_RELICS + BLOCK9_POTIONS + BLOCK10_GLOBAL
    # 约 2500-3000 维

    # 各类池大小
    CARD_POOL_SIZE = 271
    RELIC_POOL_SIZE = 180
    POTION_POOL_SIZE = 45
    POWER_POOL_SIZE = 80
    MONSTER_POOL_SIZE = ~75

    # 上下文
    MAX_HAND_SIZE = 10
    MAX_MONSTERS = 6
    MAX_ORB_SLOTS = 10
```

### 5.2 编码接口规范

```python
from typing import Dict, Any
import numpy as np

class SVectorEncoder:
    def __init__(self, config: SVectorConfig):
        self.config = config
        self._load_lookup_tables()

    def encode(self, mod_response: Dict[str, Any]) -> np.ndarray:
        """将 Mod 响应编码为 s 向量"""
        s = np.zeros(self.config.TOTAL_DIM)

        # 区块1: 玩家核心
        s[0:50] = self._encode_player_core(mod_response)

        # 区块2: 手牌
        s[50:450] = self._encode_hand(mod_response)

        # ... 其他区块

        return s

    def _encode_player_core(self, response: Dict) -> np.ndarray:
        """编码玩家核心状态"""
        # 实现细节...
        pass

    def _encode_hand(self, response: Dict) -> np.ndarray:
        """编码手牌状态"""
        # 实现细节...
        pass

    # ... 其他编码方法
```

### 5.3 归一化标准

| 特征类型 | 归一化方法 | 原因 |
|---------|-----------|------|
| HP/Energy/Block | `value / max_value` | 有明确物理上限 |
| Gold | `min(value, 999) / 999` | 金钱有软上限 |
| Turn | `turn / 50` | 回合数一般在50内 |
| Power 数量 | `amount / 10` | Power 数量通常是个位数 |

---

## 六、实施计划

### 阶段1：基础映射表建立
- [ ] 从 slaythespire.wiki.gg 导出完整卡牌列表
- [ ] 从 slaythespire.wiki.gg 导出完整遗物列表
- [ ] 从 slaythespire.wiki.gg 导出完整怪物列表
- [ ] 建立 encoder_ids_v2.yaml (更新版ID映射表)

### 阶段2：编码器实现
- [ ] 实现 SVectorEncoder 类
- [ ] 编写单元测试
- [ ] 验证与现有 encoder.py 的兼容性

### 阶段3：性能优化
- [ ] 向量化计算优化
- [ ] 缓存机制（ID查表、归一化常量）
- [ ] 批量编码支持

### 阶段段4：验证与调试
- [ ] 与真实游戏数据对比验证
- [ ] 维度重要性分析
- [ ] 可视化工具开发

---

## 附录：完整的 ID 映射表结构

```yaml
# encoder_ids_v2.yaml 结构

cards:
  UNKNOWN: 0
  # Basic Cards
  AscendersBane: 1
  Strike_R: 2
  Defend_R: 3
  Bash: 4
  ... (共271张)

relics:
  UNKNOWN: 0
  # Starter Relics
  Ring of the Snake: 1
  Burning Blood: 2
  ... (共180个)

potions:
  UNKNOWN: 0
  AttackPotion: 1
  BlockPotion: 2
  ... (共45个)

powers:
  UNKNOWN: 0
  Strength: 1
  Weak: 2
  Vulnerable: 3
  ... (共80个)

intents:
  UNKNOWN: 0
  ATTACK: 1
  DEFEND: 2
  BUFF: 3
  DEBUFF: 4
  ... (共13个)

monsters:
  UNKNOWN: 0
  # Act 1
  Cultist: 1
  Jaw Worm: 2
  ... (共~75个)
```

---

*文档版本: 2.0*
*创建时间: 2025-02-06*
*最后更新: 2025-02-06*
*负责人: AI_THE_SPIRE Team*
