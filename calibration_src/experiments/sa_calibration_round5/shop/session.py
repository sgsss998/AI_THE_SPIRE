"""Bind supported merchandise to the current shelf and confirm the paid item."""
from dataclasses import replace
from types import MethodType
from numbers import Integral

from experiments.public_shop.session import check,shop_rows,row_at,deck_rows,with_rows
from experiments.policy_grid_integration.session import monotone_bind
from experiments.common_relic193.rules import relic_id
from experiments.shop_progress193.session import ShopInner
from silent_env.observation import schema
from silent_env.canonical_choices import ActionBinding
from silent_env.runtime import StaleFrameError
from silent_env.policy_actions import POLICY_VERSION

MIRROR=relic_id('DOLLYS_MIRROR')
RING=relic_id('RING_OF_THE_SNAKE')
POTIONS={schema()['enums']['Potion'][x]+1 for x in ('FLEX_POTION','FEAR_POTION','WEAK_POTION')}

def eligible(v):
    return v[4:10]==(1,20,8,0,1,0) and int(v[16])==2 and tuple(v[32:32+int(v[23])*2:2]) in ((RING,),(RING,MIRROR))

class Merchandise(ShopInner):
    def __init__(self,old):
        self._core,self.delegate,self._lock=old._core,old.delegate,old._lock
        self._current=self._parent=self._page=self._result_action=None
        self._shop_reset()

    def _shelf(self):
        frame=super()._shelf()
        v=self._parent.state.vector
        if not eligible(v):return frame
        cap=int(v[16]); vacancy=0 in v[17:17+cap]
        source=self._core._session._current
        for i,potion in enumerate(v[17:17+cap]):
            aid=105+i
            if potion in POTIONS and any(b.policy_id==aid and b.simulator_id==75+i for b in source.bindings):
                self._commands[aid]=('discard',i)
        rows=shop_rows(v)
        for idx,(slot,row) in enumerate(rows):
            if not row[5] or not source.backend_mask[81+slot]:continue
            if slot<7 and v[22]<60 and MIRROR in v[32:32+int(v[23])*2:2]:
                self._commands[110+idx]=slot
            if row[0]==3 and row[1] in POTIONS and vacancy or row[0]==2 and row[1]==MIRROR and int(v[22])<=59:
                self._commands[110+idx]=('buy',slot)
        # Retail lists affordable merchandise even when a full belt will reject the sale.
        public=list(frame.state.vector)
        public[1769]=sum(int(row[5]) for _,row in rows)
        self._current=replace(frame,state=replace(frame.state,vector=tuple(public)),
                              supported_actions=tuple(i in self._commands for i in range(len(frame.supported_actions))))
        return self._current

    def _mirror(self):
        src=self._core._session._current
        picks=src.choice_metadata['choices']
        v=self._parent.state.vector
        deck=deck_rows(src)
        copies=tuple((int(row['parameters'][0])-1,int(row['parameters'][1])) for row in picks)
        self._mirror_slots=monotone_bind(deck,copies)
        check(self._mirror_slots is not None and len(picks)<=60, 'Mirror choices do not bind to the permanent deck')
        refs=self._mirror_slots
        rows=[row_at(v,i) for i in range(len(refs))]
        commands={110+i:('duplicate',i) for i in range(len(refs))}
        return self._publish('SHOP_MIRROR_SELECT',with_rows(v,rows,[203+x for x in refs]),commands)

    def step(self,action_id,*,frame_id,action_version):
        with self._lock:
            op=self._commands.get(action_id) if isinstance(action_id,Integral) and not isinstance(action_id,bool) else None
            if not isinstance(op,tuple) or op[0] not in ('buy','duplicate','discard'):
                return super().step(action_id,frame_id=frame_id,action_version=action_version)
            cur=self._current
            if cur is None or cur.frame_id!=frame_id:raise StaleFrameError('Shop receipt expired')
            check(action_version==POLICY_VERSION and self.delegate._current is self._parent,'Shop frame or action version changed')
            self.delegate._provider.peek()
            v=self._parent.state.vector
            pos=op[1]
            if op[0]=='discard':
                parent=self._parent
                self._current=None
                self._parent=self.delegate.step(105+pos,frame_id=parent.frame_id,action_version=parent.action_version)
                p=self._parent.state.vector
                expected=list(v[17:22]);expected[pos]=0
                check(p[6]==8 and p[2]==v[2] and list(p[17:22])==expected and p[322:706]==v[322:706],
                      'Discard should change only the occupied player slot')
                return self._shelf()
            if op[0]=='duplicate':
                deck=v[706:706+2*int(v[22])]
                ref=self._mirror_slots[pos];card=deck[2*ref:2*ref+2]
                p=self._execute(pos).state.vector
                check(p[2]==v[2] and p[22]==v[22]+1 and p[706:708+len(deck)]==deck+card,'Mirror copy differs')
                return self._shelf()
            row=row_at(v,pos)
            p=self._execute(pos).state.vector
            check(p[2]==v[2]-row[3] and p[706:898]==v[706:898], 'Invalid shop debit or deck change')
            if row[0]==2:
                k=32+int(v[23])*2
                check(p[6]==4 and p[26]==5 and p[23]==v[23]+1 and p[32:k]==v[32:k] and p[k]==MIRROR,'Mirror was not obtained')
                return self._mirror()
            expected=list(v[17:17+int(v[16])]);expected[expected.index(0)]=row[1]
            check(p[6]==8 and list(p[17:17+int(v[16])])==expected and not row_at(p,pos)[0], 'Potion stock or bottle changed')
            return self._shelf()

def install(engine):
    old=engine._inner
    check(type(old) is ShopInner and old._current is None,'Shop adapter must attach before reset')
    inner=Merchandise(old)
    engine._inner=engine._legacy._delegate=inner
    source=inner._core._session
    engine._normal_shop_stack=(engine._legacy,inner,source)
    previous_capture=source._capture
    def capture(instance):
        f=previous_capture()
        g=f.storage_state.blocks['global'][0]
        if not (g['screen']==4 and g['room']==0 and g['selection_task']==5 and g['selection_required']==1
                and g['selection_count']==0 and any(r['id']==MIRROR-1 for r in f.storage_state.blocks['relics'])):return f
        choices=f.choice_metadata['choices']
        check(not any(81<=b.simulator_id<=144 for b in f.bindings) and f.packet_sha256==f.choice_metadata['packet_sha256'],'Unbound mirror packet required')
        binds=[]
        for i,r in enumerate(choices):
            check(r['slot']==i and r['kind_name']=='CARD' and r['sim_action']==81+i and r['legal'] and f.backend_mask[81+i],'Invalid mirror slot')
            binds.append(ActionBinding(110+i,81+i,'shop_bound_mirror_choice',i))
        instance._current=replace(f,bindings=f.bindings+tuple(binds))
        return instance._current
    source._capture=MethodType(capture,source)
