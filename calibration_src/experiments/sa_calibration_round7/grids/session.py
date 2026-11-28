"""One physical card can be upgraded, transformed or removed in an identified room."""
from dataclasses import dataclass, replace
import json
from numbers import Integral
from pathlib import Path
from uuid import uuid4

from experiments.action193_grid.session import permitted, witness
from experiments.common_relic193.rules import relic_id
from experiments.permanent_grid193.session import bound, deck
from experiments.policy_neow_cards.session import require
from experiments.wing_removal_640.session import BOTTLES, NEVER_REMOVE, current_deck
from silent_env.action193 import ACTION_COUNT, POLICY_VERSION, choice_action, choice_slot
from silent_env.interface import InterfaceMismatch
from silent_env.observation import schema
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError

RULES = json.loads(Path(__file__).with_name("RULES.json").read_bytes())
UPGRADE = frozenset(RULES["single_upgrade"])
CURSE = frozenset(RULES["never_upgrade"])
GREEN = frozenset(RULES["green_transform"])
KNOWN_CARDS = UPGRADE | CURSE
EVENT = {k:v+1 for k,v in schema()["enums"]["Event"].items()}
POTION = schema()["enums"]["Potion"]
UNVERIFIED_USE = {POTION[k]+1 for k in ("BLOOD_POTION","ENTROPIC_BREW","FRUIT_JUICE","SMOKE_BOMB","FAIRY_POTION")}
ACQUIRE = {relic_id(k) for k in ("CERAMIC_FISH","DARKSTONE_PERIAPT","FROZEN_EGG","MOLTEN_EGG","TOXIC_EGG")}
DOLL = relic_id("DU_VU_DOLL")
EVENTS = {(EVENT[k],slot):(task,k) for k,slot,task in (
    ("UPGRADE_SHRINE",0,3),("OMINOUS_FORGE",0,3),("LIVING_WALL",2,3),
    ("PURIFIER",0,4),("THE_CLERIC",1,4),("TRANSMORGRIFIER",0,1),("LIVING_WALL",1,1))}
PREFIX = "PERMANENT_CARD_"


def origin(frame,raw,action):
    if (frame is None or frame.done or frame.page!="DELEGATED" or not bound(raw)
            or raw.engine_steps!=frame.engine_steps or not isinstance(action,Integral) or not 110<=action<=112):
        return None
    v=frame.state.vector
    if (v[3]<1 or v[4:6]!=(1,20) or v[7] or raw.raw_base[6:10]!=v[6:10]
            or raw.raw_base[706:898]!=v[706:898]):
        return None
    slot=action-110
    if v[6]==7 and v[8]==2 and slot==1:
        kind,operation,task,label=10,"choose_rest_option",3,"REST"
    elif v[6]==1 and v[8]==3 and (v[9],slot) in EVENTS:
        task,label=EVENTS[v[9],slot]
        kind,operation=8,"choose_event_option"
    else:
        return None
    relics=set(v[32:112:2])
    if task in (1,4) and DOLL in relics or task==1 and ACQUIRE & relics:
        return None
    if (v[322+6*slot:328+6*slot]!=(kind,slot,0,0,0,1) or not frame.supported_actions[action]
            or not any((b.policy_id,b.simulator_id,b.choice_row,b.operation)==(action,81+slot,slot,operation) for b in raw.bindings)):
        return None
    return task,label


