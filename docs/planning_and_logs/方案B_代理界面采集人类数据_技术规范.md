# 方案 B：代理界面采集人类数据 — 技术规范

> **目标**：人类通过 Python 提供的界面选择动作，Python 将命令发给 Mod 并精确记录 `action_id`。  
> **模式**：计划模式 — 详尽技术规范，不含实现代码。

---

## 一、架构概述

### 1.1 数据流

```
Mod ──(stdout)──▶ Python 脚本 ──(stdin)──▶ Mod
       │                    │
       │                    ├── 决策点：展示 UI，等待人类选择
       │                    ├── 非决策点：立即回复 "state"
       │                    └── 记录：(state, action_id) 写入文件
       │
       └── JSON 状态
```

### 1.2 与现有方案对比

| 项目 | read_state.py | test_action_server + client | 方案 B（本方案） |
|------|---------------|----------------------------|------------------|
| 人类操作方式 | 直接操作游戏 | 终端输入 action_id | 代理界面选择 |
| 数据来源 | 仅状态（需推断动作） | 精确 action_id | 精确 action_id |
| 进程数 | 1（Mod 启动） | 2（Mod + 用户另启 client） | 1（Mod 启动） |
| 输出 | 仅状态 JSON | 不记录 | 状态 + action_id |

---

## 二、协议约束

### 2.1 通信通道

- **stdin**：接收 Mod 发来的 JSON 状态（每行一条）
- **stdout**：向 Mod 发送命令（`state`、`play 1 0`、`end` 等），**仅输出命令，不得输出 UI 内容**
- **stderr**：输出 UI 提示、日志、错误信息
- **用户输入**：从 `/dev/tty` 读取（因 stdin 被 Mod 占用），Windows 需 fallback

### 2.2 决策点判定

与 `read_state.py`、`test_action_server.py` 一致：

- `in_game == true`
- `game_state.action_phase == "WAITING_ON_USER"`
- 可选：`ready_for_command == true`（当前实现已放宽，见 test_action_server 注释）

### 2.3 非决策点行为

与 `read_state.py` 一致：立即发送 `state`，不阻塞。

---

## 三、合法动作计算

### 3.1 复用逻辑

复用 `src/env/sts_env.py` 中 `StsEnvironment._get_valid_actions()` 的逻辑。

**前置条件**：需将 Mod 的原始 `msg` 转为 `GameState`。

- `GameState.from_mod_response(msg)`：接受完整 `msg`（含顶层 `available_commands`、`in_game` 等）
- `choice_list` 来源：`game_state.choice_list` 或 `game_state.screen_state.options`，需与 `from_mod_response` 的解析一致

### 3.2 合法动作列表

- 战斗：出牌 (0–69)、药水 (70–109)、选择 (110–169)、end (170)、proceed (171)、cancel (172)
- 非战斗：choose (110–169)、proceed (171)、cancel (172)
- 过滤：仅包含当前 `available_commands` 与游戏状态允许的动作

### 3.3 动作展示格式

- 出牌：`[0] 出第1张牌(无目标)  [10] 出第1张牌→敌人1` 等，可附带卡牌名称、费用
- 药水：`[70] 使用药水1  [75] 使用药水1→敌人1`
- 选择：`[110] 选项0: xxx  [111] 选项1: xxx`
- 控制：`[170] 结束回合  [171] 确认/前进  [172] 取消`

---

## 四、存储格式

### 4.1 文件路径

- 目录：`configs/default.yaml` 中 `training.data_dir`，或沿用 `read_state.py` 的 `DATA_DIR`
- 建议：`data/A20_Slient/Raw_Data_json_FORSL_PROXY/`，以区分代理采集与原始采集
- 文件名：`Silent_A20_HUMAN_PROXY_{timestamp}.json` 或 JSONL

### 4.2 单条记录格式（JSONL 推荐）

