"""Discard a carried potion on the serpent's leave page without submitting the event a second time."""
from dataclasses import replace
from numbers import Integral

from experiments.sa_calibration_round4.events.serpent import SerpentSession,LEAVE
from silent_env.interface import InterfaceMismatch
from silent_env.observation import schema
from silent_env.runtime import StaleFrameError

EXPLOSIVE=schema()["enums"]["Potion"]["EXPLOSIVE_POTION"]+1


class Belt(SerpentSession):
    def _event_page(self,page):
        frame=super()._event_page(page)
        base=self._underlying
        v=frame.state.vector
        if (page!=LEAVE or v[2969]!=2 or base.state.vector[6]!=5 or v[16]!=2
                or not any(v[17:19]) or not set(v[17:19])<={0,EXPLOSIVE} or any(v[19:22])):
            return frame
        mask=list(frame.supported_actions)
        for i,item in enumerate(v[17:19]):
            if item and not base.supported_actions[105+i]:
                return frame
            mask[105+i]=bool(item)
        mask=tuple(mask)
        self._visible=replace(frame,supported_actions=mask,policy_mask=mask,action_gaps=())
        return self._visible

    def step(self,action,*,frame_id,action_version):
        with self._lock:
            f=self._visible
            if (f is None or f.page!=LEAVE or not isinstance(action,Integral) or isinstance(action,bool)
                    or action not in (105,106) or not f.supported_actions[action]):
                return super().step(action,frame_id=frame_id,action_version=action_version)
            if frame_id!=f.frame_id:
                raise StaleFrameError("The serpent decision has changed")
            if action_version!=f.action_version:
                raise InterfaceMismatch("Wrong serpent action version")
            before=self._underlying
            after=self._submit(action)
            v,w=before.state.vector,after.state.vector
            slot=17+action-105
            if (v[6]!=5 or w[6]!=5 or w[slot]!=0 or v[:slot]!=w[:slot] or v[slot+1:112]!=w[slot+1:112]
                    or v[322:898]!=w[322:898] or after.engine_steps!=before.engine_steps+1):
                raise InterfaceMismatch("Discard changed the map, event settlement, deck, or a different bottle")
            return self._event_page(LEAVE)


def attach(owner):
    node=owner
    while node is not None:
        for name in ("delegate","base"):
            child=vars(node).get(name)
            if type(child) is SerpentSession:
                if child._visible is not None:
                    raise InterfaceMismatch("Attach before the serpent receives a frame")
                setattr(node,name,Belt(child.engine,child.delegate))
                return owner
        node=vars(node).get("delegate",vars(node).get("base"))
    raise InterfaceMismatch("No versioned serpent adapter")
