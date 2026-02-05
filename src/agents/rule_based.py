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

    def select_action(self, state: GameState) -> Action:
        """
        选择动作

        根据当前状态决定下一步动作。

        Args:
            state: 游戏状态

        Returns:
            要执行的动作
        """
        # 战斗出牌
        if state.is_ready_for_combat:
            return self._decide_combat_action(state)

        # 选择界面（商店、事件、弃牌等）
        if state.ready_for_command and "choose" in state.available_commands:
            return self._decide_choice(state)

        # 动画/过渡阶段（如怪物死亡）：发 wait 让 Mod 推进，否则会卡住
        if not state.ready_for_command and "wait" in state.available_commands:
            return Action.wait()

        # 奖励页/空面板等：有 proceed 则点前进（如 COMBAT_REWARD 奖励领完后）
        if state.ready_for_command and "proceed" in state.available_commands:
            return Action.proceed()

        # 其他情况返回 state
        return Action.state()

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

        # 获取第一个存活怪物的索引（0-based），内部 target 为 1-based
        monster_idx = self._first_living_monster_index(combat)
        target_idx = monster_idx + 1 if monster_idx >= 0 else 0

        # 3. 优先 0 费
        if zero_cost:
            return Action.play_card(zero_cost[0], target_idx)

        # 4. 敌人攻击且能秒 → 优先攻击
        if combat.is_monsters_attacking:
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

        # 7. 有攻击牌
        if attacks:
            return Action.play_card(attacks[0], target_idx)

        # 8. 其他可出牌
        if playable:
            return Action.play_card(playable[0], target_idx)

        # 9. 默认 end
        return Action.end_turn()

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

        # 其他选择：随机选一个启用的选项
        if state.combat and state.combat.screen_state:
            options = state.combat.screen_state.get("options", [])
        else:
            options = []

        if options:
            enabled = [o for o in options if not o.get("disabled", False)]
            if enabled:
                idx = random.randint(0, len(enabled) - 1)
                choice_idx = enabled[idx].get("choice_index", idx)
                return Action.choose(choice_idx)

        # 随机选择
        return Action.choose(0)

    def _is_card_selection_screen(self, state: GameState) -> bool:
        """检测是否为选牌界面（如生存者弃牌）"""
        if not state.is_combat or state.combat is None:
            return False

        commands = state.available_commands
        combat = state.combat

        # 战斗中 + choose + 无 play/end = 覆盖层
        has_choose = "choose" in commands
        no_play_end = "play" not in commands and "end" not in commands
        has_hand = bool(combat.hand)

        return has_choose and no_play_end and has_hand

    def _handle_card_selection(self, state: GameState) -> Action:
        """处理选牌界面（如生存者弃牌）"""
        commands = state.available_commands
        hand = state.combat.hand if state.combat else []

        if not hand or "choose" not in commands:
            self._last_discard_step = None
            # 如果有 proceed 命令，返回确认动作
            return Action.state() if "proceed" not in commands else Action.proceed()

        # 交替：上次发了 choose → 这次发 proceed 确认
        if self._last_discard_step == "choose":
            self._last_discard_step = "confirm"
            return Action.proceed()

        self._last_discard_step = "choose"
        return Action.choose(0)

    def _get_shop_choice(self, state: GameState) -> Action:
        """商店决策：优先买最贵的遗物/卡牌"""
        choice_list = state.choice_list if hasattr(state, 'choice_list') else []

        if len(choice_list) <= 1:
            return Action.choose(0)  # 离开商店

        # 跳过第一个 "purge"
        items = []
        for i, item_name in enumerate(choice_list[1:], start=1):
            price = SHOP_PRICES.get(item_name, 100)
            items.append((i, item_name, price))

        # 按价格排序
        items.sort(key=lambda x: x[2], reverse=True)

        # 选择买得起的最贵商品
        for choice_idx, item_name, price in items:
            if price <= self._gold:
                logger.info(f"[商店] 购买 {item_name}，价格 {price} 金币")
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
        """获取第一个存活怪物的索引"""
        for i, m in enumerate(combat.monsters):
            if m.is_alive:
                return i
        return 0


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
