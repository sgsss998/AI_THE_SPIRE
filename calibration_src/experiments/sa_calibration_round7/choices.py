"""Integrate verified opening, shop and potion choices on the second R7 candidate."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from experiments.sa_calibration_round5.reference import sha
from . import combined as parent
from .shop.session import install as install_card_shelf
from .neow.session import PaidNeowMixin
from .potions.session import TeaRewardPotions, mask

HERE=Path(__file__).resolve().parent
TAG="+r7-opening-shop-potions-v3"


class Setup(TeaRewardPotions, parent.Setup):
    pass


class Engine(PaidNeowMixin, parent.Engine):
    setup_class = Setup


def make_engine(*, neow_curse_timing="settled"):
    engine=Engine(neow_curse_timing=neow_curse_timing)
    parent.wall.parent.parent.install_shop(engine)
    parent.box_session.bind_box(engine)
    return install_card_shelf(engine)


class Session(parent.Session):
    def _publish(self, frame):
        published=mask(self.engine, super()._publish(frame))
        self.frame=replace(published,state=replace(published.state,state_version=published.state.state_version+TAG))
        return self.frame


def make_session(engine=None):
    return Session(make_engine() if engine is None else engine)


def source_hashes():
    return {name:sha(HERE/name) for name in ("choices.py","shop/session.py","neow/session.py","potions/session.py")}


def interface_signature():
    old=parent.interface_signature()
    sources=source_hashes()
    first=make_session().reset(1)
    old.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    def derive(value):
        return sha256(json.dumps([value,sources],sort_keys=True).encode()).hexdigest()
    return replace(old,state_version=first.state.state_version,state_sha256=derive(old.state_sha256),
                   state_decoder_sha256=derive(old.state_decoder_sha256),action_source_sha256=derive(old.action_source_sha256),
                   action_adapter_version=old.action_adapter_version+TAG)
