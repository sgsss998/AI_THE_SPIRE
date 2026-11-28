"""Isolated R7 diagnostic with Act II stolen-purse rewards."""
from dataclasses import replace
from experiments.sa_calibration_round7 import combined
from experiments.sa_calibration_round7.death_family import candidate as parent
from experiments.sa_calibration_round7.death_family.session import attach
from .session import ThiefRewardMixin, public_mask


class Setup(ThiefRewardMixin, combined.Setup):
    pass


class Engine(combined.Engine):
    setup_class = Setup


def make_engine(*, neow_curse_timing="settled"):
    e = Engine(neow_curse_timing=neow_curse_timing)
    combined.wall.parent.parent.install_shop(e)
    return combined.box_session.bind_box(e)


class Session(parent.Session):
    def _publish(self, frame):
        base = public_mask(self.engine, super()._publish(frame))
        self.frame = replace(
            base,
            state=replace(
                base.state,
                state_version=base.state.state_version + "+two-thieves-rewards-v1",
            ),
        )
        return self.frame


def make_session(engine=None):
    return attach(Session(engine if engine is not None else make_engine()))
