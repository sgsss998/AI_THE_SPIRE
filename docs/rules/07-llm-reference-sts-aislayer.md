# 07 - LLM 参考：STS-AISlayer

> **来源**：[Steam 创意工坊 - AI Slayer AI爬塔](https://steamcommunity.com/sharedfiles/filedetails/?id=3489693353)、[GitHub - patient1234/STS-AISlayer](https://github.com/patient1234/STS-AISlayer)  
> **用途**：借鉴其 LLM 调用范式与规则设计，用于本项目的 LLM 决策或混合策略

---

## 原理概述

**是的，STS-AISlayer 通过调用大模型 API 来控制角色。**

- **架构**：ModTheSpire  Mod，在游戏内直接调用 OpenAI 兼容的 `chat/completions` API
- **支持平台**：OpenAI、DeepSeek 等（通过配置 apiKey、apiUrl、model）
- **决策方式**：使用 **Function Calling（工具调用）**，LLM 不输出自由文本，而是选择工具并传入结构化参数

---

## 状态表示（getInfo）

Mod 将游戏状态序列化为 JSON 传给 LLM，结构大致如下：

| 字段 | 说明 |
|------|------|
| `当前回合` | 回合数 |
| `现在你可以做的事` | 当前可执行动作描述 |
| `生物` | 玩家 + 怪物数组 |

**玩家信息**：角色、金币、血量、格挡、能量、姿态、钥匙、药水、充能球、遗物、总牌组、手牌、抽牌堆、弃牌堆、消耗牌堆、效果

**手牌格式**：`(序号: N) 牌名 (需要X能量/不能打出)`，**序号为 0-based**

**怪物信息**：名称、序号、血量、格挡、意图、效果

**意图翻译**：将游戏 intent 转为中文（如 `ATTACK` → 造成X伤害，`DEFEND` → 获得格挡）

---

## 工具定义（Function Calling）

LLM 通过以下工具做出决策：

### playCard

- **描述**：选择一张手牌打出，会消耗能量
- **参数**：
  - `index`：手牌序号，**0-based**
  - `target`：目标生物序号（0=玩家，1=第一个怪物…）
  - `reason`：选择理由，一句简单幽默的话

### endTurn

- **描述**：结束当前回合
- **参数**：
  - `suicide`：若认为无机会，可设为 true 放弃
  - `reason`：结束理由

### usePotion

- **描述**：使用药水
- **参数**：`index`、`target`、`reason`

### select

- **描述**：从列表中选择（卡牌、遗物、地图路线等）
- **参数**：`Indexes`（数组）、`reason`

### boolean

- **描述**：是/否选择（如开宝箱）
- **参数**：`boolean`、`reason`

---

## 可借鉴规则

### 1. 强制 reason 字段

每个动作都要求 LLM 给出 `reason`，便于：

- 调试与日志分析
- 人类监督
- 后续做「理由 → 动作」的监督学习

**建议**：在 AI_THE_SPIRE 的 LLM 决策层也加入 reason 字段。

### 2. 动态注入未知内容说明

遇到 LLM 可能不认识的药水、遗物、卡牌、关键词时，STS-AISlayer 会：

- 检测 `knownPotions`、`knownRelics`、`knownCards`、`knownKeywords`
- 将未知项的描述以 system 消息形式追加到对话中

**建议**：在调用 LLM 前，对当前状态中的卡牌/遗物/药水/关键词做一次「未知检测」，并注入简短说明。

### 3. 使用 Function Calling 而非自由文本

- 优点：输出格式稳定，无需解析自然语言
- 缺点：需预先定义好工具 schema

**建议**：若引入 LLM，优先采用 Function Calling，工具定义与 Mod 协议（如 `play`、`end`）一一对应。

### 4. 索引约定差异

| 项目 | 手牌索引 | 说明 |
|------|----------|------|
| STS-AISlayer | 0-based | `index` 从 0 开始 |
| AI_THE_SPIRE Mod 协议 | 1-based | `play 1` = 第一张牌 |

**注意**：借鉴 STS-AISlayer 的 prompt 或工具定义时，需在发送给 Mod 前将 0-based 转为 1-based。

### 5. 自杀/放弃机制

`endTurn` 支持 `suicide`，当局面无解时可主动放弃，避免卡死。

**建议**：在规则策略或 LLM 策略中，可增加「无合法动作时选择放弃」的兜底逻辑。

### 6. 对话历史

STS-AISlayer 使用 `messagesArray` 保留多轮对话，包括：

- 用户消息：`[当前信息]: {state}`
- 系统提示：未知药水/遗物/卡牌/关键词说明
- 助手 tool_calls 与 tool 响应

**建议**：若做多步推理或需要上下文，可保留有限长度的对话历史；纯单步决策可不用。

### 7. 状态描述语言

STS-AISlayer 使用**中文**描述状态，便于中文 LLM 理解。

**建议**：根据所用 LLM 的语言能力，选择中文或英文；保持字段命名与现有规则文档一致。

---

## STS-AISlayer 的限制（作者说明）

- 事件选择、火堆选择、商店购买：**未实现**
- 选牌类操作：卡牌删除、卡牌升级等 **已支持**
- 尽量不要干扰 AI，否则可能报错或崩溃
- 与其他 Mod 的兼容性有限

---

## 与本项目的关系

| 本项目 | STS-AISlayer |
|--------|--------------|
| 外部 Python + Mod 协议 | 游戏内 Java Mod |
| 规则策略 + 可选 ML 模型 | 纯 LLM Function Calling |
| 1-based play 命令 | 0-based index |
| 精简状态日志 | 完整 JSON 状态 |

可借鉴点：**工具定义结构**、**reason 字段**、**未知内容注入**、**自杀兜底**。实现时需适配本项目的 Mod 协议与索引约定。
