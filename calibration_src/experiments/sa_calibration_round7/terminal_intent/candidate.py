from dataclasses import replace
from ..shop import candidate as parent
from .session import TerminalIntent

make_engine = parent.make_engine
TAG = "+terminal-announced-attack-v1"


class VersionedSession(parent.VersionedSession):
    def _publish(self,frame):
        assert frame.state.state_version.endswith(parent.TAG)
        return replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))


def make_session(engine=None):
    return VersionedSession(TerminalIntent(parent.make_session(engine)))
