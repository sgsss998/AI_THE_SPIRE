"""Republish existing legal bindings once ordinary casualties and live targets agree."""
from dataclasses import replace

from experiments.sa_calibration_round7.fungi.session import FungalDecisions, r3
from silent_env.actions import IllegalGameAction
from silent_env.canonical_runtime import CanonicalAuditSession, _fixed_action_to_sim
from silent_env.observation import schema
from silent_env.runtime import UnverifiedSemanticsError

VICTIMS = frozenset(
    "ACID_SLIME_S ACID_SLIME_M SPIKE_SLIME_S SPIKE_SLIME_M GREEN_LOUSE RED_LOUSE "
    "RED_SLAVER BLUE_SLAVER SENTRY FAT_GREMLIN MAD_GREMLIN SNEAKY_GREMLIN SHIELD_GREMLIN "
    "GREMLIN_WIZARD JAW_WORM CULTIST REPULSOR SPIKER LOOTER MUGGER".split()
)
# Living fungi may accompany an ordinary casualty. A dead fungus follows its own spore rule.
COMPANIONS = VICTIMS | {"FUNGI_BEAST"}
THIEVES = {"LOOTER", "MUGGER"}
MONSTERS = schema()["enums"]["MonsterId"]
STATUS = {
    field["name"].removeprefix("status_").upper(): i
    for block in schema()["base_blocks"]
    if block["name"] == "monsters"
    for i, field in enumerate(block["fields"])
    if i >= 10
}
RESIDUAL = {
    "ARTIFACT",
    "BLOCK_RETURN",
    "CHOKED",
    "CURL_UP",
    "POISON",
    "RITUAL",
    "SHACKLED",
    "STRENGTH",
    "THIEVERY",
    "THORNS",
    "VULNERABLE",
    "WEAK",
}


def casualties(frame, witness):
    """Separate physically dead, escaped, and live actors using the combat kernel."""
    v = frame.state.vector
    actors = witness["rows"]
    n = len(actors)
    if (
        not witness["in_battle"]
        or not witness["undecided"]
        or witness["over"]
        or any(
            witness[k]
            for k in (
                "card_queue",
                "end_queued",
                "turn_ended",
                "has_horn",
                "has_specimen",
            )
        )
        or witness["steps"] != frame.engine_steps
        or not 2 <= n <= 5
        or witness["physical_order"] != list(range(n))
        or not 0 < witness["alive"] < n
    ):
        return None
    rows = r3.ordinary.rows(v)
    if any(any(row) for row in rows[n:]):
        return None
    dead = []
    escaped = []
    for i, (a, z) in enumerate(zip(actors, rows)):
        if (
            a["id"] not in COMPANIONS
            or a["half_dead"]
            or a["will_escape"]
            or (MONSTERS[a["id"]] + 1, a["hp"], a["max"], a["block"]) != z[:4]
            or a["hp"] < 0
            or bool(z[6]) != a["targetable"]
            or z[5]
        ):
            return None
        if a["targetable"]:
            if a["escaping"] or a["hp"] <= 0 or z[4]:
                return None
            continue
        if a["id"] not in VICTIMS or z[4:10] != (1, 0, 0, 0, 0, 0):
            return None
        if a["escaping"]:
            if a["id"] not in THIEVES or a["hp"] <= 0:
                return None
            escaped.append(i)
            continue
        if (
            a["hp"]
            or a["block"]
            or set(a["powers"]) - RESIDUAL
            or any(
                a["powers"].get(name, 0) != z[offset] for name, offset in STATUS.items()
            )
        ):
            return None
        dead.append(i)
    return (dead, escaped) if n - len(dead) - len(escaped) == witness["alive"] else None


