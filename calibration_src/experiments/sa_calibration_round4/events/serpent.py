"""The Sssserpent's deferred agree/continue transaction, using the existing game."""
from dataclasses import dataclass, replace
from numbers import Integral
from uuid import uuid4

from experiments.action193_grid.session import permitted
from experiments.sa_calibration_round2.events.quotes import SNAKE
from silent_env.interface import InterfaceMismatch
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError


@dataclass(frozen=True)
class Offer:
    gold: int
    curse: str


def decode_offer(vector):
    """Decode the printed first option, before any acquisition or relic callback."""
    if (len(vector) >= 2974 and vector[6] == 1 and vector[9] == SNAKE and vector[1769] == 2
            and tuple(vector[2968:2971]) == (2, 0, 4) and vector[2973] > 0):
        return Offer(int(vector[2973]), 'Doubt')
    return None


CONTINUE = 'SERPENT_ACCEPTED_CONTINUE'
LEAVE = 'SERPENT_LEAVE'
ONLY_BUTTON = permitted((110,))


def event_frame(base, offer, page):
    # Keep resource, deck, relic and counter values from the actual transaction
    # stage. The underlying map reached after commit has a different room view.
    v = list(base.state.vector)
    v[6:12] = offer.state.vector[6:12]
    v[322:706] = [8, 0, 0, 0, 0, 1] + [0] * 378
    v[1769] = 1
    v[2683:2748] = [2] + [0] * 64
    v[2968:3114] = [2, 1 if page == CONTINUE else 2] + [0] * 144
    # The original receipts cover empty potion slots. A held potion may
    # introduce a separate command; do not label that mask independently complete.
    complete = not any(v[17:17 + int(v[16])])
    return replace(base, frame_id=str(uuid4()), state=replace(base.state, vector=tuple(v)),
                   page=page, supported_actions=ONLY_BUTTON, policy_mask=ONLY_BUTTON if complete else None,
                   action_gaps=() if complete else ('serpent_optional_potions_unverified',))


class SerpentSession:
    def __init__(self, engine, delegate):
        self.engine = engine
        self.delegate = delegate
        self._lock = delegate._lock
        self._visible = self._underlying = self._offer = None

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def _show(self, frame):
        self._visible = self._underlying = frame
        self._offer = None
        return frame

    def reset(self, *args, **kwargs):
        with self._lock:
            return self._show(self.delegate.reset(*args, **kwargs))

    def reset_fixture(self, request):
        with self._lock:
            return self._show(self.delegate.reset_fixture(request))

    def _event_page(self, page):
        self._visible = event_frame(self._underlying, self._offer, page)
        return self._visible

    def _submit(self, action):
        original = self._underlying
        # Invalidate first. A failure after a backend step cannot submit a
        # second reward if a caller retries its old token.
        self._visible = None
        self._underlying = self.delegate.step(action, frame_id=original.frame_id,
                                              action_version=original.action_version)
        return self._underlying

    def step(self, action, *, frame_id, action_version):
        with self._lock:
            current = self._visible
            if current is None or type(frame_id) is not str or frame_id != current.frame_id:
                raise StaleFrameError('Use the current unused event frame')
            if action_version != current.action_version:
                raise InterfaceMismatch('Event action version mismatch')
            if isinstance(action, bool) or not isinstance(action, Integral):
                raise UnverifiedSemanticsError('An event action requires an integer')
            if not 0 <= action < len(current.supported_actions) or not current.supported_actions[action]:
                raise UnverifiedSemanticsError('No supported binding for this action')
            if current.page == CONTINUE:
                self._submit(110)
                return self._event_page(LEAVE)
            if current.page == LEAVE:
                return self._show(self._underlying)
            if action in (110, 111) and current.supported_actions[action] and decode_offer(current.state.vector):
                self._offer = current
                if action == 110:
                    return self._event_page(CONTINUE)
                self._submit(111)
                return self._event_page(LEAVE)
            return self._show(self._submit(action))


def wrap(engine, session):
    return SerpentSession(engine, session)
