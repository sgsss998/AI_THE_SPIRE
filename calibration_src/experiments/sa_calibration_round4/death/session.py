"""Additional measured decisions for a single spore casualty in a two-fungus fight."""
from dataclasses import replace
from experiments.sa_calibration_round3.death import session as r3

PARTIAL = "spore_strike_or_end_other_actions_unverified"
STRENGTH = 21

def strike_follow(frame, previous, rows, dead, action):
    """A normal Strike killed the displayed slot. Bind one evidenced follow-up."""
    if not isinstance(action,int) or not 10+dead*10 <= action < 20+dead*10:
        return None
    old = previous.state.vector
    v = frame.state.vector
    before = r3.ordinary.rows(old)[:2]
    if (not previous.supported_actions[action] or old[r3.VULNERABLE] != 0 or v[r3.VULNERABLE] != 2
            or old[902] != v[902] or old[901] != v[901]+1
            or any(row[0] != r3.FUNGI or row[1] <= 0 for row in before)
            or any(prior[2] != current[2] for prior,current in zip(before,rows))
            or before[dead][r3.SPORES] != 2 or before[1-dead][1:4] != rows[1-dead][1:4]):
        return None
    i = 1253+6*(action%10)
    if old[i:i+5] != (r3.STRIKE,0,1,1,1):
        return None
    if dead == 1 and v[901] == 0:
        return 170
    if dead == 0:
        for slot in range(10):
            i=1253+6*slot
            if v[i:i+5] == (r3.STRIKE,0,1,1,1) and frame.supported_actions[20+slot]:
                return 20+slot
    return None


class DeathPages(r3.DeathPages):
    def _clear_memory(self):
        super()._clear_memory()
        self._r4_terminal = None

    def _publish(self,frame):
        terminal = self._r4_terminal
        self._r4_terminal = None
        result = super()._publish(frame)
        if terminal and self._last_action == 170 and result.done and self._backing._source._env.lost:
            previous_step, floor, dead, maxima = terminal
            rows = r3.ordinary.rows(result.state.vector)
            v = result.state.vector
            if (result.engine_steps == previous_step + 1 and v[0] == 0 and v[3] == floor
                    and all(row[0] == r3.FUNGI and row[2] == maximum for row,maximum in zip(rows,maxima))
                    and rows[dead][1] == 0 and rows[1-dead][1] > 0):
                # The killing enemy turn ended the run and the original corpse now had no powers.
                vector = list(v)
                vector[993 + 52*dead + STRENGTH] = 0
                vector[993 + 52*dead + r3.SPORES] = 0
                result = replace(result,state=replace(result.state,vector=tuple(vector)))
                self._current = result
        return result

    def _follow(self,frame,previous,rows,prior,result):
        result = super()._follow(frame,previous,rows,prior,result)
        if self.phase != r3.phase.UNKNOWN or len(rows) != 2 or any(result.supported_actions):
            return result
        dead=next(i for i,r in enumerate(rows) if r[1]==0)
        aid=strike_follow(frame,previous,rows,dead,self._last_action)
        if aid is None or not frame.supported_actions[aid]:
            return result
        w=r3.ordinary.observer().inspect(self._backing._source._env)
        if (w['steps']!=frame.engine_steps or not w['in_battle'] or not w['undecided'] or w['input']!=1
                or any(w[k] for k in ('queue','card_queue','over','end_queued','turn_ended','has_horn','has_specimen'))
                or w['alive']!=1 or w['physical_order']!=[0,1] or len(w['rows'])!=2):
            return result
        for slot,(m,row) in enumerate(zip(w['rows'],rows)):
            if (m['id']!='FUNGI_BEAST' or m['targetable']!=(slot!=dead) or m['half_dead'] or m['escaping'] or m['will_escape']
                    or (m['hp'],m['max'],m['block'])!=row[1:4] or set(m['powers'])-{'SPORE_CLOUD','STRENGTH'}
                    or row[r3.SPORES]!=2 or m['powers'].get('SPORE_CLOUD')!=2 or m['powers'].get('STRENGTH',0)!=row[STRENGTH]):
                return result
        r=rows[dead]
        if (r[4:10]!=(1,0,0,0,0,0) or any(r[i] for i in range(10,52) if i not in (STRENGTH,r3.SPORES))
                or any(frame.supported_actions[i] for i in (*range(10+10*dead,20+10*dead),*range(75+5*dead,80+5*dead)))):
            return result
        raw=self._backing._source._current
        bindings=[b for b in raw.bindings if b.policy_id==aid]
        eid=80 if aid==170 else 5*raw.hand_order.remaining[aid%10]+1-dead
        if len(bindings)!=1 or bindings[0].operation!='fixed' or bindings[0].simulator_id!=eid or not self._backing._source._env.is_valid(eid):
            return result
        self.phase=r3.phase.CLEAR
        if aid == 170:
            self._r4_terminal = (frame.engine_steps,frame.state.vector[3], dead, tuple(row[2] for row in rows))
        # Seed 59 still displayed both corpse powers at the immediate receipt.
        # R3's unconditional next-frame clearing belongs only to its two R3 witnesses.
        return replace(result,supported_actions=tuple(i==aid for i in range(193)),policy_mask=None,action_gaps=(PARTIAL,))


def attach(owner):
    node=owner
    seen=set()
    while not isinstance(node,r3.TransitionSession):
        if id(node) in seen:
            raise r3.InterfaceMismatch('Cyclic facade')
        seen.add(id(node))
        node=vars(node).get('delegate',vars(node).get('base'))
        if node is None:
            raise r3.InterfaceMismatch('Missing transition owner')
    if type(node.pages) not in (r3.DeathPages,r3.BossPages) or node._frame is not None or node.pages._current is not None:
        raise r3.InterfaceMismatch('Expected a fresh R2/R3 death owner')
    node.pages=DeathPages(delegate=node.pages._parent,backing=node.backing)
    return owner
