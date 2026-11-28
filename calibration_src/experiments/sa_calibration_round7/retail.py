"""Compare every recorded decision, including retail choices the recorded player never used."""
import argparse
from collections import Counter
from dataclasses import replace
import importlib
from pathlib import Path

from experiments.sa_calibration_round4.fresh import invocations
from experiments.sa_calibration_round5.replay import original_inputs
from experiments.sa_calibration_round6 import replay as comparator
from experiments.sa_calibration_round6.reference import R4, read, sha, write
from .wall import verify as wall
from .shop import verify as shop

HERE = Path(__file__).resolve().parent


def inspect(frame, engine, row):
    public = set(wall.legal(frame))
    mapped, unbound, missing = set(), [], []
    map_return = row["before"]["raw"]["game_state"]["screen_type"] == "MAP"
    for native in sorted(set(row["legal"])):
        try:
            aid, detail = shop.map_input(dict(row, aid=native),frame,engine)
        except (ValueError, KeyError, IndexError) as error:
            aid, detail = None, dict(reason=repr(error))
        if aid is None:
            unbound.append(dict(retail_action=native, evidence=detail))
        else:
            mapped.add(aid)
            if aid not in public:
                missing.append(dict(retail_action=native, model_action=aid, evidence=detail))
    unmatched = sorted(public-mapped)
    omitted_return = bool(map_return and any(x["retail_action"]==176 for x in missing))
    if omitted_return:
        missing = [x for x in missing if x["retail_action"] != 176]
    return dict(missing=missing, unbound=unbound, unmatched_model_actions=unmatched, map_return_only_control=omitted_return,
                declared_complete=frame.policy_mask is not None)


def run(edition, cohort):
    module = importlib.import_module(edition)
    sig = module.interface_signature().metadata()
    if cohort == "r6-natural":
        journal, calls, _ = wall.loaded()
        path = wall.R6/"fresh/ACTIONS.jsonl"
    else:
        journal, calls = original_inputs(), invocations.captures()
        path = R4/"fresh/ACTIONS.jsonl"
    seed = journal[0]["before"]["raw"]["game_state"]["seed"] % (1 << 64)
    inherited = read(wall.R6/"INTERFACE.json")["state_version"]
    def compare(engine, frame, snap):
        assert frame.state.state_version == sig["state_version"]
        projected = replace(frame, state=replace(frame.state,state_version=inherited))
        diffs = comparator.compare(projected,engine,snap)["differences"]
        if diffs.get("next_x")=={"model":[0],"original":[]} and shop.boss_entry(frame,engine,snap):
            del diffs["next_x"]
        cards = shop.combat_card_offer(frame,engine,snap)
        if cards is not None and diffs.get("offered_cards")=={"model":None,"original":cards}:
            del diffs["offered_cards"]
            if diffs.get("page")=={"model":9,"original":10}:
                del diffs["page"]
        return diffs
    result, _ = wall.retail_replay(journal, calls, seed=seed, session_factory=module.make_session,
        engine_factory=module.make_engine, compare_frame=compare, inspect_before=inspect,map_input=shop.map_input)
    counts = Counter()
    first = {}
    for row in result["rows"]:
        check = row["action_review"]
        for key in ("missing","unbound","unmatched_model_actions"):
            if check[key]:
                counts[key]+=1
                first.setdefault(key,dict(input=row["index"],floor=row["floor"],page=row["page"],evidence=check[key]))
        counts["map_return_display_difference"] += int(check["map_return_only_control"])
        counts["compared"]+=1
        counts["all_choices_bound_and_equal"]+=int(not any(check[k] for k in ("missing","unbound","unmatched_model_actions")))
    result.update(edition=edition,interface=sig,seed=seed,development_replay=True,
                  journal_sha256=sha(path),menu_counts=dict(counts),first_menu_findings=first)
    folder = HERE/"retail"/sig["state_sha256"]
    write(folder/(cohort+".json"),result)
    print(cohort,result["completed_inputs"],result["total_original_inputs"],counts,
          "first_content",result["first_substantive_difference"],"stop",result["stop"],flush=True)

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("cohort",choices=("r4-natural","r6-natural"))
    parser.add_argument("--edition",default="experiments.sa_calibration_round7.combined")
    args=parser.parse_args()
    run(args.edition,args.cohort)
