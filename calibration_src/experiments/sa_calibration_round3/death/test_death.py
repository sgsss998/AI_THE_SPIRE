from types import SimpleNamespace
import json
import pytest
from silent_env.runtime import StaleFrameError,UnverifiedSemanticsError
from experiments.sa_calibration_round3.death import anchors,cohort,session
from experiments.sa_calibration_round3.death.split import split_markers

@pytest.mark.parametrize('seed,path,k,action',((anchors.triple.SEED,anchors.triple.ARCHIVE,335,170),
                                               (anchors.probe.SEED,anchors.probe.ARCHIVE,526,10)))
def test_native_before_after(seed,path,k,action):
    r=anchors.capture(seed,path,k)
    assert r['r3']['mask']==[action] and r['original_after']==r['r3']['after']

def test_physical_binding_staleness_and_dead_targets():
    entry=json.loads(cohort.INDEX.read_text())['public']['full']
    rows=json.loads((cohort.INDEX.parent/entry['path']).read_text())['runs']
    r=next(x for x in rows if x['seed']==9000020)
    e=session.make_engine();s=session.make_session(e);f=s.reset(r['seed'])
    for a in r['episode']['actions']:
        previous=f;f=s.step(a,frame_id=f.frame_id,action_version=f.action_version)
    assert f.supported_actions[10] and not f.supported_actions[20] and not f.supported_actions[170]
    ticks=e._source._env.steps
    with pytest.raises(StaleFrameError):s.step(10,frame_id=previous.frame_id,action_version=f.action_version)
    assert e._source._env.steps==ticks
    with pytest.raises(ValueError):s.step(20,frame_id=f.frame_id,action_version=f.action_version)
    assert e._source._env.steps==ticks
    after=s.step(10,frame_id=f.frame_id,action_version=f.action_version)
    assert after.state.vector[1045+37]==0 and after.state.vector[994]==16
    assert not any(after.supported_actions)
    f=s.reset(9000020);assert all(v is None for v in split_markers(f.state.vector))

def test_negative_cases_and_split():
    records=json.loads((cohort.HERE/'COHORT.json').read_text())['actual_replays']
    assert [r['seed'] for r in records if r['new_actions']]==[9000020]
    assert all(not r['new_actions'] for r in records if r['seed'] in (19,17000028))
    v=[0.]*3118;v[7]=1
    for slot,name in enumerate(('SLIME_BOSS','ACID_SLIME_L','SPIKE_SLIME_L','ACID_SLIME_M','FUNGI_BEAST')):
        i=993+slot*52;v[i:i+7]=[session.ordinary.MONSTERS[name]+1,43,60,0,0,0,1]
    assert split_markers(tuple(v))==(True,True,True,False,False)
    v[994]=0;assert split_markers(tuple(v))[0] is None

@pytest.mark.parametrize('fault',('queue','steps','physical_order','dead_target','half_dead'))
def test_unknown_or_unsettled_kernel_refuses_followup(monkeypatch,fault):
    ref=json.loads(cohort.INDEX.read_text())['public']['full']
    rows=json.loads((cohort.INDEX.parent/ref['path']).read_text())['runs']
    actions=next(x['episode']['actions'] for x in rows if x['seed']==9000020)
    s=session.make_session();f=s.reset(9000020)
    for a in actions[:-1]:
        f=s.step(a,frame_id=f.frame_id,action_version=f.action_version)
    observer=session.ordinary.observer()
    def inspect(engine):
        source=observer.inspect(engine)
        if fault=='queue':source['queue']+=1
        elif fault=='steps':source['steps']-=1
        elif fault=='physical_order':source['physical_order']=list(reversed(source['physical_order']))
        elif fault=='dead_target':source['rows'][1]['targetable']=True
        elif fault=='half_dead':source['rows'][1]['half_dead']=True
        return source
    monkeypatch.setattr(session.ordinary,'observer',lambda:SimpleNamespace(inspect=inspect))
    f=s.step(actions[-1],frame_id=f.frame_id,action_version=f.action_version)
    assert not any(f.supported_actions) and 'death_boundary_unknown' in f.action_gaps
