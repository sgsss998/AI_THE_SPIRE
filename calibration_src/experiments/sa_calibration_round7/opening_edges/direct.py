"""Give the model the settled resources, relic state and Leave action for a validated Neow purchase."""
from dataclasses import replace
from experiments.common_relic193.rules import relic_id,START
from experiments.neow_reward_640.session import CURSES
from experiments.policy_neow_cards.session import page,require
from ..neow.session import RING

RARE={name:cls for name,cls in (
    ("CALIPERS","Calipers"),("DEAD_BRANCH","DeadBranch"),("DU_VU_DOLL","DuVuDoll"),
    ("FOSSILIZED_HELIX","FossilizedHelix"),("GAMBLING_CHIP","GamblingChip"),("GINGER","Ginger"),
    ("ICE_CREAM","IceCream"),("INCENSE_BURNER","IncenseBurner"),("LIZARD_TAIL","LizardTail"),
    ("MANGO","Mango"),("PRAYER_WHEEL","PrayerWheel"),("STONE_CALENDAR","StoneCalendar"),
    ("THE_SPECIMEN","TheSpecimen"),("THREAD_AND_NEEDLE","ThreadAndNeedle"),("TINGSHA","Tingsha"),
    ("TUNGSTEN_ROD","TungstenRod"),("TURNIP","Turnip"),("UNCEASING_TOP","UnceasingTop"))}
COMMON={"MAW_BANK":"MawBank","POTION_BELT":"PotionBelt","STRAWBERRY":"Strawberry","WAR_PAINT":"WarPaint"}
TIERS={key:{relic_id(k) for k in names} for key,names in ((8,COMMON),(14,RARE))}
MAW,LIZARD,DOLL,BURNER,MANGO,STRAWBERRY,BELT,PAINT=[relic_id(name) for name in (
    "MAW_BANK","LIZARD_TAIL","DU_VU_DOLL","INCENSE_BURNER","MANGO","STRAWBERRY","POTION_BELT","WAR_PAINT")]


def applied(v,w,action,card_ids):
    if (len(v)!=3118 or len(w)!=3118 or v[:10]!=(59,66,99,0,1,20,1,0,10,6) or w[6:10]!=(5,0,10,0)
            or v[16:24]!=(2,0,0,0,0,0,13,1) or v[706:732:2]!=START or any(v[707:732:2])
            or v[32:112]!=(RING,0)+(0,)*78 or v[1769]!=4 or action not in (111,112)):
        return None
    k=322+6*(action-110)
    kind,gift,cost,_,_,legal=v[k:k+6]
    rid=int(w[34])
    if (kind!=9 or legal!=1 or v[k+3:k+6]!=(0,0,1) or rid not in TIERS.get(gift,())
            or not ((action==111 and gift==8 and cost==2) or (action==112 and gift==14 and cost in (3,4,5,6)))):
        return None
    out=list(v)
    hp,maximum,gold=59,66,99
    if cost==3:maximum=60
    if cost==4:gold=0
    if cost==6:hp=44
    if rid in (MANGO,STRAWBERRY):
        amount=14 if rid==MANGO else 7
        hp+=amount;maximum+=amount
    out[:3]=[hp,maximum,gold]
    out[23]=out[1762]=2
    # Du-Vu Doll counts every current curse, including Ascender's Bane. Counter encoding adds one.
    out[34:36]=[rid,2+int(cost==5) if rid==DOLL else 1 if rid==BURNER else 0]
    if cost==5:
        curse=int(w[732])
        if not (0<curse<=len(card_ids) and card_ids[curse-1] in CURSES and w[733]==0 and w[2586] in (0,2)):
            return None
        out[22]=out[1763]=14;out[732]=curse;out[2586]=w[2586]
    if rid==BELT:
        out[16]=out[1771]=4
    if rid==PAINT:
        marks=[i for i in range(13) if w[707+2*i]]
        if len(marks)!=2 or not set(marks)<=set(range(6,12)):
            return None
        for i in marks:out[707+2*i]=1
    if rid in (MAW,LIZARD):
        # At acquisition none of the four flags has fired. Maw Bank starts active.
        if w[2770:2775]!=(0,0,0,0,0):return None
        out[2770:2775]=[0]*5
    for lo,hi in ((0,6),(10,322),(706,1769),(1770,2683),(2748,2968),(3114,3118)):
        if tuple(out[lo:hi])!=w[lo:hi]:
            return None
    if rid in (MAW,LIZARD):out[2770:2775]=[2,0,int(rid==MAW),0,0]
    out[322:706]=[8,0,0,0,0,1]+[0]*378
    out[1769]=1;out[2683:2748]=[2]+[0]*64;out[2968:3114]=[2,1]+[0]*144
    return out


class OpeningRelicsMixin:
    def step(self,action_id,*,frame_id,action_version):
        with self._lock:
            f=self._current
            after=super().step(action_id,frame_id=frame_id,action_version=action_version)
            if f and f.page=="NEOW_RESULT" and action_id==110 and f.engine_steps==after.engine_steps==1:
                old,new=f.state.vector,after.state.vector
                if (new[3:10]==(0,1,20,5,0,10,0) and old[34] in (MAW,LIZARD) and new[34]==old[34]
                        and old[2770]==2 and new[2770:2775]==(0,0,0,0,0)):
                    self._current=replace(after,state=replace(after.state,vector=new[:2770]+old[2770:2775]+new[2775:]))
                    return self._current
            if (f is None or f.page!="NEOW_OFFERS" or f.engine_steps or action_id not in (111,112)
                    or after.page!="NEOW_RESULT_UNVERIFIED"):
                return after
            source=self._legacy._source;raw=self._raw
            values=applied(f.state.vector,source.state.vector,action_id,self._source._backend.CARD_IDS)
            if values is None:return after
            require(source.page=="DELEGATED" and source is self._inner._current and raw is self._source._current
                    and raw.state.vector==source.state.vector and after is self._current and self._legacy._current is self._bound
                    and raw.packet_sha256==raw.choice_metadata["packet_sha256"] and len(raw.packet_sha256)==64
                    and raw.engine_steps==source.engine_steps==after.engine_steps==self._source._env.steps==1,
                    "Neow relic settlement has lost the current map")
            result=page(source,"NEOW_RESULT",values,{110})
            frame=self._sync(self._legacy._cost_projection(self._legacy._version(result)),None)
            self._current=replace(frame,policy_mask=frame.supported_actions,action_gaps=())
            return self._current
