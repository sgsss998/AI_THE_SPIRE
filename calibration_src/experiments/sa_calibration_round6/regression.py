"""Compare the frozen R6 public entry with the preceding 704 free-policy games."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime,timezone
import csv
from pathlib import Path

from experiments.episode_outcomes193.rollout import run_episode
from experiments.sa_calibration_round5 import release as prior
from experiments.sa_calibration_round5.regression import Observation, summarize
from experiments.sa_calibration_round5.reference import read,sha,source,write
from . import release
from .cohort.audit import ARCHIVE,R5,allowed,digest,parent_runs

HERE=Path(__file__).resolve().parent


class R6Observation(Observation):
    def __init__(self,engine):
        self.session=release.make_session(engine)


def trial(args):
    row,cap=args
    ep=asdict(run_episode(row["seed"],cap=cap,engine_factory=release.make_engine,wrap=R6Observation))
    old,new=row["actions"],ep["actions"]
    first=next((i for i,(a,b) in enumerate(zip(old,new),1) if a!=b),None)
    if first is None and len(old)!=len(new):first=min(len(old),len(new))+1
    return dict(**ep,cap=cap,cohort=row["cohort"],previous=row["reason"],previous_floor=row["engine_floor"],
                previous_actions=len(old),previous_action_sha256=digest(old),action_sha256=digest(new),first_different_action=first)


def changed(old,new):
    """Locate the first menu difference along both games' common actual inputs."""
    first=new["first_different_action"] or len(new["actions"])+1
    prefix=new["actions"][:first-1]
    assert prefix==old["actions"][:first-1]
    models=[v.make_session() for v in (prior,release)]
    frames=[m.reset(old["seed"],ascension=20,final_act=True) for m in models]
    different=None
    for idx in range(len(prefix)+1):
        entries=[dict(page=f.page,offered=allowed(f),floor=int(f.state.vector[3])) for f in frames]
        if different is None and entries[0]!=entries[1]:
            different=dict(decision=idx+1,r5=entries[0],r6=entries[1])
        if idx<len(prefix):
            a=prefix[idx];frames=[m.step(a,frame_id=f.frame_id,action_version=f.action_version) for m,f in zip(models,frames)]
    return dict(seed=old["seed"],first_different_menu=different,first_different_action=new["first_different_action"],
                old_action=old["actions"][first-1:first],new_action=new["actions"][first-1:first],
                previous_endpoint=old["page"],new_endpoint=new["page"],previous_reason=old["reason"],new_reason=new["reason"],
                previous_floor=old["engine_floor"],new_floor=new["engine_floor"])


def run(workers):
    sig=release.interface_signature().metadata()
    assert sig==read(HERE/"INTERFACE.json")
    rows=parent_runs()
    index=read(R5.parent/"sa_calibration_round4/regression/RESULT.json")
    r4=source(R5.parent/"sa_calibration_round4/regression",index)
    caps={r["seed"]:r["cap"] for r in read(r4)["runs"]}
    assert set(caps)=={r["seed"] for r in rows}
    started=datetime.now(timezone.utc)
    with ProcessPoolExecutor(workers) as pool:
        records=list(pool.map(trial,((r,caps[r["seed"]]) for r in rows),chunksize=2))
    changes=[changed(a,b) for a,b in zip(rows,records,strict=True) if (a["reason"],a["page"],a["engine_floor"])!=(b["reason"],b["page"],b["engine_floor"])]
    assert release.interface_signature().metadata()==sig
    result=dict(signature=sig,reference_sha256=sha(ARCHIVE),training_updates=0,smoke=False,
                elapsed_seconds=(datetime.now(timezone.utc)-started).total_seconds(),
                summary={k:summarize([r for r in records if r["cohort"]==k]) for k in ("fixed","additional")},
                combined=summarize(records),records=records)
    write(HERE/"regression/RESULT.json",result)
    write(HERE/"regression/CHANGES.json",dict(signature=sig,changes=changes,
            changed_action_sequences=sum(r["first_different_action"] is not None for r in records),
            changed_outcome_categories=sum(r["previous"]!=r["reason"] for r in records)))
    cols=("seed","cohort","previous","reason","previous_floor","engine_floor","page","incomplete_action_sets",
          "decisions","first_different_action","action_sha256","previous_action_sha256")
    with (HERE/"regression/seeds.csv").open("w",newline="") as out:
        writer=csv.DictWriter(out,cols,lineterminator="\n")
        writer.writeheader()
        for row in records:
            writer.writerow({k:len(row["actions"]) if k=="decisions" else row[k] for k in cols})
    print(result["combined"],flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--workers",type=int,choices=range(1,9),default=4)
    run(p.parse_args().workers)
