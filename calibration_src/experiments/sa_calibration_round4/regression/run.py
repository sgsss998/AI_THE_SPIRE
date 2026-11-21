"""Measure both replay of frozen R3 inputs and new free-policy runs on the R4 interface."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
import json
import traceback

from experiments.episode_outcomes193.rollout import run_episode
from experiments.sa_calibration_round1.regression import run as io
from experiments.sa_calibration_round3.regression import run as previous
from experiments.sa_calibration_round4 import release
from experiments.sa_calibration_round4.events.serpent import CONTINUE, LEAVE

HERE = Path(__file__).resolve().parent
R4 = HERE.parent
R3 = R4.parent / "sa_calibration_round3"
R3_INDEX = json.loads((R3/"regression/RESULT.json").read_bytes())
R3_FULL = R3 / "regression" / R3_INDEX["full"]["path"]

def exact_reference(row):
    path=R3_FULL.parent/"traces"/f'{row["seed"]}.json.gz'
    assert io.digest(path)==row["trace"]["sha256"]
    frames = io.read_trace(path)
    assert len(frames)==1+len(row["episode"]["actions"])
    return frames

def aligned(old, reference):
    engine=release.make_engine()
    session=release.make_session(engine)
    f=session.reset(old["seed"],ascension=20,final_act=True)
    inserted=[]
    first_difference=None
    def submit(a):
        return session.step(a,frame_id=f.frame_id,action_version=f.action_version)
    for index in range(len(old["actions"])+1):
        while f.page in (CONTINUE,LEAVE) and reference[index]["page"]!=f.page:
            only=[a for a,flag in enumerate(f.supported_actions) if flag]
            assert only==[110]
            inserted.append([index,f.page,only[0]])
            f=submit(only[0])
        new=previous.snap(f, engine, session)
        difference=previous.first_semantic([reference[index]], [new])
        if difference and not first_difference:
            first_difference=dict(difference,observation=index)
        if index==len(old["actions"]):
            return dict(complete=True,extra_serpent_inputs=inserted,first_difference=first_difference,
                        endpoint_state_equal=(new["state"]==reference[index]["state"]),endpoint_page=new["page"])
        aid=old["actions"][index]
        if not f.supported_actions[aid] or f.done:
            return dict(complete=False,index=index+1,action=aid,page=f.page,extra_serpent_inputs=inserted,first_difference=first_difference)
        f=submit(aid)

def run_one(args):
    row,out=args
    old=row["episode"]
    frames=[]
    class Recorder:
        def __init__(self,e):self.engine=e;self.session=release.make_session(e)
        def capture(self,f):
            assert f.state.state_version == EXPECTED_VERSION
            frames.append(previous.snap(f,self.engine,self.session))
            return replace(f,state=replace(f.state,vector=f.state.vector[:3118]))
        def reset(self,*a,**kw):return self.capture(self.session.reset(*a,**kw))
        def step(self,*a,**kw):return self.capture(self.session.step(*a,**kw))
    try:
        ref=exact_reference(row)
        ep=json.loads(json.dumps(asdict(run_episode(row["seed"],cap=row["cap"],engine_factory=release.make_engine,wrap=Recorder))))
        forced=previous.forced_replay(dict(prior=old,engine_factory="experiments.sa_calibration_round4.release:make_engine",
                                            session_factory="experiments.sa_calibration_round4.release:make_session",
                                            enhance_factory=None,output=str(out)),ep,frames,ref)
        trace=previous.trace_write(out/"traces"/f'{row["seed"]}.json.gz',frames)
        # R3's scanner treats the post-accept/decline confirmations as already processed.
        serpent=any(f["page"] in (CONTINUE,LEAVE) for f in frames)
        semantic=aligned(old,ref) if serpent or not forced["prefix_complete"] or forced["endpoint_changes"] else None
        new_issue=io.compare(old,ep,frames)
        return dict(seed=row["seed"],cohort=row["cohort"],cap=row["cap"],episode=ep,trace={**trace,"path":Path(trace["path"]).name},
                    r3_trace_sha256=row["trace"]["sha256"],r3_result=old["reason"],forced=forced,aligned=semantic,
                    first_different_observation=previous.first_semantic(ref,frames),free_differences=new_issue,
                    changed_actions=old["actions"]!=ep["actions"])
    except Exception:
        return dict(seed=row["seed"],cohort=row["cohort"],error=traceback.format_exc())

EXPECTED_VERSION=json.loads((R4/"INTERFACE.json").read_bytes())["state_version"]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=3)
    parser.add_argument("--smoke",action="store_true")
    args=parser.parse_args()
    assert 1<=args.workers<=8
    sig=release.interface_signature().metadata()
    assert sig==json.loads((R4/"INTERFACE.json").read_bytes())
    assert io.digest(R3_FULL)==R3_INDEX["full"]["sha256"]
    all_rows=json.loads(R3_FULL.read_bytes())["runs"]
    assert len({r["seed"] for r in all_rows})==len(all_rows)==704
    rows=[r for r in all_rows if r["seed"] in {19,59,46,48,9000020,6,17000028}] if args.smoke else all_rows
    tag=datetime.now(io.SHANGHAI).strftime("%Y%m%d_%H%M%S_%f")+("_smoke" if args.smoke else "_full")
    out=HERE/"runs"/tag
    (out/"traces").mkdir(parents=True)
    (out/"forced_traces").mkdir()
    with ProcessPoolExecutor(args.workers) as executor:
        result=list(executor.map(run_one,((row,out) for row in rows),chunksize=2))
    summary={}
    for group in ("fixed","additional"):
        subset=[r for r in result if r["cohort"]==group]
        ok=[r for r in subset if "error" not in r]
        summary[group]=dict(seeds=len(subset),errors=len(subset)-len(ok),
            old_results=dict(Counter(r["r3_result"] for r in ok)),outcomes=dict(Counter(r["episode"]["reason"] for r in ok)),
            transitions=dict(Counter(r["r3_result"]+"->"+r["episode"]["reason"] for r in ok)),decisions=sum(len(r["episode"]["actions"]) for r in ok),
            complete_literal=sum(r["forced"]["prefix_complete"] for r in ok),
            complete_after_unique_alignment=sum(r["aligned"]["complete"] if r["aligned"] else r["forced"]["prefix_complete"] for r in ok),
            changed_free_actions=sum(r["changed_actions"] for r in ok),
            stop_pages=dict(Counter(r["episode"]["page"] for r in ok if r["episode"]["reason"]=="unsupported")))
    assert sig==release.interface_signature().metadata()
    io.write_new(out/"RESULT.json",dict(signature=sig,reference_full_sha256=io.digest(R3_FULL),runner_sha256=io.digest(Path(__file__)),sample="smoke" if args.smoke else "full",summary=summary,runs=result))
    print(str(out),summary,flush=True)
    for row in result:
        if "error" in row:
            print(row["seed"],row["error"],flush=True)
            raise ValueError("Regression contains a recorded execution error")
    if not args.smoke:
        io.write_new(HERE/"RESULT.json",dict(signature=sig,reference_sha256=io.digest(R3_FULL),
                     path=str((out/"RESULT.json").relative_to(HERE)),sha256=io.digest(out/"RESULT.json"),summary=summary,training_steps=0))
if __name__ == "__main__":
    main()
