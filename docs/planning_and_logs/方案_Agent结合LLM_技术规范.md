# 方案：Agent 结合 LLM API — 技术规范

> **目标**：Agent 读取 Mod 状态，格式化后调用 LLM API，LLM 返回动作，Agent 校验并执行，可选记录数据。  
> **模式**：计划模式 — 详尽技术规范，不含实现代码。

---

## 一、架构概述

### 1.1 数据流

```
Mod ──(stdout JSON)──▶ llm_agent.py ──(stdin 命令)──▶ Mod
                            │
                            ├── 解析 msg → GameState
                            ├── 决策点：format_state_for_llm(msg) → prompt
                            ├── llm_client.chat(prompt) → LLM 响应
                            ├── parse_action_from_response(response, valid_ids) → action_id
                            ├── 校验：action_id in valid_ids
                            ├── 失败时 fallback：RuleBasedAgent 或 end
                            └── 可选：record_to_file(msg, action_id)
```

### 1.2 与现有脚本关系

| 脚本 | 决策来源 | 本方案 |
|------|----------|--------|
| test_action_server | 人类 client | 由 LLM 替代 |
| human_proxy | 人类终端输入 | 由 LLM 替代 |
| 规则 Agent 采集 | RuleBasedAgent | 作为 fallback |

---

## 二、模块规划

### 2.1 新增目录与文件

| 路径 | 职责 |
|------|------|
| `src/llm/__init__.py` | 包初始化，导出 `LLMClient`、`format_state_for_llm`、`parse_action_from_response` |
| `src/llm/client.py` | LLM API 客户端，支持 OpenAI 兼容接口 |
| `src/llm/prompt_formatter.py` | 将 Mod 的 msg 转为 LLM 的 system + user prompt |
| `src/llm/response_parser.py` | 从 LLM 响应文本中解析 action_id |
| `scripts/llm_agent.py` | 主入口，由 Mod 启动，协议循环 + LLM 决策 + fallback |

### 2.2 复用与依赖

| 依赖 | 用途 |
|------|------|
| `GameState.from_mod_response` | 解析 msg |
| `StsEnvironment._get_valid_actions` | 获取合法 action_id 列表（需通过创建 env 实例并 set_state） |
| `Action.from_id`、`to_command` | 动作转换 |
| `RuleBasedAgentImpl` | LLM 失败时的 fallback |

### 2.3 新增依赖

在 `requirements.md` 或 `requirements.txt` 中增加：

- `openai>=1.0.0` 或 `httpx>=0.24.0`（用于 HTTP 请求）
- 若用 `openai`：支持 `api_key`、`base_url` 可配置，兼容 DeepSeek、GLM 等

---

## 三、LLM 客户端规范

### 3.1 接口

**类**：`LLMClient`（位于 `src/llm/client.py`）

**构造参数**：
- `api_key: str`（必填，可从环境变量 `AI_STS_LLM_API_KEY` 读取）
- `base_url: Optional[str]`（默认 `None`，使用 OpenAI 默认；DeepSeek 等需指定）
- `model: str`（默认 `"deepseek-chat"` 或可配置）
- `max_tokens: int`（默认 64）
- `timeout: float`（默认 30.0 秒）

**方法**：
- `chat(system_prompt: str, user_prompt: str) -> str`：返回 LLM 的 content 文本，异常时抛出或返回空字符串（由实现约定）

### 3.2 API 协议

使用 OpenAI 兼容的 `chat/completions` 接口：
- `POST {base_url}/v1/chat/completions`
- Body: `{"model": "...", "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}], "max_tokens": ...}`

### 3.3 配置来源优先级

1. 环境变量：`AI_STS_LLM_API_KEY`、`AI_STS_LLM_BASE_URL`、`AI_STS_LLM_MODEL`
2. 配置文件：`configs/default.yaml` 或新建 `configs/llm.yaml` 的 `llm` 节
3. 代码默认值

---

## 四、Prompt 格式规范

### 4.1 System Prompt 内容（固定）

- 游戏简介：杀戮尖塔回合制卡牌，静默猎手
- 动作空间说明：0–69 出牌，70–109 药水，110–169 选择，170 end，171 proceed，172 cancel
- 输出格式要求：**仅输出一个数字（action_id），不要其他文字**
- 约束：必须从当前合法动作中选择

