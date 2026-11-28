"""Extend ordinary shop commands using the bound price, current inventory and exact item slot."""
from dataclasses import replace
from numbers import Integral
from types import MethodType

from experiments.action193_grid.session import witness
from experiments.common_relic193.rules import relic_id
from experiments.public_shop.session import check, row_at, shop_rows, with_rows
from silent_env.canonical_choices import ActionBinding
from silent_env.observation import schema
from silent_env.policy_actions import POLICY_VERSION
from silent_env.runtime import StaleFrameError
from ..shop.session import CardShelf, SPECIAL

OMAMORI = relic_id("OMAMORI")
FUNNEL = relic_id("TWISTED_FUNNEL")
LIGHTNING = relic_id("BOTTLED_LIGHTNING")
BOTTLES = {relic_id(k) for k in ("BOTTLED_FLAME","BOTTLED_LIGHTNING","BOTTLED_TORNADO")}
SOZU = relic_id("SOZU")
CARD_TYPES = schema()["native_card_types"]
BELT_DISCARD_ONLY = {schema()["enums"]["Potion"][name]+1 for name in
                     ("POWER_POTION","DUPLICATION_POTION","ATTACK_POTION","CULTIST_POTION","COLORLESS_POTION")}



def bind_bottle(source, original_capture):
    def capture(self):
        frame = original_capture()
        g = frame.storage_state.blocks["global"][0]
        if (frame.done or g["in_battle"] or g["ascension"]!=20 or g["room"]!=0 or g["screen"]!=4
                or (g["selection_task"],g["selection_required"],g["selection_count"])!=(7,1,0)):
            return frame
        relics={r["id"]+1 for r in frame.storage_state.blocks["relics"] if r["id"] is not None}
        if (relics & BOTTLES != {LIGHTNING} or frame.packet_sha256!=frame.choice_metadata.get("packet_sha256")
                or any(81<=b.simulator_id<=144 for b in frame.bindings)):
            return frame
        cards=[c for c in frame.storage_state.blocks["deck"] if c["id"] is not None]
        slots=[i for i,c in enumerate(cards) if CARD_TYPES[str(c["id"])]=="SKILL"]
        rows=frame.choice_metadata["choices"]
        live=witness().describe(self._env)
        if (not live["active"] or live["steps"]!=frame.engine_steps or live["task"]!=7
                or live["selected"]!=0 or live["required"]!=1 or not 1<=len(slots)<=60
                or len(rows)!=len(slots) or live["count"]!=len(slots) or len(live["rows"])!=len(slots)):
            return frame
        deals=[]
        public={pos:i for i,pos in enumerate(slots)}
        for i,(row,physical) in enumerate(zip(rows,live["rows"],strict=True)):
            cid,up,pos=physical
            if (pos not in public or cards[pos]["id"]!=cid or cards[pos]["upgraded"]!=bool(up)
                    or not row["legal"] or not row["described"] or not frame.backend_mask[81+i]
                    or row["slot"]!=i or row["sim_action"]!=81+i or row["kind_name"]!="CARD"
                    or row["parameters"][:2]!=(cid+1,int(up))
                    or row["source_ref"]["container"]!="gc.info.toSelectCards.public_grid"):
                return frame
            deals.append((pos,i))
        if sorted(k for k,_ in deals)!=slots:
            return frame
        self.bottle_rows=tuple(sorted(deals,reverse=True))
        self._current=replace(frame,bindings=frame.bindings+tuple(ActionBinding(110+i,81+i,"shop_bottle_skill",i)
                                                                 for _,i in deals))
        return self._current
    source._capture=MethodType(capture,source)


