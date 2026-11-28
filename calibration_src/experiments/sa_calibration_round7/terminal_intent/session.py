"""At an observed single-enemy lethal turn keep its announced attack on the game-over screen."""
from dataclasses import replace
from silent_env.observation import schema

ENUMS = schema()["enums"]
ATTACKS = {value+1 for name,value in ENUMS["Intent"].items() if name.startswith("ATTACK")}
LOSS = ENUMS["GameOutcome"]["PLAYER_LOSS"]
MONSTER = 993
WIDTH = 52


def published_intent(before, action, after):
    if before is None or action != 170 or not after.done or before.done:
        return after
    old, new = before.state.vector, after.state.vector
    if (not before.supported_actions[170] or after.engine_steps!=before.engine_steps+1
            or old[0]<=0 or new[0]!=0 or new[31]!=LOSS or any(after.supported_actions)
            or old[3:10]!=new[3:10] or old[6:8]!=(9,1) or old[902]!=new[902]):
        return after
    old_slots = [i for i in range(MONSTER,MONSTER+5*WIDTH,WIDTH) if old[i]]
    new_slots = [i for i in range(MONSTER,MONSTER+5*WIDTH,WIDTH) if new[i]]
    if len(old_slots)!=1 or old_slots!=new_slots:
        return after
    i = old_slots[0]
    if (old[i]!=new[i] or old[i+2]!=new[i+2] or old[i+1]<=0 or new[i+1]<=0
            or old[i+4:i+7]!=(0,0,1) or new[i+4:i+7]!=(0,0,1) or old[i+7] not in ATTACKS
            or old[i+8]*old[i+9] < old[0]+old[900]):
        return after
    values = new[:i+7]+old[i+7:i+10]+new[i+10:]
    return replace(after,state=replace(after.state,vector=values))


class TerminalIntent:
    def __init__(self, delegate):
        self.delegate = delegate
        self._latest = None

    def __getattr__(self,name):
        return getattr(self.delegate,name)

    def reset(self,*args,**kwargs):
        with self.delegate._lock:
            self._latest = self.delegate.reset(*args,**kwargs)
            return self._latest

    def reset_fixture(self, request):
        with self.delegate._lock:
            self._latest = self.delegate.reset_fixture(request)
            return self._latest

    def step(self,action,*,frame_id,action_version):
        with self.delegate._lock:
            before=self._latest
            after=self.delegate.step(action,frame_id=frame_id,action_version=action_version)
            self._latest=published_intent(before,action,after)
            return self._latest
