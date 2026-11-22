"""Present ordinary A20 combat loot for two verified Snake Ring inventories."""
from experiments.combat_loot193 import session as loot
from experiments.common_relic193.rules import relic_id
from experiments.reward_discard193.session import DiscardReward
from experiments.reward_ui_adapter.adapter import RewardSession, Unsupported
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.sa_calibration_round5.chest.session import InkBottleSetup


INK = relic_id("INK_BOTTLE")
PUZZLE = relic_id("CENTENNIAL_PUZZLE")


def inventory(vector):
    """OBS4 reserves zero for a missing counter; the game's 0..9 is stored as 1..10."""
    if vector[23] != 2 or tuple(vector[32:34]) != (loot.RING, 0) or any(vector[36:112]):
        return None
    relic, counter = vector[34:36]
    if (relic == INK and counter == int(counter) and 1 <= counter <= 10) or (relic == PUZZLE and counter == 0):
        return tuple(vector[32:36])
    return None


# The frozen ordinary-victory predicate validates the same 0..9 cycling counter
# on the last play. Bind that slot to Ink Bottle only for our two-relic domain.
victory = _local_dependencies(loot.ordinary, inventory=inventory, NIB=INK)


class Controls(loot.Controls):
    __init__ = _local_dependencies(loot.Controls.__init__, inventory=inventory)
    _raw = _local_dependencies(loot.Controls._raw, inventory=inventory)


class RewardPage(loot.Page):
    def __init__(self, provider):
        self.checked = Controls(provider)
        RewardSession.__init__(self, self.checked)


class RewardDiscard(DiscardReward):
    _bindings = _local_dependencies(DiscardReward._bindings, allowed_inventory=inventory)


class InkRewardSetup(InkBottleSetup):
    def _capture(self, source):
        if self._ordinary_run and self._reward is None and victory(self._prior, source):
            try:
                self._reward = RewardDiscard(RewardPage(self._provider), self._delegate)
            except Unsupported:
                # Leave the same packet available for the parent's other reward handlers.
                pass
        return super()._capture(source)