### 4.2 User Prompt 内容（动态）

由 `format_state_for_llm(msg)` 生成，包含：

**战斗时**：
- 能量、当前血量、格挡
- 手牌列表：每张的索引(1-based)、名称、费用、是否可出、是否需要目标
- 敌人列表：索引、名称、当前血量、最大血量、意图（若可见）
- 合法动作列表：`valid_action_ids`（如 `[0, 10, 170]`）

**非战斗时**：
- 当前界面类型（事件/商店/奖励/地图等）
- 选项列表（含索引与文本）
- 合法动作列表

**格式**：建议用简洁的键值对或短段落，控制 token 量。

### 4.3 示例（简化）

```
【战斗】能量3 | HP 68/66 | 格挡0
手牌: 1.打击(1费,可出,需目标) 2.防御(1费,可出) 3.中和(0费,可出,需目标)
敌人: 1.Jaw Worm 12/46 意图:攻击12
合法动作: [0, 10, 20, 1, 11, 21, 2, 12, 22, 170]
请输出 action_id:
```

---

## 五、响应解析规范

### 5.1 解析逻辑（`parse_action_from_response`）

- 输入：`response: str`（LLM 返回的 content）、`valid_ids: List[int]`
- 行为：从 response 中提取数字（正则如 `\b(\d+)\b`），取第一个或最后一个匹配
- 校验：若解析出的数字在 `valid_ids` 中，返回该 `action_id`；否则返回 `None`

### 5.2 多数字情况

- 若 LLM 输出多个数字，优先取在 `valid_ids` 中出现的第一个
- 若均不合法，返回 `None`

---

## 六、主循环逻辑（llm_agent.py）

### 6.1 流程

1. 发送 `ready`
2. 循环读取 stdin 每行
3. 空行 → 发送 `state`，continue
4. 解析 JSON 失败 → 发送 `state`，continue
5. `in_game == false` → 发送 `state`，continue
6. `action_phase != "WAITING_ON_USER"` → 发送 `state`，continue
7. **决策点**：
   - 调用 `get_valid_actions(msg)` 得到 `valid_ids`
   - 若 `valid_ids` 为空，发送 `state`，continue
   - 调用 `format_state_for_llm(msg, valid_ids)` 得到 system + user prompt
   - 调用 `llm_client.chat(system_prompt, user_prompt)`
   - 调用 `parse_action_from_response(response, valid_ids)` 得到 `action_id`
   - 若 `action_id is None`：使用 `RuleBasedAgentImpl().select_action(state)` 得到 Action，再 `to_id()` 得到 action_id（fallback）
   - 若 fallback 仍失败：发送 `end` 或 `state`（按安全策略）
   - `action = Action.from_id(action_id)`，`cmd = action.to_command()`
   - 可选：`record_to_file(msg, action_id, cmd)`
   - 发送 `cmd`

### 6.2 Fallback 策略

- 第一选择：LLM 解析出的合法 action_id
- 第二选择：RuleBasedAgent 的决策
- 第三选择：若为战斗且 `170` 在 valid_ids 中，发送 `end`；否则发送 `state`

---

## 七、合法动作获取

### 7.1 实现方式

创建 `src/utils/valid_actions.py`（若方案 B 已实现则复用），实现：

```python
def get_valid_actions(msg: dict) -> List[int]:
    state = GameState.from_mod_response(msg)
    env = StsEnvironment()
    env.set_state(state)
    return env._get_valid_actions()
```

### 7.2 choice_list 兼容

在 `GameState.from_mod_response` 中，`choice_list` 的解析需支持 Mod 的 `choice_list` 键：

```python
choice_list = gs.get("choices", gs.get("cards", gs.get("event", gs.get("choice_list", []))))
```

若方案 B 已修改则无需重复。

---

## 八、数据记录（可选）

### 8.1 开关

- 环境变量 `AI_STS_LLM_RECORD=1` 时启用记录
- 或通过 `--record` 命令行参数

### 8.2 格式

与方案 B 一致：JSONL，每行 `{"ts", "action_id", "cmd", "state"}`，目录 `data/A20_Slient/Raw_Data_json_LLM/`

