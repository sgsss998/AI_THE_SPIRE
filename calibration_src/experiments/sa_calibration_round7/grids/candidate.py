"""Independent R7 single-card grid candidate."""
from .. import release as parent
from .session import SingleGridMixin


class Engine(SingleGridMixin,parent.Round7Engine):
    pass


def make_engine(*,neow_curse_timing="settled"):
    engine=Engine(neow_curse_timing=neow_curse_timing)
    parent.parent.parent.install_shop(engine)
    return engine


def make_session(engine=None):
    return parent.make_session(make_engine() if engine is None else engine)
