"""Allow discarding an occupied potion during an ordinary reward with the Ancient Tea Set."""
from dataclasses import replace

from experiments.common_relic193.rules import relic_id
from experiments.reward_discard193.session import DiscardReward
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.reward_mask_parity193.session import project, SCREENS

RING = relic_id("RING_OF_THE_SNAKE")
TEA = relic_id("ANCIENT_TEA_SET")


def inventory(v):
    return v[23] == 2 and v[32:36:2] == (RING,TEA) and not any(v[36:112])


class PotionDiscard(DiscardReward):
    _bindings = _local_dependencies(DiscardReward._bindings, allowed_inventory=inventory)


class TeaRewardPotions:
    def _capture(self, source):
        frame = super()._capture(source)
        control = self._reward
        if (type(control) is DiscardReward and frame.page in ("COMBAT_REWARD","CARD_REWARD")
                and inventory(frame.state.vector)):
            self._reward = PotionDiscard(control.reward,control.core)
            buttons = self._reward.frame().policy.mask189
            self._current = replace(frame,supported_actions=tuple(map(bool,buttons)))
        return self._current


tea_proof = _local_dependencies(project, allowed_inventory=inventory)


def mask(engine, frame):
    if frame.page not in ("COMBAT_REWARD","CARD_REWARD") or not isinstance(engine._inner.delegate._reward,PotionDiscard):
        return frame
    prefix = replace(frame,state=replace(frame.state,vector=frame.state.vector[:3118]))
    proof = tea_proof(prefix)
    if proof is not None and proof.complete_execution and proof.game_mask == frame.supported_actions:
        return replace(frame,policy_mask=proof.game_mask,action_gaps=tuple(g for g in frame.action_gaps if g not in SCREENS))
    return frame
