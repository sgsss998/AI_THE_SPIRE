"""Reproduce green, colorless and curse transformation cases using independent original draws."""
import gzip
import json
from pathlib import Path

from experiments.hand_selection_frontiers193 import evidence
from experiments.sa_calibration_round6.reference import read,sha,write
from experiments.sa_calibration_round7.triage import RUNS
from experiments.wing_removal_640.session import observer, current_deck
from silent_env.action193 import choice_action
from . import card_order,color_candidate
from .colorless import COLORLESS
from .original import transformations
from .retail import case as capture_case
from .session import CURSE,NEVER_REMOVE
from .verify import probe,step

HERE=Path(__file__).resolve().parent


def examples():
    engine=color_candidate.make_engine()
    color_candidate.make_session(engine).reset(1)
    names=engine._source._backend.CARD_IDS
    found={"colorless":[],"curse":[]}
    root=RUNS/"discovery-r6"
    for index in range(32):
        for line in gzip.open(root/f"shard-{index:04}.jsonl.gz","rt"):
            row=json.loads(line)
            if row["page"]!="GRID_UNVERIFIED":
                continue
            stop=row["stop"]
            after=dict(stop["after"].get("state_nonzero",[]))
            if after.get(26)!=1:
                continue
            for i in range(706,898,2):
                if i not in after:continue
                name=names[int(after[i])-1]
                color="colorless" if name in COLORLESS else "curse" if name in CURSE and name not in NEVER_REMOVE else None
                if color and (stop["before"].get("event"),row["actions"][-1]) in (("LIVING_WALL",111),("TRANSMORGRIFIER",110)):
                    found[color].append((len(row["actions"]),row["seed"],name,row["actions"]))
    return {color:sorted(options)[:12] for color,options in found.items()}


def branch(seed,name,actions,color):
    e=color_candidate.make_engine();s=color_candidate.make_session(e);f=s.reset(seed)
    for a in actions:
        if not f.supported_actions[a]:return None
        f=step(s,f,a)
    if f.page!="PERMANENT_CARD_GRID":return None
    p=e._r7_picker
    names=e._source._backend.CARD_IDS
    j=next(i for i,pos in enumerate(p.positions) if names[p.cards[pos][0]-1]==name)
    aid=choice_action(j)
    g=probe().audit(e._source._env)
    rec=dict(seed=seed,floor=int(f.state.vector[3]),rng=[int(x)%(1<<64) for x in g["all_rng"][6]],
             chosen=name,color=color,position=p.positions[j],public_action=aid,offered=bool(f.supported_actions[aid]))
    if color=="colorless":
        assert rec["offered"]
        f=step(s,f,aid);f=step(s,f,172);f=step(s,f,110)
        rec["result"]=names[current_deck(e)[-1][0]-1]
        assert f.state.vector[6]==5
    else:
        # The protected public mask stays closed. Inspect the original backing rule on a detached clone.
        assert not rec["offered"]
        clone=e._source._env.clone()
        assert clone.is_valid(81+j) and clone.step(81+j)
        cards=observer().deck(clone)
        rec["result"]=names[cards[-1][0]-1]
        rec["unchanged_public_deck"]=current_deck(e)==p.cards
        if len(cards)!=len(p.cards):return None
    return rec


def main():
    order=card_order.extract()
    assert order==read(HERE/"CARD_ORDER.json")
    picks=examples()
    caseargs,= [q for q in evidence.event_paths() if q[3]=="Living Wall"]
    path,seq,row,source,nlog=caseargs
    samples={r["sequence"]:r for r in evidence.lines(path)}
    prefix=next(r["actions"] for _,r in evidence.cases() if r["seed"]==6000008)
    result=branch(6000008,"Master of Strategy",prefix,"colorless")
    assert result is not None
    tested=[result]
    for color,entries in picks.items():
        for _,seed,name,acts in entries:
            r=branch(seed,name,acts,color)
            if r:tested.append(r)
    expected=transformations(tested)
    for row,original in zip(tested,expected,strict=True):
        row["retail"]=original
        row["matched"]=row["result"]==original
        if row["offered"]:assert row["matched"],row
    colors=[r for r in tested if r["offered"]]
    curses=[r for r in tested if not r["offered"]]
    assert len(colors)>=1
    stages=capture_case(6000008,prefix,[samples[i] for i in range(seq,seq+4)],1,runtime=color_candidate)
    assert all(not s["measured_action_gaps"].get("missing") for s in stages)
    out=dict(independent_original_cards=order["registered_cards"],silent_positions_verified=order["validated_silent_pool_positions"],
             colorless_pool=len(order["source_colorless"]),colorless_branches=len(colors),retained_curse_branches=len(curses),
             curse_counterexamples=sum(not r["matched"] for r in curses),historical_wall=stages,results=tested)
    write(HERE/"COLORS.json",out)
    print(len(colors),len(curses),out["curse_counterexamples"])


if __name__=="__main__":
    main()
