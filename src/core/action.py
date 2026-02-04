#!/usr/bin/env python3
"""
动作定义

定义了所有可能的动作类型和动作表示。
动作是 AI 输出给游戏的指令。

基于 CommunicationMod (spirecomm) 的完整协议实现。
参考：https://github.com/ForgottenArbiter/spirecomm

支持的命令类型：
- play [card_index] [target?] - 出牌
- potion use/discard [potion_index] [target?] - 使用/丢弃药水
- end - 结束回合
- proceed - 确认/前进
- cancel - 取消
- choose [index/name] - 选择选项
- start [class] [ascension] [seed?] - 开始新游戏
- state - 获取状态
- ready - 初始化握手

扩展模式支持最多 6 个敌人的目标选择。
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Union


class ActionType(Enum):
    """动作类型 - 基于 CommunicationMod 协议"""
    PLAY_CARD = "play"
    END_TURN = "end"
    CHOOSE = "choose"
    PROCEED = "proceed"
    CANCEL = "cancel"
    POTION_USE = "potion_use"
    POTION_DISCARD = "potion_discard"
    START_GAME = "start"
    STATE = "state"
    READY = "ready"
    WAIT = "wait"  # 用于等待状态，不发送命令


@dataclass(frozen=True)
class Action:
    """动作
    不可变数据类，表示一个游戏动作。

    索引约定：
    - 内部使用 0-based 索引（card_index, target_index, potion_index）
    - Mod 协议使用 1-based 索引（play 命令），但 choose 命令保持 0-based
    - to_command() 会自动转换

    策略决策空间（173 维）- 药水原子化设计：
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │ 出牌动作 (70个)：                                                           │
    │   0-69：出第N张牌（无目标或目标=敌人1-6）                                    │
    │                                                                             │
    │ 药水动作 (40个)：                                                           │
    │   使用药水不指定目标 (5个)：70-74                                           │
    │   使用药水指定目标 (30个)：75-104（对敌人1-6）                              │
    │   丢弃药水 (5个)：105-109                                                    │
    │                                                                             │
    │ 选择动作 (60个)：110-169                                                     │
    │ 控制动作 (3个)：170-172 (end/proceed/cancel)                                │
    │                                                                             │
    │ 系统功能（不在动作空间中）：state, wait                                     │
    └─────────────────────────────────────────────────────────────────────────────┘

    策略决策空间：173 个离散动作（不含 state/wait）
    """
    type: ActionType
    card_index: Optional[int] = None      # 出牌索引（0-based，内部使用）
    target_index: Optional[int] = None    # 目标索引（0=无目标/玩家, 1-6=怪物, 1-3=药水目标）
    choice_index: Optional[int] = None    # choose 命令的索引（0-based）
    choice_name: Optional[str] = None     # choose 命令的名称（用于商店/事件等）
    potion_index: Optional[int] = None    # 药水索引（0-based）
    player_class: Optional[str] = None    # 角色类（用于 start 命令）
    ascension: Optional[int] = None       # 异层等级（用于 start 命令）
    seed: Optional[str] = None            # 随机种子（用于 start 命令）

    def to_command(self) -> str:
        """转换为 CommunicationMod 命令

        Returns:
            Mod 协议命令字符串
        """
        # 出牌：play [card_index+1] [target?]
        # Mod 的 target 为 0-based（敌人1=0），内部 target_index 为 1-based（敌人1=1）
        if self.type == ActionType.PLAY_CARD and self.card_index is not None:
            cmd = f"play {self.card_index + 1}"
            if self.target_index is not None and self.target_index > 0:
                cmd += f" {self.target_index - 1}"
            return cmd

        # 结束回合
        if self.type == ActionType.END_TURN:
            return "end"

        # 选择：choose [index] 或 choose [name]
        if self.type == ActionType.CHOOSE:
            if self.choice_name is not None:
                return f"choose {self.choice_name}"
            elif self.choice_index is not None:
                return f"choose {self.choice_index}"

        # 前进/确认
        if self.type == ActionType.PROCEED:
            return "proceed"

        # 取消
        if self.type == ActionType.CANCEL:
            return "cancel"

        # 使用药水：potion use [potion_index+1] [target?]
        # Mod 的 target 为 0-based
        if self.type == ActionType.POTION_USE and self.potion_index is not None:
            cmd = f"potion use {self.potion_index + 1}"
            if self.target_index is not None and self.target_index > 0:
                cmd += f" {self.target_index - 1}"
            return cmd

        # 丢弃药水：potion discard [potion_index+1]
        if self.type == ActionType.POTION_DISCARD and self.potion_index is not None:
            return f"potion discard {self.potion_index + 1}"

        # 开始游戏：start [class] [ascension] [seed?]
        if self.type == ActionType.START_GAME:
            cmd = f"start {self.player_class} {self.ascension or 0}"
            if self.seed is not None:
                cmd += f" {self.seed}"
            return cmd

        # 握手信号
        if self.type == ActionType.READY:
            return "ready"

        # 获取状态
        if self.type == ActionType.STATE:
            return "state"

        # 等待（不发送命令）
        if self.type == ActionType.WAIT:
            return "wait"

        return "state"

    @classmethod
    def from_command(cls, cmd: str) -> 'Action':
        """从命令解析

        Args:
            cmd: Mod 协议命令字符串

        Returns:
            Action 对象
        """
        parts = cmd.strip().split()

        if not parts or cmd == "state":
            return cls(type=ActionType.STATE)

        cmd_type = parts[0]

        # 出牌：play [card_index] [target?]
        # Mod 的 target 为 0-based，内部 target_index 为 1-based
        if cmd_type == "play" and len(parts) >= 2:
            card_idx = int(parts[1]) - 1  # 1-based → 0-based
            target_idx = (int(parts[2]) + 1) if len(parts) > 2 else 0  # Mod 0-based → 内部 1-based
            return cls(type=ActionType.PLAY_CARD, card_index=card_idx, target_index=target_idx)

        # 结束回合
        if cmd_type == "end":
            return cls(type=ActionType.END_TURN)

        # 选择：choose [index] 或 choose [name]
        if cmd_type == "choose" and len(parts) >= 2:
            try:
                choice_idx = int(parts[1])
                return cls(type=ActionType.CHOOSE, choice_index=choice_idx)
            except ValueError:
                # 不是数字，则是名称
                return cls(type=ActionType.CHOOSE, choice_name=parts[1])

        # 前进/确认
        if cmd_type == "proceed":
            return cls(type=ActionType.PROCEED)

        # 取消
        if cmd_type == "cancel":
            return cls(type=ActionType.CANCEL)

        # 药水：potion [use/discard] [potion_index] [target?]
        # Mod 的 target 为 0-based
        if cmd_type == "potion" and len(parts) >= 3:
            potion_idx = int(parts[2]) - 1  # 1-based → 0-based
            target_idx = (int(parts[3]) + 1) if len(parts) > 3 else None  # Mod 0-based → 内部 1-based
            if parts[1] == "use":
                return cls(type=ActionType.POTION_USE, potion_index=potion_idx, target_index=target_idx)
            elif parts[1] == "discard":
                return cls(type=ActionType.POTION_DISCARD, potion_index=potion_idx)

        # 开始游戏：start [class] [ascension] [seed?]
        if cmd_type == "start" and len(parts) >= 3:
            ascension = int(parts[2])
            seed = parts[3] if len(parts) > 3 else None
            return cls(type=ActionType.START_GAME, player_class=parts[1], ascension=ascension, seed=seed)

        # 握手信号
        if cmd_type == "ready":
            return cls(type=ActionType.READY)

        # 等待
        if cmd_type == "wait":
            return cls(type=ActionType.WAIT)

        # 默认返回状态
        return cls(type=ActionType.STATE)

    # ==================== 构造方法 ====================

    @classmethod
    def end_turn(cls) -> 'Action':
        """创建结束回合动作"""
        return cls(type=ActionType.END_TURN)

    @classmethod
    def play_card(cls, card_idx: int, target_idx: int = 0) -> 'Action':
        """创建出牌动作（0-based 索引）

        Args:
            card_idx: 手牌索引（0-9）
            target_idx: 目标索引（0=无目标, 1-6=敌人）
        """
        return cls(type=ActionType.PLAY_CARD, card_index=card_idx, target_index=target_idx)

    @classmethod
    def choose_by_index(cls, choice_idx: int) -> 'Action':
        """创建选择动作（按索引）

        Args:
            choice_idx: 选项索引（0-based）
        """
        return cls(type=ActionType.CHOOSE, choice_index=choice_idx)

    @classmethod
    def choose_by_name(cls, name: str) -> 'Action':
        """创建选择动作（按名称）

        Args:
            name: 选项名称（如 "shop", "open", "purge", "bowl" 等）
        """
        return cls(type=ActionType.CHOOSE, choice_name=name)

    @classmethod
    def choose(cls, choice: Union[int, str]) -> 'Action':
        """创建选择动作（自动判断索引或名称）

        Args:
            choice: 选项索引（int）或名称（str）
        """
        if isinstance(choice, int):
            return cls.choose_by_index(choice)
        return cls.choose_by_name(choice)

    @classmethod
    def proceed(cls) -> 'Action':
        """创建前进/确认动作"""
        return cls(type=ActionType.PROCEED)

    @classmethod
    def cancel(cls) -> 'Action':
        """创建取消动作"""
        return cls(type=ActionType.CANCEL)

    @classmethod
    def use_potion(cls, potion_idx: int, target_idx: Optional[int] = None) -> 'Action':
        """创建使用药水动作

        Args:
            potion_idx: 药水索引（0-based）
            target_idx: 目标索引（None=无目标, 1-3=敌人）
        """
        return cls(type=ActionType.POTION_USE, potion_index=potion_idx, target_index=target_idx)

    @classmethod
    def discard_potion(cls, potion_idx: int) -> 'Action':
        """创建丢弃药水动作

        Args:
            potion_idx: 药水索引（0-based）
        """
        return cls(type=ActionType.POTION_DISCARD, potion_index=potion_idx)

    @classmethod
    def start_game(cls, player_class: str, ascension: int = 0, seed: Optional[str] = None) -> 'Action':
        """创建开始游戏动作

        Args:
            player_class: 角色类（"IRONCLAD", "THE_SILENT", "DEFECT", "WATCHER"）
            ascension: 异层等级（0-20）
            seed: 随机种子（可选）
        """
        return cls(type=ActionType.START_GAME, player_class=player_class, ascension=ascension, seed=seed)

    @classmethod
    def ready(cls) -> 'Action':
        """创建握手信号"""
        return cls(type=ActionType.READY)

    @classmethod
    def state(cls) -> 'Action':
        """创建状态请求动作"""
        return cls(type=ActionType.STATE)

    @classmethod
    def wait(cls) -> 'Action':
        """创建等待动作（不发送命令）"""
        return cls(type=ActionType.WAIT)

    # ==================== 动作 ID 映射 ====================

    def to_id(self, hand_size: int = 10, max_monsters: int = 6,
              max_potions: int = 5, max_choose: int = 60) -> int:
        """转换为动作 ID（用于训练标签）

        策略决策空间（173 维）- 药水原子化设计：
        ┌─────────────────────────────────────────────────────────────────────────────┐
        │ 出牌动作 (70个)：                                                           │
        │   0-9：   出第N张牌（无目标/玩家自己）                                       │
        │   10-19： 出第N张牌（目标=敌人1）                                            │
        │   20-29： 出第N张牌（目标=敌人2）                                            │
        │   30-39： 出第N张牌（目标=敌人3）                                            │
        │   40-49： 出第N张牌（目标=敌人4）                                            │
        │   50-59： 出第N张牌（目标=敌人5）                                            │
        │   60-69： 出第N张牌（目标=敌人6）                                            │
        │                                                                             │
        │ 药水动作 (40个)：                                                           │
        │   使用药水不指定目标 (5个)：70-74                                           │
        │     70-74：potion use 1~5（烟雾弹等无目标药水）                             │
        │   使用药水指定目标 (30个)：75-104                                           │
        │     75-79：  potion use 1~5 1（对敌人1）                                   │
        │     80-84：  potion use 1~5 2（对敌人2）                                   │
        │     85-89：  potion use 1~5 3（对敌人3）                                   │
        │     90-94：  potion use 1~5 4（对敌人4）                                   │
        │     95-99：  potion use 1~5 5（对敌人5）                                   │
        │     100-104：potion use 1~5 6（对敌人6）                                   │
        │   丢弃药水 (5个)：105-109                                                  │
        │     105-109：potion discard 1~5                                            │
        │                                                                             │
        │ 选择动作 (60个)：110-169                                                    │
        │   110-169：choose 0-59                                                     │
        │                                                                             │
        │ 控制动作 (3个)：170-172                                                      │
        │   170： end                                                                │
        │   171： proceed                                                            │
        │   172： cancel                                                             │
        │                                                                             │
        │ 系统功能（不在动作空间中）：state, wait                                     │
        └─────────────────────────────────────────────────────────────────────────────┘

        Args:
            hand_size: 手牌数量（默认10）
            max_monsters: 最大怪物数（默认6）
            max_potions: 最大药水数（默认5，有药水袋遗物）
            max_choose: 最大选择数（默认60）

        Returns:
            动作 ID (0-172)，或 -1（系统功能不在策略空间内）
        """
        # 出牌动作 (0-69)
        if self.type == ActionType.PLAY_CARD and self.card_index is not None:
            if 0 <= self.card_index < hand_size:
                target = self.target_index or 0
                if 0 <= target <= max_monsters:
                    return self.card_index + target * 10

        # 使用药水
        if self.type == ActionType.POTION_USE and self.potion_index is not None:
            if 0 <= self.potion_index < max_potions:
                target = self.target_index or 0
                if target == 0:
                    # 不指定目标：70-74
                    return 70 + self.potion_index
                elif 1 <= target <= 6:
                    # 指定目标1-6：75-104
                    # 75-79: target=1, 80-84: target=2, ...
                    return 75 + self.potion_index + (target - 1) * max_potions

        # 丢弃药水 (105-109)
        if self.type == ActionType.POTION_DISCARD and self.potion_index is not None:
            if 0 <= self.potion_index < max_potions:
                return 105 + self.potion_index

        # 选择动作 (110-129)
        if self.type == ActionType.CHOOSE and self.choice_index is not None:
            if 0 <= self.choice_index < max_choose:
                return 110 + self.choice_index

        # 结束回合
        if self.type == ActionType.END_TURN:
            return 170

        # 前进/确认
        if self.type == ActionType.PROCEED:
            return 171

        # 取消
        if self.type == ActionType.CANCEL:
            return 172

        # 获取状态（系统级功能，不在策略空间中）
        if self.type == ActionType.STATE:
            # 不返回动作 ID，state 由主循环自动调用
            return -1  # 返回 -1 表示不在策略空间内

        # 等待（系统级功能，不在策略空间中）
        if self.type == ActionType.WAIT:
            # 不返回动作 ID，wait 由主循环处理空动作情况
            return -1  # 返回 -1 表示不在策略空间内

        # 开始游戏（训练时不使用）
        if self.type == ActionType.START_GAME:
            return -1  # 不在策略空间内

        # 握手信号（训练时不使用）
        if self.type == ActionType.READY:
            return -1  # 不在策略空间内

        # 默认返回安全的后备动作
        return cls.cancel()

    @classmethod
    def from_id(cls, action_id: int, hand_size: int = 10) -> 'Action':
        """从动作 ID 创建（用于模型预测）

        Args:
            action_id: 动作 ID (0-172)
            hand_size: 手牌数量（用于验证）

        Returns:
            Action 对象
        """
        # 出牌动作 (0-69)
        if 0 <= action_id <= 9:
            return cls.play_card(action_id, target_idx=0)        # 目标为空
        elif 10 <= action_id <= 19:
            return cls.play_card(action_id - 10, target_idx=1)    # 目标为敌人1
        elif 20 <= action_id <= 29:
            return cls.play_card(action_id - 20, target_idx=2)    # 目标为敌人2
        elif 30 <= action_id <= 39:
            return cls.play_card(action_id - 30, target_idx=3)    # 目标为敌人3
        elif 40 <= action_id <= 49:
            return cls.play_card(action_id - 40, target_idx=4)    # 目标为敌人4
        elif 50 <= action_id <= 59:
            return cls.play_card(action_id - 50, target_idx=5)    # 目标为敌人5
        elif 60 <= action_id <= 69:
            return cls.play_card(action_id - 60, target_idx=6)    # 目标为敌人6

        # 使用药水不指定目标 (70-74)
        elif 70 <= action_id <= 74:
            return cls.use_potion(action_id - 70, target_idx=None)

        # 使用药水指定目标 (75-104)
        elif 75 <= action_id <= 79:
            return cls.use_potion(action_id - 75, target_idx=1)    # 目标敌人1
        elif 80 <= action_id <= 84:
            return cls.use_potion(action_id - 80, target_idx=2)    # 目标敌人2
        elif 85 <= action_id <= 89:
            return cls.use_potion(action_id - 85, target_idx=3)    # 目标敌人3
        elif 90 <= action_id <= 94:
            return cls.use_potion(action_id - 90, target_idx=4)    # 目标敌人4
        elif 95 <= action_id <= 99:
            return cls.use_potion(action_id - 95, target_idx=5)    # 目标敌人5
        elif 100 <= action_id <= 104:
            return cls.use_potion(action_id - 100, target_idx=6)   # 目标敌人6

        # 丢弃药水 (105-109)
        elif 105 <= action_id <= 109:
            return cls.discard_potion(action_id - 105)

        # 选择动作 (110-169)
        elif 110 <= action_id <= 169:
            return cls.choose_by_index(action_id - 110)

        # 结束回合
        elif action_id == 170:
            return cls.end_turn()

        # 前进/确认
        elif action_id == 171:
            return cls.proceed()

        # 取消
        elif action_id == 172:
            return cls.cancel()

        # 超出策略空间（173 个动作）
        else:
            # 返回 cancel 作为安全的后备
            # （理论上不应该到这里，因为动作被 mask 限制了）
            return cls.cancel()

    def __str__(self) -> str:
        """字符串表示"""
        return self.to_command()


# ========== 常量定义 ==========

# 完整动作空间（穷举所有 CommunicationMod 命令）
ACTION_SPACE_SIZE = 173    # 总动作空间大小（策略决策，不含 state/wait）
ACTION_SPACE_EXTENDED = 173

# 动作 ID 边界
ACTION_CARD_END = 70         # 出牌动作结束 ID (0-69)
ACTION_POTION_USE_END = 105  # 使用药水结束 ID (70-104, 5不指定+5×6指定)
ACTION_POTION_DISCARD_END = 110  # 丢弃药水结束 ID (105-109)
ACTION_CHOOSE_END = 170      # 选择动作结束 ID (110-169)

# 特殊动作 ID
ACTION_END_ID = 170          # 结束回合的固定 ID
ACTION_PROCEED_ID = 171      # 前进/确认
ACTION_CANCEL_ID = 172       # 取消
# ACTION_STATE_ID 和 ACTION_WAIT_ID 已移除
# state 和 wait 是系统级功能，由主循环处理，不属于 AI 策略决策空间

# 游戏限制
MAX_HAND_SIZE = 10           # 最多10张手牌
MAX_MONSTERS = 6             # 最多6个敌人
MAX_POTIONS = 5              # 最多5个药水（有药水袋遗物）
MAX_CHOICES = 60             # 最多60个选择选项（火堆/商店删牌等）

# 简单模式常量（兼容旧版，仅用于基础测试）
ACTION_CARD_COUNT = 10
ACTION_SPACE_SIMPLE = 11

# 动作空间文档字符串
ACTION_SPACE_DOC = """
策略决策空间（173 维）- 基于 CommunicationMod (spirecomm) 协议：

