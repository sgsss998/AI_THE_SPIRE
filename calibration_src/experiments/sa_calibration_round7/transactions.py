"""Seventh R7 candidate: select the actual curse, slime target, box outcome and campfire control."""
from dataclasses import replace
from hashlib import sha256
import json

from experiments.sa_calibration_round5.reference import sha
from . import events_and_grids as parent
from .grids.curse.session import CurseGridMixin
from .event_box.session import DelayedBoxResult
from .combat_edges.session import attach as attach_split
from .smith.session import install as install_smith

TAG="+r7-native-choices-v7"


class Setup(DelayedBoxResult,parent.Setup):
    pass


class Engine(CurseGridMixin,parent.Engine):
    setup_class=Setup


def configure(engine):
    decisions=parent.parent
    battle=decisions.battle
    battle.install_shop(engine)
    battle.bind_box(engine)
    battle.parent.install_card_shelf(engine)
    battle.install_merchandise(engine)
    parent.install_door(engine)
    install_smith(engine)
    return decisions.install_opening(engine)


def make_engine(*,neow_curse_timing="settled"):
    return configure(Engine(neow_curse_timing=neow_curse_timing))


class Session(parent.Session):
    def _publish(self, frame):
        frame=super()._publish(frame)
        if frame.page in ("GRID","GRID_CONFIRM"):
            inner=self.engine._inner._current
            if (inner and inner.page==frame.page and inner.engine_steps==frame.engine_steps
                    and inner.policy_mask is not None and not inner.action_gaps
                    and list(inner.supported_actions)==list(frame.supported_actions[:len(inner.supported_actions)])
                    and not any(frame.supported_actions[len(inner.supported_actions):])):
                frame=replace(frame,policy_mask=frame.supported_actions,action_gaps=())
        self._latest=replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))
        return self._latest


def make_session(engine=None):
    engine=make_engine() if engine is None else engine
    return Session(attach_split(parent.parent.make_session(engine)),engine)


def interface_signature():
    old=parent.interface_signature()
    folder=parent.parent.battle.parent.HERE
    paths=("transactions.py","smith/session.py","smith/cancel.cpp","event_box/session.py","combat_edges/session.py",
           "grids/curse/session.py","grids/curse/correction.cpp","grids/curse/build.py","grids/curse/build/BUILD.json")
    sources={p:sha(folder/p) for p in paths}
    def derive(value):
        return sha256(json.dumps([value,sources],sort_keys=True).encode()).hexdigest()
    first=make_session().reset(1)
    old.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    return replace(old,state_version=first.state.state_version,state_sha256=derive(old.state_sha256),
                   state_decoder_sha256=derive(old.state_decoder_sha256),action_source_sha256=derive(old.action_source_sha256),
                   action_adapter_version=old.action_adapter_version+TAG)
