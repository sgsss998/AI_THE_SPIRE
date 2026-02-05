#!/usr/bin/env python3
"""
杀戮尖塔 Gymnasium 环境封装

实现标准的 OpenAI/Gymnasium RL 环境接口。

【核心功能】
- 将杀戮尖塔游戏状态转换为 RL 环境可用的格式
- 支持 action masking（动作掩码）- 标记当前合法的动作
- 计算奖励函数（基于伤害、击杀、回合数等）
- 判断回合是否结束

【动作空间：173 维离散动作】
基于 CommunicationMod (spirecomm) 协议穷举所有可能的动作：
  0-69:   出牌（支持 0-6 个目标）
  70-109: 药水（使用/丢弃）
  110-169: 选择选项（商店/事件/奖励/地图/火堆删牌等，最多60个）
  170:    结束回合
  171:    确认/前进
  172:    取消

【观察空间：~252 维连续向量】
包含：手牌、玩家状态、怪物信息、遗物、牌库、房间、药水等

参考：https://github.com/ForgottenArbiter/spirecomm
"""
import logging
from typing import Tuple, Dict, Any, Optional, List
import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    import gym as gym
    from gym import spaces

from src.core.game_state import GameState, CombatState, RoomPhase
from src.core.action import Action, ActionType, ACTION_SPACE_SIZE, ACTION_END_ID, ACTION_PROCEED_ID, ACTION_CANCEL_ID
from src.core.config import get_config

logger = logging.getLogger(__name__)


