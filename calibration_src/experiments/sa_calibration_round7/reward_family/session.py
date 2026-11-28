"""Ordinary Act I and recorded Act II rewards with carried relics that do not alter these claims."""
from dataclasses import replace

from experiments.combat_loot193 import session as loot
from experiments.common_relic193.rules import relic_id
from experiments.reward_discard193.session import DiscardReward
from experiments.reward_mask_parity193.session import SCREENS, project
from experiments.reward_ui_adapter.adapter import RewardSession, Unsupported, require
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies

# Per-class retail callbacks and external uses are checked in evidence.py.
CLASSES = {
    "ANCHOR": "Anchor", "BLUE_CANDLE": "BlueCandle", "CULTIST_HEADPIECE": "CultistMask",
    "CURSED_KEY": "CursedKey", "DREAM_CATCHER": "DreamCatcher", "HOVERING_KITE": "HoveringKite",
    "NLOTHS_HUNGRY_FACE": "NlothsMask", "ODDLY_SMOOTH_STONE": "OddlySmoothStone",
    "TINY_HOUSE": "TinyHouse", "MERCURY_HOURGLASS": "MercuryHourglass", "KUNAI": "Kunai",
    "MEAL_TICKET": "MealTicket", "RUNIC_PYRAMID": "RunicPyramid",
    "ORICHALCUM": "Orichalcum", "PRESERVED_INSECT": "PreservedInsect",
    "RING_OF_THE_SNAKE": "SnakeRing", "WARPED_TONGS": "WarpedTongs", "WRIST_BLADE": "WristBlade",
}
DEEP = frozenset(map(relic_id, ("TINY_HOUSE", "MERCURY_HOURGLASS", "KUNAI", "MEAL_TICKET", "RUNIC_PYRAMID")))
STATIC = frozenset(map(relic_id, CLASSES)) - DEEP


def inventory(v, *, combat=False):
    count = v[23]
    if not ((v[4] == 1 and count in (1, 2, 3)) or (v[4] == 2 and count == len(DEEP))):
        return None
    end = 32 + 2 * int(count)
    relics = tuple(v[32:end])
    ids = relics[::2]
    scope = set(ids) <= STATIC if v[4] == 1 else set(ids) == DEEP
    counters = all(counter == 0 or (combat and v[4] == 2 and key == relic_id("KUNAI") and counter in (1,2,3))
                   for key, counter in zip(ids, relics[1::2]))
    if any(v[end:112]) or len(set(ids)) != count or not scope or not counters:
        return None
    return relics


def ordinary(before, after):
    if before is None or before.done or after.done or before.engine_steps + 1 != after.engine_steps:
        return False
    a, b = before.state.vector, after.state.vector
    previous, current = inventory(a, combat=True), inventory(b)
    if (a[4] not in (1,2) or a[5:10] != (20, 9, 1, 5, 0) or b[5:10] != (20, 2, 0, 5, 0)
            or not (a[3] > 0 and 0 < b[0] <= a[0] <= a[1]) or a[1:6] != b[1:6]
            or a[10:17] != b[10:17] or a[16] != 2 or a[22:26] != b[22:26]
            or a[706:898] != b[706:898] or not previous or not current or previous[::2] != current[::2]):
        return False
    # Preserve every settled inventory already served by the prior ordinary adapter.
    if loot.inventory(a) and a[0] == b[0] and a[17:22] == b[17:22]:
        return False
    if previous == (loot.RING, 0):
        return False
    # A final damaging potion consumes its slot before the reward is shown.
    changed = [(x, y) for x, y in zip(a[17:22], b[17:22]) if x != y]
    return not changed or (len(changed) == 1 and changed[0][0] > 0 and changed[0][1] == 0)


class Controls(loot.Controls):
    __init__ = _local_dependencies(loot.Controls.__init__, inventory=inventory)
    def _raw(self, packet):
        v = packet.base
        layout = inventory(v)
        require(layout and layout == self.baseline and v[3] > 0 and v[5:10] == (20,2,0,5,0) and not packet.event,
                "Expected a stable ordinary reward inventory")
        labels = tuple("Ring of the Snake" if key == loot.RING else f"other:{int(key)-1}" for key in layout[::2])
        require(labels == packet.relic_ids, "Relic IDs disagree with the current packet")
        raw = self.provider.backend._current
        choices = raw.choice_metadata["choices"]
        require(raw.raw_base == v and raw.engine_steps == packet.step_count and len(raw.packet_sha256) == 64
                and raw.packet_sha256 == raw.choice_metadata["packet_sha256"]
                and len(choices) == sum(any(v[i:i+6]) for i in range(322,706,6)), "Stale reward backing")
        backend = self.provider.backend._backend
        for i, choice in enumerate(choices):
            r = v[322+6*i:328+6*i]
            source = choice["source_ref"]
            require(source["container"] == "displayed_reward_actions" and source["public_slot"] == choice["slot"] == i
                    and source["base_offset"] == 322+6*i and choice["sim_action"] == 81+i and choice["described"]
                    and choice["kind_name"] == {1:"CARD",3:"POTION",4:"GOLD",6:"SKIP"}.get(r[0])
                    and choice["parameters"] == r[1:5] and bool(r[5]) == choice["legal"] == bool(packet.mask146[81+i]),
                    "Reward row lost its physical choice")
            if r[0] == 1:
                card = choice.get("card_identity") or {}
                idx = int(r[1])-1
                require(0 <= idx < len(backend.CARD_IDS) and card.get("enum_id") == idx
                        and card.get("observation_id") == idx+1 and card.get("native_id") == backend.CARD_IDS[idx]
                        and not backend.CARD_FACTS[0,idx,6] and not backend.CARD_FACTS[0,idx,7],
                        "Unverified reward card identity")
        self.last = packet
        certified = list(v)
        certified[23] = 0
        certified[32:112] = [0]*80
        return replace(packet, base=tuple(certified), relic_ids=())


class RewardPage(loot.Page):
    def __init__(self, provider):
        self.checked = Controls(provider)
        RewardSession.__init__(self, self.checked)


class RewardDiscard(DiscardReward):
    _bindings = _local_dependencies(DiscardReward._bindings, allowed_inventory=inventory)


class StandardRewardMixin:
    def _capture(self, source):
        if self._ordinary_run and self._reward is None and ordinary(self._prior, source):
            try:
                self._reward = RewardDiscard(RewardPage(self._provider), self._delegate)
            except Unsupported:
                pass
        return super()._capture(source)


prove_mask = _local_dependencies(project, allowed_inventory=inventory)


def public_mask(engine, frame):
    # The frozen A193 oracle reads only its 3118-field prefix. The caller receives S3122.
    if frame.page not in ("COMBAT_REWARD", "CARD_REWARD") or not isinstance(engine._inner.delegate._reward, RewardDiscard):
        return frame
    values = frame.state.vector[:3118]
    if values[4] == 2:
        if not inventory(values):
            return frame
        # The published inventory and act stay intact. Reuse the Act I legality rules
        # for this audited Act II layout after its physical rows have been verified.
        values = list(values)
        values[4] = 1
        values[23] = 1
        values[32:112] = [loot.RING,0] + [0]*78
        values = tuple(values)
    observed = replace(frame, state=replace(frame.state, vector=values))
    proof = prove_mask(observed)
    if proof is None or not proof.complete_execution:
        return frame
    return replace(frame, policy_mask=proof.game_mask, action_gaps=tuple(g for g in frame.action_gaps if g not in SCREENS))
