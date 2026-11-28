"""Standalone composition for the reward-family regression."""
from experiments.sa_calibration_round6 import release as parent
from experiments.sa_calibration_round7.wall.session import WallRemovalMixin
from .session import StandardRewardMixin, public_mask


class StandardRewardSetup(StandardRewardMixin, parent.InkRewardSetup):
    pass


class Engine(WallRemovalMixin, parent.Round6Engine):
    setup_class = StandardRewardSetup


def make_engine(*, neow_curse_timing="settled"):
    engine = Engine(neow_curse_timing=neow_curse_timing)
    parent.parent.install_shop(engine)
    return engine


class Session(parent.VersionedSession):
    def __init__(self, engine):
        super().__init__(parent.make_session(engine))
        self.engine = engine

    def _publish(self, frame):
        return public_mask(self.engine, frame)


def make_session(engine=None):
    return Session(make_engine() if engine is None else engine)
