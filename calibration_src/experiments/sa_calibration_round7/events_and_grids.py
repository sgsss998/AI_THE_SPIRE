"""R7 v6 integrates event settlements, physical grid choices, lethal events and the shop door."""
from dataclasses import replace
from hashlib import sha256
import json

from experiments.sa_calibration_round5.reference import sha
from . import decisions as parent
from .event_results.session import VerifiedEventResult
from .event_death.session import Session as EventDeath
from .grids.colorless import ColorlessGridMixin
from .shop_door.session import install as install_door

TAG = "+r7-events-and-grids-v6"


class Setup(VerifiedEventResult,parent.Setup):
    pass


class Engine(ColorlessGridMixin,parent.Engine):
    setup_class=Setup


def make_engine(*,neow_curse_timing="settled"):
    engine=Engine(neow_curse_timing=neow_curse_timing)
    battle=parent.battle
    battle.install_shop(engine)
    battle.bind_box(engine)
    battle.parent.install_card_shelf(engine)
    battle.install_merchandise(engine)
    install_door(engine)
    return parent.install_opening(engine)


class Session(EventDeath):
    def _publish(self,frame):
        frame=super()._publish(frame)
        if frame.page=="SHOP_ROOM":
            inner=self.engine._inner._current
            if (inner and inner.page==frame.page and inner.engine_steps==frame.engine_steps
                    and inner.policy_mask is not None and not inner.action_gaps
                    and list(inner.supported_actions)==list(frame.supported_actions[:len(inner.supported_actions)])
                    and not any(frame.supported_actions[len(inner.supported_actions):])):
                frame=replace(frame,policy_mask=frame.supported_actions,action_gaps=())
        self._latest=replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))
        return self._latest

    def real_action_mask(self,*,frame_id):
        from silent_env.runtime import StaleFrameError
        if self._latest is None or self._latest.frame_id!=frame_id:
            raise StaleFrameError("This decision has changed")
        return self._latest.policy_mask


def make_session(engine=None):
    engine=make_engine() if engine is None else engine
    return Session(parent.make_session(engine),engine)


def interface_signature():
    old=parent.interface_signature()
    folder=parent.battle.parent.HERE
    paths=("events_and_grids.py","shop_door/session.py","event_death/session.py","event_results/session.py",
           "event_results/shuffle.py","event_results/PASSIVE.json","grids/session.py","grids/RULES.json",
           "grids/colorless.py","grids/CARD_ORDER.json")
    sources={p:sha(folder/p) for p in paths}
    first=make_session().reset(1)
    old.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    def derive(value):
        return sha256(json.dumps([value,sources],sort_keys=True).encode()).hexdigest()
    return replace(old,state_version=first.state.state_version,state_sha256=derive(old.state_sha256),
                   state_decoder_sha256=derive(old.state_decoder_sha256),action_source_sha256=derive(old.action_source_sha256),
                   action_adapter_version=old.action_adapter_version+TAG)
