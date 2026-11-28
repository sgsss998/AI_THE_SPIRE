from .. import candidate as grids
from .session import CurseGridMixin


class Engine(CurseGridMixin,grids.parent.Round7Engine):
    pass


def make_engine(*,neow_curse_timing="settled"):
    engine=Engine(neow_curse_timing=neow_curse_timing)
    grids.parent.parent.parent.install_shop(engine)
    return engine


def make_session(engine=None):
    return grids.make_session(make_engine() if engine is None else engine)
