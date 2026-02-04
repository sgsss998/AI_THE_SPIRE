# AI_THE_SPIRE

**A20 进阶静默猎手，冲击人类连胜记录的终极目标。** NoSL 盗贼人类纪录 27 连胜，本项目目标超越。

规则 Agent + 监督学习 (SL) + 强化学习 (RL)，三种方式从易到难：规则是写死的策略，SL 是跟人类学，RL 是 AI 自己打自己练。

---

## 项目结构（事无巨细）

```
AI_THE_SPIRE/
├── src/                           # 核心源代码
│   ├── core/                      # 游戏状态与动作定义
│   │   ├── game_state.py          # GameState、Card、Monster、CombatState 等数据结构
│   │   ├── action.py              # Action 数据类，所有可执行动作（出牌、选选项等）
│   │   └── config.py              # 配置加载与解析
│   ├── protocol/                  # 与 CommunicationMod 的通信层
│   │   ├── reader.py              # 从 stdin 读取 Mod 发来的 JSON 状态
│   │   ├── writer.py              # 向 stdout 发送命令（出牌、选选项等）
│   │   └── parser.py              # 解析 JSON，转成 GameState
│   ├── env/                       # RL 训练用的 Gymnasium 环境
│   │   └── sts_env.py             # StsEnvironment、StsEnvWrapper，封装游戏为 step/reset 接口
│   ├── agents/                    # AI 决策模块
│   │   ├── base.py                # Agent 基类、create_agent 工厂函数
│   │   ├── rule_based.py          # 规则 Agent，按预定义策略选动作
│   │   ├── supervised.py          # 监督学习 Agent，用人类数据训练的模型决策
│   │   └── rl_agent.py            # 强化学习 Agent，PPO/A2C/DQN
│   └── training/                  # 训练相关
│       ├── encoder.py             # 状态编码器（旧版）
│       ├── encoder_v2.py          # 状态编码器 V2，把 Mod 状态转成 723 维向量 s
│       ├── encoder_utils.py       # ID 归一化、卡牌/遗物查表（依赖 encoder_v2_ids.yaml）
│       ├── power_parser.py        # 从 player.powers 解析力量、虚弱、易伤等数值
│       └── experiment.py          # 实验跟踪，记录训练 runs、模型路径、指标
│
├── scripts/                       # 可执行脚本
│   ├── train.py                   # ⭐ 统一入口，collect/sl/rl/pipeline/eval/interactive 子命令
│   ├── collect_data.py           # 收集人类对局数据，保存为 JSON
│   ├── train_sl.py               # 监督学习训练
│   ├── train_rl.py               # 强化学习训练
│   ├── evaluate.py               # 评估 Agent 胜率等指标
│   ├── interactive.py            # 让 AI 实际玩一局，观察行为
│   ├── read_state.py             # 读取并打印当前游戏状态，调试用
│   ├── extract_mod_schema.py     # 从 Mod 日志提取所有参数路径，排除法用
│   ├── extract_ids_from_raw.py   # 从 Raw JSON 提取卡牌/遗物 ID，更新 encoder_v2_ids
│   ├── test_action_client.py     # 动作客户端测试
│   ├── test_action_server.py     # 动作服务端测试
│   └── README.md                 # 脚本详细说明
│
├── configs/                       # 配置文件
│   ├── default.yaml              # 默认训练参数、游戏配置、日志配置
│   ├── encoder_v2_ids.yaml       # 卡牌/遗物/药水/Power/Intent ID 映射表，编码器查表用
│   ├── sts_path.txt              # StS 安装路径（本地配置，不提交）
│   └── window_policy.txt         # 窗口与焦点策略（分辨率、全屏等）
│
├── data/                          # 数据目录（.gitignore，不提交）
│   ├── A20_Slient/               # A20 静默人类对局
│   │   └── Raw_Data_json_FORSL/  # 原始 JSON，每局一个文件
│   └── models/                   # 训练好的模型 .pkl / .zip
│
├── docs/                          # 文档
│   ├── README.md                 # 文档索引
│   ├── API.md                    # API 文档
│   ├── ARCHITECTURE.md           # 架构说明
│   ├── rules/                    # 游戏规则与 Mod 协议
│   │   ├── 00-index.md           # 规则总览
│   │   ├── 01-game-flow.md       # 游戏流程
│   │   ├── 02-combat-turn.md     # 战斗回合结构
│   │   ├── 03-protocol.md        # CommunicationMod 协议
│   │   ├── 04-data-recording.md   # 数据记录规则
│   │   ├── 05-silent-basics.md    # 静默猎手基础
│   │   ├── 06-ascension.md       # A20 难度加成
│   │   ├── 07-llm-reference-sts-aislayer.md   # LLM 参考
│   │   ├── 08-sts-ai-master-reference.md    # STS-AI-Master 参考
│   │   └── ACTION_ID_MAP.md      # 动作 ID 映射
│   ├── planning_and_logs/        # 计划与开发日志
│   │   ├── DEVELOPMENT_LOG.md    # 开发日志
│   │   ├── rules.md              # 规则
│   │   ├── StS_AI开发计划-细颗粒度实施指南.md
│   │   ├── 实施检查清单-可打印.md
│   │   ├── 方案_Agent结合LLM_技术规范.md
│   │   ├── 方案A_修改Mod记录人类动作_研究计划.md
│   │   ├── 方案B_代理界面采集人类数据_技术规范.md
│   │   └── 状态向量s_表达式与Mod转换_计划.md
│   ├── 状态向量s_技术规范.md     # 状态向量 s 技术规范（排除法、维度、编码）
│   ├── 状态向量s_前218维_表达式清单.md  # 前 218 维每维表达式
│   └── 杀戮尖塔_官方本体A20_卡牌遗物穷尽清单.md  # 卡牌遗物穷尽清单
│
├── tests/                         # 单元测试
│   ├── test_core/                # core 模块测试
│   │   ├── test_game_state.py
│   │   └── test_action_exhaustive.py
│   ├── test_protocol/             # protocol 模块测试
│   │   └── test_reader.py
│   ├── test_env/                  # env 模块测试
│   │   └── test_sts_env.py
│   ├── test_agents/               # agents 模块测试
│   │   ├── test_base.py
│   │   ├── test_rule_based.py
│   │   ├── test_supervised.py
│   │   └── test_rl_agent.py
│   └── test_training/             # training 模块测试
│       └── test_experiment.py
│
├── Received                       # Mod 通信管道（运行时用）
├── Sending                        # Mod 通信管道（运行时用）
├── requirements.md                # Python 依赖列表与版本说明
├── rules_for_all.md               # Cursor 规则（RIPER-5 模式等）
└── README.md                      # 本文件
```

---

## 怎么跑

```bash
# 规则 Agent 自动玩一局（不需要模型）
python scripts/train.py interactive --agent-type rule

# 完整训练：收集人类对局 → 训练 SL → 训练 RL
python scripts/train.py pipeline --collect-games 50 --sl-epochs 100 --rl-timesteps 100000
```

更多命令：`python scripts/train.py --help`

---

## 需要什么资源、去哪找

| 资源 | 说明 |
|------|------|
| **Slay the Spire** | Steam 购买，需安装 |
| **CommunicationMod** | [Steam 创意工坊](https://steamcommunity.com/app/646570/workshop/) 或 [GitHub](https://github.com/ForgottenArbiter/CommunicationMod)，游戏和本项目的桥梁 |
| **ModTheSpire** | 运行 Mod 的加载器，同上 |
| **Python 依赖** | `requirements.md` 有列表，`pip install numpy scipy scikit-learn pyyaml` 起步，RL 还需 `torch stable-baselines3 gymnasium` |

---

## 项目特例（容易踩坑）

**sklearn + numpy 2.0 会报 `_ARRAY_API not found`**：用 `--model-type pytorch` 或 `pip install "numpy<2.0" "scipy<2.0"`。
