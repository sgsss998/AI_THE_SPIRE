"""Independent, versioned fungus candidate. The frozen 704-game R7 baseline stays reproducible."""
from dataclasses import replace
from .. import release as base
from .session import attach

make_engine = base.make_engine
TAG = "+fungi-candidate-v1"


class VersionedSession(base.VersionedSession):
    def _publish(self, frame):
        assert frame.state.state_version.endswith(base.TAG)
        return replace(frame, state=replace(frame.state, state_version=frame.state.state_version + TAG))


def make_session(engine=None):
    return VersionedSession(attach(base.make_session(engine)))
