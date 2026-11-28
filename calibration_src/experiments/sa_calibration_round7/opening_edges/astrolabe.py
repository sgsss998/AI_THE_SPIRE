"""The ordinary Silent opening exchange for Astrolabe and its three physical transformations."""
from dataclasses import dataclass
from numbers import Integral

from experiments.action193_grid.session import witness
from experiments.common_relic193.rules import relic_id
from experiments.grid_sources193.session import held,original_deck
from experiments.permanent_grid193.session import bound
from experiments.policy_neow_cards.session import require
from experiments.wing_removal_640.session import current_deck
from silent_env.action193 import ACTION_COUNT,POLICY_VERSION,choice_action,choice_slot
from silent_env.interface import InterfaceMismatch
from silent_env.runtime import StaleFrameError,UnverifiedSemanticsError
from ..grids.session import GREEN
from ..neow.session import RING

ASTROLABE=relic_id("ASTROLABE")
GRID="ASTROLABE_GRID"
LEAVE="ASTROLABE_LEAVE"


@dataclass
class Astrolabe:
    initial:object
    raw:object
    cards:tuple
    selected:tuple=()
    next_map:object=None
    next_raw:object=None


def matches(engine,offer,after):
    raw=engine._raw
    if not (offer and offer.page=="NEOW_OFFERS" and offer.engine_steps==0 and after.page=="GRID_UNVERIFIED"
            and raw is engine._source._current and bound(raw) and raw.engine_steps==after.engine_steps==1):
        return False
    v,w=offer.state.vector,after.state.vector
    if (v[:10]!=(59,66,99,0,1,20,1,0,10,6) or held(v)!=((RING,0),) or v[340:346]!=(9,19,7,0,0,1)
            or w[:6]!=v[:6] or w[6:10]!=(4,0,10,0) or w[16:24]!=(2,0,0,0,0,0,13,1)
            or w[26:29]!=(2,3,0) or held(w)!=((ASTROLABE,0),) or w[706:898]!=v[706:898]
            or not original_deck(w,engine._source._backend) or w[1769]!=12):
        return False
    live=witness().describe(engine._source._env)
    expected=[(w[706+2*i]-1,False,i) for i in range(1,13)]
    if (not live["active"] or (live["steps"],live["task"],live["required"],live["selected"])!=(1,2,3,0)
            or list(live["rows"])!=expected or len(raw.choice_metadata["choices"])!=12
            or [i for i,x in enumerate(raw.backend_mask) if x]!=list(range(81,93))):
        return False
    for j,item in enumerate(raw.choice_metadata["choices"]):
        wire=int(expected[j][0])+1
        if ((item["slot"],item["sim_action"],item["kind_name"],item["legal"])!=(j,81+j,"CARD",True)
                or item["card_identity"]["native_id"]!=engine._source._backend.CARD_IDS[wire-1]
                or item["source_ref"]["container"]!="gc.info.toSelectCards.public_grid" or item["source_ref"]["public_slot"]!=j
                or w[322+6*j:328+6*j]!=(1,wire,0,0,0,1)):
            return False
    return True


class AstrolabeMixin:
    def _astrolabe_grid(self,p):
        v=list(p.initial.state.vector)
        v[28]=len(p.selected)
        v[2683:2748]=[2,*range(204,216)]+[0]*52
        for j in range(12):
            v[325+6*j]=int(j+1 in p.selected)
        return self._remove_publish(p.initial,v,GRID,[choice_action(j) for j in range(12)],complete=True)

    def _astrolabe_commit(self,p):
        environment=self._source._env
        raw=p.raw
        self._current=None
        for n,i in enumerate(p.selected):
            live=witness().describe(environment)
            require(live["active"] and (live["task"],live["required"],live["selected"],live["steps"])==(2,3,n,1+n),
                    "Astrolabe selection count or original screen changed")
            matches=[j for j,(cid,up,pos) in enumerate(live["rows"]) if pos==i and (cid+1,int(up))==p.cards[i][:2]]
            require(len(matches)==1 and environment.is_valid(81+matches[0]),"Astrolabe lost the selected physical card")
            aid=81+matches[0]
            require(environment.step(aid) and environment.steps==2+n,"Astrolabe selection was not recorded once")
            raw,parent=self._refresh(raw,aid)
            if n<2:
                require(current_deck(self)==p.cards,"Astrolabe replaced cards before selecting three")
        survivors=tuple(c for i,c in enumerate(p.cards) if i not in p.selected)
        cards=current_deck(self)
        old=p.initial.state.vector
        w=parent.state.vector
        require(w[6]==5 and w[:6]==old[:6] and w[16:26]==old[16:26] and w[32:322]==old[32:322]
                and cards[:-3]==survivors and len(cards)==13 and all(up==1 and self._source._backend.CARD_IDS[cid-1] in GREEN
                and not misc and not bottled for cid,up,misc,bottled in cards[-3:]),"Astrolabe changed survivors, resources or upgrades")
        p.next_raw,p.next_map=raw,parent
        v=list(w)
        v[6:10]=[1,0,10,6]
        v[26:29]=[0]*3
        v[322:706]=[8,0,0,0,0,1]+[0]*378
        v[1769]=1
        v[2683:2748]=[2]+[0]*64
        v[2968:3114]=[2,1]+[0]*144
        return self._remove_publish(parent,v,LEAVE,(110,),complete=True)

    def step(self,action_id,*,frame_id,action_version):
        with self._lock:
            f=self._current
            if f is not None and f.page in (GRID,LEAVE):
                p=self._astrolabe
                raw=p.next_raw if f.page==LEAVE else p.raw
                if f.frame_id!=frame_id or self._raw is not raw or raw is not self._source._current or self._source._env.steps!=raw.engine_steps:
                    raise StaleFrameError("This Astrolabe choice expired")
                if action_version!=POLICY_VERSION:
                    raise InterfaceMismatch("Expected A193")
                if isinstance(action_id,bool) or not isinstance(action_id,Integral) or not 0<=action_id<ACTION_COUNT or not f.supported_actions[action_id]:
                    raise UnverifiedSemanticsError("Unavailable Astrolabe control")
                if f.page==LEAVE:
                    self._astrolabe=None
                    self._current=p.next_map
                    return self._current
                require(current_deck(self)==p.cards,"Opening deck changed during Astrolabe selection")
                pos=choice_slot(action_id)+1
                p.selected=tuple(i for i in p.selected if i!=pos) if pos in p.selected else (*p.selected,pos)
                return self._astrolabe_commit(p) if len(p.selected)==3 else self._astrolabe_grid(p)
            after=super().step(action_id,frame_id=frame_id,action_version=action_version)
            if action_id==113 and matches(self,f,after):
                self._astrolabe=Astrolabe(after,self._raw,current_deck(self))
                return self._astrolabe_grid(self._astrolabe)
            return after
