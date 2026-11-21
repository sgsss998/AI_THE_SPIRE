"""Verify two R3 public inputs against each original action receipt and after-state."""
import json
from types import SimpleNamespace
from experiments.sa_calibration_round2.frontiers import verify as triple
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.sa_calibration_round2.diagnostic_slime import probe
from experiments.sa_calibration_round2.boss.verify_opening import read_case,receipt
from experiments.sa_calibration_round1.fidelity.boss import check as old
from . import session
from .cohort import HERE,digest
from .split import split_markers


def scalar(frame):
    v=frame.state.vector
    return dict(hp=int(v[0]),block=int(v[900]),energy=int(v[901]),turn=int(v[902])+1,vulnerable=int(v[911]),
               enemies=[[int(r[1]),int(r[2]),int(r[3]),int(r[37])] for r in session.ordinary.rows(v) if r[0]])

def oracle(g):
    c=g['combat_state'];p=c['player']
    def power(unit,key):return sum(z['amount'] for z in unit['powers'] if z['id']==key)
    return dict(hp=p['current_hp'],block=p['block'],energy=p['energy'],turn=c['turn'],vulnerable=power(p,'Vulnerable'),
                enemies=[[m['current_hp'],m['max_hp'],m['block'],power(m,'Spore Cloud')] for m in c['monsters']])

def capture(seed,path,k,factory=session):
    seen=[]
    def owner(e):
        s=factory.make_session(e);current=None
        def reset(*args,**kw):
            nonlocal current
            current=s.reset(*args,**kw);return current
        def step(a,**kw):
            nonlocal current
            before=current;after=s.step(a,**kw);current=after
            if session.PARTIAL in before.action_gaps:
                seen.append(dict(a=a,mask=[i for i,b in enumerate(before.supported_actions) if b],prev=scalar(before),
                    after=scalar(after),next_mask=[i for i,b in enumerate(after.supported_actions) if b],
                    ticks=[before.engine_steps,after.engine_steps],state_version=before.state.state_version,
                    full_mask_known=before.policy_mask is not None,width=len(before.state.vector),
                    shape_after=len(after.state.vector),split_before=list(split_markers(before.state.vector)),split_after=list(split_markers(after.state.vector))))
            return after
        return SimpleNamespace(step=step,reset=reset,route_columns=s.route_columns)
    entry=SimpleNamespace(make_engine=factory.make_engine,make_session=owner)
    if k==335:
        r=triple.run(entry,until=k+1);assert r['stop'] is None
    else:
        r=_local_dependencies(old.check,release=entry)(path,seed);assert r['stop']['sequence']==k+1
    rec,=seen;raw,d=read_case(path,seed)
    a=receipt(path,raw,d[k-1],k-1);b=receipt(path,raw,d[k],k)
    prev=raw[k]['raw']['game_state'];after=raw[k+1]['raw']['game_state']
    assert rec['prev']==oracle(prev) and rec['after']==oracle(after)
    assert rec['mask']==[b['action']]==[rec['a']] and not rec['full_mask_known']
    assert rec['ticks'][1]==rec['ticks'][0]+1
    dead=next(j for j,m in enumerate(prev['combat_state']['monsters']) if m['current_hp']==0)
    first=prev['combat_state']['monsters'][dead];last=after['combat_state']['monsters'][dead]
    assert first['is_dying'] and not first['is_dead'] and last['is_dead'] and not last['powers']
    return dict(seed=seed,sequence=k,original_raw_sha256=digest(path/'raw.jsonl'),lethal_receipt=a,
                follow_receipt=b,original_before=oracle(prev),original_after=oracle(after),r3=rec)

def main():
    records=[capture(triple.SEED,triple.ARCHIVE,335),capture(probe.SEED,probe.ARCHIVE,526)]
    (HERE/'ANCHORS.json').write_text(json.dumps(records,indent=2)+'\n')
    print([(r['seed'],r['r3']['mask'],r['original_after']['enemies']) for r in records])
if __name__=='__main__':main()
