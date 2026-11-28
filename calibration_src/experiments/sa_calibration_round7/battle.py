"""Fourth R7 candidate, including ordinary casualties, one-click hand replacement and Pandora's Box."""
from dataclasses import replace
from hashlib import sha256
import json
from . import choices as parent
from .death_family.session import attach as attach_casualties
from .hand.session import HandSwap
from .neow.pandora import PandoraMixin
from .terminal_intent.session import TerminalIntent
from .shop_extra.session import BottleObservation, install as install_merchandise
from experiments.sa_calibration_round5.reference import sha
from experiments.sa_calibration_round5.shop.session import install as install_shop
from experiments.box_omamori193.session import bind_box

TAG="+r7-casualties-hand-pandora-v4"


class Engine(PandoraMixin,parent.Engine):
    pass


def make_engine(*,neow_curse_timing="settled"):
    engine=Engine(neow_curse_timing=neow_curse_timing)
    install_shop(engine)
    bind_box(engine)
    parent.install_card_shelf(engine)
    return install_merchandise(engine)


class Session(TerminalIntent):
    def _version(self,frame):
        return replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))

    def reset(self,*args,**kwargs):
        return self._version(super().reset(*args,**kwargs))

    def reset_fixture(self,*args,**kwargs):
        return self._version(super().reset_fixture(*args,**kwargs))

    def step(self,*args,**kwargs):
        return self._version(super().step(*args,**kwargs))


def make_session(engine=None):
    engine=make_engine() if engine is None else engine
    owner=attach_casualties(parent.make_session(engine))
    return Session(HandSwap(BottleObservation(owner,engine),engine))


def source_hashes():
    return {name:sha(parent.HERE/name) for name in ("battle.py","death_family/session.py","hand/session.py",
            "neow/pandora.py","terminal_intent/session.py","shop_extra/session.py")}


def interface_signature():
    old=parent.interface_signature()
    first=make_session().reset(1)
    old.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    sources=source_hashes()
    def derive(value):
        return sha256(json.dumps([value,sources],sort_keys=True).encode()).hexdigest()
    return replace(old,state_version=first.state.state_version,state_sha256=derive(old.state_sha256),
                   state_decoder_sha256=derive(old.state_decoder_sha256),action_source_sha256=derive(old.action_source_sha256),
                   action_adapter_version=old.action_adapter_version+TAG)
