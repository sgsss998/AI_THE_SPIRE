"""Freeze all known test/development seeds before the original game starts."""
from datetime import datetime, timezone
import json
from .instance import HERE,ROOT
from native_runtime import sha


def collect():
    assert not (HERE/'START_INPUT.json').exists()
    r3=HERE.parents[1]/'sa_calibration_round3'
    old=r3/'fresh/SEEDS_BEFORE.json'; previous=r3/'fresh/SEED.json'
    seeds=set(json.loads(old.read_bytes())['seeds_u64'])
    seeds.add(json.loads(previous.read_bytes())['unsigned'])
    sources=[old,previous]
    for path in sorted(HERE.parent.glob('**/*.json')):
        if path.is_relative_to(HERE):continue
        value=json.loads(path.read_bytes())
        def visit(obj):
            if isinstance(obj,list):
                for item in obj:visit(item)
            if isinstance(obj,dict):
                for k,v in obj.items():
                    if k in ('seed','seed_u64','seed_unsigned') and isinstance(v,int):
                        seeds.add(v % (1<<64))
                    elif k in ('seeds','seeds_u64','seeds_unsigned') and isinstance(v,list):
                        seeds.update(i%(1<<64) for i in v if type(i) is int)
                    else:visit(v)
        visit(value)
        sources.append(path)
    data=dict(as_of=datetime.now(timezone.utc).isoformat(), seeds_u64=sorted(seeds), sources={str(p.relative_to(ROOT)):sha(p) for p in sources})
    (HERE/'SEEDS_BEFORE.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('sealed',len(seeds),'already-known seeds')

if __name__=='__main__':collect()
