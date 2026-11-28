"""Check whether an earlier natural ending remains reachable on its actual old decisions."""
import argparse
import importlib
from pathlib import Path

from experiments.sa_calibration_round5.reference import read,write
from experiments.sa_calibration_round6 import release as baseline

HERE=Path(__file__).resolve().parent


def run(edition):
    module=importlib.import_module(edition)
    sig=module.interface_signature().metadata()
    folder=HERE/"regression"/sig["state_sha256"]
    result=read(folder/"RESULT.json")
    reference={r["seed"]:r for r in read(HERE.parent/"sa_calibration_round6/regression/RESULT.json")["records"]}
    changed={r["seed"]:r for r in result["changed"]}
    checked=[]
    for seed in result["lost_natural_end"]:
        path=reference[seed]
        old, new = baseline.make_session(),module.make_session()
        frames = [old.reset(seed),new.reset(seed)]
        first_choice=changed[seed]["first_different_decision"]
        split=None
        issue=None
        for i,a in enumerate(path["actions"],1):
            x,y=frames
            if i==first_choice:
                split=dict(step=i,page=x.page,old_action=a,new_action=changed[seed]["candidate_at_difference"],
                           old_menu=[j for j,k in enumerate(x.supported_actions) if k],
                           new_menu=[j for j,k in enumerate(y.supported_actions) if k])
            if not y.supported_actions[a]:
                issue=dict(step=i,reason="old action unavailable",action=a,page=y.page)
                break
            # These public outcomes cover resources, deck, hand, enemies and objects even if the new interface
            # publishes additional actions or later corrects a previously inaccurate choice-count field.
            for name,start,end in (("resources",0,6),("inventory",16,26),("relics",32,112),
                                   ("deck",706,898),("enemy HP",993,997),("hand",1253,1313)):
                if x.state.vector[start:end]!=y.state.vector[start:end]:
                    issue=dict(step=i,reason=name,old=x.state.vector[start:end],new=y.state.vector[start:end])
                    break
            if issue:break
            frames=[s.step(a,frame_id=f.frame_id,action_version=f.action_version) for s,f in zip((old,new),frames)]
        final=frames[-1]
        reached=not issue and final.done and not final.state.vector[0] and final.state.vector[3]==path["engine_floor"]
        checked.append(dict(seed=seed,earlier_terminal_reached=bool(reached),first_changed_policy_decision=split,
                            earlier_decisions=len(path["actions"]),first_old_path_issue=issue))
    write(folder/"FORMER_TERMINALS.json",dict(interface=sig,checked=checked))
    print("Replayed",len(checked),"former terminals;",sum(x["earlier_terminal_reached"] for x in checked),"still reachable")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("edition")
    run(p.parse_args().edition)