---

## 九、配置示例

### 9.1 环境变量

```
AI_STS_LLM_API_KEY=sk-xxx
AI_STS_LLM_BASE_URL=https://api.deepseek.com/v1
AI_STS_LLM_MODEL=deepseek-chat
AI_STS_LLM_RECORD=1
```

### 9.2 configs/llm.yaml（可选）

```yaml
llm:
  api_key: ${AI_STS_LLM_API_KEY}
  base_url: "https://api.deepseek.com/v1"
  model: deepseek-chat
  max_tokens: 64
  timeout: 30.0
```

---

## 十、Mod 配置

在 Mod 的 SpireConfig 中：

```
command=/Volumes/T7/AI_THE_SPIRE/venv/bin/python -u /Volumes/T7/AI_THE_SPIRE/scripts/llm_agent.py
```

---

## 十一、边界情况

| 情况 | 处理 |
|------|------|
| API 超时 | 使用 RuleBasedAgent fallback，发送其决策 |
| API 返回空 | 同上 |
| 解析出非法 action_id | 同上 |
| 网络错误 | 同上，可选 stderr 日志 |
| valid_ids 仅含 end | 直接发送 end，可不调 LLM |

---

## 十二、实施检查清单

实施检查清单:

1. 在 `requirements.md` 中增加 `openai>=1.0.0` 或 `httpx>=0.24.0`，并执行 `pip install`
2. 创建 `src/llm/` 目录
3. 创建 `src/llm/__init__.py`，导出 `LLMClient`、`format_state_for_llm`、`parse_action_from_response`
4. 创建 `src/llm/client.py`，实现 `LLMClient` 类：从环境变量或参数读取 `api_key`、`base_url`、`model`，实现 `chat(system_prompt, user_prompt) -> str`，使用 OpenAI 兼容的 `chat/completions` 接口
5. 创建 `src/llm/prompt_formatter.py`，实现 `format_state_for_llm(msg: dict, valid_ids: List[int]) -> Tuple[str, str]`，返回 (system_prompt, user_prompt)，system 含游戏规则与输出格式要求，user 含当前状态与合法动作
6. 创建 `src/llm/response_parser.py`，实现 `parse_action_from_response(response: str, valid_ids: List[int]) -> Optional[int]`，用正则提取数字，校验在 valid_ids 中则返回，否则返回 None
7. 创建或复用 `src/utils/valid_actions.py`，实现 `get_valid_actions(msg: dict) -> List[int]`，通过 `GameState.from_mod_response` 与 `StsEnvironment._get_valid_actions` 获取
8. 检查 `GameState.from_mod_response` 对 `choice_list` 的解析，若 Mod 使用 `choice_list` 键则增加 `gs.get("choice_list", [])` 作为 fallback
9. 创建 `scripts/llm_agent.py`，实现主循环：发送 ready、读取 stdin、解析 msg、判定决策点、调用 `get_valid_actions`、调用 `format_state_for_llm`、调用 `LLMClient.chat`、调用 `parse_action_from_response`、失败时用 `RuleBasedAgentImpl` fallback、发送命令
10. 在 `llm_agent.py` 中实现 fallback 逻辑：LLM 解析失败或超时时，使用 `RuleBasedAgentImpl().select_action(state)`，将 Action 转为 action_id 与命令
11. 在 `llm_agent.py` 中实现可选的 `record_to_file(msg, action_id, cmd)`，当 `AI_STS_LLM_RECORD=1` 时写入 JSONL 到 `data/A20_Slient/Raw_Data_json_LLM/`
12. 创建 `configs/llm.yaml`（可选），定义 `llm.api_key`、`base_url`、`model`、`max_tokens`、`timeout`
13. 在 `llm_agent.py` 启动时加载 LLM 配置（环境变量优先于配置文件）
14. 更新 `docs/rules/` 或 `scripts/README.md`，说明 `llm_agent.py` 的用法、环境变量、Mod 配置方式
15. 手动测试：设置 `AI_STS_LLM_API_KEY` 等，将 Mod 的 command 配置为 `llm_agent.py`，启动游戏，进入决策点，验证 LLM 被调用且命令正确发送