```json
{"ts": "2026-02-02T20:06:23.218194", "action_id": 42, "cmd": "play 2 0", "state": {...}}
```

- `ts`：ISO 时间戳
- `action_id`：0–172，精确记录
- `cmd`：Mod 命令字符串（便于调试与回放）
- `state`：**精简状态**，与 `04-data-recording.md` 一致，仅保留训练所需字段

### 4.3 状态精简规则

- 战斗：`combat_state`（hand、player、monsters、turn），不含 map、deck、draw_pile 等
- 非战斗：`screen_type`、`choice_list`、`screen_state.options`

---

## 五、文件与模块规划

### 5.1 新增文件

| 路径 | 职责 |
|------|------|
| `scripts/human_proxy.py` | 主入口，Mod 配置的 command，负责协议循环、决策分支、记录 |
| `src/ui/__init__.py` | UI 包 |
| `src/ui/terminal_ui.py` | 终端 UI：打印状态摘要、合法动作列表，从 `/dev/tty` 读取用户输入 |
| `src/utils/valid_actions.py` | 从 `msg` 计算合法 action_id 列表（封装 `_get_valid_actions` 逻辑，接受 `GameState` 或 `msg`） |

### 5.2 修改文件

| 路径 | 修改内容 |
|------|----------|
| `src/env/sts_env.py` | 将 `_get_valid_actions` 抽为可被 `valid_actions.py` 调用的函数，或直接由 `valid_actions` 复用逻辑 |
| `configs/default.yaml` 或新建 | 增加 `proxy.data_dir`、`proxy.use_jsonl` 等配置项（可选） |
| `docs/rules/04-data-recording.md` | 补充代理界面采集的存储格式说明 |

### 5.3 依赖关系

```
human_proxy.py
  ├── src.core.action (Action.from_id, to_command)
  ├── src.core.game_state (GameState.from_mod_response)
  ├── src.utils.valid_actions (get_valid_actions)
  └── src.ui.terminal_ui (display_and_get_choice)
```

---

## 六、主循环逻辑（伪代码）

```
发送 "ready"
循环:
  从 stdin 读取一行 line
  若 line 为空: 发送 "state"; continue
  解析 msg = json.loads(line)
  若 in_game 为 false: 发送 "state"; continue
  gs = msg.game_state
  若 action_phase != "WAITING_ON_USER": 发送 "state"; continue

  # 决策点
  valid_ids = get_valid_actions(msg)
  若 valid_ids 为空: 发送 "state"; continue  # 兜底

  display_state_summary(gs, stderr)
  display_valid_actions(valid_ids, gs, stderr)
  user_input = read_from_tty()

  若 user_input 为 "q" 或 "state": 发送 "state"; continue
  action_id = parse_int(user_input)
  若 action_id 不在 valid_ids: 发送 "state"; continue

  action = Action.from_id(action_id)
  cmd = action.to_command()
  record_to_file(msg, action_id, cmd)
  发送 cmd
```

---

## 七、局开始/结束与去重

### 7.1 局开始

与 `read_state.py` 一致：`screen_state.event_id == "Neow Event"` 且 `last_game_ended` 时，新建文件。

### 7.2 局结束

`screen_type == "GAME_OVER"` 时置 `last_game_ended = True`。

### 7.3 去重

代理界面下，每次决策点仅一条人类选择，无需按状态哈希去重。若同一状态被多次发送（Mod 重试等），以首次人类选择为准，后续可忽略或覆盖。

---

## 八、配置与启动

### 8.1 Mod 配置

在 Mod 的 `config`（如 SpireConfig）中，将 `command` 改为：

```
command=/Volumes/T7/AI_THE_SPIRE/venv/bin/python -u /Volumes/T7/AI_THE_SPIRE/scripts/human_proxy.py
```

### 8.2 环境变量（可选）

- `AI_STS_PROXY_DATA_DIR`：覆盖默认数据目录
- `AI_STS_PROXY_NO_RECORD=1`：不写入文件（仅测试协议）

