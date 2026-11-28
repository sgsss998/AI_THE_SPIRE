"""Bind three ordinary Neow card choices and certify the retail empty-belt menus."""
from dataclasses import replace
from functools import wraps

from experiments.policy_neow_cards.session import read_offer
from experiments.reward_resolution193.mask import game_mask
from experiments.sa_calibration_round5.release import VersionedSession
from silent_env.runtime import StaleFrameError

OPTIONAL = {"native_neow_card_optional_inputs_unverified","other_neow_result_inputs_unverified",
            "native_neow_optional_controls_not_certified"}


def install(engine):
    legacy=engine._legacy
    if legacy._current is not None or getattr(legacy,"_expanded_colorless",False):
        raise ValueError("Install once on a fresh opening")
    original=legacy._offer
    @wraps(original)
    def offer(before,after,bonus):
        frame=original(before,after,bonus)
        if bonus!=6 or frame.page!="NEOW_CARD_OFFER":
            return frame
        inner=legacy._delegate
        packet=inner.delegate._provider.peek()
        rows=read_offer(packet,inner._core._session._current.choice_metadata)
        v=frame.state.vector
        if (v[16:22]!=(2,0,0,0,0,0) or len(rows)!=3
                or any(v[322+i*6:328+i*6]!=r for i,r in enumerate(rows))
                or [i for i,x in enumerate(frame.supported_actions) if x]!=[177]):
            return frame
        buttons=list(frame.supported_actions)
        buttons[110:113]=[True]*3
        legacy._current=replace(frame,supported_actions=tuple(buttons))
        return legacy._current
    legacy._expanded_colorless=True
    legacy._offer=offer
    return engine


class OpeningMenus(VersionedSession):
    def __init__(self,delegate):
        super().__init__(delegate)
        self.current=None

    def _publish(self,f):
        self.current=f
        if (f.done or not f.action_gaps or not set(f.action_gaps)<=OPTIONAL or
                f.state.vector[3:6]!=(0,1,20) or f.state.vector[16:22]!=(2,0,0,0,0,0)):
            return f
        v=f.state.vector
        if f.page in ("NEOW_CARD_OFFER","NEOW_CARD_LEAVE"):
            # Reuse the paid-card proof (same UI). The data still come from this gift's actual frame.
            slim=replace(f,state=replace(f.state,vector=v[:3118]))
            deck=v[706:706+2*int(v[22])]
            buttons=game_mask(slim,"offer" if f.page=="NEOW_CARD_OFFER" else "leave",v[:3],deck)
        elif (f.page=="NEOW_RESULT" and v[6:10]==(1,0,10,6) and v[1769]==1
              and v[322:706]==(8,0,0,0,0,1)+(0,)*378 and v[2968:2970]==(2,1)):
            buttons=tuple(i==110 for i in range(len(f.supported_actions)))
        else:
            return f
        if buttons is not None and tuple(buttons)==f.supported_actions:
            self.current=replace(f,policy_mask=f.supported_actions,action_gaps=())
        return self.current

    def real_action_mask(self,*,frame_id):
        if self.current is None or self.current.frame_id!=frame_id:
            raise StaleFrameError("Opening menu has changed")
        return self.current.policy_mask
