"""Replay sealed fixed and pilot GRID counterexamples, then verify the economic effect and occurrence."""
from concurrent.futures import ProcessPoolExecutor
from collections import Counter, defaultdict
import gzip
import json
from functools import lru_cache
from pathlib import Path

from experiments.common_relic193.hidden import verify as observed_rng
from experiments.policy_event_integration.session import load_extension
from experiments.sa_calibration_round6.reference import read,sha,write
from experiments.sa_calibration_round6.rewards.verify import view
from experiments.sa_calibration_round7.triage import rows,RUNS
from experiments.wing_removal_640.session import current_deck
from silent_env.action193 import choice_action
from silent_env.runtime import StaleFrameError
from . import candidate
from .original import transformations
from .rules import inspect
from .session import PREFIX

HERE=Path(__file__).resolve().parent
R6=HERE.parents[1]/"sa_calibration_round6"
probe=lru_cache(maxsize=1)(lambda: load_extension(observed_rng.BUILD,observed_rng.PIN))


def step(s,f,a):
    return s.step(a,frame_id=f.frame_id,action_version=f.action_version)


def check(job):
    cohort,r=job
    engine=candidate.make_engine()
    s=candidate.make_session(engine)
    f=s.reset(r["seed"])
    for aid in r["actions"]:
        if not f.supported_actions[aid]:
            return dict(seed=r["seed"],cohort=cohort,earlier_changed=f.page)
        f=step(s,f,aid)
    if f.page!=PREFIX+"GRID":
        return dict(seed=r["seed"],cohort=cohort,unchanged_or_other_adapter=f.page)
    picker=engine._r7_picker
    task,label=picker.task,picker.label
    ids=engine._source._backend.CARD_IDS
    positions=picker.positions
    old=current_deck(engine)
    chosen=next((j for j,pos in reversed(list(enumerate(positions))) if j in picker.selectable and ids[old[pos][0]-1]=="Strike_G"),picker.selectable[0])
    # Alternate between same-faced duplicate and non-starting target.
    if r["seed"]%2:
        for j in range(len(positions)-1,-1,-1):
            if j in picker.selectable and ids[old[positions[j]][0]-1] not in ("Strike_G","Defend_G","Neutralize","Survivor","Parasite"):
                chosen=j
                break
    target=positions[chosen]
    aid=choice_action(chosen)
    assert tuple(int(f.state.vector[2684+j])-203 for j in range(len(positions)))==positions
    preview=step(s,f,aid)
    assert current_deck(engine)==old and preview.state.vector[28]==1 and preview.state.vector[325+6*chosen]==1
    assert not any(preview.supported_actions[a] for a in range(110,170)) and preview.supported_actions[172] and preview.supported_actions[173]
    back=step(s,preview,173)
    assert back.state.vector==f.state.vector and back.supported_actions==f.supported_actions
    f=step(s,back,aid)
    discarded=None
    for j in range(2):
        if f.supported_actions[105+j]:
            previous=f;discarded=int(f.state.vector[17+j]);f=step(s,f,105+j)
            assert f.page==previous.page and f.state.vector[17+j]==0 and not f.supported_actions[105+j]
            assert current_deck(engine)==old and f.state.vector[28]==1 and f.state.vector[325+6*chosen]==1
            break
    record=dict(seed=r["seed"],cohort=cohort,origin=label,task=task,offer_rows=len(positions),choose_slot=chosen,
                deck_position=target,chosen=ids[old[target][0]-1],same_face_occurrences=sum(c[:2]==old[target][:2] for c in old),
                floor=int(f.state.vector[3]),discarded=discarded,paid_gold=75 if label=="THE_CLERIC" else 0)
    old_hp,old_max,old_gold=f.state.vector[:3]
    if task==1:
        g=probe().audit(engine._source._env)
        counter,s0,s1=g["all_rng"][6]
        record["rng"]=[counter,s0%(1<<64),s1%(1<<64)]
    leave=step(s,f,172)
    assert leave.page==PREFIX+"LEAVE" and leave.engine_steps==f.engine_steps+1
    try:
        step(s,f,172)
    except StaleFrameError:
        pass
    else:
        raise AssertionError("Old card confirmation accepted again")
    now=current_deck(engine)
    others=old[:target]+old[target+1:]
    if task==3:
        assert now==old[:target]+((old[target][0],old[target][1]+1,*old[target][2:]),)+old[target+1:]
    elif task==4:
        assert now==others
    else:
        assert now[:-1]==others
        record["replacement"]=ids[now[-1][0]-1]
    hp,maxhp,gold=leave.state.vector[:3]
    assert gold==old_gold and (record["chosen"]=="Parasite" or (hp,maxhp)==(old_hp,old_max))
    mapped=step(s,leave,171 if label=="REST" else 110)
    assert mapped.state.vector[6]==5 and view.allowed(mapped) and current_deck(engine)==now
    record["post_game_map"]=True
    return record


def seed_result(job):
    try:
        return check(job)
    except Exception as exc:
        print(job[0],job[1]["seed"],type(exc).__name__,str(exc),flush=True)
        return dict(seed=job[1]["seed"],cohort=job[0],error=repr(exc))


def main():
    fixed=read(R6/"regression/RESULT.json")["records"]
    pilot=[r for _,r in rows(RUNS/"pilot-r6")]
    work=[(n,r) for n,records in (("fixed704",fixed),("pilot200",pilot)) for r in records if r["page"]=="GRID_UNVERIFIED"]
    assert len([r for n,r in work if n=="fixed704"])==92
    # The first 3,200 sealed baseline games had finished when this family was assigned.
    # Pick the shortest five old prefixes per origin/action for practical independent replay.
    discovery=RUNS/"discovery-r6"
    samples=defaultdict(list)
    for index in range(32):
        part=discovery/f"shard-{index:04}.jsonl.gz"
        with gzip.open(part,"rt") as stream:
            for line in stream:
                row=json.loads(line)
                if row["page"]!="GRID_UNVERIFIED":
                    continue
                previous=row["stop"]["before"]
                if previous.get("event") or "REST_ROOM" in previous["scene"]:
                    key=(previous.get("event"),previous["page"],row["actions"][-1])
                    samples[key].append(row)
    for entries in samples.values():
        entries.sort(key=lambda r:(len(r["actions"]),r["seed"]))
        work.extend(("discovery_sample",r) for r in entries[:5])
    assert inspect()==read(HERE/"RULES.json")
    with ProcessPoolExecutor(3) as pool:
        cases=list(pool.map(seed_result,work))
    assert not [r for r in cases if "error" in r], [r for r in cases if "error" in r]
    changed=[r for r in cases if r.get("post_game_map")]
    transformed=[r for r in changed if r["task"]==1]
    for record,retail in zip(transformed,transformations(transformed),strict=True):
        assert record["replacement"]==retail,(record,retail)
        record["retail_replacement"]=retail
    reports={}
    for n in ("fixed704","pilot200","discovery_sample"):
        sub=[r for r in changed if r["cohort"]==n]
        reports[n]=dict(grid_stops=sum(c==n for c,_ in work),fixed=len(sub),by_source=dict(Counter(r["origin"] for r in sub)),
                        potion_discards=sum(bool(r["discarded"]) for r in sub))
    out=dict(reports=reports, original_jar=read(HERE/"RULES.json")["retail_jar"], hashes={p.name:sha(p) for p in sorted(HERE.glob("*")) if p.is_file() and p.suffix in (".java",".py")}, matched_original_transformations=len(transformed),cases=cases)
    write(HERE/"RESULT.json",out)
    print(reports,len(transformed))


if __name__=="__main__":
    main()
