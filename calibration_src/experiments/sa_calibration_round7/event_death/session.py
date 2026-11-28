"""Resolve a witnessed lethal event choice before publishing any event continuation."""
from dataclasses import replace
from threading import RLock

from silent_env.observation import schema
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError

E = schema()["enums"]
EVENT_ROOM = E["Room"]["EVENT"] + 1
EVENT_SCREEN = E["ScreenState"]["EVENT_SCREEN"]
NO_SCREEN = E["ScreenState"]["INVALID"]
LOSS = E["GameOutcome"]["PLAYER_LOSS"]
TAG = "+event-defeat-v1"


def defeat(before, aid, after, engine):
    """A real consumed event input, permanent kernel loss, and absent backend controls."""
    if (
        not after.done
        or before is None
        or before.done
        or not 0 <= aid < len(before.supported_actions)
    ):
        return after
    a, b = before.state.vector, after.state.vector
    if (
        not before.supported_actions[aid]
        or not (110 <= aid < 170 or 189 <= aid <= 192)
        or a[0] <= 0
        or a[6:9] != (EVENT_SCREEN, 0, EVENT_ROOM)
        or not a[9]
        or b[0] != 0
        or b[3:6] != a[3:6]
        or b[7:9] != (0, EVENT_ROOM)
        or b[31] != LOSS
    ):
        return after
    src = engine._source
    core = src._env
    raw = src._current
    if (
        not core.done
        or core.won
        or not core.lost
        or raw is None
        or not raw.done
        or raw.engine_steps != core.steps
        or core.steps != after.engine_steps
        or before.engine_steps + 1 != core.steps
        or raw.raw_base[0] != 0
        or raw.raw_base[3:6] != b[3:6]
        or raw.raw_base[31] != LOSS
        or any(raw.backend_mask)
        or any(core.mask())
    ):
        return after
    state = list(b)
    # There is no gameplay screen or pending card choice at the defeat screen.
    state[6] = NO_SCREEN
    state[9] = 0
    state[26:29] = [0] * 3
    state[322:706] = [0] * 384
    state[1769] = 0
    state[2683:2748] = [1] + [0] * 64
    state[2968:3114] = [1] + [0] * 145
    empty = (False,) * len(after.supported_actions)
    return replace(
        after,
        page="GAME_OVER",
        state=replace(after.state, vector=tuple(state)),
        supported_actions=empty,
        policy_mask=empty,
        action_gaps=(),
    )


class Session:
    def __init__(self, delegate, engine):
        self.delegate = delegate
        self.engine = engine
        self._lock = RLock()
        self._latest = None
        self._defeated = False

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def _publish(self, frame):
        self._latest = replace(
            frame,
            state=replace(frame.state, state_version=frame.state.state_version + TAG),
        )
        return self._latest

    def reset(self, *args, **kw):
        with self._lock:
            self._defeated = False
            return self._publish(self.delegate.reset(*args, **kw))

    def reset_fixture(self, *args, **kw):
        with self._lock:
            self._defeated = False
            return self._publish(self.delegate.reset_fixture(*args, **kw))

    def step(self, action, *, frame_id, action_version):
        with self._lock:
            if self._defeated:
                if self._latest.frame_id != frame_id:
                    raise StaleFrameError("The decision has changed")
                raise UnverifiedSemanticsError("The run ended at this event")
            before = self._latest
            frame = self.delegate.step(
                action, frame_id=frame_id, action_version=action_version
            )
            resolved = defeat(before, action, frame, self.engine)
            self._defeated = resolved is not frame
            return self._publish(resolved)

    def real_action_mask(self, *, frame_id):
        with self._lock:
            if self._defeated:
                if self._latest.frame_id != frame_id:
                    raise StaleFrameError("The decision has changed")
                return self._latest.policy_mask
            return self.delegate.real_action_mask(frame_id=frame_id)
