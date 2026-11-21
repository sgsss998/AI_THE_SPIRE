"""Two receipted player commands after Spore Cloud and their subsequent public corpse display."""
from dataclasses import replace
from experiments.compact_transitions193 import TransitionSession
from experiments.ordinary_targeting193 import session as ordinary
from experiments.public_hand_fees.session import SUFFIX
from experiments.runtime_death_boundary import session as phase
from experiments.sa_calibration_round2 import release as r2
from experiments.sa_calibration_round2.boss.session import BossPages
from silent_env.interface import InterfaceMismatch

TAG='+r3-spore-receipts-v1'
PARTIAL='spore_followup_other_actions_unverified'
FUNGI=ordinary.MONSTERS['FUNGI_BEAST']+1
SPRAY=ordinary.CARDS['DAGGER_SPRAY']+1
STRIKE=ordinary.STRIKE
SPORES=37
VULNERABLE=911

def fresh_casualty(previous,v,action,rows,dead):
    before=ordinary.rows(previous.state.vector)[:len(rows)]
    u=previous.state.vector
    if (not isinstance(action,int) or not previous.supported_actions[action] or u[902]!=v[902]
            or u[VULNERABLE]!=0 or v[VULNERABLE]!=2 or any(r[1]<=0 for r in before)
            or before[dead][SPORES]!=2 or any(r[2]!=q[2] or r[0]!=q[0] for r,q in zip(before,rows))):
        return None
    face=u[1253+6*(action%10):1259+6*(action%10)]
    if (len(rows)==3 and dead==0 and action<10 and face[:2]==(SPRAY,0) and face[3:5]==(1,0)
            and v[901]==0 and all(a[1]-b[1]==8 for a,b in zip(before[1:],rows[1:]))
            and 0<before[0][1]<=8):
        return 170
    if (len(rows)==2 and dead==1 and 20<=action<30 and face[:2]==(STRIKE,0) and face[3:5]==(1,1)
            and rows[0][1]==before[0][1] and v[1253:1255]==(STRIKE,1) and v[1256:1258]==(1,1)):
        return 10
    return None


class DeathPages(BossPages):
    def _clear_memory(self):
        super()._clear_memory()
        self._spore_follow=None

    def _publish(self,frame):
        previous=self._source
        mark=self._spore_follow
        result=super()._publish(frame)
        self._spore_follow=None
        v=frame.state.vector
        raw=self._backing._source._current
        if (previous is not None and previous.page=='DELEGATED' and frame.page=='DELEGATED'
                and frame is self._parent._current and not frame.done and v[4:8]==(1,20,9,1)
                and previous.state.vector[3:8]==v[3:8] and not frame.action_gaps
                and raw is not None and raw is self._backing._raw and v==self._backing._current.state.vector
                and frame.engine_steps==raw.engine_steps==self._backing._current.engine_steps
                and frame.engine_steps==previous.engine_steps+1 and v[993:1253]==raw.raw_base[993:1253]):
            rows=[r for r in ordinary.rows(v) if r[0]]
            if (len(rows) in (2,3) and all(r[0]==FUNGI for r in rows)
                    and sum(r[1]==0 for r in rows)==1):
                result=self._follow(frame,previous,rows,mark,result)
        self._current=replace(result,state=replace(result.state,state_version=result.state.state_version.removesuffix(SUFFIX)+TAG+SUFFIX))
        return self._current

    def _follow(self,frame,previous,rows,prior,result):
        v=frame.state.vector
        w=ordinary.observer().inspect(self._backing._source._env)
        idx=next(j for j,r in enumerate(rows) if r[1]==0)
        if (w['steps']!=frame.engine_steps or not w['in_battle'] or not w['undecided'] or w['input']!=1
                or any(w[k] for k in ('queue','card_queue','over','end_queued','turn_ended','has_horn','has_specimen'))
                or len(w['rows'])!=len(rows) or w['physical_order']!=list(range(len(rows))) or w['alive']!=len(rows)-1
                or any(frame.supported_actions[i] for i in (*range(10+10*idx,20+10*idx),*range(75+5*idx,80+5*idx)))):
            return result
        for j,(m,r) in enumerate(zip(w['rows'],rows)):
            if (m['id']!='FUNGI_BEAST' or (m['hp'],m['max'],m['block'])!=r[1:4]
                    or m['escaping'] or m['half_dead'] or m['will_escape']
                    or m['targetable']!=(j!=idx) or set(m['powers'])-{'SPORE_CLOUD','STRENGTH'}
                    or m['powers'].get('SPORE_CLOUD')!=r[SPORES] or r[SPORES]!=2):
                return result
        if rows[idx][4:10]!=(1,0,0,0,0,0) or any(rows[idx][i] for i in range(10,52) if i!=SPORES):
            return result
        key=(v[3],tuple(r[2] for r in rows),idx)
        if prior and prior[0]==key and prior[1]==self._last_action:
            # Both archived successors have an empty dead object's power list.
            vector=list(result.state.vector);vector[993+52*idx+SPORES]=0
            return replace(result,state=replace(result.state,vector=tuple(vector)))
        aid=fresh_casualty(previous,v,self._last_action,rows,idx)
        if aid is None or self.phase!=phase.UNKNOWN or not frame.supported_actions[aid]:
            return result
        raw=self._backing._source._current
        bindings=[b for b in raw.bindings if b.policy_id==aid]
        eid=80 if aid==170 else 5*raw.hand_order.remaining[0]
        if (len(bindings)!=1 or bindings[0].operation!='fixed' or bindings[0].simulator_id!=eid
                or not self._backing._source._env.is_valid(eid)):
            return result
        self.phase=phase.CLEAR
        self._spore_follow=(key,aid)
        return replace(result,supported_actions=tuple(i==aid for i in range(193)),policy_mask=None,action_gaps=(PARTIAL,))


def attach(owner):
    node=owner
    seen=set()
    while not isinstance(node,TransitionSession):
        if id(node) in seen:raise InterfaceMismatch('Cyclic facade')
        seen.add(id(node))
        fields=vars(node)
        node=fields.get('delegate',fields.get('base'))
        if node is None:raise InterfaceMismatch('Missing R2 transition owner')
    if type(node.pages) is not BossPages or node._frame is not None or node.pages._current is not None:
        raise InterfaceMismatch('Expected a fresh R2 death owner')
    node.pages=DeathPages(delegate=node.pages._parent,backing=node.backing)
    return owner


def make_engine():return r2.make_engine()

def make_session(engine=None):return attach(r2.make_session(engine))
