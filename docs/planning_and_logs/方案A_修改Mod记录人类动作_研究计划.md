# 方案 A：修改 CommunicationMod 记录人类动作 — 研究计划

> **目标**：在 Mod 内部 hook 人类操作，将 `action_id` 写入 JSON，供 `read_state.py` 精确记录。  
> **模式**：研究阶段 — 仅收集信息、验证可行性，不实施代码。

---

## 一、研究目标

1. 确认 CommunicationMod 中可 hook 的人类操作入口点
2. 明确各操作类型（出牌、结束回合、选择、药水等）对应的游戏内部调用链
3. 设计 `last_action` 字段格式，与 `action.py` 的 173 维 action_id 对齐
4. 评估实现难度与风险

---

## 二、前置知识梳理

### 2.1 现有 Mod 架构（已掌握）

| 组件 | 职责 |
|------|------|
| `GameStateConverter.getCommunicationState()` | 构造发往 Python 的 JSON，当前含 `available_commands`、`ready_for_command`、`in_game`、`game_state` |
| `CommandExecutor` | 执行 Python 发来的命令（play、end、choose 等），人类操作不经过此路径 |
| `GameStateListener` | 检测状态变化，决定何时发送新状态；已有 `registerStateChange()`、`signalTurnStart()` 等 |
| `patches/` | 使用 SpirePatch 注入游戏逻辑，如 `GameActionManagerTopPatch`、`EnableEndTurnPatch` |

### 2.2 本项目 action_id 定义（ACTION_ID_MAP.md）

| ID 范围 | 操作 | Mod 命令格式 |
|---------|------|--------------|
| 0–69 | 出牌（手牌 1–10 × 目标 0–6） | `play <i> [t]` |
| 70–109 | 药水使用/丢弃 | `potion use/discard <i> [t]` |
| 110–169 | 选择 | `choose <index>` |
| 170–172 | end / proceed / cancel | `end` / `proceed` / `cancel` |

---

## 三、研究任务清单

### 阶段 1：定位人类操作的 Hook 点

#### 任务 1.1 出牌（play）

- [ ] **1.1.1** 查阅 Slay the Spire 源码或 ModTheSpire 文档，确认人类点击出牌时的调用链
  - 候选：`AbstractPlayer.useCard(AbstractCard, AbstractMonster, int)`
  - 或：`AbstractGameAction` 子类、`CardQueueItem` 入队处
- [ ] **1.1.2** 在 CommunicationMod 的 `patches/` 中查找是否已有相关 patch
- [ ] **1.1.3** 确定可获取的信息：手牌索引（0-based 或 1-based）、目标怪物索引
- [ ] **1.1.4** 验证：手牌顺序在「点击时」与「Mod 发送的 hand 列表」是否一致（uuid 匹配）

#### 任务 1.2 结束回合（end）

- [ ] **1.2.1** 查阅人类点击「结束回合」按钮时的调用链
  - 已知：`EnableEndTurnPatch` 监听 `EnableEndTurnButtonAction`，用于 `signalTurnStart()`
  - 需找：结束回合按钮被点击时的 Action 或回调
- [ ] **1.2.2** 确认是否有 `EndTurnAction` 或类似类可 patch

#### 任务 1.3 选择（choose）

- [ ] **1.3.1** 查阅 `ChoiceScreenUtils.executeChoice()` 的调用者（人类点击选项时）
- [ ] **1.3.2** 确认可获取：`choice_index`（0-based）
- [ ] **1.3.3** 区分：事件、商店、奖励、地图、涅奥、火堆删牌等，choice_index 是否统一

#### 任务 1.4 确认/取消（proceed / cancel）

- [ ] **1.4.1** 查阅 `ChoiceScreenUtils.pressConfirmButton()` / `pressCancelButton()` 的调用者
- [ ] **1.4.2** 确认人类点击「确认」「取消」时的入口

#### 任务 1.5 药水（potion use / discard）

- [ ] **1.5.1** 查阅人类使用/丢弃药水时的调用链
- [ ] **1.5.2** 确认可获取：药水槽位索引、目标索引（若需要）

