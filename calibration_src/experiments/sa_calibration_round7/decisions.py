"""Versioned R7 S3127 candidate with reviewed opening menus and stolen-purse rewards."""
from dataclasses import replace
from hashlib import sha256
import json

from experiments.sa_calibration_round5.reference import sha
from . import battle
from .opening_controls.session import OpeningMenus, install as install_opening
from .death_family.thief_rewards.session import ThiefRewardMixin, public_mask
from .death_family.thief_rewards.observation import session as purses

TAG = "+r7-opening-thief-rewards-v5"


class Setup(ThiefRewardMixin, battle.Engine.setup_class):
    pass


class Engine(battle.Engine):
    setup_class = Setup


def make_engine(*, neow_curse_timing="settled"):
    engine = Engine(neow_curse_timing=neow_curse_timing)
    battle.install_shop(engine)
    battle.bind_box(engine)
    battle.parent.install_card_shelf(engine)
    battle.install_merchandise(engine)
    return install_opening(engine)


class Menus(OpeningMenus):
    def __init__(self, owner, engine):
        super().__init__(owner)
        self.engine = engine

    def _publish(self, frame):
        frame = super()._publish(public_mask(self.engine, frame))
        self.current = replace(frame, state=replace(frame.state, state_version=frame.state.state_version + TAG))
        return self.current


def make_session(engine=None):
    engine = make_engine() if engine is None else engine
    return purses.Session(Menus(battle.make_session(engine), engine), engine)


def interface_signature():
    old = battle.interface_signature()
    paths = ["decisions.py", "opening_controls/session.py", "death_family/thief_rewards/session.py"]
    sources = {name:sha(battle.parent.HERE/name) for name in paths}
    def derive(value):
        return sha256(json.dumps([value,sources], sort_keys=True).encode()).hexdigest()
    result = purses.signature(replace(old, state_version=old.state_version+TAG,
        state_sha256=derive(old.state_sha256), state_decoder_sha256=derive(old.state_decoder_sha256),
        action_source_sha256=derive(old.action_source_sha256), action_adapter_version=old.action_adapter_version+TAG))
    frame = make_session().reset(1)
    result.assert_model_dimensions(len(frame.state.vector),len(frame.supported_actions))
    assert result.state_version == frame.state.state_version
    return result
