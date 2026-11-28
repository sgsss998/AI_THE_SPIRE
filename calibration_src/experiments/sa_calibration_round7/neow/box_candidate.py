"""Standalone Pandora candidate, composed with the paid Neow candidate."""
from . import candidate as paid
from .pandora import PandoraMixin


class Engine(PandoraMixin, paid.Engine):
    pass


def make_engine(*, neow_curse_timing="settled"):
    engine = Engine(neow_curse_timing=neow_curse_timing)
    paid.wall.parent.parent.install_shop(engine)
    return engine


def make_session(engine=None):
    return paid.wall.make_session(make_engine() if engine is None else engine)
