"""The original campfire has two distinct Cancel actions before a smith choice is committed."""
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments.hand_binding_v3.model_env import _model_frame
from experiments.public_shop.session import check
from silent_env.policy_actions import POLICY_VERSION
from silent_env.runtime import StaleFrameError
from ..death_family.thief_rewards.observation.build import build
from ..shop_door.session import Room


@lru_cache(maxsize=1)
def rule():
    with TemporaryDirectory() as output:
        return build(output,Path(__file__).with_name("cancel.cpp"),"_r7_cancel_smith")


class SmithRoom(Room):
    def _render(self):
        frame=super()._render()
        page=self._page
        if (getattr(self,"_smith_origin",None) is not None and page and page.source_kind=="rest"
                and page.grid.task=="upgrade" and frame.page in ("GRID","GRID_CONFIRM")
                and frame.state.vector[17:22]==(0,)*5):
            mask=list(frame.supported_actions)
            mask[173]=True
            mask=tuple(mask)
            self._current=replace(frame,supported_actions=mask,policy_mask=mask,action_gaps=())
        return self._current

    def step(self,action_id,*,frame_id,action_version):
        with self._lock:
            f=self._current
            if f is not None and f.frame_id==frame_id and f.page=="DELEGATED" and action_id==111:
                v=f.state.vector
                if v[6:9]==(7,0,2) and v[17:22]==(0,)*5 and f.supported_actions[111] and v[328:330]==(10,1):
                    self._smith_origin=self._core._session._env.clone(),f
            if (f is not None and f.page=="GRID" and action_id==173 and f.supported_actions[173]
                    and self._page and self._page.source_kind=="rest" and self._page.grid.pending is None):
                if f.frame_id!=frame_id or self.delegate._current is not self._parent:
                    raise StaleFrameError("Old campfire decision")
                check(action_version==POLICY_VERSION,"Expected current campfire action coordinates")
                self.delegate._provider.peek()
                old,opening=self._smith_origin
                source=self._core._session
                rule().return_to_fire(source._env,old)
                self._smith_origin=None
                raw=source._capture()
                self._core._current=_model_frame(raw)
                out=self._sync(self.delegate._capture(self._core._current))
                p,q=opening.state.vector,out.state.vector
                check(out.page==opening.page and out.supported_actions==opening.supported_actions
                      and p[:322]==q[:322] and p[322:898]==q[322:898],
                      "Cancel failed to return to the original campfire with the same options and resources")
                return out
            result=super().step(action_id,frame_id=frame_id,action_version=action_version)
            if result.page not in ("GRID","GRID_CONFIRM"):
                self._smith_origin=None
            return result

    def reset(self,*args,**kwargs):
        self._smith_origin=None
        return super().reset(*args,**kwargs)

    def reset_fixture(self,*args,**kwargs):
        self._smith_origin=None
        return super().reset_fixture(*args,**kwargs)


def install(engine):
    old=engine._inner
    check(type(old) is Room and old._current is None,"Install on an unused versioned inventory")
    room=SmithRoom(old)
    engine._inner=engine._legacy._delegate=room
    engine._normal_shop_stack=(engine._legacy,room,room._core._session)
    return engine
