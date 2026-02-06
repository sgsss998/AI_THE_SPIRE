# A20 静默猎手 S 向量精简执行计划

> **目标**：将 encoder 精简为仅针对 A20 静默猎手的训练配置，降低参数量、提高训练效率。
> **原则**：直接修改 `encoder.py` 及关联文件，不新建 `encoder_silent.py`。

---

## 一、精简规则汇总

### 1.1 可移除的维度
| 维度 | 原因 |
|------|------|
| 角色编码 (4维) | 固定静默猎手 |
| 难度编码 (1维) | 固定 A20 |
| Orb 相关 (6维) | 猎人无 orb：槽位数、球类型 one-hot、Evoke 计数 |

### 1.2 卡牌池变更
| 保留 | 移除 |
|------|------|
| UNKNOWN + 诅咒14 + 状态5 + **静默职业牌** + 无色47 | 铁甲、缺陷、观者职业牌 |
| 遗物完整保留 | - |

**静默卡牌数量**：猎手专属卡牌共 **75 张**（来源：[18183 杀戮尖塔猎手卡牌图鉴](https://www.18183.com/gonglue/202207/4064551.html)）。  
当前 encoder_ids.yaml 中静默牌约 69 张，执行时需**核对并补全缺失的 6 张**（如 Adrenaline 肾上腺素、Alchemize 炼制药水、Accuracy 精准等）。

### 1.3 参数上限调整
| 参数 | 原值 | 新值 |
|------|------|------|
| MAX_HP | 999 | 200 |
| MAX_DEBUFF (易伤等) | 15 | 99 |
| MAX_POWER (力量) | 50 | 99 |
| MAX_BLOCK | 99 | 999 |
| MAX_ENERGY | 10 | 20 |

### 1.4 灼热 (Searing Blow) 逻辑
- 移除灼热无限升级的特殊处理（铁甲牌，猎人无此牌）
- 手牌编码中 `upgrade_times` 简化为普通牌逻辑（0/1）

### 1.5 不可精简
- **遗物**：保持完整
- **药水、怪物、事件、房间**：保持完整

---

## 二、维度变化预估

| 区块 | 原维度 | 新维度 | 变化 |
|------|--------|--------|------|
| 区块1 玩家核心 | 58 | 47 | -11 (角色4 + 难度1 + Orb6) |
| 区块2 手牌 | 500 | CARD_DIM+229 | -129 (CARD_DIM 271→142) |
| 区块3 抽牌堆 | 450 | CARD_DIM+179 | -129 |
| 区块4 弃牌堆 | 450 | CARD_DIM+179 | -129 |
| 区块5 消耗堆 | 350 | CARD_DIM+79 | -129 |
| 区块6 玩家 Powers | 100 | 100 | 0 |
| 区块7 怪物 | 618 | 618 | 0 |
| 区块8 遗物 | 200 | 200 | 0 |
| 区块9 药水 | 200 | 200 | 0 |
| 区块10 全局 | 500 | 500 | 0 |
| **总计** | **3126** | **~2877** | **~-249** |

**CARD_DIM**：1 + 14 + 5 + **75** + 47 = **142**（猎手 75 张，来源：18183）

---

## 三、实施检查清单

### 阶段 1：configs/encoder_ids.yaml

1. **补全静默卡牌**：对照 [18183 猎手卡牌图鉴](https://www.18183.com/gonglue/202207/4064551.html) 核对，确保静默区有 **75 张**；若缺失则补充（如 Adrenaline、Alchemize、Accuracy 等）
2. 在 `cards` 区块中，删除铁甲战士 (Ironclad) 全部卡牌（索引 34–106 对应行）
3. 删除缺陷 (Defect) 全部卡牌（索引 187–263 对应行）
4. 删除观者 (Watcher) 全部卡牌（索引 265–328 对应行）
5. 保留：UNKNOWN、诅咒14、状态5、静默75、无色47
6. 更新文件头部注释，说明新结构：`UNKNOWN + 诅咒14 + 状态5 + 静默75 + 无色47 = 142`

### 阶段 2：src/training/encoder_utils.py

7. 将 `CARD_DIM` 从 271 改为 **142**
8. 移除 `orb_type_to_index` 函数及其 `_ORB_TYPE_MAP`（或保留但不再导出给 encoder）
9. 移除 `ORB_TYPE_DIM` 常量
10. 在 `encoder_utils.py` 的 `__all__` 或导出列表中移除 `orb_type_to_index`、`ORB_TYPE_DIM`（如有）

### 阶段 3：src/training/encoder.py

11. 更新 `MAX_HP = 200`, `MAX_BLOCK = 999`, `MAX_ENERGY = 20`, `MAX_POWER = 99`, `MAX_DEBUFF = 99`
12. 移除 `orb_type_to_index`、`ORB_TYPE_DIM` 的导入
13. 将 `BLOCK1_DIM` 从 58 改为 47
14. 在 `_encode_block1_player_core` 中：
    - 删除 [8–11] 角色 one-hot 编码逻辑
    - 删除 [12] 难度编码逻辑
    - 删除 [40] Orb 槽位、[45–48] 球类型、[49] Evoke 计数
    - 将原 [14–17] 章节 one-hot 前移为 [8–11]
    - 将原 [18–24] 房间阶段前移为 [12–18]
    - 将原 [25–29] Buff/Debuff 前移为 [19–23]
    - 将原 [30–39] 等后续维度整体前移，填补删除的 11 维
15. 重写区块1 的索引映射，确保 47 维连续且语义正确
16. 将 `BLOCK2_DIM` 从 500 改为 `CARD_DIM + 229`（= 371）
17. 将 `BLOCK3_DIM` 从 450 改为 `CARD_DIM + 179`（= 321）
18. 将 `BLOCK4_DIM` 从 450 改为 `CARD_DIM + 179`（= 321）
19. 将 `BLOCK5_DIM` 从 350 改为 `CARD_DIM + 79`（= 221）
20. 在 `_encode_block2_hand` 中：将 multi-hot 范围从 [0–270] 改为 [0–CARD_DIM-1]（即 [0–141]）
21. 在 `_encode_block2_hand` 中：移除灼热 (Searing Blow) 特殊逻辑，`upgrade_times` 统一为 0/1
22. 在 `_encode_block3_draw_pile`、`_encode_block4_discard_pile`、`_encode_block5_exhaust_pile` 中：将 multi-hot 范围改为 [0–CARD_DIM-1]
23. 更新 `OUTPUT_DIM` 计算公式
24. 更新文件头部注释中的区块维度和总维度说明（总维 ~2877）

### 阶段 4：关联代码检查

25. 检查 `src/env/sts_env.py`：使用 `StateEncoder`，仅依赖 `get_output_dim()`，无需修改
26. 检查 `src/agents/rl_agent.py`：同上，无需修改
27. 检查 `src/training/__init__.py`：导出 `OUTPUT_DIM`，无需修改
28. 检查 `src/training/power_parser.py`：保留所有 parse 函数（怪物/玩家可能仍有相关 power），无需修改

### 阶段 5：验证与测试

29. 运行 `python -c "from src.training.encoder import encode, get_output_dim; print(get_output_dim())"` 确认输出为 ~2877
30. 使用一份 Mod 格式的静默猎手战斗 JSON 调用 `encode(mod_response)`，检查无异常、输出形状正确
31. 若有 `scripts/verify_encoder*.py` 或相关测试，执行并修复失败用例

---

## 四、区块1 新结构（47 维）详细映射

| 索引 | 内容 |
|------|------|
| 0–7 | HP/能量/护甲/金币（同原 [0–7]） |
| 8–11 | 章节 one-hot (4维，原 [14–17]) |
| 12–18 | 房间阶段 one-hot (7维，原 [18–24]) |
| 19–23 | Buff/Debuff (5维，原 [25–29]) |
| 24 | 回合（原 [30]） |
| 25 | 牌组大小（原 [32]） |
| 26–31 | 本回合统计 + 牌堆数量 (6维，原 [34–39]) |
| 32–34 | 钥匙状态（红/蓝/绿，原 [41–43]） |
| 35 | 最大能量（原 [44]） |
| 36–46 | 预留 (11维，原 [50–57] 及合并后剩余) |

---

## 五、风险与注意事项

1. **encoder_ids.yaml 卡牌顺序**：删除铁甲/缺陷/观者后，静默和无色的索引会变化；`_build_card_id_to_index` 会按新列表重建映射，无需手动改索引。
2. **未知卡牌**：若 Mod 日志中出现其他职业牌（理论上不应发生，因不拿棱镜），会映射到 UNKNOWN (index 0)。
3. **power_parser**：保留 `parse_focus`、`parse_combust` 等，对静默无影响，仅返回 0。

---

## 六、执行顺序

按阶段 1 → 2 → 3 → 4 → 5 顺序执行。阶段 3 中区块1 的重构需仔细核对索引，建议先完成 10–14，再完成 15–23。
