"""Run the same 640 fixed and 64 additional Silent A20 games through R5."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict,replace
from datetime import datetime,timezone
import csv
from hashlib import sha256
import json

from experiments.episode_outcomes193.rollout import run_episode
from .reference import HERE,R4,read,source,write


class Observation:
    """Keep public decisions intact; the unchanged endpoint checker reads its 3118-field prefix."""
    def __init__(self, engine):
        from .release import make_session
        self.session = make_session(engine)

    def prefix(self, frame):
        assert len(frame.state.vector) == 3122 and len(frame.supported_actions) == 193
        return replace(frame,state=replace(frame.state,vector=frame.state.vector[:3118]))

    def reset(self,*args,**kwargs):
        return self.prefix(self.session.reset(*args,**kwargs))

    def step(self,*args,**kwargs):
        return self.prefix(self.session.step(*args,**kwargs))


def trial(row):
    from .release import make_engine
    episode = asdict(run_episode(row["seed"],cap=row["cap"],engine_factory=make_engine,wrap=Observation))
    old = row["episode"]
    actions = episode["actions"]
    return dict(cohort=row["cohort"],previous=old["reason"],previous_floor=old["engine_floor"],
                first_different_action=next((i for i,(a,b) in enumerate(zip(actions,old["actions"]),1) if a!=b),
                                            min(len(actions),len(old["actions"]))+1 if len(actions)!=len(old["actions"]) else None),
                previous_trace_sha256=row["trace"]["sha256"],**episode)


def summarize(rows):
    return dict(seeds=len(rows),outcomes=dict(Counter(r["reason"] for r in rows)),
                transitions=dict(Counter(r["previous"]+"->"+r["reason"] for r in rows)),
                max_floor=max(r["engine_floor"] for r in rows),decisions=sum(len(r["actions"]) for r in rows),
                deaths_with_partial_action_sets=sum(r["reason"]=="loss" and r["incomplete_action_sets"]>0 for r in rows),
                stop_pages=dict(Counter(r["page"] for r in rows if r["reason"]=="unsupported")))


def run(workers, smoke):
    from .release import interface_signature
    signature = interface_signature().metadata()
    index = read(R4/"regression/RESULT.json")
    baseline = read(source(R4/"regression",index))["runs"]
    assert len(baseline) == len({r["seed"] for r in baseline}) == 704
    if smoke:
        baseline = [r for r in baseline if r["seed"] in {19,46,48,59,17000028,9000020}]
    started = datetime.now(timezone.utc)
    with ProcessPoolExecutor(workers) as pool:
        records = list(pool.map(trial,baseline,chunksize=3))
    assert signature == interface_signature().metadata()
    summary = {name:summarize([r for r in records if r["cohort"]==name]) for name in ("fixed","additional") if any(r["cohort"]==name for r in records)}
    result = dict(signature=signature,reference_sha256=index["sha256"],smoke=smoke,training_updates=0,
                  elapsed_seconds=(datetime.now(timezone.utc)-started).total_seconds(),
                  summary=summary,combined=summarize(records),records=records)
    target = HERE/"regression"/("SMOKE.json" if smoke else "RESULT.json")
    write(target,result)
    if not smoke:
        with (target.parent/"seeds.csv").open("w",newline="") as fp:
            names=("seed","cohort","previous","reason","previous_floor","engine_floor","page","incomplete_action_sets","decisions",
                   "first_different_action","action_sha256","previous_trace_sha256")
            writer=csv.DictWriter(fp,names,lineterminator="\n")
            writer.writeheader()
            for rec in records:
                actions=rec["actions"]
                derived=dict(decisions=len(actions),action_sha256=sha256(json.dumps(actions,separators=(",",":")).encode()).hexdigest())
                writer.writerow({k:derived[k] if k in derived else rec[k] for k in names})
    print(result["combined"],flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=4,choices=range(1,9))
    parser.add_argument("--smoke",action="store_true")
    args=parser.parse_args()
    run(args.workers,args.smoke)
