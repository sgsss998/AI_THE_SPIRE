from dataclasses import replace
from ..event_results import candidate as base
from .session import DelayedBoxResult


class Setup(DelayedBoxResult,base.Setup):
    pass


class Engine(base.Engine):
    setup_class=Setup


def make_engine(**kwargs):
    engine=Engine(**kwargs)
    base.base.parent.parent.install_shop(engine)
    return base.box.bind_box(engine)


class Session(base.VersionedSession):
    def _publish(self,frame):
        frame=super()._publish(frame)
        return replace(frame,state=replace(frame.state,state_version=frame.state.state_version+'+event-box-callbacks-v1'))


def make_session(engine=None):
    return Session(base.base.make_session(make_engine() if engine is None else engine))
