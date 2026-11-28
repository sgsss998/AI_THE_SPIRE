"""Independent entry point for the paid Neow regression."""
from experiments.sa_calibration_round7 import release as wall
from .session import PaidNeowMixin


class Engine(PaidNeowMixin, wall.Round7Engine):
    pass


def make_engine(*, neow_curse_timing="settled"):
    engine = Engine(neow_curse_timing=neow_curse_timing)
    wall.parent.parent.install_shop(engine)
    return engine


def make_session(engine=None):
    return wall.make_session(make_engine() if engine is None else engine)
