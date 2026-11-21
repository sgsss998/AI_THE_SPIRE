"""Present the Wheel's full-heal prize and settle it exactly when accepted."""
from dataclasses import replace
from functools import lru_cache
from numbers import Integral
from pathlib import Path
from uuid import uuid4

from experiments.action193_grid.session import permitted
from experiments.policy_event_integration.session import load_extension
from silent_env.interface import InterfaceMismatch
from silent_env.observation import schema
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError

BUILD=Path(__file__).resolve().parent/'build/BUILD.json'
PIN='d5fe7fbd23f645b598c011a5fcef587e7809fc06335e72eb58baa332359b0b80'
WHEEL=schema()['enums']['Event']['WHEEL_OF_CHANGE']+1

@lru_cache(maxsize=1)
def observer():
    return load_extension(BUILD,PIN)

class WheelSession:
    def __init__(self, engine, delegate):
        self.engine,self.delegate,self._lock=engine,delegate,delegate._lock
        self.current=self.parent=self.offer=None
    def __getattr__(self,name):
        return getattr(self.delegate,name)
    def show(self,frame):
        self.current=self.parent=frame
        self.offer=None
        return frame
    def reset(self,*args,**kw):
        with self._lock:
            return self.show(self.delegate.reset(*args,**kw))
    def reset_fixture(self,*args,**kw):
        with self._lock:
            return self.show(self.delegate.reset_fixture(*args,**kw))
    def display(self,prize):
        base=self.parent
        v=list(base.state.vector)
        v[6:12]=self.offer.state.vector[6:12]
        v[322:706]=[8,0,0,0,0,1]+[0]*378
        v[1769]=1
        v[2683:2748]=[2]+[0]*64
        v[2968:3114]=[2,1 if prize else 2]+[0]*144
        if prize:
            v[2970]=8
            v[2974]=int(v[1]-v[0])
        controls=permitted((110,))
        full=not any(v[17:17+int(v[16])])
        self.current=replace(base,frame_id=str(uuid4()),page='WHEEL_HEAL_PRIZE' if prize else 'WHEEL_HEAL_LEAVE',
                state=replace(base.state,vector=tuple(v)),supported_actions=controls,
                policy_mask=controls if full else None,action_gaps=() if full else ('wheel_potion_choices_unverified',))
        return self.current
    def step(self,action,*,frame_id,action_version):
        with self._lock:
            cur=self.current
            if cur is None or cur.frame_id!=frame_id:raise StaleFrameError('Wheel frame expired')
            if cur.action_version!=action_version:raise InterfaceMismatch('Wheel action interface changed')
            if isinstance(action,bool) or not isinstance(action,Integral) or not 0<=action<len(cur.supported_actions) or not cur.supported_actions[action]:
                raise UnverifiedSemanticsError('Action not listed on current page')
            if cur.page=='WHEEL_HEAL_LEAVE':
                return self.show(self.parent)
            if cur.page=='WHEEL_HEAL_PRIZE':
                self.current=None
                self.parent=self.delegate.step(action,frame_id=self.parent.frame_id,action_version=action_version)
                return self.display(False)
            v=cur.state.vector
            if (action==110 and v[4:10]==(1,20,1,0,3,WHEEL)
                    and observer().heal_pending(self.engine._source._env,cur.engine_steps)):
                self.offer=cur
                return self.display(True)
            self.current=None
            return self.show(self.delegate.step(action,frame_id=cur.frame_id,action_version=action_version))

def wrap(engine,delegate):
    return WheelSession(engine,delegate)
