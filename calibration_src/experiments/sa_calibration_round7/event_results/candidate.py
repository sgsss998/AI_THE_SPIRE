from dataclasses import replace
from experiments.box_omamori193 import result as box_result, session as box
from .. import release as base
from .session import VerifiedEventResult


class Setup(VerifiedEventResult,box_result.BoxResultMixin,base.Round7Engine.setup_class):
    pass


class Engine(base.Round7Engine):
    setup_class=Setup


def make_engine(**kwargs):
    engine=Engine(**kwargs)
    base.parent.parent.install_shop(engine)
    return box.bind_box(engine)


TAG="+verified-event-outcomes-v1"


class VersionedSession(base.VersionedSession):
    def _publish(self,frame):
        assert frame.state.state_version.endswith(base.TAG)
        return replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))


def make_session(engine=None):
    return VersionedSession(base.make_session(make_engine() if engine is None else engine))
