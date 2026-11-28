"""One-click replacement in a single-card hand picker, preserving physical occurrence and order."""
from dataclasses import replace
from numbers import Integral

from experiments.hand_binding_v3.hand_binding import Candidate, STATE_VERSION, layout_from_candidate
from silent_env.interface import InterfaceMismatch
from silent_env.runtime import StaleFrameError


class HandSwap:
    def __init__(self, delegate, engine):
        self.delegate, self.engine = delegate, engine
        self.frame = None
        self.replacements = ()

    def __getattr__(self, name):
        return getattr(self.delegate,name)

    def _publish(self, frame):
        self.frame = frame
        self.replacements = ()
        v=frame.state.vector
        if (frame.done or not v[7] or v[26] not in (6,9,21,22,28) or v[27:29]!=(1,1)
                or not frame.supported_actions[172] or not frame.supported_actions[179]):
            return frame
        source=self.engine._source._current
        if source is None or source.engine_steps!=frame.engine_steps or not source.hand_order.active:
            return frame
        layout=layout_from_candidate(Candidate(STATE_VERSION,v[:3118]))
        if (not layout.remaining or len(layout.selected)!=1 or layout.remaining!=source.hand_order.remaining
                or layout.selected!=source.hand_order.selected):
            return frame
        buttons=list(frame.supported_actions)
        if any(buttons[110+i] for i in range(len(layout.remaining))):
            return frame
        values=list(v)
        for screen_slot,physical_slot in enumerate(layout.remaining):
            row=322+6*physical_slot
            if (values[row]!=1 or values[row+3]!=0 or values[row+5]!=0
                    or values[row+1]!=values[1253+6*physical_slot]):
                return frame
            values[row+5]=1
            buttons[110+screen_slot]=True
        self.replacements=layout.remaining
        buttons=tuple(buttons)
        gaps=tuple(g for g in frame.action_gaps if g!="additional_hand_replacement_unverified")
        full=frame.policy_mask is not None or frame.action_gaps==("additional_hand_replacement_unverified",)
        self.frame=replace(frame,state=replace(frame.state,vector=tuple(values)),supported_actions=buttons,
                           policy_mask=buttons if full else None,action_gaps=gaps)
        return self.frame

    def reset(self,*args,**kwargs):
        with self.delegate._lock:
            return self._publish(self.delegate.reset(*args,**kwargs))

    def reset_fixture(self,*args,**kwargs):
        with self.delegate._lock:
            return self._publish(self.delegate.reset_fixture(*args,**kwargs))

    def real_action_mask(self,*,frame_id):
        with self.delegate._lock:
            if self.frame is None or self.frame.frame_id!=frame_id:
                raise StaleFrameError("Hand selection has changed")
            return self.frame.policy_mask

    def step(self,action,*,frame_id,action_version):
        with self.delegate._lock:
            old=self.frame
            if old is None or old.frame_id!=frame_id:
                raise StaleFrameError("Hand selection has changed")
            if action_version!=old.action_version:
                raise InterfaceMismatch("Unexpected hand action version")
            if isinstance(action,bool) or not isinstance(action,Integral) or not (110<=action<110+len(self.replacements)):
                return self._publish(self.delegate.step(action,frame_id=frame_id,action_version=action_version))
            previous=self.engine._source._current.hand_order
            wanted=self.replacements[action-110]
            self.frame=None
            # The two backing choices update the picker only. No card is discarded or played before Confirm.
            opened=self.delegate.step(179,frame_id=frame_id,action_version=action_version)
            interim=self.engine._source._current.hand_order
            if (interim.selected or interim.remaining!=previous.remaining+previous.selected
                    or not opened.supported_actions[action]):
                raise InterfaceMismatch("Deselect did not restore the visible cards in retail order")
            changed=self.delegate.step(action,frame_id=opened.frame_id,action_version=action_version)
            end=self.engine._source._current.hand_order
            if end.selected!=(wanted,) or end.remaining!=tuple(i for i in interim.remaining if i!=wanted):
                raise InterfaceMismatch("The replacement changed another card or its visible order")
            return self._publish(changed)
