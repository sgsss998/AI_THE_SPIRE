# 规则体系总览

> **版本**：v0.1  
> **范围**：标准模式、A20、静默猎手  
> **用途**：AI 开发与数据采集的语义基准

---

## 文档索引

| 编号 | 文件 | 说明 | 依赖 |
|------|------|------|------|
| 01 | [01-game-flow.md](./01-game-flow.md) | 游戏流程：进入游戏后第一步、第二步… | 无 |
| 02 | [02-combat-turn.md](./02-combat-turn.md) | 战斗回合结构 | 01 |
| 03 | [03-protocol.md](./03-protocol.md) | CommunicationMod 协议与状态字段 | 01 |
| 04 | [04-data-recording.md](./04-data-recording.md) | 数据记录规则 | 01, 02, 03 |
| 05 | [05-silent-basics.md](./05-silent-basics.md) | 静默猎手基础 | 02 |
| 06 | [06-ascension.md](./06-ascension.md) | A20 难度加成 | 01 |
| 07 | [07-llm-reference-sts-aislayer.md](./07-llm-reference-sts-aislayer.md) | LLM 参考：STS-AISlayer 原理与可借鉴规则 | 02, 03 |
| 08 | [08-sts-ai-master-reference.md](./08-sts-ai-master-reference.md) | STS-AI-Master 参考：监督学习可借鉴规则 | 02, 03, 04 |
| — | [ACTION_ID_MAP.md](./ACTION_ID_MAP.md) | Action ID 简明映射表（0–132） | 03 |

---

## 规则层级

| 层级 | 文件 | 变更频率 |
|------|------|----------|
| 核心 | 01, 02, 03 | 极少 |
| 数据 | 04 | 中 |
| 角色/难度 | 05, 06 | 低 |
| 参考 | 07 | 低 |

---

## 扩展规则引入

1. 新规则放入 `rules/` 或 `rules/_extensions/`，按编号排序（如 `07-map.md`）。
2. 在本文件「文档索引」中登记。
3. 核心规则（01–03）不轻易增删。

---

## 参考资料

- [Slay the Spire Wiki - Combat Mechanics](https://slay-the-spire.fandom.com/wiki/Combat_Mechanics)
- [Slay the Spire Wiki - Card Draw](https://slay-the-spire.fandom.com/wiki/Card_Draw)
- [Slay the Spire Wiki - Energy](https://slay-the-spire.fandom.com/wiki/Energy)
- [Slay the Spire Wiki - Ascension](https://slay-the-spire.fandom.com/wiki/Ascension)
- [游民星空 - 杀戮尖塔新手入门指南](https://www.gamersky.com/handbook/201901/1148245.shtml)
- [游民星空 - 战斗流程介绍](https://www.gamersky.com/handbook/201901/1148245_2.shtml)