def positions(engine,frame,raw,cards,task):
    v=frame.state.vector
    if (frame.page!="GRID_UNVERIFIED" or not bound(raw) or raw is not engine._source._current
            or v[6:8]!=(4,0) or v[26:29]!=(task,1,0) or raw.engine_steps!=frame.engine_steps
            or raw.raw_base[706:898]!=v[706:898] or len(cards)!=v[22] or deck(v)!=tuple(c[:2] for c in cards)):
        return None
    if v[2586]==2 and v[2587:2587+len(cards)]!=tuple(c[2] for c in cards):
        return None
    if v[3114]!=2 or any(v[3115:3118]) or any(c[3] for c in cards) or set(v[32:112:2])&set(BOTTLES):
        return None
    names=engine._source._backend.CARD_IDS
    eligible=[]
    for i,(cid,up,_,_) in enumerate(cards):
        name=names[cid-1]
        if task==3:
            if name not in KNOWN_CARDS or up not in (0,1):
                return None
            include=not up and name in UPGRADE
        else:
            include=name not in NEVER_REMOVE
        if include:
            eligible.append(i)
    size=len(eligible)
    live=witness().describe(engine._source._env)
    metadata=raw.choice_metadata["choices"]
    if (not 1<=size<=64 or not live["active"] or live["steps"]!=frame.engine_steps or
            (live["task"],live["required"],live["selected"])!=(task,1,0) or
            not size==v[1769]==len(live["rows"])==live["count"]==len(metadata) or
            {i for i,x in enumerate(raw.backend_mask) if x and 81<=i<=144}!=set(range(81,81+size))):
        return None
    for j,(i,wire,actual) in enumerate(zip(eligible,metadata,live["rows"],strict=True)):
        cid,up=cards[i][:2]
        if (tuple(actual)!=(cid-1,bool(up),i) or not wire["described"] or not wire["legal"]
                or (wire["slot"],wire["sim_action"],wire["kind_name"])!=(j,81+j,"CARD")
                or wire["parameters"][:2]!=(cid,up) or wire["card_identity"]["native_id"]!=names[cid-1]
                or (wire["source_ref"]["container"],wire["source_ref"]["public_slot"])!=("gc.info.toSelectCards.public_grid",j)
                or v[322+6*j:328+6*j]!=(1,cid,up,0,0,1)):
            return None
    return tuple(eligible)


@dataclass
class Picker:
    task: int
    label: str
    offer: object
    base: object
    raw: object
    cards: tuple
    positions: tuple
    selectable: tuple
    selected: int|None=None
    mapped: object=None
    final_raw: object=None


