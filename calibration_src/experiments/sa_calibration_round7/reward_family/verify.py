"""Re-execute fixed stop prefixes, claim or leave rewards, then compare retail receipts."""
import argparse
from dataclasses import replace
from tempfile import TemporaryDirectory
from importlib import import_module
from pathlib import Path

from experiments.sa_calibration_round5.reference import read, sha, write
from experiments.sa_calibration_round6.cohort.audit import parent_runs
from experiments.sa_calibration_round6.rewards.verify import step, view
from experiments.sa_calibration_round7.oracles.verify import checked_file
from silent_env.runtime import StaleFrameError
from . import evidence
from .session import inventory, ordinary
from experiments.common_relic193.rules import relic_id

HERE = Path(__file__).resolve().parent
R6 = HERE.parents[1] / "sa_calibration_round6"


def play_to(runtime, seed, actions):
    engine = runtime.make_engine()
    session = runtime.make_session(engine)
    frame = session.reset(seed)
    for a in actions:
        frame = step(session, frame, a)
    return engine, session, frame


def bound_step(session, frame, a):
    nxt = step(session, frame, a)
    try:
        session.step(a,frame_id=frame.frame_id,action_version=frame.action_version)
    except StaleFrameError:
        return nxt
    raise AssertionError("A consumed reward token was accepted a second time")


def branch(runtime, seed, prefix, mode):
    e,s,f = play_to(runtime, seed, prefix)
    initial = view.model(f,e)
    gold, = [v for k,v in initial["rewards"] if k == "GOLD"]
    potions = [v for k,v in initial["rewards"] if k == "POTION"]
    assert len(potions) <= 1 and initial["rewards"][-1] == ["CARD",None]
    actions = []
    def apply(frame, a):
        actions.append(a)
        return bound_step(s,frame,a)
    def claim(frame, kind):
        before = view.model(frame,e)
        pos, = [i for i,(k,_) in enumerate(before["rewards"]) if k == kind]
        nxt = apply(frame,110+pos)
        if kind != "CARD":
            assert view.model(nxt,e)["rewards"] == before["rewards"][:pos]+before["rewards"][pos+1:]
        return nxt

    expected_deck = list(initial["deck"])
    expected_gold = initial["resources"][2]
    expected_belt = list(initial["potions"])
    chosen = None
    if mode == "all":
        f = claim(f,"GOLD")
        expected_gold += gold
        assert f.state.vector[2] == expected_gold
        if potions:
            f = claim(f,"POTION")
            expected_belt[expected_belt.index(None)] = potions[0]
            assert view.model(f,e)["potions"] == expected_belt
        f = claim(f, "CARD")
        offer = view.model(f,e)["offered_cards"]
        assert len(offer) == 3
        f = apply(f,177)
        f = claim(f,"CARD")
        assert view.model(f,e)["offered_cards"] == offer
        chosen = offer[seed % 3]
        f = apply(f,110+seed%3)
        expected_deck.append(chosen)
        assert view.model(f,e)["deck"] == expected_deck
    f = apply(f,171)
    actual = view.model(f,e)
    assert f.state.vector[6] == 5 and actual["next_x"] and actual["relics"] == initial["relics"]
    assert actual["deck"] == expected_deck and actual["potions"] == expected_belt and f.state.vector[2] == expected_gold
    return dict(actions=actions, old_frame_rejections=len(actions), gold=expected_gold, potions=expected_belt,
                deck_size=len(expected_deck), chosen=chosen, next_x=actual["next_x"])


def cohort(runtime):
    cohort = read(checked_file(R6, "cohort/R6.json"))["records"]
    fixed = {r["seed"]:r["actions"] for r in parent_runs()}
    gained=[]
    rows=[]
    for item in cohort:
        seed=item["seed"]
        e,s,f = play_to(runtime,seed,fixed[seed])
        old=item["endpoint"]["actions"]
        record = dict(seed=seed, source=item["source"], previous_actions=old, actions=view.allowed(f), page=f.page,
                      held_relics=item["held_relics"])
        if not old and record["actions"]:
            # Input here is selected from all 58 historical stops, not a whitelist of seeds.
            assert item["source"] == "MONSTER" and inventory(f.state.vector)
            assert f.policy_mask == f.supported_actions and not f.action_gaps
            record["claimed"] = branch(runtime,seed,fixed[seed],"all")
            record["left_all"] = branch(runtime,seed,fixed[seed],"leave")
            gained.append(seed)
        else:
            assert old == record["actions"], (seed, old, record)
        rows.append(record)
    assert len(rows) == 58 and len(gained) == 9
    return dict(previous_stops=57, newly_opened=len(gained), seeds=gained, closed=57-len(gained), records=rows)


def scope_controls(runtime):
    row = next(r for r in parent_runs() if r["seed"] == 9000003)
    e,s,last = play_to(runtime, row["seed"], row["actions"][:-1])
    final = step(s,last,row["actions"][-1])
    assert ordinary(last,final)
    negatives = {}
    for name, changes in {
        "event_reward": {8:3}, "second_act_wrong_inventory": {4:2},
        "sozu": {34:relic_id("SOZU")}, "golden_idol": {34:relic_id("GOLDEN_IDOL")},
        "ectoplasm": {34:relic_id("ECTOPLASM")}, "counter_changed": {35:2},
        "wallet_changed_before_claim": {2:final.state.vector[2]+11}, "invalid_potion_gain_in_transition": {17:1},
    }.items():
        vector=list(final.state.vector)
        for i,value in changes.items():
            vector[i]=value
        changed=replace(final,state=replace(final.state,vector=tuple(vector)))
        assert not ordinary(last,changed), name
        negatives[name] = sorted(changes)
    return negatives


def deep(runtime):
    from experiments.sa_calibration_round7.deep.replay import parasite
    with TemporaryDirectory() as directory:
        result = parasite(runtime, directory)
    assert result["real_commands"] == len(result["simulated_commands"]) == 30
    assert result["stop"] is None and result["first_difference"] is None
    assert all(not x["diff"] for x in result["comparisons"])
    return dict(seed=result["seed"], opening="retail precombat save, Act II floor 18",
                precombat_save_sha256=result["precombat_save_sha256"], sources=result["real_input_archives"],
                matched_actions=30, compared_frames=len(result["comparisons"]), first_difference=None,
                final_frames=result["comparisons"][-2:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default="experiments.sa_calibration_round7.reward_family.candidate")
    parser.add_argument("--output", type=Path, default=HERE/"RESULT.json")
    args = parser.parse_args()
    runtime = import_module(args.runtime)
    data = dict(runtime=args.runtime, sources={p.name:sha(p) for p in HERE.glob("*.py")}, rules=evidence.retail_rules(),
                cohort=cohort(runtime), wrist=evidence.wrist_receipts(runtime,"wrist"),
                wrist_drop=evidence.wrist_receipts(runtime,"wrist_drop"), stone_retail=evidence.stone_archive(),
                stone_prefix=evidence.smooth_replay(runtime), deep_act2=deep(runtime), rejected=scope_controls(runtime))
    write(args.output,data)
    print(data["cohort"]["seeds"], data["wrist"]["matched_public_reward_and_map_frames"],
          data["wrist_drop"]["matched_public_reward_and_map_frames"], data["stone_prefix"])


if __name__ == "__main__":
    main()
