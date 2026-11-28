from . import candidate
from .colorless import ColorlessGridMixin


class Engine(ColorlessGridMixin,candidate.parent.Round7Engine):
    pass


def make_engine(*,neow_curse_timing="settled"):
    engine=Engine(neow_curse_timing=neow_curse_timing)
    candidate.parent.parent.parent.install_shop(engine)
    return engine


def make_session(engine=None):
    return candidate.make_session(make_engine() if engine is None else engine)