【架构原则】
- state 和 wait 是系统级功能，由主循环处理，不属于 AI 决策空间
- 主循环在每次决策前自动调用 state 获取游戏状态
- 主循环通过重试逻辑处理空动作情况（等待、加载动画等）
- AI 只学习真正的游戏策略动作
- 药水动作原子化：一次性决定"对谁用哪个药水"，无需多轮交互

┌─────────────────────────────────────────────────────────────────────────────┐
│ 出牌动作 (70个)：0-69                                                         │
│   0-9：   出第N张牌（无目标/玩家自己）                                       │
│   10-19： 出第N张牌（目标=敌人1）                                            │
│   ...                                                                        │
│   60-69： 出第N张牌（目标=敌人6）                                            │
│                                                                             │
│ 药水动作 (40个)：70-109                                                       │
│   使用药水不指定目标 (5个)：                                                 │
│     70-74：potion use 1~5（烟雾弹、力量药水等）                              │
│   使用药水指定目标 (30个)：                                                 │
│     75-79：  potion use 1~5 1（对敌人1）                                     │
│     80-84：  potion use 1~5 2（对敌人2）                                     │
│     85-89：  potion use 1~5 3（对敌人3）                                     │
│     90-94：  potion use 1~5 4（对敌人4）                                     │
│     95-99：  potion use 1~5 5（对敌人5）                                     │
│     100-104：potion use 1~5 6（对敌人6）                                     │
│   丢弃药水 (5个)：105-109                                                    │
│     105-109：potion discard 1~5                                              │
│                                                                             │
│ 选择动作 (60个)：110-169                                                      │
│   110-169：choose 0-59（商店、事件、奖励、地图、火堆删牌等）                │
│                                                                             │
│ 控制动作 (3个)：170-172                                                       │
│   170：end（结束回合）                                                       │
│   171：proceed（确认/前进）                                                  │
│   172：cancel（取消）                                                        │
│                                                                             │
│ 系统功能（不在动作空间中）：state, wait                                     │
└─────────────────────────────────────────────────────────────────────────────┘

CommunicationMod 命令格式参考：
- play [card_index] [target?]         - 出牌（card_index 1-based）
- potion use [index]                  - 使用药水（无目标）
- potion use [index] [target]         - 使用药水（指定目标1-6）
- potion discard [index]              - 丢弃药水
- end                                 - 结束回合
- proceed                             - 确认/前进
- cancel                              - 取消
- choose [index/name]                 - 选择
- start [class] [ascension] [seed?]   - 开始游戏
- state                               - 获取状态（系统级，主循环调用）
- ready                               - 握手信号（系统级）

参考：https://github.com/ForgottenArbiter/spirecomm
"""
