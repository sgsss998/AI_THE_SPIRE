"""Replay every archived R5 reward stop using the pinned decisions, retaining live reward rows."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from importlib import import_module
import json
from pathlib import Path
import sys

from experiments.reward_ui_adapter.adapter import Unsupported
from experiments.sa_calibration_round5.reference import read, sha, write
from silent_env.observation import schema

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parents[1]
R5 = EXPERIMENTS / "sa_calibration_round5"
ARCHIVE = R5 / "regression/RESULT.json"
SEALED = "96b2e043c2fe1f75b7fe75adf45ba58dcd0bce5b4c6fffa5430b311f47af4b4e"
ENUMS = schema()["enums"]


def digest(value):
    return sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def parent_runs():
    assert sha(R5/"RELEASE.json") == SEALED
    assert sha(ARCHIVE) == read(R5/"RELEASE.json")["files"]["regression/RESULT.json"]
    rows = read(ARCHIVE)["records"]
    assert len(rows) == len({r["seed"] for r in rows}) == 704
    return rows


def enum_name(domain, wire):
    return next((key for key,number in ENUMS[domain].items() if number+1 == wire),None)


def held(vector):
    return [[enum_name("RelicId",vector[i]),int(vector[i+1])-1]
            for i in range(32,112,2) if vector[i]]


def allowed(frame):
    return [i for i,bit in enumerate(frame.supported_actions) if bit]


def frame_info(frame):
    return dict(page=frame.page, state_sha256=digest(frame.state.vector), actions=allowed(frame),
                floor=int(frame.state.vector[3]), gaps=frame.action_gaps, steps=frame.engine_steps)


def review(args):
    row,revision = args
    version = import_module(f"experiments.sa_calibration_round{revision}.release")
    game = version.make_engine()
    session = version.make_session(game)
    seed,actions = row["seed"],row["actions"]
    frame = session.reset(seed,ascension=20,final_act=True)
    rejected = []

    def trace(call,event,arg):
        if event=="exception" and isinstance(arg[1],Unsupported):
            # Store each originating reward rejection and its actual caller, not every stack unwind.
            if call.f_code.co_name=="require" and call.f_back is not None:
                parent = call.f_back
                witness=[Path(parent.f_code.co_filename).parent.name+"/"+Path(parent.f_code.co_filename).name,
                         parent.f_code.co_name, parent.f_lineno, str(arg[1])]
                if witness not in rejected: rejected.append(witness)
        return trace

    evidence=dict(seed=seed, cohort=row["cohort"], expected_floor=row["engine_floor"],prefix_sha256=digest(actions),
                  original_actions=len(actions),last_action=actions[-1])
    for n,action in enumerate(actions,1):
        before=frame
        if not frame.supported_actions[action]:
            assert revision!=5
            return dict(**evidence,status="old_prefix_unavailable",endpoint=frame_info(frame),index=n)
        if n==len(actions):
            sys.settrace(trace)
        try:
            frame=session.step(action,frame_id=before.frame_id,action_version=before.action_version)
        finally:
            if n==len(actions):sys.settrace(None)
    if revision==5:
        assert frame.page=="REWARD_UNVERIFIED" and not allowed(frame) and not frame.done
        assert frame.engine_steps==row["engine_steps"] and row["engine_floor"]==int(frame.state.vector[3])
        assert list(frame.action_gaps)==row["cause"]
    raw=game._source._current
    assert raw.choice_metadata["packet_sha256"]==raw.packet_sha256 and raw.engine_steps==frame.engine_steps
    w,v=before.state.vector,raw.raw_base
    room=enum_name("Room",v[8]);event=enum_name("Event",w[9])
    acquired=[ref for ref,_ in held(v) if ref not in {i for i,c in held(w)}]
    source="NEOW_SWAP_"+"+".join(acquired) if before.page=="NEOW_OFFERS" and acquired else event if event and event!="INVALID" else room
    choices=[]
    for c in raw.choice_metadata["choices"]:
        aid=c["sim_action"]
        assert raw.backend_mask[aid]==c["legal"]
        assert game._source._env.is_valid(aid)==c["legal"]
        choice=dict(slot=c["slot"],physical=aid,kind=c["kind_name"],parameters=list(c["parameters"]),legal=c["legal"])
        if c.get("card_identity"):
            choice["native_card"]=c["card_identity"]["native_id"]
        if c["kind_name"]=="POTION":
            choice["potion"]=enum_name("Potion",c["parameters"][0])
        choices.append(choice)
    group=source+"/"+",".join(sorted({c["kind"] for c in choices}))
    rows=[list(frame.state.vector[i:i+6]) for i in range(322,706,6) if frame.state.vector[i]]
    return dict(**evidence,status="replayed",origin=frame_info(before),endpoint=frame_info(frame),group=group,
                room=room,event=event, source=source, prior_relics=held(w), held_relics=held(v),
                monsters=[enum_name("MonsterId",w[i]) for i in range(993,1253,52) if w[i]],
                potion_slots=[enum_name("Potion",p) for p in v[17:17+int(v[16])]],
                packet_sha256=raw.packet_sha256,raw_reward_rows=choices,public_rows=rows,rejections_during_last_input=rejected)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("revision",type=int,choices=(5,6))
    parser.add_argument("--workers",type=int,default=4,choices=range(1,9))
    args=parser.parse_args()
    reference=parent_runs()
    stops=[r for r in reference if r["reason"]=="unsupported" and r["page"]=="REWARD_UNVERIFIED"]
    assert Counter(r["cohort"] for r in stops)=={"fixed":53,"additional":5}
    module=import_module(f"experiments.sa_calibration_round{args.revision}.release")
    signature=module.interface_signature().metadata()
    assert read(EXPERIMENTS/f"sa_calibration_round{args.revision}/INTERFACE.json")==signature
    with ProcessPoolExecutor(args.workers) as pool:
        rows=list(pool.map(review,((r,args.revision) for r in stops),chunksize=1))
    assert module.interface_signature().metadata()==signature
    result=dict(signature=signature,original_machine_chosen_actions=0,reference_sha256=sha(ARCHIVE),cohorts=dict(Counter(r["cohort"] for r in rows)),
                groups=dict(Counter(r.get("group","unmatched") for r in rows)),records=rows)
    if args.revision==6:
        old=read(HERE/"R5.json")["records"]
        for prev,new in zip(old,rows,strict=True):
            assert prev["seed"]==new["seed"] and prev["prefix_sha256"]==new["prefix_sha256"]
            if new["status"]!="replayed":continue
            for key in ("source","raw_reward_rows","held_relics","potion_slots","monsters"):
                assert new[key]==prev[key],(new["seed"],key)
        result["opened"]=[r["seed"] for r in rows if r["status"]=="replayed" and r["endpoint"]["actions"]]
    write(HERE/f"R{args.revision}.json",result)
    print(result["groups"],result.get("opened"),flush=True)


if __name__=="__main__":main()