class AdditionalMerchandise(CardShelf):
    def _shelf(self):
        frame=super()._shelf()
        v=self._parent.state.vector
        source=self._core._session._current
        if (source.engine_steps!=self._parent.engine_steps or v[5:9]!=(20,8,0,1) or not 0<v[22]<=60
                or source.packet_sha256!=source.choice_metadata.get("packet_sha256")):
            return frame
        held=set(v[32:112:2])-{0}
        if held & SPECIAL:
            return frame
        belt=v[17:17+int(v[16])]
        for i,potion in enumerate(belt):
            if potion and any(b.policy_id==105+i and b.simulator_id==75+i for b in source.bindings):
                self._commands[105+i]=("belt_discard",i)
        for index,(slot,row) in enumerate(shop_rows(v)):
            aid=110+index
            if not row[5]:
                continue
            item=source.choice_metadata["choices"][slot]
            if item["source_ref"]["container"]!="displayed_shop_slots" or item["slot"]!=slot or item["sim_action"]!=81+slot:
                continue
            available = any(b.operation=="shop_internal_slot" and b.simulator_id==81+slot and b.choice_row==slot
                            for b in source.bindings)
            if row[0]==3 and SOZU not in held and (0 not in belt or available):
                self._commands[aid]=("buy" if 0 in belt else "full_potions",slot)
            elif available and row[0]==11 and not (held & BOTTLES):
                self._commands[aid]=slot
            elif available and row[0]==2 and row[1] in (OMAMORI,FUNNEL,LIGHTNING) and row[1] not in held:
                if row[1]!=LIGHTNING or (not held & BOTTLES and any(
                        c["id"] is not None and CARD_TYPES[str(c["id"])]=="SKILL" for c in source.storage_state.blocks["deck"])):
                    self._commands[aid]=("relic",slot)
        mask=tuple(i in self._commands for i in range(len(frame.supported_actions)))
        expected={178}|{105+i for i,p in enumerate(belt) if p}|{
            110+j for j,(_,row) in enumerate(shop_rows(v)) if row[5]}
        complete=(set(self._commands)==expected and set(belt) <= BELT_DISCARD_ONLY|{0})
        self._current=replace(frame,supported_actions=mask,policy_mask=mask if complete else None,
                              action_gaps=() if complete else frame.action_gaps)
        return self._current

    def _bottle(self):
        source=self._core._session
        raw=source._current
        if not any(b.operation=="shop_bottle_skill" for b in raw.bindings):
            return self._publish("SHOP_BOTTLE_UNBOUND",self._parent.state.vector,{})
        items=source.bottle_rows
        v=self._parent.state.vector
        # The original getCardsOfType inserts each match at index zero (addToBottom).
        choices=[row_at(v,internal) for _,internal in items]
        return self._publish("SHOP_BOTTLE_SKILL",with_rows(v,choices,[203+pos for pos,_ in items]),
                             {110+j:("bottle",internal,pos) for j,(pos,internal) in enumerate(items)})

    def step(self,action_id,*,frame_id,action_version):
        with self._lock:
            op=self._commands.get(action_id) if isinstance(action_id,Integral) and not isinstance(action_id,bool) else None
            if not isinstance(op,tuple) or op[0] not in ("relic","bottle","full_potions","belt_discard"):
                return super().step(action_id,frame_id=frame_id,action_version=action_version)
            cur=self._current
            if cur is None or cur.frame_id!=frame_id or self.delegate._current is not self._parent:
                raise StaleFrameError("Shop decision expired")
            check(action_version==POLICY_VERSION,"Expected current shop action version")
            self.delegate._provider.peek()
            v=self._parent.state.vector
            if op[0]=="belt_discard":
                expected=list(v[17:22])
                expected[op[1]]=0
                old=self._parent
                self._current=None
                self._parent=self.delegate.step(105+op[1],frame_id=old.frame_id,action_version=old.action_version)
                post=self._parent.state.vector
                # Freeing a belt slot makes potions actionable in the backend. The
                # stock, identities and prices must remain identical, not the legal bits.
                old_stock=[row_at(v,i)[:5] for i in range(14)]
                new_stock=[row_at(post,i)[:5] for i in range(14)]
                check(post[:6]==v[:6] and post[6]==8 and list(post[17:22])==expected
                      and old_stock==new_stock and post[32:112]==v[32:112] and post[706:898]==v[706:898],
                      "Discard changed resources or stock")
                return self._shelf()
            if op[0]=="full_potions":
                check(0 not in v[17:17+int(v[16])],"Potion belt has room")
                return self._shelf()
            if op[0]=="bottle":
                post=self._execute(op[1]).state.vector
                actual=self._core._session._env
                from experiments.wing_removal_640.session import observer
                cards=observer().deck(actual)
                check(post[6]==8 and post[:3]==v[:3] and post[706:898]==v[706:898]
                      and [j for j,c in enumerate(cards) if c[3]]==[op[2]],"Wrong permanent skill bottled")
                return self._shelf()
            slot=op[1];row=row_at(v,slot)
            post=self._execute(slot).state.vector
            k=32+int(v[23])*2
            check(post[2]==v[2]-row[3] and post[706:898]==v[706:898] and post[17:22]==v[17:22]
                  and post[23]==v[23]+1 and post[32:k]==v[32:k] and post[k]==row[1],"Wrong relic or debit")
            if row[1]==LIGHTNING:
                check(post[6]==4 and post[26]==7,"Bottled Lightning should request one skill")
                return self._bottle()
            check(post[6]==8 and not row_at(post,slot)[0],"Purchased relic remained on sale")
            return self._shelf()