class SingleGridMixin:
    def _r7_grid_page(self,pick,base,values,phase,buttons):
        raw=pick.final_raw if pick.mapped is not None else pick.raw
        belt=raw.state.vector[17:22]
        values[17:22]=belt
        discard={105+j for j,item in enumerate(belt) if item and raw.backend_mask[75+j]
                 and any(b.policy_id==105+j and b.simulator_id==75+j for b in raw.bindings)}
        full=(not UNVERIFIED_USE.intersection(belt) and len(discard)==sum(bool(item) for item in belt)
              and not (phase=="GRID" and (pick.label=="REST" or len(pick.selectable)!=len(pick.positions))))
        legal=permitted((*buttons,*discard))
        self._current=replace(base,frame_id=str(uuid4()),page=PREFIX+phase,state=replace(base.state,vector=tuple(values)),
                              supported_actions=legal,policy_mask=legal if full else None,
                              action_gaps=() if full else ("remaining_grid_potion_or_rest_cancel",))
        return self._current

    def _r7_grid_list(self,p):
        v=list(p.base.state.vector)
        n=len(p.positions)
        v[2683:2748]=[2]+[203+i for i in p.positions]+[0]*(64-n)
        if p.selected is None:
            return self._r7_grid_page(p,p.base,v,"GRID",[choice_action(j) for j in p.selectable])
        v[28]=1
        v[1769]=0
        for j in range(n):
            v[325+6*j]=int(j==p.selected)
            v[327+6*j]=0
        return self._r7_grid_page(p,p.base,v,"PREVIEW",(172,173))

    def _r7_grid_result(self,p):
        f=p.mapped;w=f.state.vector
        v=list(p.offer.state.vector)
        v[:3]=w[:3]
        v[22]=v[1763]=w[22]
        v[706:898]=w[706:898]
        v[2586:2683]=w[2586:2683]
        v[3114:3118]=w[3114:3118]
        v[26:29]=[0,0,0]
        rest=p.label=="REST"
        v[322:706]=([0]*6 if rest else [8,0,0,0,0,1])+[0]*378
        v[1769]=0 if rest else 1
        v[2683:2748]=[2]+[0]*64
        v[2968:3114]=([1,0] if rest else [2,1])+[0]*144
        return self._r7_grid_page(p,f,v,"LEAVE",(171 if rest else 110,))

    def _r7_grid_commit(self,p):
        eid=81+p.selected
        i=p.positions[p.selected]
        env=self._source._env
        old=p.base.state.vector
        if p.label=="THE_CLERIC":
            stack=self._inner.delegate
            original=stack._grid_origin
            require(original is not None and original.name=="The Cleric" and original.physical==1
                    and original.vector[:10]==p.offer.state.vector[:10] and not stack._event_pending,"Cleric payment lost its original frame")
            stack._grid_origin=None
        self._current=None
        require(env.is_valid(eid) and env.step(eid) and env.steps==p.base.engine_steps+1,"Card did not settle exactly once")
        raw,post=self._refresh(p.raw,eid)
        w=post.state.vector
        after=current_deck(self)
        old_card=p.cards[i]
        if p.task==3:
            expected=p.cards[:i]+((old_card[0],old_card[1]+1,*old_card[2:]),)+p.cards[i+1:]
        else:
            expected=p.cards[:i]+p.cards[i+1:]
            if p.task==1:
                fresh=after[-1]
                require(fresh[0]!=old_card[0] and fresh[1:]==(0,0,False),"Unexpected transformed card or persistent attributes")
                expected+= (fresh,)
        hp,maximum=old[:2]
        if p.task!=3 and self._source._backend.CARD_IDS[old_card[0]-1]=="Parasite":
            maximum=max(1,maximum-3);hp=min(hp,maximum)
        require(post.page=="DELEGATED" and w[6]==5 and w[:6]==(hp,maximum,*old[2:6])
                and w[16:22]==old[16:22] and w[32:112]==old[32:112] and expected==after
                and w[22]==len(after) and deck(w)==tuple(row[:2] for row in after), "Different card occurrence, inventory or settlement")
        p.mapped,p.final_raw=post,raw
        return self._r7_grid_result(p)

    def _r7_grid_discard(self,p,action):
        eid=75+action-105
        source=p.final_raw if p.mapped is not None else p.raw
        env=self._source._env
        before=current_deck(self)
        belt=list(source.state.vector[17:22]);belt[action-105]=0
        require(env.is_valid(eid) and env.step(eid) and env.steps==source.engine_steps+1,"Discard did not advance exactly once")
        raw,post=self._refresh(source,eid)
        w=post.state.vector;v=source.state.vector
        require(w[:6]==v[:6] and w[17:22]==tuple(belt) and w[22:322]==v[22:322] and current_deck(self)==before,
                "Discard changed non-potion fields")
        if p.mapped is not None:
            require(post.page==p.mapped.page,"Discard consumed the next map")
            p.mapped,p.final_raw=post,raw
            return self._r7_grid_result(p)
        require(positions(self,post,raw,p.cards,p.task)==p.positions,"Discard modified permanent choices")
        p.base,p.raw=post,raw
        return self._r7_grid_list(p)

    def step(self, action_id, *, frame_id, action_version):
        with self._lock:
            f=self._current
            if f is not None and f.page.startswith(PREFIX):
                p=self._r7_picker
                raw=p.final_raw if p.mapped is not None else p.raw
                if (f.frame_id!=frame_id or self._raw is not raw or self._source._current is not raw or self._source._env.steps!=raw.engine_steps):
                    raise StaleFrameError("The permanent-card decision has expired")
                if action_version!=POLICY_VERSION:
                    raise InterfaceMismatch("Expected A193")
                if not isinstance(action_id,Integral) or isinstance(action_id,bool) or not 0<=action_id<ACTION_COUNT or not f.supported_actions[action_id]:
                    raise UnverifiedSemanticsError("Control unavailable on this card screen")
                if 105<=action_id<110:
                    return self._r7_grid_discard(p,action_id)
                if p.mapped is not None:
                    self._r7_picker=None
                    self._current=p.mapped
                    return self._current
                require(current_deck(self)==p.cards and positions(self,p.base,p.raw,p.cards,p.task)==p.positions,
                        "The original card targets have changed")
                if p.selected is not None and action_id==172:
                    return self._r7_grid_commit(p)
                p.selected=None if action_id==173 else choice_slot(action_id)
                return self._r7_grid_list(p)

            orig=origin(f,self._raw,action_id) if self._raw is self._source._current else None
            before=current_deck(self) if orig else None
            after=super().step(action_id,frame_id=frame_id,action_version=action_version)
            if not orig or after.page!="GRID_UNVERIFIED":
                return after
            task,label=orig
            v,w=f.state.vector,after.state.vector
            gold=v[2]-(75 if label=="THE_CLERIC" else 0)
            if (gold<0 or w[:6]!=(*v[:2],gold,*v[3:6]) or w[16:26]!=v[16:26] or w[32:322]!=v[32:322]
                    or before!=current_deck(self) or after.engine_steps!=f.engine_steps+1):
                return after
            positions_=positions(self,after,self._raw,before,task)
            if positions_ is None:
                return after
            # Keep every original row visible. Select each green transform already independently checked.
            names=self._source._backend.CARD_IDS
            selectable=tuple(j for j,i in enumerate(positions_) if task!=1 or names[before[i][0]-1] in GREEN)
            if not selectable:
                return after
            self._r7_picker=Picker(task,label,f,after,self._raw,before,positions_,selectable)
            return self._r7_grid_list(self._r7_picker)
