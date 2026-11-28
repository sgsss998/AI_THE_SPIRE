"""Add the ordinary-casualty checks to the second R7 candidate."""
from dataclasses import replace
from .. import combined
from .session import attach

TAG = "+ordinary-casualty-r7-v1"
make_engine = combined.make_engine


class Session(combined.Session):
    def _publish(self, frame):
        base = super()._publish(frame)
        self.frame = replace(
            base,
            state=replace(base.state, state_version=base.state.state_version + TAG),
        )
        return self.frame


def make_session(engine=None):
    engine = make_engine() if engine is None else engine
    return attach(Session(engine))
