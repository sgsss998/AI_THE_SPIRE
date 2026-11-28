"""Check original inputs, discovered counterexamples, and stale corpse powers with a read-only retail archive."""
from dataclasses import replace
import gzip
import json
from pathlib import Path

from experiments.sa_calibration_round3.death import anchors
from experiments.sa_calibration_round4.death.live import dest, source
from experiments.sa_calibration_round4.fresh import invocations
from experiments.sa_calibration_round5.replay import original_inputs
from experiments.sa_calibration_round6.reference import ROOT, R4, read, sha, write
from .. import episode
from ..wall import verify as replay
from . import candidate

HERE = Path(__file__).resolve().parent


def compare(engine, frame, snap):
    assert frame.state.state_version.endswith(candidate.TAG)
    projected = replace(frame, state=replace(frame.state, state_version=frame.state.state_version.removesuffix(candidate.TAG)))
    return replay.compare(engine, projected, snap)


def natural_trace():
    journal = original_inputs()
    seed = journal[0]["before"]["raw"]["game_state"]["seed"] % (1<<64)
    report, _ = replay.retail_replay(journal, invocations.captures(), seed=seed,
                                      session_factory=candidate.make_session, compare_frame=compare)
    fungal = []
    for row in report["rows"]:
        g = journal[row["index"]-1]["before"]["raw"]["game_state"]
        c = g.get("combat_state") or {}
        if any(m["id"]=="FungiBeast" and m["current_hp"]==0 for m in c.get("monsters",[])):
            fungal.append(dict(index=row["index"],floor=g["floor"],action=row["public_action"],command=row["command"],
                               offered=row["offered"],retail_legal=row["retail_legal"],
                               observed_actions_match=row["offered"]==row["retail_legal"]))
    return dict(seed=seed,original_journal_sha256=sha(R4/"fresh/ACTIONS.jsonl"),fungal_steps=fungal,**report)


def before_death(seed):
    prefix, _ = source(seed)
    session = candidate.make_session()
    frame = session.reset(seed)
    for action in prefix:
        frame = replay.step(session,frame,action)
    return session, frame


def original_case(seed):
    archive = next(row for row in read(R4/"death/RESULT.json")["cases"] if row["seed"]==seed)
    for path, digest in archive["archive_hashes"].items():
        assert sha(ROOT/path) == digest
    root = dest(seed)/"r4_death"
    orig, settled = read(root/"RESULT.json"), read(root/"SETTLED.json")
    session, frame = before_death(seed)
    before = anchors.scalar(frame)
    assert before == orig["native_before"] and replay.legal(frame) == orig["legal_before"]
    successor = replay.step(session,frame,orig["real"]["model_action"])
    if seed==59:
        assert settled["query"]["command"]=="state" and settled["records"][1]["CM"]==anchors.scalar(successor)
        assert orig["next_legal"]==replay.legal(successor)
    else:
        assert successor.done and successor.state.vector[0]==0
    return dict(seed=seed,before=before,menu=replay.legal(frame),action=orig["real"]["model_action"],
                next_menu=replay.legal(successor),immediate_native=orig["native_after"],
                settled_native=settled["records"][1]["CM"],model_after=anchors.scalar(successor),
                native_gone_flags_and_powers=[r["native_monsters"] for r in settled["records"]],
                original_hashes=archive["archive_hashes"])


def discovery():
    # Fixed completed shards make repeated verification independent of the running campaign.
    root = HERE.parent/"runs/discovery-r6"
    selections = {}
    for n in range(4):
        path = root/f"shard-{n:04}.jsonl.gz"
        digest = sha(path)
        for old in map(json.loads,gzip.open(path,"rt")):
            if old["reason"]!="unsupported" or "death_boundary_unknown" not in old["cause"]:
                continue
            v = dict(old["stop"]["after"]["state_nonzero"])
            rows = [993+52*i for i in range(5) if v.get(993+52*i)]
            if len(rows)!=2 or not all(v[r]==22 for r in rows):
                continue
            dead = [i for i,r in enumerate(rows) if not v.get(r+1)]
            if len(dead)!=1:
                continue
            key = old["strategy"],dead[0]
            selections.setdefault(key,(old,path.name,digest))
    results = []
    for (strategy,side),(old,name,digest) in sorted(selections.items()):
        session = candidate.make_session()
        frame = session.reset(old["seed"])
        for action in old["actions"]:
            frame = replay.step(session,frame,action)
        legal = replay.legal(frame)
        free = episode.trial(old["seed"],strategy,cap=2000,runtime=candidate,verify_repeat=True)
        results.append(dict(seed=old["seed"],strategy=strategy,dead_slot=side,shard=name,shard_sha256=digest,
                            old_inputs=len(old["actions"]),old_floor=old["engine_floor"],old_gaps=old["cause"],
                            actions_on_exact_old_stop=legal,current_gaps=list(frame.action_gaps),
                            new_inputs=len(free["actions"]),new_outcome=free["reason"],new_floor=free["engine_floor"],
                            new_page=free["page"],new_gaps=free["cause"],repeat=free["determinism"],
                            free_trace_sha256=free["trace_sha256"]))
    return results


def main():
    trace = natural_trace()
    cases = [original_case(i) for i in (59,19)]
    samples = discovery()
    write(HERE/"RESULT.json",dict(runtime={p.name:sha(p) for p in (HERE/"candidate.py",HERE/"session.py")},
                                  natural=trace,original_cases=cases,discovery_samples=samples))
    print(trace["completed_inputs"],trace["first_substantive_difference"],trace["stop"])
    print([(x["seed"],len(x["actions_on_exact_old_stop"]),x["new_outcome"],x["new_floor"]) for x in samples])


if __name__ == "__main__":
    main()
