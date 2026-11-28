"""Composable candidate used only by the shop replay and its regression tests."""
from dataclasses import replace
from ..fungi import candidate as parent
from .session import CardShelf, install

TAG = "+ordinary-card-shop-v1"


def make_engine(**kwargs):
    return install(parent.make_engine(**kwargs))


class VersionedSession(parent.VersionedSession):
    def _publish(self, frame):
        assert frame.state.state_version.endswith(parent.TAG)
        return replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))


def make_session(engine=None):
    if engine is None:
        engine = make_engine()
    elif not isinstance(engine._inner, CardShelf):
        install(engine)
    return VersionedSession(parent.make_session(engine))
