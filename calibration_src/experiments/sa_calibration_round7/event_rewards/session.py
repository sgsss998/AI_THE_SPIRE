"""Reward rows opened by the Lab, Woman in Blue, and Gremlin Wheel."""
from uuid import uuid4
from experiments.reward_ui_adapter.adapter import Exit,Frame,RewardView,Unsupported,require
from experiments.sa_calibration_round7.event_results import session as events
from silent_env.action193 import POLICY_VERSION
from silent_env.runtime import StaleFrameError

EVENTS=events.schema()['enums']['Event']
LAB=EVENTS['LAB']+1
WOMAN=EVENTS['THE_WOMAN_IN_BLUE']+1
WHEEL=EVENTS['WHEEL_OF_CHANGE']+1
SOZU=events.relic_id('SOZU')
LEAVE=6
POTION=3
RELIC=2
STRAWBERRY=events.DIRECT_HP
IMMEDIATE={**events.CHARGES,**{k:0 for k in STRAWBERRY}}
IMMEDIATE.pop(events.relic_id('WHETSTONE'),None)


def entry(before,after,action):
    if (before is None or after.done or before.done or before.engine_steps+1!=after.engine_steps):
        return None
    v,w=before.state.vector,after.state.vector
    id=v[9]
    if not (id in (LAB,WOMAN,WHEEL) and v[3]>0 and v[4:9]==(1,20,1,0,3)
            and w[3:10]==v[3:6]+(2,0,3,0) and v[10:26]==w[10:26]
            and v[32:112]==w[32:112] and v[706:898]==w[706:898]):
        return None
    slot=action-81
    if id==WOMAN and slot in (0,1,2):
        count=1+slot
        price=(20,30,40)[slot]
        kind=POTION
    elif id in (LAB,WHEEL) and slot==0:
        count=2 if id==LAB else 1
        price=0
        kind=POTION if id==LAB else RELIC
    else:
        return None
    if v[2]<price or w[:3]!=(v[0],v[1],v[2]-price):
        return None
    return kind,count


def rows(provider,p):
    raw=provider.backend._current
    b=p.base
    require(raw is not None and len(raw.packet_sha256)==64 and raw.packet_sha256==raw.choice_metadata['packet_sha256']
            and raw.engine_steps==p.step_count and raw.raw_base==b and not p.event and b[6:9]==(2,0,3),
            'Missing source event reward frame')
    parsed=[]
    choices=raw.choice_metadata['choices']
    require(1<=len(choices)<=4 and not any(b[322+6*len(choices):706])
            and not any(p.mask146[81+len(choices):]),'Invalid event reward extent')
    for i,item in enumerate(choices):
        j=322+6*i
        r=b[j:j+6]
        k,n=int(r[0]),int(r[1])
        ref=item['source_ref']
        require(k in (POTION,RELIC,LEAVE) and item['kind']==k and item['kind_name']=={POTION:'POTION',RELIC:'RELIC',LEAVE:'SKIP'}[k]
                and item['slot']==ref['public_slot']==i and ref['container']=='displayed_reward_actions'
                and ref['base_offset']==j and item['sim_action']==81+i and item['described']
                and item['parameters']==r[1:5] and r[2:5]==(0,0,0) and r[5]==p.mask146[81+i]==item['legal']
                and ((k==LEAVE and n==0 and r[5]) or (k!=LEAVE and n>0)), 'Reward lost its physical binding')
        if k==POTION:
            require(2<n<=len(provider.backend._backend.POTION_NAMES),'Unknown potion')
        parsed.append((k,n,bool(r[5])))
    require(parsed[-1]==(LEAVE,0,True) and all(r[0]!=LEAVE for r in parsed[:-1]),'Missing proceed')
    return tuple(parsed)


class EventRewards:
    def __init__(self,provider,core,expected):
        self.provider=provider
        self.core=core
        self.packet=provider.peek()
        self.rows=rows(provider,self.packet)
        kind,count=expected
        require(len(self.rows)==count+1 and all(r[0]==kind for r in self.rows[:-1]),'Incorrect event reward quantities')
        self.active=True
        self.token=None
        self._publish()

    def _publish(self):
        b=list(self.packet.base)
        self.token=uuid4().hex
        self._actions={}
        unknown=[]
        b[322:706]=[0]*384
        held={w for w,_ in events.relics(b)}
        belt=b[17:17+int(b[16])]
        core=self.core._current
        binds={(x.policy_id,x.simulator_id) for x in core.action_bindings}
        for i,n in enumerate(belt):
            if n and (105+i,75+i) in binds and self.packet.mask146[75+i]:
                self._actions[105+i]=('discard',75+i)
            if n:
                unknown.append(70+i)
        for i,(k,n,opened) in enumerate(self.rows):
            if k==LEAVE:
                self._actions[171]=('proceed',81+i)
                continue
            action=110+i
            if k==POTION:
                available=opened and 0 in belt and SOZU not in held
            else:
                available=opened and n in IMMEDIATE and n not in held and b[23]<40
            b[322+6*i:328+6*i]=[k,n,0,0,0,int(available)]
            if available:
                self._actions[action]=('potion' if k==POTION else 'relic',81+i)
            else:
                unknown.append(action)
        mask=tuple(i in self._actions for i in range(189))
        self.view=Frame(self.token,RewardView(tuple(b),mask,'COMBAT_REWARD',tuple(unknown)))

    def frame(self):
        require(self.active,'Expired event reward')
        return self.view

    def step(self,action,*,token):
        if not self.active or token!=self.token or self.provider.peek()!=self.packet:
            raise StaleFrameError('Expired event reward')
        require(action in self._actions,'Unknown event reward button')
        effect,index=self._actions[action]
        old=self.packet
        self.active=False
        if effect=='discard':
            origin=self.core._current
            self.core.step(action,frame_id=origin.frame_id,action_version=origin.action_version)
            new=self.provider.peek()
        else:
            new=self.provider.step(index)
        a,b=old.base,new.base
        require(new.step_count==old.step_count+1 and a[3:6]==b[3:6] and a[706:898]==b[706:898],
                'Unexpected event reward floor or deck')
        expected=list(a[:112])
        if effect=='proceed':
            require(b[6:8]==(5,0) and a[:6]==b[:6] and a[10:26]==b[10:26] and a[32:112]==b[32:112],
                    'Leaving event rewards changed inventory')
            return Exit()
        rest=self.rows
        if effect=='discard':
            expected[17+action-105]=0
        else:
            row=index-81
            k,n,_=self.rows[row]
            rest=self.rows[:row]+self.rows[row+1:]
            if effect=='potion':
                slot=list(a[17:17+int(a[16])]).index(0)
                expected[17+slot]=n
            else:
                j=32+2*int(a[23])
                expected[23]+=1
                expected[j:j+2]=[n,IMMEDIATE[n]]
                increase=STRAWBERRY.get(n,0)
                expected[0]+=increase
                expected[1]+=increase
        after=rows(self.provider,new)
        require(tuple(expected)==b[:112] and [r[:2] for r in after]==[r[:2] for r in rest],
                'Wrong event reward amount, item, slot or remaining rows')
        self.packet,self.rows,self.active=new,after,True
        self._publish()
        return self.frame()


class EventRewardMixin:
    def _capture(self,source):
        t=self._transition
        if t and self._reward is None:
            expected=entry(self._prior,source,t[1])
            if expected:
                try:
                    self._reward=EventRewards(self._provider,self._delegate,expected)
                except Unsupported:
                    pass
        return super()._capture(source)
