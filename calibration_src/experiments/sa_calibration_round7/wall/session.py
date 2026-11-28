"""Bind Living Wall Forget to the permanent-card picker on the current game."""
from dataclasses import replace
from numbers import Integral
from uuid import uuid4

from experiments.action193_grid.session import permitted
from experiments.permanent_grid193.session import bound
from experiments.wing_removal_640.session import (
    Removal, candidates, current_deck,
)
from silent_env.action193 import POLICY_VERSION
from silent_env.interface import InterfaceMismatch
from silent_env.observation import schema
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError

WALL = schema()["enums"]["Event"]["LIVING_WALL"] + 1
EXPLOSIVE = schema()["enums"]["Potion"]["EXPLOSIVE_POTION"] + 1
DU_VU_DOLL = schema()["enums"]["RelicId"]["DU_VU_DOLL"] + 1
PAGES = {
    "WING_REMOVE_GRID": "WALL_REMOVE_GRID",
    "WING_REMOVE_PREVIEW": "WALL_REMOVE_PREVIEW",
    "WING_REMOVE_LEAVE": "WALL_REMOVE_LEAVE",
}


def forget_offer(frame, raw, action):
    if (action != 110 or frame is None or frame.done or frame.page != "DELEGATED"
            or not bound(raw) or raw.engine_steps != frame.engine_steps):
        return False
    v = frame.state.vector
    return (v[4:10] == (1, 20, 1, 0, 3, WALL)
            and v[4:10] == raw.raw_base[4:10] and v[322:328] == (8, 0, 0, 0, 0, 1)
            and DU_VU_DOLL not in v[32:112:2]
            and any((b.policy_id, b.simulator_id, b.choice_row, b.operation)
                    == (110, 81, 0, "choose_event_option") for b in raw.bindings))


class WallRemovalMixin:
    """Reuse the checked target, preview, cancel, and single-commit removal machinery."""

    def _wing_page(self, base, v, name, actions):
        removal = getattr(self, "_wing", None)
        if removal is None or removal.offer.state.vector[9] != WALL:
            return super()._wing_page(base, v, name, actions)
        raw = self._raw
        v[16:22] = raw.state.vector[16:22]
        held = tuple(int(n) for n in v[17:17+int(v[16])])
        discard = {105+i for i, item in enumerate(held) if item
                   and any(b.policy_id == 105+i and b.simulator_id == 75+i for b in raw.bindings)}
        full = (set(held) <= {0, EXPLOSIVE}
                and len(discard) == sum(bool(item) for item in held))
        mask = permitted((*actions, *discard))
        self._current = replace(base, frame_id=str(uuid4()), page=PAGES[name],
                                state=replace(base.state, vector=tuple(v)), supported_actions=mask,
                                policy_mask=mask if full else None,
                                action_gaps=() if full else ("wall_potion_controls_unverified",))
        return self._current

    def _wall_discard(self, action, frame_id, action_version):
        f, r, raw = self._current, self._wing, self._raw
        if f.frame_id != frame_id or raw is not self._source._current or raw.engine_steps != f.engine_steps:
            raise StaleFrameError("Living Wall potion decision expired")
        if action_version != POLICY_VERSION:
            raise InterfaceMismatch("Expected A193")
        if not f.supported_actions[action]:
            raise UnverifiedSemanticsError("Potion is unavailable in this slot")
        slot = action - 105
        env = self._source._env
        seen = current_deck(self)
        belt = list(f.state.vector[17:22])
        belt[slot] = 0
        eid = 75 + slot
        if not env.is_valid(eid) or not env.step(eid) or env.steps != raw.engine_steps + 1:
            raise InterfaceMismatch("Discard did not advance exactly once")
        source, post = self._refresh(raw, eid)
        v = post.state.vector
        if (v[:6] != f.state.vector[:6] or v[17:22] != tuple(belt)
                or current_deck(self) != seen or v[32:112] != f.state.vector[32:112]):
            raise InterfaceMismatch("Discard changed other resources")
        if r.map is not None:
            if post.page != r.map.page:
                raise InterfaceMismatch("Discard changed the pending map")
            r.map, r.final_raw = post, source
            out = list(f.state.vector)
            out[17:22] = belt
            return self._wing_result(post, out, 2)
        if candidates(self, post, source, seen) != r.positions:
            raise InterfaceMismatch("Discard changed the removal choices")
        r.base, r.raw = post, source
        return self._wing_list()

    def step(self, action_id, *, frame_id, action_version):
        with self._lock:
            f = self._current
            if (f and f.page in PAGES.values() and isinstance(action_id, Integral)
                    and not isinstance(action_id, bool) and 105 <= action_id < 110):
                return self._wall_discard(action_id, frame_id, action_version)
            origin = self._raw is self._source._current and forget_offer(f, self._raw, action_id)
            before = current_deck(self) if origin else None
            after = super().step(action_id, frame_id=frame_id, action_version=action_version)
            if not origin or after.page != "GRID_UNVERIFIED":
                return after
            v, w = f.state.vector, after.state.vector
            if (self._raw is not self._source._current or after.engine_steps != f.engine_steps + 1
                    or w[:6] != v[:6] or w[10:26] != v[10:26] or w[32:322] != v[32:322]
                    or w[706:898] != v[706:898] or current_deck(self) != before):
                return after
            positions = candidates(self, after, self._raw, before)
            if positions is None:
                return after
            self._wing = Removal(f, after, self._raw, before, positions)
            return self._wing_list()
