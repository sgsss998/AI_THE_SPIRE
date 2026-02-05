#!/usr/bin/env python3
"""
规则 Agent

基于硬编码规则的 AI，用于生成训练数据和作为基线对比。
迁移自 scripts/strategy.py 的逻辑。
"""
import random
import logging
from typing import Dict, Any, List, Optional

from src.agents.base import RuleBasedAgent
from src.core.game_state import (
    GameState, CombatState, RoomPhase, Card, CardType, Monster, IntentType
)
from src.core.action import Action, ActionType

logger = logging.getLogger(__name__)


# 卡牌数据（id -> (damage, block)）
CARD_STATS = {
    "Strike_G": (6, 0),
    "Defend_G": (0, 5),
    "Neutralize": (3, 0),
    "Survivor": (0, 8),
    "Strike_R": (6, 0),
    "Defend_R": (0, 5),
    "AscendersBane": (0, 0),
    "Shiv": (4, 0),
}

# 默认估算
DEFAULT_ATTACK_DMG = 6
DEFAULT_BLOCK = 5

# 商店价格表
SHOP_PRICES = {
    # 遗物
    "袋中硬币": 150, "锚": 150, "黑星": 150, "猴子假身": 150,
    "煤块": 150, "奇异 spoon": 150, "冻结之眼": 150, "茶壶": 150,
    "花碟": 150, "Old Coin": 150, "赌博芯片": 150, "铜币": 150, "金币": 150,
    # 卡牌
    "灾祸": 80, "匕首雨": 80, "刀刃之舞": 100, "恐怖": 80,
    "无限刀刃": 90, "致盲": 70, "瓶中精灵": 100,
    # 英文版
    "Cataclysm": 80, "Dagger Rain": 80, "Blade Dance": 100,
    "Terror": 80, "Infinite Blades": 90, "Blind": 70, "Bottled Spirit": 100,
    # 药水
    "药水": 50, "potion": 50, "虚弱药水": 50, "能力药水": 50,
    # 清除
    "purge": 50,
}


