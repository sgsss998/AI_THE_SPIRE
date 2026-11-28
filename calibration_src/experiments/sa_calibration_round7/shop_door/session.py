"""Expose native belt discards on the shop-room page without opening the shelf."""
from dataclasses import replace
from numbers import Integral

from experiments.public_shop.session import check, row_at
from silent_env.policy_actions import POLICY_VERSION
from silent_env.runtime import StaleFrameError
from ..shop_extra.session import AdditionalMerchandise, BELT_DISCARD_ONLY


class Room(AdditionalMerchandise):
    def _door(self):
        frame = super()._door()
        parent = self._parent
        raw = self._core._session._current
        v = parent.state.vector
        if (raw.engine_steps != parent.engine_steps or parent.done or v[5:9] != (20,8,0,1)
                or not 0 < v[16] <= 5):
            return frame
        belt = v[17:17+int(v[16])]
        for i, item in enumerate(belt):
            if item and raw.backend_mask[75+i] and any((b.policy_id,b.simulator_id)==(105+i,75+i) for b in raw.bindings):
                self._commands[105+i] = ("room_discard",i)
        expected = {110,171} | {105+i for i,item in enumerate(belt) if item}
        complete = set(self._commands)==expected and set(belt)<=BELT_DISCARD_ONLY|{0}
        mask = tuple(i in self._commands for i in range(len(frame.supported_actions)))
        self._current = replace(frame,supported_actions=mask,policy_mask=mask if complete else None,
            action_gaps=() if complete else frame.action_gaps)
        return self._current

    def step(self,action_id,*,frame_id,action_version):
        with self._lock:
            op = self._commands.get(action_id) if isinstance(action_id,Integral) and not isinstance(action_id,bool) else None
            if not isinstance(op,tuple) or op[0]!="room_discard":
                return super().step(action_id,frame_id=frame_id,action_version=action_version)
            current = self._current
            if current is None or current.frame_id!=frame_id or self.delegate._current is not self._parent:
                raise StaleFrameError("Shop room changed before discard")
            check(action_version==POLICY_VERSION,"Expected current shop action version")
            self.delegate._provider.peek()
            before = self._parent
            belt = list(before.state.vector[17:22])
            belt[op[1]] = 0
            self._current = None
            self._parent = self.delegate.step(action_id,frame_id=before.frame_id,action_version=before.action_version)
            v,w = before.state.vector,self._parent.state.vector
            check(v[:17]==w[:17] and list(w[17:22])==belt and v[22:112]==w[22:112]
                  and v[706:898]==w[706:898] and all(row_at(v,i)[:5]==row_at(w,i)[:5] for i in range(14)),
                  "Discard changed shop inventory, wallet or deck")
            return self._door()


def install(engine):
    old=engine._inner
    check(type(old) is AdditionalMerchandise and old._current is None and old.shop_page is None,"Install on a fresh ordinary shop")
    room = Room(old)
    engine._inner = engine._legacy._delegate = room
    engine._normal_shop_stack = (engine._legacy,room,room._core._session)
    return engine
