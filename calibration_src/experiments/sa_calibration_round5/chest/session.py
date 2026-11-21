"""Model-facing choice of an Ink Bottle linked to a sapphire key in an opened chest."""
from dataclasses import replace

from experiments.common_relic193.rules import relic_id
from experiments.reward_ui_adapter.adapter import Unsupported
from experiments.sa_calibration_round2.boss import session as parent
from experiments.treasure_reward_640.session import KEY, RELIC, bound_rows, require

INK_BOTTLE = relic_id("INK_BOTTLE")


class InkBottleChest(parent.Chest):
    def _publish(self):
        super()._publish()
        if (KEY, 2) not in self.rows or (RELIC, INK_BOTTLE) not in self.rows:
            return
        index = self.rows.index((RELIC, INK_BOTTLE))
        choice = 110 + index
        public = self.view.policy
        if choice not in public.unknown_actions:
            return
        self._actions[choice] = ("ink_bottle", 81 + index)
        self.view = replace(self.view, policy=replace(public,
            mask189=tuple(flag or i == choice for i, flag in enumerate(public.mask189)),
            unknown_actions=tuple(i for i in public.unknown_actions if i != choice)))

    def step(self, action, *, token):
        if action not in self._actions or self._actions[action][0] != "ink_bottle":
            return super().step(action, token=token)
        require(self.active and token == self.frame().token and self.provider.peek() == self.packet,
                "Chest decision expired before taking the relic")
        physical = self._actions[action][1]
        before = self.packet
        require(bound_rows(self.provider, before) == self.rows and before.mask146[physical]
                and self.rows[physical - 81] == (RELIC, INK_BOTTLE) and (KEY, 2) in self.rows,
                "Ink Bottle and its sapphire key must share the current reward list")
        old = before.base
        offset = 32 + 2 * int(old[23])
        require(offset+1 < 112 and INK_BOTTLE not in old[32:offset:2] and not old[14],
                "Duplicate, overflowing or already claimed linked reward")
        self.active = False
        after = self.provider.step(physical)
        expected = list(old[:112])
        expected[23] += 1
        # A stored counter of one encodes a native counter of zero.
        expected[offset:offset+2] = [INK_BOTTLE, 1]
        remaining = bound_rows(self.provider, after)
        require(after.step_count == before.step_count+1 and tuple(expected) == after.base[:112]
                and old[706:898] == after.base[706:898]
                and tuple(row for row in self.rows if row[0] not in (RELIC, KEY)) == remaining,
                "Ink Bottle claim changed unrelated assets or retained a linked reward")
        self.packet, self.rows, self.active = after, remaining, True
        self._publish()
        return self.frame()


class InkBottleSetup(parent.ChestSetup):
    def _capture(self, source):
        if self._ordinary_run and self._reward is None and parent.opened(self._prior, source):
            try:
                packet = self._provider.peek()
                if (RELIC, INK_BOTTLE) in bound_rows(self._provider, packet):
                    self._reward = InkBottleChest(self._provider)
            except Unsupported:
                pass
        return super()._capture(source)
