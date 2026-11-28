from dataclasses import replace
from ..shop import candidate as parent
from .session import AdditionalMerchandise, BottleObservation, install

TAG="+shop-stock-v1"


def make_engine(**kwargs):
    return install(parent.make_engine(**kwargs))


class VersionedSession(parent.VersionedSession):
    def _publish(self,frame):
        assert frame.state.state_version.endswith(parent.TAG)
        return replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))


def make_session(engine=None):
    from ..shop.session import CardShelf
    if engine is None:
        engine=make_engine()
    elif not isinstance(engine._inner,AdditionalMerchandise):
        if not isinstance(engine._inner,CardShelf):
            parent.install(engine)
        install(engine)
    return VersionedSession(BottleObservation(parent.make_session(engine),engine))
