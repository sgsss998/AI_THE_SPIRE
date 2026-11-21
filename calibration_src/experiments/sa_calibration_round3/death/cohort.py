"""Read all R2 stop frames and actually replay the 20 candidate prefixes on the R3 public owner."""
import gzip
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from . import session

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
INDEX=ROOT/'experiments/sa_calibration_round2/regression/RESULT.json'
def digest(p):return sha256(p.read_bytes()).hexdigest()

def replay(it,base):
    e=session.make_engine();s=session.make_session(e);f=s.reset(it['seed'])
    for n,aid in enumerate(it['episode']['actions']):
        assert f.supported_actions[aid],(it['seed'],n,aid)
        f=s.step(aid,frame_id=f.frame_id,action_version=f.action_version)
    assert list(f.state.vector)==base['state'] and f.engine_steps==base['engine_steps']
    first=[i for i,x in enumerate(f.supported_actions) if x];next_frame=None
    if first:
        assert len(first)==1
        nxt=s.step(first[0],frame_id=f.frame_id,action_version=f.action_version)
        next_frame=dict(hp=nxt.state.vector[0],enemy_hp=[r[1] for r in session.ordinary.rows(nxt.state.vector) if r[0]],dead_spores=[r[37] for r in session.ordinary.rows(nxt.state.vector) if r[0] and r[1]==0],
                        supported=[i for i,x in enumerate(nxt.supported_actions) if x],gaps=list(nxt.action_gaps),done=nxt.done)
    return dict(seed=it['seed'],floor=base['kernel_floor'],lethal_action=it['episode']['actions'][-1],trace_sha256=it['trace']['sha256'],
                previous_prefix_inputs=len(it['episode']['actions']),original_supported=base['supported'],new_actions=first,
                corpse_slots=[j for j,r in enumerate(session.ordinary.rows(f.state.vector)) if r[0] and r[1]==0],
                first_successor=next_frame)

def main():
    entry=json.loads(INDEX.read_text())['public']['full'];source=INDEX.parent/entry['path']
    assert digest(source)==entry['sha256']
    records=json.loads(source.read_text())['runs'];counts={};cases=[]
    for group in ('fixed','additional'):
        group_runs=[r for r in records if r['cohort']==group]
        pure=[r for r in group_runs if r['episode']['cause']==['death_boundary_unknown']]
        counts[group]=dict(total=len(group_runs),sole_death_gap=len(pure),contains_death_gap=sum('death_boundary_unknown' in r['episode']['cause'] for r in group_runs))
        for r in pure:
            trace=Path(r['trace']['path']);assert digest(trace)==r['trace']['sha256']
            with gzip.open(trace) as stream:last=json.load(stream)[-1]
            if not any(row[0]==session.FUNGI and row[1]==0 and row[37] for row in session.ordinary.rows(last['state'])):continue
            x=replay(r,last);x['cohort']=group;cases.append(x);print(x['seed'],x['new_actions'],flush=True)
    assert len(cases)==21 and sum(x['cohort']=='fixed' for x in cases)==20
    out=dict(index_digest=entry['sha256'],denominators=counts,actual_replays=cases)
    (HERE/'COHORT.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
