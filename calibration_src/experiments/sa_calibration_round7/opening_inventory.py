"""Eighth R7 candidate: direct Neow relics, three Astrolabe transforms and event inventories."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from experiments.sa_calibration_round5.reference import sha
from . import transactions as parent
from .event_rewards.session import EventRewardMixin
from .opening_edges.astrolabe import AstrolabeMixin
from .opening_edges.direct import OpeningRelicsMixin
from .snake_belt.session import attach as attach_serpent

TAG="+r7-opening-inventory-v8"
HERE=Path(__file__).resolve().parent


class Setup(EventRewardMixin,parent.Setup):
    pass


class Engine(AstrolabeMixin,OpeningRelicsMixin,parent.Engine):
    setup_class=Setup


def make_engine(*,neow_curse_timing="settled"):
    return parent.configure(Engine(neow_curse_timing=neow_curse_timing))


class Session(parent.Session):
    def _publish(self,frame):
        frame=super()._publish(frame)
        self._latest=replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))
        return self._latest


def make_session(engine=None):
    engine=make_engine() if engine is None else engine
    owner=parent.parent.parent.make_session(engine)
    return Session(attach_serpent(parent.attach_split(owner)),engine)


def version(old,session_factory,tag,paths):
    sources={p:sha(HERE/p) for p in paths}
    def derive(value):
        return sha256(json.dumps([value,sources],sort_keys=True).encode()).hexdigest()
    first=session_factory().reset(1)
    old.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    return replace(old,state_version=first.state.state_version,state_sha256=derive(old.state_sha256),
                   state_decoder_sha256=derive(old.state_decoder_sha256),action_source_sha256=derive(old.action_source_sha256),
                   action_adapter_version=old.action_adapter_version+tag)


def interface_signature():
    return version(parent.interface_signature(),make_session,TAG,("opening_inventory.py","event_rewards/session.py",
        "opening_edges/direct.py","opening_edges/astrolabe.py","snake_belt/session.py"))