def install(engine):
    old=engine._inner
    check(type(old) is CardShelf and old._current is None and old.shop_page is None,"Expected unused ordinary card shop")
    shelf=AdditionalMerchandise(old)
    engine._inner=engine._legacy._delegate=shelf
    source=shelf._core._session
    engine._normal_shop_stack=(engine._legacy,shelf,source)
    bind_bottle(source,source._capture)
    return engine


class BottleObservation:
    """Publish the bottle's verified permanent-deck location while the relic is held."""
    def __init__(self,delegate,engine):
        self.delegate=delegate
        self.engine=engine
        self._observed=None

    def __getattr__(self,name):
        return getattr(self.delegate,name)

    def _publish(self,frame):
        legacy=self.engine._inner._current
        if (frame.page=="SHOP_SCREEN" and legacy and legacy.page==frame.page and legacy.policy_mask is not None
                and legacy.engine_steps==frame.engine_steps and not frame.action_gaps
                and [i for i,b in enumerate(frame.supported_actions) if b]==[i for i,b in enumerate(legacy.policy_mask) if b]):
            frame=replace(frame,policy_mask=frame.supported_actions)
        frame=self._bottle_reference(frame)
        self._observed=frame
        return frame

    def real_action_mask(self,*,frame_id):
        if self._observed is None or self._observed.frame_id!=frame_id:
            raise StaleFrameError("Expected latest inventory decision")
        return self._observed.policy_mask

    def _bottle_reference(self,frame):
        v=frame.state.vector
        if set(v[32:112:2]) & BOTTLES != {LIGHTNING} or v[3114]==2:
            return frame
        from experiments.wing_removal_640.session import current_deck
        deck=current_deck(self.engine)
        positions=[i for i,row in enumerate(deck) if row[3]]
        if len(positions)!=1 or len(deck)!=v[22]:
            return frame
        pos=positions[0]
        if (CARD_TYPES[str(deck[pos][0]-1)]!="SKILL"
                or any(row[:2]!=v[706+2*i:708+2*i] for i,row in enumerate(deck))):
            return frame
        values=v[:3114]+(2,0,pos+1,0)+v[3118:]
        return replace(frame,state=replace(frame.state,vector=values))

    def reset(self,*args,**kwargs):
        with self.delegate._lock:
            return self._publish(self.delegate.reset(*args,**kwargs))

    def reset_fixture(self,request):
        with self.delegate._lock:
            return self._publish(self.delegate.reset_fixture(request))

    def step(self,action,*,frame_id,action_version):
        with self.delegate._lock:
            return self._publish(self.delegate.step(action,frame_id=frame_id,action_version=action_version))
