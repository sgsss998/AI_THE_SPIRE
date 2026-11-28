from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import gzip,json
from experiments.sa_calibration_round6.reference import sha,write
from ..wall.verify import legal,step
from . import candidate,session

HERE=Path(__file__).resolve().parent
KEYS={n+1:k for k,n in session.EVENTS.items()}


def cases():
    records=[]
    for i in range(64):
        p=HERE.parent/'runs/discovery-r6'/f'shard-{i:04}.jsonl.gz'
        with gzip.open(p,'rt') as file:
            for r in map(json.loads,file):
                if r['page']!='REWARD_UNVERIFIED':
                    continue
                v=dict(r['stop']['before']['state_nonzero'])
                name=KEYS.get(v.get(9))
                if name in ('NEOW','LAB','THE_WOMAN_IN_BLUE','WHEEL_OF_CHANGE'):
                    records.append(dict(seed=r['seed'],actions=r['actions'],event=name))
    return records


def replay(row):
    s=candidate.make_session()
    f=s.reset(row['seed'])
    for i,a in enumerate(row['actions']):
        if a not in legal(f):
            return dict(seed=row['seed'],event=row['event'],resolved=False,blocked_at=i+1,page=f.page)
        f=step(s,f,a)
    out=dict(seed=row['seed'],event=row['event'],page=f.page,resolved=False,actions=legal(f))
    if f.page!='COMBAT_REWARD':
        return out
    v=f.state.vector
    out.update(floor=int(v[3]),initial_rows=[tuple(v[i:i+6]) for i in range(322,382,6) if v[i]],history=[])
    for _ in range(8):
        eligible=legal(f)
        takes=[i for i in eligible if 110<=i<170]
        # Vary the order across seeds. Prefer claiming, or emptying one slot to collect a full-belt potion.
        discards=[i for i in eligible if 105<=i<110]
        blocked_potion=any(f.state.vector[j]==3 and not f.state.vector[j+5] for j in range(322,382,6))
        if takes:
            a=takes[-1] if row['seed']%2 else takes[0]
        elif discards and blocked_potion:
            a=discards[0]
        else:
            a=171
        f=step(s,f,a)
        out['history'].append(a)
        if a==171:
            out['resolved']=f.state.vector[6]==5
            assert out['resolved']
            break
    return out


def main():
    all_rows=cases()
    rows=[r for r in all_rows if r['event']!='NEOW']
    with ProcessPoolExecutor(max_workers=2) as pool:
        facts=list(pool.map(replay,rows,chunksize=4))
    counts=Counter((r['event'],r['resolved']) for r in facts)
    first={}
    for row in rows:
        first.setdefault((row['event'],row['actions'][-1]),row)
    write(HERE/'PROBES.json',list(first.values()))
    write(HERE/'RESULT.json',dict(shards=64,counts={k:{str(b):counts[k,b] for b in (False,True)} for k,_ in counts},
                                  neow_cases=sum(r['event']=='NEOW' for r in all_rows),session_sha256=sha(HERE/'session.py'),cases=facts))
    print(counts)


if __name__=='__main__':
    main()
