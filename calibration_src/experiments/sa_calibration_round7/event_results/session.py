"""Validate the selected original event outcome before exposing its single Leave option."""
from dataclasses import replace
import json
from pathlib import Path
from experiments.box_omamori193.result import REGRET
from experiments.common_relic193.rules import COUNTERS,relic_id
from experiments.event_result_frontiers193.session import EMPTY_RESULT,quoted_result
from experiments.policy_neow_cards.session import require
from experiments.public_event_values.projection import IDS
from silent_env.observation import schema
from .shuffle import upgraded_positions

PASSIVE={int(q):0 for q in json.loads((Path(__file__).with_name("PASSIVE.json")).read_bytes())["passive"].values()}
CHARGES=PASSIVE|COUNTERS
OMAMORI=relic_id("OMAMORI")
CERAMIC=relic_id("CERAMIC_FISH")
DARKSTONE=relic_id("DARKSTONE_PERIAPT")
DIRECT_HP={relic_id(k):n for k,n in (("STRAWBERRY",7),("PEAR",10),("MANGO",14))}
TYPES=schema()["native_card_types"]
MULTI_UPGRADE=schema()["enums"]["CardId"]["SEARING_BLOW"]+1
LEAVE=tuple(a==110 for a in range(189))
SLOTS={"World of Goop":(1,),"The Cleric":(0,),"Big Fish":(1,2),"Shining Light":(0,)}


def deck(v):
    return tuple((int(v[i]),int(v[i+1])) for i in range(706,706+2*int(v[22]),2))


def relics(v):
    return tuple((int(v[i]),int(v[i+1])) for i in range(32,32+2*int(v[23]),2))


def upgraded(v,w,seed):
    before,after=deck(v),deck(w)
    if (len(before)!=len(after) or any(a[0]!=b[0] for a,b in zip(before,after))
            or v[2970:2979]!=(129,v[2971],0,0,0,0,0,0,2)
            or w[:3]!=(v[0]-v[2971],v[1],v[2]) or w[0]<=0):
        return False
    if any(face==MULTI_UPGRADE or n not in (0,1) for face,n in before):
        return False
    eligible=[i for i,(face,n) in enumerate(before) if not n and TYPES[str(face-1)] in ("ATTACK","SKILL","POWER")]
    selected=upgraded_positions(int(seed),int(v[3]),eligible)
    if not selected:
        return False
    return all(new[1]==old[1]+int(i in selected) for i,(old,new) in enumerate(zip(before,after)))


def box(v,w):
    old,post=relics(v),relics(w)
    if len(post)!=len(old)+1:
        return False
    new_id,initial=post[-1]
    held=dict(old)
    if new_id in held or initial!=CHARGES.get(new_id,0 if new_id in DIRECT_HP else None):
        return False
    # A charged Omamori already in inventory blocks the curse. A charm inside
    # this box is obtained after the curse checks the old inventory.
    blocked=held.get(OMAMORI,0)>1
    expected_old=tuple((r,n-int(r==OMAMORI and blocked)) for r,n in old)
    if post[:-1]!=expected_old or deck(w)!=deck(v)+(() if blocked else ((REGRET,0),)):
        return False
    current_hp,max_hp,gold=v[:3]
    health=DIRECT_HP.get(new_id,0)+(6 if DARKSTONE in held and not blocked else 0)
    coins=9 if CERAMIC in held and not blocked else 0
    return tuple(w[:3])==(current_hp+health,max_hp+health,gold+coins)


def event_result(name,slot,v,w,seed):
    if (name not in SLOTS or slot not in SLOTS[name] or v[4:10]!=(1,20,1,0,3,IDS[name]+1)
            or v[2968:2970]!=(2,0) or w[3:6]!=v[3:6] or w[6:10]!=(5,0,3,0)
            or v[322+6*slot:328+6*slot]!=(8,slot,0,0,0,1)
            or not 1<=v[22]<=96 or not 1<=w[22]<=96 or not 1<=v[23]<=40 or not 1<=w[23]<=40):
        return None
    stable=((10,22),(24,26),(112,322),(898,1761),(1764,1769),(1770,2586),(2748,2770),(2775,2968))
    if any(v[a:b]!=w[a:b] for a,b in stable):
        return None
    boxed = name=="Big Fish" and slot==2
    if not boxed and v[2770:2775]!=w[2770:2775]:
        return None
    if boxed:
        if not box(v,w):
            return None
    else:
        if v[32:112]!=w[32:112] or v[22:24]!=w[22:24]:
            return None
        if name=="Shining Light":
            if not upgraded(v,w,seed):
                return None
        elif quoted_result(name,v)!=w[:3] or deck(v)!=deck(w):
            return None
    if any(v[i]!=w[i] for i in range(2587,2683)) or any(w[706+2*int(w[22]):898]):
        return None
    out=list(v)
    out[:3]=w[:3]
    out[22:24]=w[22:24]
    out[32:112]=w[32:112]
    out[706:898]=w[706:898]
    out[1762:1764]=w[1762:1764]
    if boxed:
        if w[2770]==2:
            out[2770:2775]=w[2770:2775]
        elif v[2770]==2 and relics(w)[-1][0]==relic_id("MAW_BANK"):
            out[2772]=1
    out[322:706]=[8,0,0,0,0,1]+[0]*378
    out[1769]=1
    out[2683:2748]=[2]+[0]*64
    out[2968:3114]=[2,1]+[0]*144
    return tuple(out)


class VerifiedEventResult:
    def _capture(self,source):
        transition=self._transition
        out=super()._capture(source)
        if out.page!="EVENT_RESULT_UNVERIFIED" or out.done or not self._event_pending or not transition:
            return out
        before,action,offer=transition
        if offer is None or offer.name not in SLOTS or action!=81+offer.physical:
            return out
        require(source is self._delegate._current and source.frame_id==self._source_id
                and out.engine_steps==source.engine_steps==before.engine_steps+1,"Different event transaction")
        env=self._delegate._session._env
        vector=event_result(offer.name,offer.physical,offer.vector,source.state.vector,env.seed)
        if vector is None:
            return out
        gap=EMPTY_RESULT if vector[16:22]==(2,0,0,0,0,0) else "event_result_full_mask_unverified"
        self._current=replace(out,state=replace(out.state,vector=vector),page="EVENT_RESULT",
                              policy_mask=None,supported_actions=LEAVE,action_gaps=(gap,))
        return self._current
