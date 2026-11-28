"""Restore the owned combat interface at a physically verified fungal death boundary."""
from dataclasses import replace
from experiments.poison_death193.session import POISON
from experiments.sa_calibration_round4.death import session as previous

r3 = previous.r3
POWER_FIELDS = {"POISON": POISON, "WEAK": 23, "STRENGTH": previous.STRENGTH, "SPORE_CLOUD": r3.SPORES}


def occupied_rows(vector):
    return [row for row in r3.ordinary.rows(vector) if row[0]]


def checked_corpses(witness, frame):
    v = frame.state.vector
    rows = occupied_rows(v)
    actors = witness["rows"]
    if (not witness["in_battle"] or not witness["undecided"] or witness["over"]
            or any(witness[key] for key in ("card_queue","end_queued","turn_ended","has_horn","has_specimen"))
            or witness["steps"] != frame.engine_steps or not 2 <= len(rows) <= 5
            or len(actors) != len(rows) or witness["physical_order"] != list(range(len(rows)))):
        return ()
    dead = []
    for i, (actor, row) in enumerate(zip(actors, rows)):
        if (actor["id"] != "FUNGI_BEAST" or row[0] != r3.FUNGI
                or (actor["hp"],actor["max"],actor["block"]) != row[1:4]
                or actor["half_dead"] or actor["escaping"] or actor["will_escape"]
                or actor["targetable"] != bool(row[1]) or bool(row[6]) != actor["targetable"]):
            return ()
        if row[1] > 0:
            continue
        powers = actor["powers"]
        if (row[4:10] != (1,0,0,0,0,0) or row[3] or set(powers) - POWER_FIELDS.keys()
                or powers.get("SPORE_CLOUD") != 2
                or any(powers.get(name,0) != row[offset] for name,offset in POWER_FIELDS.items())
                or any(row[j] for j in range(10,52) if j not in POWER_FIELDS.values())):
            return ()
        dead.append(i)
    if witness["alive"] != len(rows)-len(dead) or not witness["alive"]:
        return ()
    return tuple(dead)


class FungalDecisions(previous.DeathPages):
    def _publish(self, frame):
        before = self._source
        result = super()._publish(frame)
        v = frame.state.vector
        if (frame.done and self._backing._source._env.lost and before is not None
                and before.state.vector[3:6] == v[3:6]):
            old, final = occupied_rows(before.state.vector), occupied_rows(v)
            if len(old) == len(final) and all(a[0] == b[0] == r3.FUNGI and a[2] == b[2]
                                                  for a,b in zip(old, final)):
                settled = list(result.state.vector)
                for i,(a,b) in enumerate(zip(old, final)):
                    if a[1] == b[1] == 0:
                        for offset in POWER_FIELDS.values():
                            settled[993+52*i+offset] = 0
                self._current = replace(result,state=replace(result.state,vector=tuple(settled)))
                return self._current
        if (frame.done or not v[7] or frame.page != "DELEGATED" or frame.action_gaps
                or before is None or before.state.vector[3:6] != v[3:6]
                or not any(r[0] == r3.FUNGI and r[1] == 0 for r in occupied_rows(v))):
            return result
        raw = self._backing._raw
        if (raw is None or raw is not self._backing._source._current or self._source is not frame
                or raw.engine_steps != frame.engine_steps or frame.policy_mask is None
                or raw.raw_base[993:1253] != v[993:1253]):
            return result
        witness = r3.ordinary.observer().inspect(self._backing._source._env)
        corpses = checked_corpses(witness, frame)
        hand = (witness["input"] == 2 and raw.hand_order.active and raw.bindings
                and all(b.operation in ("select_hand_card", "confirm_hand_selection", "unselect_hand_card")
                        for b in raw.bindings))
        if not corpses or not (hand or witness["input"] == 1 and witness["queue"] == 0):
            return result
        offered = {i for i, bit in enumerate(frame.supported_actions) if bit}
        bindings = {b.policy_id: b.simulator_id for b in raw.bindings}
        invalid = {a for i in corpses for a in (*range(10+10*i,20+10*i),*range(75+5*i,80+5*i))}
        if (not offered or offered & invalid or len(bindings) != len(raw.bindings)
                or set(bindings) != offered or not all(self._backing._source._env.is_valid(eid) for eid in bindings.values())):
            return result
        out = list(result.state.vector)
        old = occupied_rows(before.state.vector)
        if len(old) == len(witness["rows"]) and all(
                (m["max"],r3.FUNGI) == (row[2],row[0]) for m,row in zip(witness["rows"],old)):
            for i in corpses:
                # Fresh casualties keep the immediate display; after another input publish
                # the settled corpse. Retail can also settle during an idle animation tick.
                if old[i][1] == 0:
                    for offset in POWER_FIELDS.values():
                        out[993+52*i+offset] = 0
        self.phase = r3.phase.CLEAR
        partial = bool(hand and raw.hand_order.selected)
        self._current = replace(result, state=replace(result.state, vector=tuple(out)),
                                policy_mask=None if partial else frame.policy_mask, supported_actions=frame.supported_actions,
                                action_gaps=("additional_hand_replacement_unverified",) if partial else ())
        return self._current


def attach(session):
    node = session
    seen = set()
    while not isinstance(node, r3.TransitionSession):
        if id(node) in seen:
            raise r3.InterfaceMismatch("Cycle in the combat decision chain")
        seen.add(id(node))
        node = vars(node).get("delegate",vars(node).get("base"))
        if node is None:
            raise r3.InterfaceMismatch("Missing combat decision owner")
    if type(node.pages) is not previous.DeathPages or node._frame is not None:
        raise r3.InterfaceMismatch("Expected a fresh R4 death observer")
    node.pages = FungalDecisions(delegate=node.pages._parent, backing=node.backing)
    return session
