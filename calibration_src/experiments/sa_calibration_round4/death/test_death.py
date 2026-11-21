"""Only release the spore follow-up at the observed physical combat boundary."""
from types import SimpleNamespace
import pytest
from experiments.sa_calibration_round4.death import session
from experiments.sa_calibration_round4.death.live import source
from experiments.sa_calibration_round4 import release


@pytest.mark.parametrize("seed,action", [(59,23),(19,170)])
def test_observed_followup(seed,action):
    actions,_=source(seed)
    owner=release.make_session()
    frame=owner.reset(seed)
    for aid in actions:
        frame=owner.step(aid,frame_id=frame.frame_id,action_version=frame.action_version)
    assert [i for i,b in enumerate(frame.supported_actions) if b]==[action]
    result=owner.step(action,frame_id=frame.frame_id,action_version=frame.action_version)
    assert result.engine_steps==frame.engine_steps+1
    if seed==19:
        assert result.done and result.state.vector[0]==0
        assert [result.state.vector[1045+i] for i in (21,37)]==[0,0]
        assert [result.state.vector[993+i] for i in (21,37)]==[5,2]
    else:
        assert not result.done and result.state.vector[1046]==16
        assert [result.state.vector[993+i] for i in (21,37)]==[5,2]


@pytest.mark.parametrize("fault", ["physical_order","queue","dead_targetable","half_dead","step"])
def test_ambiguous_observer_keeps_stop(monkeypatch,fault):
    actions,_=source(59)
    owner=release.make_session()
    frame=owner.reset(59)
    for aid in actions[:-1]:
        frame=owner.step(aid,frame_id=frame.frame_id,action_version=frame.action_version)
    observer=session.r3.ordinary.observer()
    def inspect(engine):
        reading=observer.inspect(engine)
        if fault=="physical_order":reading["physical_order"]=[1,0]
        elif fault=="queue":reading["queue"]+=1
        elif fault=="dead_targetable":reading["rows"][0]["targetable"]=True
        elif fault=="half_dead":reading["rows"][0]["half_dead"]=True
        elif fault=="step":reading["steps"]-=1
        return reading
    monkeypatch.setattr(session.r3.ordinary,"observer",lambda:SimpleNamespace(inspect=inspect))
    f=owner.step(actions[-1],frame_id=frame.frame_id,action_version=frame.action_version)
    assert not any(f.supported_actions) and 'death_boundary_unknown' in f.action_gaps
