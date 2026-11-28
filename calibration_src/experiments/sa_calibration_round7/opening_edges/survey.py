"""Reproduce original early Neow stops on the composed edition and identify actual backing outcomes."""
from collections import Counter
from pathlib import Path
import gzip
import json
from .. import events_and_grids as v6
from ..triage import RUNS
from experiments.sa_calibration_round6.reference import read,write

HERE=Path(__file__).resolve().parent


def baseline():
    folder=RUNS/"discovery-r6"
    for idx in range(32):
        for line in gzip.open(folder/f"shard-{idx:04}.jsonl.gz","rt"):
            row=json.loads(line)
            if len(row["actions"])==2 and row["actions"][0]==110 and row["page"] in ("GRID_UNVERIFIED","NEOW_RESULT_UNVERIFIED","REWARD_UNVERIFIED"):
                yield "discovery3200",row
    fixed=read(HERE.parents[1]/"sa_calibration_round6/regression/RESULT.json")["records"]
    for row in fixed:
        if len(row["actions"])==2 and row["actions"][0]==110 and row["page"] in ("GRID_UNVERIFIED","NEOW_RESULT_UNVERIFIED","REWARD_UNVERIFIED"):
            yield "fixed704",row


def run():
    cases=[]
    for group,r in baseline():
        e=v6.make_engine();s=v6.make_session(e);f=s.reset(r["seed"])
        f=s.step(110,frame_id=f.frame_id,action_version=f.action_version)
        aid=r["actions"][-1];off=f.state.vector[322+6*(aid-110):328+6*(aid-110)]
        old=f
        f=s.step(aid,frame_id=f.frame_id,action_version=f.action_version)
        x=e._raw.raw_base
        rel=[e._source._backend.RELIC_NAMES[int(x[k])-1] for k in range(32,112,2) if x[k]]
        cases.append(dict(group=group,seed=r["seed"],aid=aid,gift=int(off[1]),cost=int(off[2]),page=f.page,legal=sum(f.supported_actions),
                          raw_screen=int(x[6]),raw_relics=rel,original=r["page"]))
    write(HERE/"SURVEY.json",{"cases":cases})
    for tag in ("fixed704","discovery3200"):
        target=[r for r in cases if r["group"]==tag and not r["legal"]]
        print(tag,len(target),Counter((r["aid"],r["gift"],r["page"],r["raw_relics"][-1]) for r in target))


if __name__=="__main__":
    run()