### 8.3 启动方式

- 由 Mod 启动，与 `read_state.py` 相同
- 用户无需单独启动 client，所有交互在同一进程内完成

---

## 九、边界情况

| 情况 | 处理 |
|------|------|
| 用户输入非数字 | 提示无效，发送 `state`，重新等待下一帧 |
| 用户输入非法 action_id | 同上 |
| `/dev/tty` 不可用（如无 TTY） | fallback 到 `sys.stdin`（可能破坏协议，仅作兜底），或报错退出 |
| 连接断开 | 与 read_state 一致，捕获异常，落盘后退出 |
| 快速连续状态 | 每个决策点只处理一次，每次只记录一条 |

---

## 十、与现有脚本的关系

| 脚本 | 关系 |
|------|------|
| `read_state.py` | 保留，用于「人类直接操作游戏」的原始状态采集 |
| `test_action_server.py` | 保留，用于 Agent 测试、RL 等 |
| `test_action_client.py` | 保留，用于终端手动输入 action_id 测试 |
| `human_proxy.py` | 新增，用于「人类通过代理界面」的精确 action_id 采集 |

---

## 十一、实施检查清单

实施检查清单:

1. 创建 `src/utils/` 目录（若不存在）
2. 检查 `GameState.from_mod_response` 对 `choice_list` 的解析：Mod 可能使用 `choice_list` 键，若 `gs.get("choices", ...)` 无法获取，需增加 `gs.get("choice_list", [])` 作为 fallback
3. 创建 `src/utils/valid_actions.py`，实现 `get_valid_actions(msg: dict) -> List[int]`：调用 `GameState.from_mod_response(msg)` 得到 state，创建 `StsEnvironment()` 实例并 `set_state(state)`，调用 `_get_valid_actions()` 返回合法 action_id 列表
4. 创建 `src/ui/` 目录（若不存在）
5. 创建 `src/ui/__init__.py`（空或导出）
6. 创建 `src/ui/terminal_ui.py`，实现 `display_state_summary(gs: dict, file)`、`display_valid_actions(valid_ids: List[int], gs: dict, file)`、`read_from_tty() -> str`（从 `/dev/tty` 读取，Windows 时 fallback）
7. 创建 `scripts/human_proxy.py`，实现主循环：发送 ready、读取 stdin、解析 msg、判定决策点、调用 `get_valid_actions`、调用 `terminal_ui` 展示并获取输入、校验 action_id、调用 `Action.from_id` 与 `to_command`、记录到文件、发送命令
8. 在 `human_proxy.py` 中实现 `record_to_file(msg, action_id, cmd)`，按 JSONL 格式写入，路径为 `data/A20_Slient/Raw_Data_json_FORSL_PROXY/`，文件名含时间戳
9. 在 `human_proxy.py` 中实现局开始/结束判定（Neow Event、GAME_OVER），与 `read_state.py` 一致
10. 在 `human_proxy.py` 中实现 `_canonical_state` 或等价的状态精简逻辑，用于 `record_to_file` 的 state 字段
11. 确保 `human_proxy.py` 的 stdout 仅输出 Mod 命令，所有 UI 输出到 stderr
12. 在 `human_proxy.py` 启动时通过 `os.makedirs(data_dir, exist_ok=True)` 确保数据目录存在
13. 在 `configs/default.yaml` 或新建 `configs/proxy.yaml` 中增加 `proxy.data_dir` 等配置（可选）
14. 更新 `docs/rules/04-data-recording.md`，补充代理界面采集的存储格式与 `human_proxy.py` 的说明
15. 在项目 `README.md` 或 `scripts/README.md` 中说明 `human_proxy.py` 的用法及 Mod 配置方式
16. 手动测试：将 Mod 的 command 配置为 `human_proxy.py`，启动游戏，进入一局，在决策点通过终端选择动作，验证命令正确发送且文件正确记录