class StsEnvironment(gym.Env):
    """
    杀戮尖塔标准 RL 环境

    【观察空间】~252 维向量
        - 手牌基础：卡牌池 one-hot（~90 维）
        - 手牌详情：cost + type + playable（30 维）
        - 玩家状态：HP/block/energy/gold/power/orbs（15 维）
        - 怪物信息：6 个怪物 × 10 维（60 维）
        - 遗物：常见遗物 one-hot（30 维）
        - 牌库/房间/药水：（20 维）

    【动作空间】Discrete(110) - 完整穷举所有 CommunicationMod 命令
        - 出牌：70 个（10 张牌 × 7 个目标）
        - 药水：15 个（3 个药水 × 5 种操作）
        - 选择：20 个
        - 其他：5 个

    【Action Masking】
        每个步骤返回 action_mask，标记当前合法的动作。
        RL 模型应使用此掩码避免选择非法动作。
    """

    metadata = {"render_modes": ["human", "none", "ansi"]}

    def __init__(
        self,
        render_mode: str = "none",
        observation_dim: int = None,  # None=使用扩展模式自动计算
        character: str = "silent",
        mode: str = "extended",  # "simple" 或 "extended"
    ):
        """
        初始化环境

        Args:
            render_mode: 渲染模式 ("human", "none", "ansi")
            observation_dim: 观察向量维度（None=自动计算）
            character: 角色 (silent, ironclad, defect)
            mode: 编码模式 ("simple"=30维, "extended"=~180维)
        """
        super().__init__()

        self.render_mode = render_mode
        self.character = character
        self.config = get_config()
        self.mode = mode

        # 根据模式设置观察维度
        if observation_dim is None:
            if mode == "simple":
                self.observation_dim = 30
            else:
                # 使用扩展模式的编码器获取维度
                from src.training.encoder import StateEncoder
                temp_encoder = StateEncoder(mode="extended")
                self.observation_dim = temp_encoder.get_output_dim()
        else:
            self.observation_dim = observation_dim

        # 动作空间：离散动作（110 维完整动作空间）
        self.action_space = spaces.Discrete(ACTION_SPACE_SIZE)

        # 观察空间：连续向量
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.observation_dim,),
            dtype=np.float32
        )

        # 状态
        self._current_state: Optional[GameState] = None
        self._episode_reward = 0.0
        self._episode_length = 0
        self._last_combat_hp: Tuple[int, int] = (0, 0)  # (player_hp, monster_hp)

        # 延迟加载编码器（避免循环导入）
        self._encoder = None

    @property
    def encoder(self):
        """获取状态编码器（延迟加载）"""
        if self._encoder is None:
            from src.training.encoder import StateEncoder
            self._encoder = StateEncoder(mode=self.mode)
        return self._encoder

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict] = None
    ) -> Tuple[np.ndarray, Dict]:
        """
        重置环境

        Args:
            seed: 随机种子
            options: 额外选项

        Returns:
            (observation, info) 元组
        """
        super().reset(seed=seed)

        # 重置状态
        self._current_state = None
        self._episode_reward = 0.0
        self._episode_length = 0
        self._last_combat_hp = (0, 0)

        # 创建空状态的观察
        obs = np.zeros(self.observation_dim, dtype=np.float32)
        action_mask = np.zeros(ACTION_SPACE_SIZE, dtype=np.int8)

        info = {
            "action_mask": action_mask,
            "valid_actions": [],
            "state": None,
            "episode_reward": 0.0,
        }

        if self.render_mode == "human":
            self.render()

        return obs, info

    def set_state(self, state: GameState):
        """
        设置当前游戏状态（由外部调用）

        Args:
            state: 从游戏读取的状态
        """
        self._current_state = state

        # 初始化战斗 HP（用于奖励计算）
        if state.combat:
            self._last_combat_hp = (
                state.combat.player.current_hp,
                state.combat.total_monster_hp
            )

    def step(
        self,
        action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        执行一步

        Args:
            action: 动作 ID (0-79，扩展模式)

        Returns:
            (observation, reward, terminated, truncated, info) 元组
        """
        if self._current_state is None:
            return self._get_empty_step_result()

        # 检查动作合法性
        valid_actions = self._get_valid_actions()
        action_mask = self._get_action_mask(valid_actions)

        if action not in valid_actions and action != ACTION_END_ID:
            logger.warning(f"Invalid action {action}, valid: {valid_actions}")
            # 惩罚非法动作
            reward = -1.0
            terminated = False
            truncated = False
            obs = self._encode_observation()
            info = {
                "action_mask": action_mask,
                "valid_actions": valid_actions,
                "error": "invalid_action",
                "episode_reward": self._episode_reward,
            }
            return obs, reward, terminated, truncated, info

        # 执行动作（实际执行由外部处理）
        self._episode_length += 1

        # 计算奖励
        reward = self._compute_reward()
        self._episode_reward += reward

        # 判断是否结束
        terminated = self._is_terminal()
        truncated = self._episode_length >= 1000  # 防止无限循环

        # 编码观察
        obs = self._encode_observation()

        # 获取合法动作
        valid_actions = self._get_valid_actions()
        action_mask = self._get_action_mask(valid_actions)

        info = {
            "action_mask": action_mask,
            "valid_actions": valid_actions,
            "state": self._current_state,
            "episode_reward": self._episode_reward,
            "episode_length": self._episode_length,
        }

        if self.render_mode == "human":
            self.render()

        return obs, reward, terminated, truncated, info

    def _get_empty_step_result(self) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """获取空状态的步骤结果"""
        obs = np.zeros(self.observation_dim, dtype=np.float32)
        return obs, 0.0, False, False, {
            "action_mask": np.zeros(ACTION_SPACE_SIZE, dtype=np.int8),
            "valid_actions": [],
            "state": None,
            "episode_reward": 0.0,
        }

    def _encode_observation(self) -> np.ndarray:
        """编码状态为观察向量"""
        if self._current_state is None or self._current_state.combat is None:
            return np.zeros(self.observation_dim, dtype=np.float32)

        try:
            state_vec = self.encoder.encode_state(self._current_state)
            # 填充或截断到指定维度
            if len(state_vec) < self.observation_dim:
                padded = np.zeros(self.observation_dim, dtype=np.float32)
                padded[:len(state_vec)] = state_vec
                return padded
            elif len(state_vec) > self.observation_dim:
                return state_vec[:self.observation_dim].astype(np.float32)
            return state_vec.astype(np.float32)
        except Exception as e:
            logger.error(f"Encoding error: {e}")
            return np.zeros(self.observation_dim, dtype=np.float32)

    def _get_valid_actions(self) -> List[int]:
        """
        获取当前合法动作列表（Action Masking）

        【核心功能】实现 Action Masking，返回当前状态下所有合法的动作 ID。
        RL 模型应使用此列表创建掩码，避免选择非法动作。

        【完整动作空间：110 维】
        ┌─────────────────────────────────────────────────────────────────────────────┐
        │ 出牌动作 (70个)：0-69                                                      │
        │ 药水动作 (12个)：70-81                                                    │
        │ 丢弃药水 (3个)：82-84                                                     │
        │ 选择动作 (20个)：85-104                                                   │
        │ 其他动作 (5个)：105-109                                                   │
        └─────────────────────────────────────────────────────────────────────────────┘
        """
        if self._current_state is None:
            return []

        valid = []
        commands = self._current_state.available_commands

        # ========== 非战斗状态 ==========
        # 商店、事件、奖励、地图等场景
        if not self._current_state.is_combat:
            if "choose" in commands:
                max_choice = min(len(self._current_state.choice_list), 60)
                for i in range(max_choice):
                    valid.append(110 + i)  # choose 0-59
            if "proceed" in commands:
                valid.append(ACTION_PROCEED_ID)
            if "cancel" in commands:
                valid.append(ACTION_CANCEL_ID)
            if not valid:
                valid.append(ACTION_END_ID)  # 无其他动作时 fallback
            return valid

        # ========== 战斗状态 ==========
        if self._current_state.combat is None:
            return []

        combat = self._current_state.combat

        # 1. 卡牌动作（支持多目标选择）
        if "play" in commands:
            living_monsters = combat.get_living_monsters()
            num_monsters = min(len(living_monsters), 6)  # 最多6个怪物

            # 遍历手牌（最多10张）
            for card_idx in range(min(len(combat.hand), 10)):
                card = combat.hand[card_idx]

                # 检查是否可打出：卡牌可用 + 能量足够
                if not card.is_playable:
                    continue
                if combat.player.energy < card.cost:
                    continue

                # 无目标卡牌：0-9（自身、所有敌人、无目标）
                valid.append(card_idx)

                # 需要目标的卡牌：10-69（为每个活着的怪物生成动作）
                if card.has_target:
                    for target_idx in range(num_monsters):
                        valid.append(card_idx + (target_idx + 1) * 10)

        # 2. 药水使用（支持目标选择）
        if combat.potions and len(combat.potions) > 0:
            num_potions = min(len(combat.potions), 3)
            # 获取活着的怪物数量用于药水目标
            num_targets = min(len(living_monsters) if 'living_monsters' in locals() else 1, 3)

            for potion_idx in range(num_potions):
                # 无目标使用：70-72（自己、所有敌人、无目标）
                valid.append(70 + potion_idx)
                # 带目标使用：73-81（可以指定敌人）
                for target_idx in range(num_targets):
                    valid.append(70 + potion_idx + (target_idx + 1) * 3)

        # 3. 丢弃药水：105-109
        if combat.potions and len(combat.potions) > 0:
            num_potions = min(len(combat.potions), 5)
            for i in range(num_potions):
                valid.append(105 + i)

        # 4. 选择命令：110-169（战斗中的选择，如遗物、Survivor 弃牌等）
        if "choose" in commands:
            max_choice = min(len(self._current_state.choice_list), 60)
            for i in range(max_choice):
                valid.append(110 + i)

        # 5. 结束回合：170
        if "end" in commands:
            valid.append(ACTION_END_ID)

        # 6. 前进/确认：171
        if "proceed" in commands:
            valid.append(ACTION_PROCEED_ID)

        # 7. 取消：172
        if "cancel" in commands:
            valid.append(ACTION_CANCEL_ID)

        # 如果没有合法动作，返回 end 作为 fallback
        if not valid:
            valid.append(ACTION_END_ID)

        return valid

    def _get_action_mask(self, valid_actions: List[int]) -> np.ndarray:
        """
        生成动作掩码（用于 Action Masking）

        【用途】将合法动作列表转换为 173 维的 0/1 向量
        - 1 表示该动作合法，可以被选择
        - 0 表示该动作不合法，应该被屏蔽

        RL 训练时使用此掩码：
        ```python
        action_probs = model(state)
        masked_probs = action_probs * action_mask
        action = sample(masked_probs)
        ```
        """
        mask = np.zeros(ACTION_SPACE_SIZE, dtype=np.int8)
        for action in valid_actions:
            if 0 <= action < ACTION_SPACE_SIZE:
                mask[action] = 1
        return mask

    def _compute_reward(self) -> float:
        """
        计算奖励值（Reward Shaping）

        【奖励设计原则】参考 STS-AI-Master 和强化学习最佳实践
        - 稀疏奖励（胜负）难以学习，需要密集的中间奖励
        - 奖励应该引导 AI  toward 最优策略
        - 避免奖励 hack（AI 找到获取奖励但不 win 的方法）

        【奖励项】
        + 造成伤害：0.1 × 伤害值（鼓励进攻）
        + 击杀怪物：+5（鼓励完成战斗）
        - 受到伤害：-0.2 × 伤害值（鼓励防御）
        - 玩家死亡：-50（强烈避免死亡）
        - 回合过长：每超过 20 回合 -0.01 × (回合-20)（鼓励效率）
        """
        if self._current_state is None or self._current_state.combat is None:
            return 0.0

        combat = self._current_state.combat
        player_hp = combat.player.current_hp
        monster_hp = combat.total_monster_hp

        # 上次状态
        last_player_hp, last_monster_hp = self._last_combat_hp

        reward = 0.0

        # 1. 怪物受伤（正面）
        monster_damage = last_monster_hp - monster_hp
        if monster_damage > 0:
            reward += monster_damage * 0.1

        # 2. 击杀怪物（额外奖励）
        if last_monster_hp > 0 and monster_hp == 0:
            reward += 5.0

        # 3. 玩家受伤（负面）
        player_damage = last_player_hp - player_hp
        if player_damage > 0:
            reward -= player_damage * 0.2

        # 4. 玩家死亡（大惩罚）
        if player_hp <= 0:
            reward -= 50.0

        # 5. 回合长度惩罚（鼓励快速结束）
        if self._episode_length > 20:
            reward -= 0.01 * (self._episode_length - 20)

        # 更新上次状态
        self._last_combat_hp = (player_hp, monster_hp)

        return reward

    def _is_terminal(self) -> bool:
        """
        判断回合是否结束（Terminal State 检测）

        【回合结束条件】
        1. 不在游戏中（游戏结束/退出）
        2. 不在战斗中（战斗结束）
        3. 玩家死亡（战斗失败）
        4. 所有怪物死亡（战斗胜利）

        Returns:
            True=回合应该结束，False=继续
        """
        if self._current_state is None:
            return False

        # 不在游戏中 = 结束
        if not self._current_state.in_game:
            return True

        # 不在战斗中 = 结束（对于单战斗环境）
        if not self._current_state.is_combat:
            return True

        # 玩家死亡 = 结束（战斗失败）
        if self._current_state.combat and self._current_state.combat.player.current_hp <= 0:
            return True

        # 所有怪物死亡 = 胜利结束
        if self._current_state.combat and self._current_state.combat.total_monster_hp <= 0:
            return True

        return False

    def render(self):
        """渲染环境"""
        if self.render_mode == "human" and self._current_state:
            print(f"\n=== StsEnv ===")
            print(f"Floor: {self._current_state.floor}, Phase: {self._current_state.room_phase.value}")
            if self._current_state.combat:
                c = self._current_state.combat
                print(f"Player: {c.player.current_hp}/{c.player.max_hp} HP, {c.player.energy} Energy, {c.player.block} Block")
                print(f"Hand: {len(c.hand)} cards")
                print(f"Monsters: {', '.join(f'{m.name}({m.current_hp}/{m.max_hp})' for m in c.get_living_monsters())}")
            print(f"Episode Reward: {self._episode_reward:.2f}, Length: {self._episode_length}")
            print("=" * 40)

        elif self.render_mode == "ansi":
            if self._current_state and self._current_state.combat:
                c = self._current_state.combat
                return (
                    f"F{self._current_state.floor} | "
                    f"P:{c.player.current_hp}/{c.player.max_hp} E:{c.player.energy} | "
                    f"M:{c.total_monster_hp} | "
                    f"R:{self._episode_reward:.1f}"
                )

    def close(self):
        """关闭环境"""
        logger.info(f"[StsEnv] Environment closed. Total episodes: {self._episode_length}")


class StsEnvWrapper:
    """
    环境包装器 - 连接 Gymnasium 环境和 CommunicationMod

    【核心功能】
    - 桥接 Gymnasium 环境和实际游戏的 Mod 通信
    - 将动作 ID 转换为 Mod 命令并发送
    - 从 Mod 读取游戏状态并更新环境

    【两种使用模式】
    1. 真实游戏模式（protocol != None）：
       - 连接到 CommunicationMod
       - 实际与杀戮尖塔游戏交互

    2. 模拟训练模式（protocol == None）：
       - 不需要真实游戏
       - 用于离线训练、单元测试等

    【使用示例】
    ```python
    # 真实游戏模式
    protocol = ModProtocol(stdin, stdout)
    env_wrapper = StsEnvWrapper(protocol=protocol)

    # 模拟训练模式
    env_wrapper = StsEnvWrapper(mode="extended")
    env_wrapper.set_state(mock_game_state)
    ```
    """

    def __init__(
        self,
        protocol=None,
        mode: str = "extended",
        character: str = "silent",
        ascension: int = 0,
    ):
        """
        初始化包装器

        Args:
            protocol: ModProtocol 实例（可选，用于实际游戏）
            mode: 编码模式 ("simple" 或 "extended")
            character: 角色 (silent, ironclad, defect)
            ascension: Ascension 等级
        """
        self.env = StsEnvironment(mode=mode)
        self.protocol = protocol
        self._last_action: Optional[Action] = None
        self.mode = mode
        self.character = character
        self.ascension = ascension

        # Gymnasium 兼容属性
        self.observation_space = self.env.observation_space
        self.action_space = self.env.action_space

    def reset(self) -> Tuple[np.ndarray, Dict]:
        """
        重置环境并返回初始观察

        【流程】
        1. 如果有 protocol，从游戏读取初始状态
        2. 调用环境的 reset 方法
        3. 因 env.reset() 会清空 _current_state，需重新 set_state 并确保 info["state"] 正确

        Returns:
            (observation, info) 元组，info["state"] 为 GameState
        """
        if self.protocol is not None:
            # 读取初始状态（collect_data 已提前发送 ready）
            state = self.protocol.read_state()
            # 若首次读到空/EOF，发送 state 请求并重试（Mod 可能先发空行）
            if state is None:
                for _ in range(5):
                    self.protocol.send_command("state")
                    state = self.protocol.read_state()
                    if state is not None:
                        break
            if state is None:
                return self.env.reset()
            self.env.set_state(state)
            result = self.env.reset()
            # env.reset() 会清空 _current_state，需恢复
            self.env.set_state(state)
            obs = self.env._encode_observation()
            info = result[1]
            info["state"] = state
            return obs, info
        return self.env.reset()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        执行动作并返回结果

        【真实游戏模式流程】
        1. 获取当前游戏状态
        2. 将动作 ID 转换为 Mod 命令
        3. 发送命令给游戏
        4. 读取新的游戏状态
        5. 调用环境的 step 方法

        Args:
            action: 动作 ID (0-109)

        Returns:
            (observation, reward, terminated, truncated, info) 元组
        """
        if self.protocol is not None:
            # 获取当前状态
            state = self._current_state_from_env()
            if state is None:
                state = self.protocol.read_state()
                self.env.set_state(state)

            # 将动作 ID 转换为命令
            mod_action = self._action_to_command(action, state)

            # 发送命令到游戏
            self.protocol.send_action(mod_action)

            # 读取新状态
            new_state = self.protocol.read_state()
            self.env.set_state(new_state)

        # 执行环境步骤（计算奖励、判断结束等）
        return self.env.step(action)

    def _current_state_from_env(self) -> Optional[GameState]:
        """从环境获取当前游戏状态"""
        return self.env._current_state

    def set_state(self, state: GameState):
        """
        设置游戏状态

        【用途】用于模拟训练、单元测试等不需要真实游戏的场景
        """
        self.env.set_state(state)

    def _action_to_command(self, action: int, state: GameState) -> Action:
        """
        将动作 ID 转换为 Mod 命令

        【完整动作空间：110 维】
        ┌─────────────────────────────────────────────────────────────────────────────┐
        │ 出牌动作 (70个)：0-69                                                      │
        │ 药水动作 (12个)：70-81                                                    │
        │ 丢弃药水 (3个)：82-84                                                     │
        │ 选择动作 (20个)：85-104                                                   │
        │ 其他动作 (5个)：105-109                                                   │
        └─────────────────────────────────────────────────────────────────────────────┘

        Args:
            action: 动作 ID (0-109)
            state: 当前游戏状态

        Returns:
            Action 对象
        """
        # action_id=-1 表示 Action.state()（系统轮询），需发送 "state" 而非 cancel
        if action < 0:
            return Action(type=ActionType.STATE)
        return Action.from_id(action)

    def close(self):
        """关闭环境"""
        self.env.close()
        if self.protocol is not None:
            # 可以在这里关闭 protocol 连接
            pass