class RuleBasedAgentImpl(RuleBasedAgent):
    """
    规则 AI 实现

    迁移自旧版 scripts/strategy.py，保持相同的行为逻辑。

    策略要点：
    - 战斗：优先 0 费牌，敌人攻击时优先防御，能秒则攻击
    - 选择：简单随机选择
    - 商店：优先买最贵
    """

    def __init__(self, name: str = "RuleBased", config: Optional[Dict] = None):
        super().__init__(name, config)
        self._last_discard_step: Optional[str] = None
        self._gold = 200  # 默认金币

        # 防卡住机制：重试计数器
        self._selection_step_count = 0  # 选牌界面步数计数
        self._last_screen_type: Optional[str] = None  # 上次的屏幕类型
        self._same_screen_count = 0  # 同一屏幕连续出现次数

        # 防卡住机制：命令重复检测（核心功能）
        self._last_command: Optional[str] = None  # 上次发送的命令
        self._same_command_count = 0  # 相同命令连续次数
        self._last_state_hash: Optional[str] = None  # 上次状态的哈希
        self._same_state_count = 0  # 相同状态连续次数
        self._blacklisted_commands: set = set()  # 被禁用的命令（卡住过的命令）

        # 阈值配置
        self.STUCK_COMMAND_THRESHOLD = 5  # 连续 5 次相同命令判定为卡住
        self.STUCK_STATE_THRESHOLD = 10   # 连续 10 次相同状态判定为卡住
        self.BLACKLIST_DURATION = 10      # 命令被禁用 10 步

    def select_action(self, state: GameState) -> Action:
        """
        选择动作

        根据当前状态决定下一步动作。

        Args:
            state: 游戏状态

        Returns:
            要执行的动作
        """
        # ========== 防卡住检测：核心逻辑 ==========
        action = self._decide_action_internal(state)

        # 检测命令重复和状态重复
        action = self._check_and_handle_stuck(state, action)

        return action

    def _decide_action_internal(self, state: GameState) -> Action:
        """内部决策逻辑（不含防卡住检测）"""
        # ========== 防卡住检测：屏幕级别 ==========
        current_screen = state.screen_type or "UNKNOWN"
        if current_screen == self._last_screen_type:
            self._same_screen_count += 1
        else:
            self._same_screen_count = 0
            self._last_screen_type = current_screen

        # 检测：同一屏幕出现超过 10 次，可能卡住
        if self._same_screen_count > 10:
            logger.error(
                f"[防卡住] 同一屏幕 {current_screen} 连续出现 {self._same_screen_count} 次，"
                f"可能卡住！commands={state.available_commands}"
            )
            # 尝试强制前进
            if "proceed" in state.available_commands:
                return Action.proceed()
            elif "choose" in state.available_commands:
                return Action.choose(0)
            elif "play" in state.available_commands:
                return Action.end_turn()
            else:
                # 兜底：发送 state 获取最新状态
                return Action.state()

        # ========== 正常决策逻辑 ==========
        # 优先检查选牌界面（HAND_SELECT，如生存者弃牌）
        # 必须在战斗出牌之前检查，因为选牌界面仍在战斗中
        if self._is_card_selection_screen(state):
            return self._handle_card_selection(state)

        # 战斗出牌
        if state.is_ready_for_combat:
            return self._decide_combat_action(state)

        # 奖励页/确认页等：有 proceed 则优先点前进（拿完奖励后需 proceed 才能继续）
        if state.ready_for_command and "proceed" in state.available_commands:
            return Action.proceed()

        # 选择界面（商店、事件、奖励选牌等）
        if state.ready_for_command and "choose" in state.available_commands:
            return self._decide_choice(state)

        # 动画/过渡阶段（如怪物死亡）：发 wait 让 Mod 推进，否则会卡住
        if not state.ready_for_command and "wait" in state.available_commands:
            return Action.wait()

        # 其他情况返回 state
        return Action.state()

    def _check_and_handle_stuck(self, state: GameState, action: Action) -> Action:
        """
        检测并处理卡住情况

        核心逻辑：
        1. 检测是否连续发送相同命令
        2. 检测是否连续收到相同状态
        3. 如果卡住，返回替代动作

        Args:
            state: 当前游戏状态
            action: Agent 决策的原始动作

        Returns:
            原始动作或替代动作
        """
        command = action.to_command()
        state_hash = state.hash()
        is_stuck = False
        stuck_reason = ""

        # ========== 检测 1: 相同命令重复 ==========
        if command == self._last_command:
            self._same_command_count += 1
        else:
            self._same_command_count = 0
            self._last_command = command

        # ========== 检测 2: 相同状态重复 ==========
        if state_hash == self._last_state_hash:
            self._same_state_count += 1
        else:
            self._same_state_count = 0
            self._last_state_hash = state_hash

        # ========== 判断是否卡住 ==========
        # 条件 1: 连续发送相同命令达到阈值
        if self._same_command_count >= self.STUCK_COMMAND_THRESHOLD:
            is_stuck = True
            stuck_reason = (
                f"连续 {self._same_command_count} 次发送相同命令: '{command}'"
            )

        # 条件 2: 连续收到相同状态达到阈值（即使命令不同）
        elif self._same_state_count >= self.STUCK_STATE_THRESHOLD:
            is_stuck = True
            stuck_reason = (
                f"连续 {self._same_state_count} 次收到相同状态 "
                f"(screen_type={state.screen_type})"
            )

        # 条件 3: 混合检测（命令重复 + 状态重复，各放宽要求）
        elif (
            self._same_command_count >= 3
            and self._same_state_count >= 5
        ):
            is_stuck = True
            stuck_reason = (
                f"命令重复 {self._same_command_count} 次 + "
                f"状态重复 {self._same_state_count} 次"
            )

        # ========== 处理卡住 ==========
        if is_stuck:
            logger.error(f"[防卡住] {stuck_reason}")

            # 将当前命令加入黑名单
            self._blacklisted_commands.add(command)
            logger.warning(f"[防卡住] 将命令加入黑名单: '{command}'")

            # 尝试获取替代动作
            alternative = self._get_alternative_action(state, command)
            alt_command = alternative.to_command()

            logger.info(f"[防卡住] 使用替代命令: '{alt_command}'")

            # 重置计数器
            self._same_command_count = 0
            self._same_state_count = 0

            return alternative

        # 更新黑名单命令的计时（每次正常决策后减少计数）
        self._update_blacklist()

        return action

    def _get_alternative_action(self, state: GameState, stuck_command: str) -> Action:
        """
        获取替代动作

        关键修复：直接使用 available_commands 中的原始命令字符串，
        不经过 Action 类型系统的转换，确保 Mod 能正确识别。

        Args:
            state: 当前游戏状态
            stuck_command: 卡住的命令

        Returns:
            替代动作
        """
        commands = state.available_commands
        logger.debug(f"[防卡住] 可用命令: {commands}")

        # 策略 1: 优先级顺序（直接从可用命令中选择）
        priority = ["confirm", "proceed", "cancel", "end", "skip", "return", "leave", "key", "click"]

        for cmd_name in priority:
            if cmd_name in commands and cmd_name not in self._blacklisted_commands:
                logger.info(f"[防卡住] 尝试优先命令: {cmd_name}")
                # 直接使用原始命令字符串，创建对应的 Action
                # 对于 confirm/proceed/cancel/end 等简单命令，直接映射
                if cmd_name == "confirm":
                    # confirm 和 proceed 在语义上是相同的，都是"确认/前进"
                    # 但 Mod 在选牌界面使用 confirm
                    return Action.confirm()
                elif cmd_name == "proceed":
                    return Action.proceed()
                elif cmd_name == "cancel":
                    return Action.cancel()
                elif cmd_name == "end":
                    return Action.end_turn()
                elif cmd_name == "skip":
                    return Action.choose(-1)  # skip 通常是 choose -1
                elif cmd_name in ("key", "click"):
                    # 这些命令需要参数，暂时跳过
                    continue
                else:
                    return Action.from_command(cmd_name)

        # 策略 2: 处理 choose 类命令
        if "choose" in commands:
            # 如果是 choose X 卡住了，尝试 choose Y（Y != X）
            try:
                if "choose" in stuck_command:
                    stuck_index = int(stuck_command.split()[1])
                    # 尝试下一个索引
                    for i in range(5):  # 尝试 0-4
                        if i != stuck_index:
                            cmd = f"choose {i}"
                            if cmd not in self._blacklisted_commands:
                                logger.info(f"[防卡住] 尝试替代 choose 命令: choose {i}")
                                return Action.choose(i)
                else:
                    # stuck_command 不是 choose，直接尝试 choose 0
                    if "choose 0" not in self._blacklisted_commands:
                        logger.info(f"[防卡住] 尝试 choose 命令: choose 0")
                        return Action.choose(0)
            except (ValueError, IndexError):
                # 解析失败，直接尝试 choose 0
                if "choose 0" not in self._blacklisted_commands:
                    logger.info(f"[防卡住] 尝试 choose 命令: choose 0")
                    return Action.choose(0)

        # 策略 3: 随机选择一个非黑名单的可用命令
        for cmd in commands:
            if cmd not in self._blacklisted_commands:
                logger.info(f"[防卡住] 随机选择命令: {cmd}")
                # 对于简单命令，直接使用
                if cmd in ("confirm", "proceed", "cancel", "end"):
                    if cmd == "confirm":
                        return Action.confirm()
                    elif cmd == "proceed":
                        return Action.proceed()
                    elif cmd == "cancel":
                        return Action.cancel()
                    elif cmd == "end":
                        return Action.end_turn()
                else:
                    try:
                        return Action.from_command(cmd)
                    except Exception as e:
                        logger.warning(f"[防卡住] 无法解析命令 {cmd}: {e}")

        # 策略 4: 兜底 - 清空黑名单，返回 state 或 wait
        logger.warning("[防卡住] 所有命令都在黑名单中，清空黑名单")
        self._blacklisted_commands.clear()
        if "wait" in commands:
            logger.info("[防卡住] 使用兜底命令: wait")
            return Action.wait()
        logger.info("[防卡住] 使用兜底命令: state")
        return Action.state()

    def _update_blacklist(self):
        """更新黑名单（减少禁用计时）"""
        # 简化实现：每次决策后清空黑名单
        # 更复杂的实现可以使用计时器
        if self._blacklisted_commands and self._same_command_count == 0:
            # 只有在正常执行时才减少黑名单
            pass  # 暂时保持黑名单，直到检测到新的卡住

    def _decide_combat_action(self, state: GameState) -> Action:
        """
        决定战斗动作

        策略：
        1. 无能量且无 0 费 → end
        2. 优先 0 费牌
        3. 敌人攻击且能秒 → 优先攻击
        4. 敌人攻击且不能秒 → 优先防御
        5. 有能量且有格挡/增益 → 尽量用
        6. 其他攻击牌
        7. 无牌可出 → end
        """
        combat = state.combat
        if combat is None:
            return Action.state()

        hand = combat.hand
        energy = combat.player.energy
        valid_indices = combat.get_valid_card_indices()

        # 分组各类牌
        zero_cost = [i for i in valid_indices if i < len(hand) and hand[i].cost <= 0]
        attacks = [i for i in valid_indices if i < len(hand) and hand[i].card_type == CardType.ATTACK]
        blocks = [i for i in valid_indices if i < len(hand) and self._card_block(hand[i]) > 0]
        buffs = [i for i in valid_indices if i < len(hand) and self._is_block_or_buff(hand[i])]

        # 可出的牌（不含 end）
        playable = [i for i in valid_indices if i != 10]

        # 1. 无能量且无 0 费 → end
        if energy <= 0 and not zero_cost:
            return Action.end_turn()

        # 2. 无牌可出 → end
        if not playable:
            return Action.end_turn()

        # 获取存活怪物索引列表（安全处理）
        living_monster_indices = combat.get_living_monster_indices()

        # 边界检查：如果没有存活怪物，不指定目标
        if not living_monster_indices:
            target_idx = 0  # 无目标
        else:
            # 选择第一个存活怪物作为目标
            target_idx = living_monster_indices[0] + 1  # 转为 1-based

        # 3. 优先 0 费
        if zero_cost:
            return Action.play_card(zero_cost[0], target_idx)

        # 4. 敌人攻击且能秒 → 优先攻击
        if combat.is_monsters_attacking and living_monster_indices:
            total_damage = sum(self._card_damage(hand[i]) for i in attacks if i < len(hand))
            if total_damage >= combat.total_monster_hp:
                best = max(attacks, key=lambda i: self._card_damage(hand[i]) if i < len(hand) else 0)
                return Action.play_card(best, target_idx)

        # 5. 敌人攻击且不能秒 → 优先防御
        if combat.is_monsters_attacking and blocks:
            best = max(blocks, key=lambda i: self._card_block(hand[i]) if i < len(hand) else 0)
            return Action.play_card(best, 0)

        # 6. 有能量且有格挡/增益 → 尽量用
        if energy > 0 and buffs:
            return Action.play_card(buffs[0], 0)

        # 7. 有攻击牌（确保有存活怪物）
        if attacks and living_monster_indices:
            return Action.play_card(attacks[0], target_idx)

        # 8. 其他可出牌（如果有目标才用）
        if playable and living_monster_indices:
            return Action.play_card(playable[0], target_idx)
        elif playable:
            # 没有怪物了，不出需要目标的牌
            non_target_playable = [i for i in playable if i < len(hand) and not hand[i].has_target]
            if non_target_playable:
                return Action.play_card(non_target_playable[0], 0)

        # 9. 默认 end
        return Action.end_turn()

    def _get_shop_choice(self, state: GameState) -> Action:
        """商店决策：优先买最贵的遗物/卡牌"""
        choice_list = state.choice_list if hasattr(state, 'choice_list') else []

        # 边界检查：空列表
        if not choice_list:
            logger.warning("[商店] choice_list 为空，离开商店")
            return Action.choose(0)

        # 边界检查：只有 purge（离开选项）
        if len(choice_list) <= 1:
            return Action.choose(0)  # 离开商店

        # 更新金币（从 game_state 获取最新值）
        gs_dict = state.to_mod_response().get("game_state", {})
        self._gold = gs_dict.get("gold", self._gold)

        # 跳过第一个 "purge"，安全处理 None 值
        items = []
        for i, item_name in enumerate(choice_list[1:], start=1):
            if item_name is None:
                continue
            price = SHOP_PRICES.get(item_name, 100)
            items.append((i, item_name, price))

        # 如果没有有效商品，离开商店
        if not items:
            logger.warning("[商店] 没有有效商品，离开商店")
            return Action.choose(0)

        # 按价格排序
        items.sort(key=lambda x: x[2], reverse=True)

        # 选择买得起的最贵商品
        for choice_idx, item_name, price in items:
            if price <= self._gold:
                logger.info(f"[商店] 购买 {item_name}，价格 {price} 金币")
                self._gold -= price  # 扣除金币
                return Action.choose(choice_idx)

        logger.info(f"[商店] 买不起任何商品（{self._gold} 金），跳过")
        return Action.choose(0)

    # ==================== 辅助方法 ====================

    def _card_damage(self, card: Card) -> int:
        """获取卡牌伤害"""
        if card.id in CARD_STATS:
            return CARD_STATS[card.id][0]
        if card.card_type == CardType.ATTACK:
            return DEFAULT_ATTACK_DMG
        return 0

    def _card_block(self, card: Card) -> int:
        """获取卡牌格挡"""
        if card.id in CARD_STATS:
            return CARD_STATS[card.id][1]
        if card.card_type == CardType.SKILL and "Defend" in card.id:
            return DEFAULT_BLOCK
        if card.id in ("Survivor", "Defend_G", "Defend_R"):
            return DEFAULT_BLOCK
        return 0

    def _is_block_or_buff(self, card: Card) -> bool:
        """是否格挡或增益牌"""
        if self._card_block(card) > 0:
            return True
        if card.card_type == CardType.POWER:
            return True
        if card.id in ("Survivor", "Defend_G", "Defend_R", "Backflip"):
            return True
        return False

    def _first_living_monster_index(self, combat: CombatState) -> int:
        """获取第一个存活怪物的索引（安全版本）"""
        living_indices = combat.get_living_monster_indices()
        if living_indices:
            return living_indices[0]
        return -1  # 表示没有存活怪物

    def _is_card_selection_screen(self, state: GameState) -> bool:
        """检测是否为选牌界面（如生存者弃牌）"""
        # 方法1：检查 screen_type 是否为 HAND_SELECT
        if state.screen_type == "HAND_SELECT":
            return True

        # 方法2：战斗中 + choose + 无 play/end = 覆盖层（兼容旧版）
        if not state.is_combat or state.combat is None:
            return False

        commands = state.available_commands
        combat = state.combat

        has_choose = "choose" in commands
        no_play_end = "play" not in commands and "end" not in commands
        has_hand = bool(combat.hand)

        return has_choose and no_play_end and has_hand

    def _handle_card_selection(self, state: GameState) -> Action:
        """处理选牌界面（如生存者弃牌）"""
        commands = state.available_commands
        hand = state.combat.hand if state.combat else []
        screen_state = state.screen_state or {}

        # 检查是否已经选择了牌（通过 screen_state.selected）
        selected_cards = screen_state.get("selected", [])
        has_selected = len(selected_cards) > 0

        # 获取需要选择的牌数
        max_cards = screen_state.get("max_cards", 1)
        can_pick_zero = screen_state.get("can_pick_zero", False)

        # 检查是否有确认命令（proceed 或 confirm）
        has_confirm_cmd = "proceed" in commands or "confirm" in commands

        # 调试日志
        logger.debug(
            f"[选牌界面] screen_type={state.screen_type}, "
            f"commands={commands}, "
            f"hand_count={len(hand)}, "
            f"selected={len(selected_cards)}/{max_cards}, "
            f"can_pick_zero={can_pick_zero}, "
            f"has_confirm={has_confirm_cmd}, "
            f"last_step={self._last_discard_step}, "
            f"retry={self._selection_step_count}"
        )

        # ========== 防卡住：重试次数检测 ==========
        self._selection_step_count += 1
        if self._selection_step_count > 8:
            logger.error(
                f"[选牌界面] 重试次数超限（{self._selection_step_count}），"
                f"强制重置并尝试退出"
            )
            self._selection_step_count = 0
            self._last_discard_step = None
            # 强制发送确认命令（proceed 或 confirm）
            if "confirm" in commands:
                logger.info("[选牌界面] 强制发送 confirm")
                return Action.confirm()
            elif "proceed" in commands:
                return Action.proceed()
            elif hand and "choose" in commands:
                return Action.choose(0)
            return Action.state()

        # ========== 正常逻辑 ==========
        # 如果已经选择了足够的牌，且有确认命令，确认选择
        if has_selected and len(selected_cards) >= max_cards and has_confirm_cmd:
            logger.info(f"[选牌界面] 已选择 {len(selected_cards)} 张牌，发送确认")
            self._selection_step_count = 0  # 重置计数
            self._last_discard_step = None
            # 优先使用 confirm，否则用 proceed
            if "confirm" in commands:
                logger.info("[选牌界面] 使用 confirm 命令确认")
                return Action.confirm()
            else:
                logger.info("[选牌界面] 使用 proceed 命令确认")
                return Action.proceed()

        # 如果可以选择 0 张，且不需要强制选择，直接确认
        if can_pick_zero and len(selected_cards) == 0 and has_confirm_cmd:
            logger.info(f"[选牌界面] 可以跳过，发送确认")
            self._selection_step_count = 0
            self._last_discard_step = None
            if "confirm" in commands:
                return Action.confirm()
            else:
                return Action.proceed()

        # 如果没有手牌或没有 choose 命令，说明选牌界面已结束
        if not hand or "choose" not in commands:
            self._last_discard_step = None
            if has_confirm_cmd:
                if "confirm" in commands:
                    return Action.confirm()
                else:
                    return Action.proceed()
            return Action.state()

        # 根据上次操作决定下一步
        if self._last_discard_step == "choose":
            # 上次已选择，这次确认
            logger.info(f"[选牌界面] 上次已选择，发送确认")
            self._last_discard_step = "confirm"
            if "confirm" in commands:
                return Action.confirm()
            else:
                return Action.proceed()
        elif self._last_discard_step == "confirm":
            # 上次已确认，这次应该已经退出选牌界面
            # 如果还在选牌界面，尝试继续确认或重置
            logger.info(f"[选牌界面] 上次已确认，仍在界面，继续发送确认")
            self._last_discard_step = None
            if has_confirm_cmd:
                if "confirm" in commands:
                    return Action.confirm()
                else:
                    return Action.proceed()
            return Action.state()
        else:
            # 第一次进入选牌界面，选择第一张牌
            card_name = hand[0].name if hand else "未知"
            logger.info(f"[选牌界面] 第一次进入，选择第1张牌: {card_name}")
            self._last_discard_step = "choose"
            return Action.choose(0)

    def _decide_choice(self, state: GameState) -> Action:
        """
        决定选择动作

        处理商店、事件、弃牌等选择界面。
        """
        # 检查是否为弃牌/选牌界面
        if self._is_card_selection_screen(state):
            return self._handle_card_selection(state)

        # 商店特殊处理
        if state.screen_type == "SHOP_SCREEN":
            return self._get_shop_choice(state)

        # 选项来源：战斗内用 screen_state.options，奖励/事件等用 choice_list
        options = []
        if state.combat and hasattr(state.combat, 'screen_state') and state.combat.screen_state:
            options = state.combat.screen_state.get("options", [])
        else:
            # COMBAT_REWARD/CARD_REWARD/EVENT 等：choice_list 即选项
            choice_list = getattr(state, "choice_list", []) or []
            if choice_list:
                options = [{"choice_index": i} for i in range(len(choice_list))]

        # 边界检查：空选项列表
        if not options:
            logger.warning(f"[选择界面] choice_list 为空，screen_type={state.screen_type}")
            return Action.choose(0)  # 兜底

        # 过滤可用选项
        enabled = [o for o in options if not o.get("disabled", False)]

        # 边界检查：没有可用选项
        if not enabled:
            logger.warning(f"[选择界面] 没有可用选项，选择第一个")
            return Action.choose(0)

        # 随机选择一个可用选项
        idx = random.randint(0, len(enabled) - 1)
        choice_idx = enabled[idx].get("choice_index", idx)
        logger.debug(f"[选择界面] 选择索引 {choice_idx}，共 {len(enabled)} 个可用选项")
        return Action.choose(choice_idx)


# 兼容旧版接口
def decide_combat_action(combat_state: Dict, available_commands: List) -> str:
    """
    兼容旧版 decide_combat_action 函数

    将字典格式转换为新的 GameState 格式。
    """
    from src.core.game_state import GameState

    # 构造临时 GameState
    state = GameState(
        room_phase=RoomPhase.COMBAT,
        floor=combat_state.get("floor", 1),
        act=1,
        combat=CombatState.from_dict(combat_state) if isinstance(combat_state, dict) else combat_state,
        available_commands=available_commands,
        ready_for_command=True
    )

    agent = RuleBasedAgentImpl()
    action = agent._decide_combat_action(state)
    return action.to_command()


def decide_choice(data: Dict) -> Optional[str]:
    """
    兼容旧版 decide_choice 函数
    """
    from src.core.game_state import GameState

    state = GameState.from_mod_response(data)
    agent = RuleBasedAgentImpl()
    action = agent._decide_choice(state)

    if action.type == ActionType.STATE:
        return None
    return action.to_command()
