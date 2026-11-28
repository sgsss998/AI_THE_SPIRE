"""Hold recorded R6 actions fixed when assessing a new candidate on the 200 discovery-pilot seeds."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from importlib import import_module
from pathlib import Path

from experiments.sa_calibration_round5.reference import sha,write
from . import episode
from .oracles import extended
from .triage import rows

HERE=Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def edition(name):
    return import_module(name)


def check(task):
    name,old=task
    module=edition(name)
    engine=module.make_engine()
    owner=module.make_session(engine)
    frame=owner.reset(old["seed"],ascension=20,final_act=True)
    new_issues=[]
    actions=old["actions"]
    first_missing=None
    for i,aid in enumerate(actions,1):
        if frame.done or not frame.supported_actions[aid]:
            first_missing=dict(index=i,aid=aid,frame=episode.snapshot(frame))
            break
        previous=frame
        frame=owner.step(aid,frame_id=frame.frame_id,action_version=frame.action_version)
        if not new_issues:
            findings=extended.audit_frame(frame)+extended.audit_transition(previous,aid,frame)
            if findings:
                new_issues.append(dict(index=i,findings=findings))
    core=engine._source._env
    reached=first_missing is None
    if not reached:
        status="old_action_no_longer_executable"
    elif core.floor!=old["engine_floor"]:
        status="old_actions_reached_another_floor"
    elif old["reason"]=="loss":
        status="same_natural_loss" if core.lost and frame.done and frame.policy_mask is not None and not any(frame.supported_actions) else "old_terminal_differs"
    elif frame.done:
        status="candidate_natural_loss" if core.lost and not core.won and not any(frame.supported_actions) and frame.policy_mask is not None else "contradictory_terminal"
    else:
        status="old_stop_has_choices" if any(frame.supported_actions) else "still_no_choices"
    return dict(seed=old["seed"],policy=old["strategy"],old_reason=old["reason"],old_page=old["page"],
        old_floor=old["engine_floor"],old_actions=len(actions),old_trace_sha256=old["trace_sha256"],
        held_actions=len(actions) if reached else first_missing["index"]-1,
        status=status,first_missing=first_missing,first_semantic_findings=new_issues,
        outcome=episode.snapshot(frame),candidate_kernel_floor=int(core.floor))


def run(name,workers):
    sig=edition(name).interface_signature().metadata()
    assert sig["observation_dimension"]==3127
    folder=HERE/"runs/pilot-r6"
    old=[r for _,r in rows(folder)]
    assert len(old)==200
    with ProcessPoolExecutor(workers) as pool:
        tested=list(pool.map(check,((name,r) for r in old),chunksize=2))
    assert sig==edition(name).interface_signature().metadata()
    totals=dict(Counter(r["status"] for r in tested))
    write(HERE/"paired"/sig["state_sha256"]/"RESULT.json",dict(edition=name,interface=sig,
        source_sha256=sha(folder/"RESULT.json"),games=len(tested),outcomes=totals,records=tested,
        scope="Same historical numeric actions, checked for availability. A different binding behind the same number requires a physical target audit. Newly available choices alone are not natural endings."))
    print(name,totals,flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("edition")
    p.add_argument("--workers",type=int,choices=range(1,17),default=3)
    args=p.parse_args()
    run(args.edition,args.workers)
