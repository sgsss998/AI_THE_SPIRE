"""R3 public, occurrence-bound opening transforms and Golden Wing removals."""
from dataclasses import replace

from experiments.hand_selection_frontiers193.session import SingleTransformMixin
from experiments.sa_calibration_round2.boss import session as boss
from experiments.wing_removal_640.session import WingRemovalMixin
from silent_env.action193 import POLICY_VERSION
from silent_env.interface import InterfaceMismatch


class GridEngine(SingleTransformMixin, WingRemovalMixin, boss.BossEngine):
    """Reuse the physical-grid witnesses on the two reviewed origins."""

    def _single_show(self, base, vector, page, ids):
        frame = super()._single_show(base, vector, page, ids)
        # The global action/state release is signed by R3. The observation layout
        # and version must stay constant across the preview and other pages.
        self._current = replace(frame, state=replace(frame.state, state_version=base.state.state_version))
        return self._current

    def step(self, action_id, *, frame_id, action_version):
        with self._lock:
            active = getattr(self, '_single', None)
            if active is None and self._current is not None and self._current.page != 'NEOW_OFFERS':
                advance = super(SingleTransformMixin, self).step
            else:
                advance = super().step
            result = advance(action_id, frame_id=frame_id, action_version=action_version)
            if result.page not in ('WING_PRAYER_CONTINUE','WING_REMOVE_LEAVE','SINGLE_TRANSFORM_LEAVE'):
                return result
            if [i for i, flag in enumerate(result.supported_actions) if flag] != [110]:
                raise InterfaceMismatch('Expected one presentation acknowledgement')
            # Selecting, confirming and cancelling remain independent decisions.
            # These three intermediate acknowledgements consume no engine step.
            following = advance(110, frame_id=result.frame_id, action_version=POLICY_VERSION)
            if following.engine_steps != result.engine_steps:
                raise InterfaceMismatch('A presentation acknowledgement consumed an engine step')
            return following


def make_engine():
    return GridEngine()


def make_base_session(engine=None):
    engine = make_engine() if engine is None else engine
    if not isinstance(engine, GridEngine):
        raise TypeError('Expected GridEngine')
    return boss.make_session(engine)


def make_session(engine=None):
    from experiments.sa_calibration_round2.events.quotes import QuoteSession
    engine = make_engine() if engine is None else engine
    return QuoteSession(engine, make_base_session(engine))
