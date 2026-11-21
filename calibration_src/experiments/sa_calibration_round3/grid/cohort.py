"""Rerun every eligible occurrence for each of the 33 old R2 fixed endpoints."""
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from hashlib import sha256
from pathlib import Path
import gzip
import json
from experiments.sa_calibration_round2 import release as r2
from silent_env.observation import schema
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError
from . import session

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
COHORT=ROOT/'experiments/sa_calibration_round2/regression/runs/20261120_201657_593083_R2_final/full'
def digest(p):return sha256(p.read_bytes()).hexdigest()

def prefix(seed, actions, factory):
    engine=factory.make_engine()
    public=factory.make_session(engine)
    f=public.reset(seed)
    for a in actions:f=step(public,f,a)
    return engine,public,f

def step(public,f,a):
    assert f.supported_actions[a]
    return public.step(a,frame_id=f.frame_id,action_version=f.action_version)

def deck(f):
    v=f.state.vector
    return [(int(v[i]),int(v[i+1])) for i in range(706,898,2) if v[i]]

def check(job):
    seed,actions,kind=job
    old,_,of=prefix(seed,actions,r2)
    assert of.page=='GRID_UNVERIFIED' and not any(of.supported_actions)
    e,s,f=prefix(seed,actions,session)
    v=f.state.vector
    path='SINGLE_TRANSFORM' if kind=='neow' else 'WING_REMOVE'
    assert f.page==path+'_GRID'
    allowed=[i for i,on in enumerate(f.supported_actions) if on]
    assert allowed==list(range(110,110+int(v[1769])))
    old_deck=deck(f);rows=[]
    for ordinal,a in enumerate(allowed):
        if ordinal:e,s,f=prefix(seed,actions,session)
        j=a-110;pos=int(f.state.vector[2684+j])-203
        selected=old_deck[pos]
        assert tuple(f.state.vector[322+j*6+1:322+j*6+3])==tuple(selected)
        preview=step(s,f,a)
        assert preview.page==path+'_PREVIEW' and preview.engine_steps==f.engine_steps and deck(preview)==old_deck
        assert [i for i,flag in enumerate(preview.supported_actions) if flag]==[172,173]
        try:s.step(a,frame_id=f.frame_id,action_version=f.action_version)
        except StaleFrameError:pass
        else:raise AssertionError('Accepted a stale grid frame')
        restored=step(s,preview,173)
        assert restored.state.vector==f.state.vector and restored.supported_actions==f.supported_actions
        preview=step(s,restored,a)
        committed=step(s,preview,172);after=deck(committed);left=old_deck[:pos]+old_deck[pos+1:]
        assert committed.state.vector[6]==5 and committed.engine_steps==f.engine_steps+1
        assert committed.state.vector[:6]==f.state.vector[:6]
        assert committed.state.vector[16:22]==f.state.vector[16:22] and committed.state.vector[32:112]==f.state.vector[32:112]
        if kind=='neow':assert after[:-1]==left and after[-1]!=selected and after[-1][1]==0
        else:assert after==left
        rows.append(dict(row=j,permanent_slot=pos,selected=[e._source._backend.CARD_IDS[selected[0]-1],selected[1]],
                         new_card=[e._source._backend.CARD_IDS[after[-1][0]-1],after[-1][1]] if kind=='neow' else None))
    return dict(seed=seed,kind=kind,old_steps=of.engine_steps,old_cause=list(of.action_gaps),
                prefix=actions,grid_page=path+'_GRID',eligible=len(rows),rows=rows)

def main():
    table=json.loads((COHORT/'RESULT.json').read_bytes())
    E=schema()['enums']['Event'];jobs=[]
    for r in table['runs']:
        ep=r['episode']
        if r['cohort']!='fixed' or ep['page']!='GRID_UNVERIFIED':continue
        path=COHORT/'traces'/f"{r['seed']}.json.gz"
        assert digest(path)==r['trace']['sha256']
        data=json.load(gzip.open(path));prior=data[-2]['state'];last=data[-1]['state']
        if last[26:29]==[1,1,0] and prior[9]==E['NEOW']+1:kind='neow'
        elif last[26:29]==[4,1,0] and prior[9]==E['WING_STATUE']+1:kind='wing'
        else:continue
        jobs.append((r['seed'],ep['actions'],kind))
    assert Counter(x[2] for x in jobs)=={'neow':18,'wing':15}
    with ProcessPoolExecutor(4) as pool:rows=list(pool.map(check,jobs))
    stats={k:{'seeds':sum(z['kind']==k for z in rows),'branches':sum(z['eligible'] for z in rows if z['kind']==k)} for k in ('neow','wing')}
    print(stats,flush=True)
    result=dict(fixed_sample=640,original_grid_stops=107,remaining_untested_endpoints=74,
                stats=stats,cases=rows,original_games=0,training_updates=0,cohort_sha=digest(COHORT/'RESULT.json'),
                engine_sha=digest(HERE/'session.py'))
    (HERE/'COHORT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