def checked_bindings(frame, raw, kernel, casualties, hand):
    """Every restored fixed action must name its actual hand/potion and physical row."""
    offered = {a for a, enabled in enumerate(frame.supported_actions) if enabled}
    mapped = {b.policy_id: b for b in raw.bindings}
    simulator_ids = {b.simulator_id for b in mapped.values()}
    if (
        not offered
        or offered != set(mapped)
        or len(mapped) != len(raw.bindings)
        or len(simulator_ids) != len(mapped)
        or simulator_ids != {i for i, bit in enumerate(raw.backend_mask) if bit}
        or any(not kernel.is_valid(i) for i in simulator_ids)
    ):
        return False
    context = None if hand else CanonicalAuditSession._canonical_context_from_frame(raw)
    for aid, b in mapped.items():
        if hand:
            if b.operation == "confirm_hand_selection":
                if (aid, b.simulator_id, b.choice_row) != (172, 145, None):
                    return False
                continue
            if b.operation == "select_hand_card":
                start, slots = 110, raw.hand_order.remaining
            elif b.operation == "unselect_hand_card":
                start, slots = 179, raw.hand_order.selected
            else:
                return False
            pos = aid - start
            if not 0 <= pos < len(slots):
                return False
            slot = slots[pos]
            if b.simulator_id != 81 + slot or b.choice_row != raw.hand_order.all.index(
                slot
            ):
                return False
            continue
        if b.operation != "fixed":
            return False
        row = (
            aid // 10 - 1
            if 10 <= aid < 60
            else (aid - 75) // 5
            if 75 <= aid < 100
            else None
        )
        if row in casualties:
            return False
        try:
            expected = _fixed_action_to_sim(aid, context)
        except (IllegalGameAction, UnverifiedSemanticsError):
            return False
        if b.simulator_id != expected:
            return False
    return True


class OrdinaryDecisions(FungalDecisions):
    def _publish(self, frame):
        before = self._source
        result = super()._publish(frame)
        v = frame.state.vector
        if (
            self.phase != r3.phase.UNKNOWN
            or frame.done
            or frame.page != "DELEGATED"
            or frame.action_gaps
            or v[4] not in (1, 2, 3, 4)
            or v[5:8] != (20, 9, 1)
            or before is None
            or before.done
            or before.state.vector[3:6] != v[3:6]
            or before.page != "DELEGATED"
        ):
            return result
        raw = self._backing._source._current
        if (
            raw is None
            or raw is not self._backing._raw
            or self._source is not frame
            or raw.engine_steps != frame.engine_steps
            or frame.policy_mask is None
            or frame.policy_mask != frame.supported_actions
            or raw.raw_base[993:1253] != v[993:1253]
        ):
            return result
        kernel = self._backing._source._env
        witness = r3.ordinary.observer().inspect(kernel)
        separated = casualties(frame, witness)
        hand = witness["input"] == 2 and raw.hand_order.active
        if separated is None or not (
            hand or witness["input"] == 1 and not witness["queue"]
        ):
            return result
        dead, escaped = separated
        if not checked_bindings(frame, raw, kernel, set(dead + escaped), hand):
            return result
        values = list(result.state.vector)
        for i in dead:
            # On the next decision the permanent corpse has finished its death
            # animation; do not clear powers on a living or escaped actor.
            old = before.state.vector
            offset = 993 + 52 * i
            if old[offset : offset + 3] == v[offset : offset + 3]:
                values[offset + 10 : offset + 52] = (0,) * 42
        self.phase = r3.phase.CLEAR
        partial = hand and bool(raw.hand_order.selected)
        self._current = replace(
            result,
            state=replace(result.state, vector=tuple(values)),
            supported_actions=frame.supported_actions,
            policy_mask=None if partial else frame.policy_mask,
            action_gaps=("additional_hand_replacement_unverified",)
            if partial
            else frame.action_gaps,
        )
        return self._current


def attach(owner):
    node = owner
    while not isinstance(node, r3.TransitionSession):
        node = vars(node).get("delegate", vars(node).get("base"))
        if node is None:
            raise r3.InterfaceMismatch("Missing death settlement owner")
    if type(node.pages) is not FungalDecisions or node._frame is not None:
        raise r3.InterfaceMismatch("Expected the unused, fungus-aware settlement owner")
    node.pages = OrdinaryDecisions(delegate=node.pages._parent, backing=node.backing)
    return owner