---

### 阶段 2：设计 last_action 字段

#### 任务 2.1 字段格式

- [ ] **2.1.1** 设计 JSON 结构，与 `action.py` 的 `from_command()` 兼容
  - 方案 A：`last_action: {"id": 42, "cmd": "play 2 0"}`（冗余，便于调试）
  - 方案 B：`last_action: {"id": 42}`（精简）
  - 方案 C：`last_action_id: 42`（最简）
- [ ] **2.1.2** 确定「无动作」时的表示：`null` 或省略

#### 任务 2.2 作用域与生命周期

- [ ] **2.2.1** `last_action` 应关联到「上一次状态变化前人类执行的动作」
- [ ] **2.2.2** 何时清空：每次发送 JSON 后清空？还是保留直到下一次人类操作？
- [ ] **2.2.3** 动画/过渡帧：`action_phase != WAITING_ON_USER` 时是否填充 `last_action`（可能为上一决策点的动作）

---

### 阶段 3：注入点与实现路径

#### 任务 3.1 注入位置

- [ ] **3.1.1** 在 `GameStateConverter.getCommunicationState()` 或 `getGameState()` 中，从「全局/静态存储」读取 `last_action` 并加入 response
- [ ] **3.1.2** 设计存储类：如 `HumanActionRecorder`，线程安全（若游戏为单线程可简化）

#### 任务 3.2 与 GameStateListener 的协作

- [ ] **3.2.1** 人类操作触发 `registerStateChange()` 的时机，与「记录 last_action」的先后顺序
- [ ] **3.2.2** 确保：先记录动作，再在状态稳定时发送 JSON

#### 任务 3.3 与 Python 命令执行的区分

- [ ] **3.3.1** 当 Python 发送 `play` 等命令时，Mod 通过 `CommandExecutor` 执行，此时可**直接**在 `CommandExecutor` 内记录（来源为 Python，非人类）
- [ ] **3.3.2** 决策：人类操作与 Python 命令是否共用 `last_action` 字段？若共用，需在 Mod 内区分来源；若仅记录人类，则 Python 命令时 `last_action` 为 null

---

### 阶段 4：风险与边界情况

#### 任务 4.1 边界情况

- [ ] **4.1.1** 人类快速连续操作：两帧之间多个动作，是否都能记录？是否只记录最后一个？
- [ ] **4.1.2** key/click 命令：`action_id` 中未显式包含 `key Confirm` 等，是否映射到 171/172？
- [ ] **4.1.3** 多目标卡牌、多选界面（GridCardSelectScreen、HandCardSelectScreen）：如何映射到 110–169？

#### 任务 4.2 兼容性

- [ ] **4.2.1** 修改后的 Mod 与原生 CommunicationMod 的协议兼容性：新增字段是否破坏现有 Python 解析
- [ ] **4.2.2** 其他 Mod 冲突：若 patch 了相同方法，加载顺序的影响

---

## 四、产出物

| 产出 | 说明 |
|------|------|
| Hook 点清单 | 每个动作类型对应的类、方法、参数 |
| last_action 规范 | 字段名、结构、取值约定 |
| 实现路径图 | 从 patch 到 JSON 输出的数据流 |
| 风险清单 | 已知边界情况与缓解措施 |

---

## 五、参考资源

- [CommunicationMod 源码](https://github.com/ForgottenArbiter/CommunicationMod)
- [ModTheSpire SpirePatch 文档](https://github.com/kiooeht/ModTheSpire/wiki/SpirePatch)
- 本项目：`docs/rules/ACTION_ID_MAP.md`、`src/core/action.py`
- 本项目：`docs/rules/03-protocol.md`

---

## 六、下一步

研究完成后，根据结论决定：

1. **进入计划模式**：若可行，编写详细技术规范与实施检查清单  
2. **调整方案**：若某类动作无法 hook，评估是否接受「部分精确 + 部分推断」  
3. **退回方案 B**：若 Mod 修改成本过高，考虑代理界面方案
