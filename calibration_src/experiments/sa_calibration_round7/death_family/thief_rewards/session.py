"""Act II Two Thieves: one defeated thief and one escaped thief leave distinct purses."""
from dataclasses import replace

from experiments.reward_discard193.session import DiscardReward
from experiments.reward_mask_parity193.session import SCREENS, project
from experiments.reward_sources193.session import double_page
from experiments.reward_ui_adapter.adapter import (
    GOLD,
    RewardSession,
    require,
    Unsupported,
)
from experiments.stolen_gold193.session import GoldPage, NongoldProvider, rows
from experiments.sa_calibration_round7.reward_family import session as family
from ..session import MONSTERS, r3


class Layout(family.Controls):
    def __init__(self, provider):
        self.provider = provider
        self.baseline = family.inventory(provider.peek().base)
        self.last = None


class Purses(NongoldProvider):
    def __init__(self, raw):
        self.raw = raw
        self.layout = Layout(raw)
        pkt = self.layout._raw(raw.peek())
        require(
            not any(pkt.base[17:22])
            and [row[0] for row in rows(pkt.base)] == [4, 4, 1, 1, 1, 6],
            "Reviewed purse layout with two empty potion slots required",
        )
        # The independent Act I validator checks the two amounts and all physical rows.
        check = replace(pkt, base=pkt.base[:4] + (1,) + pkt.base[5:])
        stolen, other, _ = double_page(check)
        self.gold = [(stolen[1], 1), (other[GOLD][0][1][1], 0)]
        self.peek()

    def without_gold(self, packet):
        if packet.base[6] == 5:
            require(
                packet.base[4] == 2
                and family.inventory(packet.base) == self.layout.baseline,
                "Exited to an inconsistent map",
            )
            return packet
        checked = self.layout._raw(packet)
        return super().without_gold(checked)


class ThiefPage(GoldPage):
    def __init__(self, provider, core):
        self.provider = Purses(provider)
        self.core = core
        self.ordinary = RewardSession(self.provider)
        self.controls = DiscardReward(self.ordinary, core)

    def frame(self):
        frame = super().frame()
        v = list(frame.policy.base1761)
        actual = self.provider.layout.last.base
        v[23] = actual[23]
        v[32:112] = actual[32:112]
        return replace(frame, policy=replace(frame.policy, base1761=tuple(v)))


def one_escaped(witness, step):
    if (
        witness["steps"] != step
        or witness["in_battle"]
        or witness["undecided"]
        or witness["alive"]
        or witness["queue"]
        or witness["card_queue"]
        or witness["physical_order"] != [0, 1]
    ):
        return False
    actors = witness["rows"]
    if [a["id"] for a in actors] != ["LOOTER", "MUGGER"] or any(
        a["hp"] < 0 or a["half_dead"] or a["targetable"] for a in actors
    ):
        return False
    return sorted((a["hp"] > 0, a["escaping"]) for a in actors) == [
        (False, False),
        (True, True),
    ]


class ThiefRewardMixin:
    def _capture(self, source):
        prior = self._prior
        if (
            self._ordinary_run
            and self._reward is None
            and family.ordinary(prior, source)
        ):
            v = prior.state.vector
            if (
                v[4] == 2
                and not any(source.state.vector[17:22])
                and [int(v[i]) for i in (993, 1045)]
                == [MONSTERS["LOOTER"] + 1, MONSTERS["MUGGER"] + 1]
                and not any(v[1097:1253])
            ):
                witness = r3.ordinary.observer().inspect(self._provider.backend._env)
                if one_escaped(witness, source.engine_steps):
                    try:
                        self._reward = ThiefPage(self._provider, self._delegate)
                    except Unsupported:
                        pass
        return super()._capture(source)


def public_mask(engine, frame):
    if frame.page not in ("COMBAT_REWARD", "CARD_REWARD") or not isinstance(
        engine._inner.delegate._reward, ThiefPage
    ):
        return frame
    v = list(frame.state.vector[:3118])
    if v[4] != 2 or not family.inventory(v) or any(v[17:22]):
        return frame
    v[4] = 1
    v[23] = 1
    v[32:112] = [family.loot.RING, 0] + [0] * 78
    if v[322] == 4 and v[324] == 1 and v[328] != 4:
        v[324] = 0
    proof = project(replace(frame, state=replace(frame.state, vector=tuple(v))))
    if proof is None or not proof.complete_execution:
        return frame
    return replace(
        frame,
        policy_mask=proof.game_mask,
        action_gaps=tuple(g for g in frame.action_gaps if g not in SCREENS),
    )
