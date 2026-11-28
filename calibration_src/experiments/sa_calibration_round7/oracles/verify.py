"""Replay three independent, fixed retail witnesses on the old and requested interfaces."""
import argparse
from dataclasses import replace
from hashlib import sha256
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments.sa_calibration_round2 import release as r2
from experiments.sa_calibration_round2.boss.verify_opening import read_case, receipt
from experiments.sa_calibration_round2.boss.verify_prefix import build_tea
from experiments.sa_calibration_round3.fresh import replay as view
from experiments.sa_calibration_round5 import release as r5
from experiments.sa_calibration_round5.replay import original_inputs
from experiments.sa_calibration_round6 import release as r6
from experiments.sa_calibration_round6.reference import read, sha, write
from experiments.sa_calibration_round6.rewards.verify import checkpoint, step
from . import step_checks
from .step_checks import mismatch

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parents[1]
R2, R5, R6 = (EXPERIMENTS / f"sa_calibration_round{n}" for n in (2, 5, 6))
R7 = "experiments.sa_calibration_round7.release"


def digest(value):
    return sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def checked_file(round_dir, name):
    source = round_dir / name
    expected = read(round_dir / "RELEASE.json")["files"][name]
    if sha(source) != expected:
        raise ValueError(f"Historical witness changed: {source}")
    return source


def compare(kind, expected, actual):
    return [] if expected == actual else [mismatch(kind, expected, actual)]


def tea_pair(version, make_session, actions, probe, charged, uncharged):
    engines = [version.make_engine(), version.make_engine()]
    sessions = [make_session(engine) for engine in engines]
    frames = [session.reset(54072728) for session in sessions]
    for record in actions:
        seq = record["sequence"]
        if seq == 750:
            probe.clear_test_charge(engines[1]._source._env)
        frames = [step(s, f, record["action"]) for s, f in zip(sessions, frames)]
        if seq == 750:
            break
    assert seq == 750
    left, right = frames
    mask_equal = left.supported_actions == right.supported_actions
    evidence = dict(state_sha256=[digest(f.state.vector) for f in frames],
                    state_width=len(left.state.vector), actions_equal=mask_equal,
                    differing_positions=[i for i, pair in enumerate(zip(left.state.vector, right.state.vector)) if pair[0] != pair[1]])
    assert evidence["state_width"] == len(right.state.vector) and mask_equal
    if left.state.vector == right.state.vector:
        return evidence, [mismatch("tea_states_collide", [charged, uncharged], "identical_public_state")]
    values = [int(f.state.vector[3121]) for f in frames]
    return evidence, compare("tea_charge", [charged, uncharged], values)


def tea(candidate):
    case = read(checked_file(R2, "boss/PREFIX.json"))["cases"][0]
    archive = Path(case["source"])
    for name, expected in case["archival_hashes"].items():
        assert sha(archive / name) == expected
    raw, attempts = read_case(archive, case["seed"])
    actions = case["frozen_with_tea_semantics"]["actions"]
    for r in actions:
        assert r == receipt(archive, raw, attempts[r["sequence"]], r["sequence"])
        if r["sequence"] == 750:
            break
    game = raw[751]["raw"]["game_state"]
    counter, = [x["counter"] for x in game["relics"] if x["id"] == "Ancient Tea Set"]
    assert counter == -2 and raw[755]["raw"]["game_state"]["combat_state"]["player"]["energy"] == 5
    with TemporaryDirectory() as directory:
        probe = build_tea(directory)
        legacy, bugs = tea_pair(r2, r2.make_privileged_session, actions, probe, 1, 0)
        current, issues = tea_pair(candidate, candidate.make_session, actions, probe, 1, 0)
    assert [d["kind"] for d in bugs] == ["tea_states_collide"]
    return dict(seed=case["seed"], original_after=raw[751]["raw_hash"], native_counter=counter,
                first_combat_energy=5, control="one simulator copy clears the pending charge; no second retail run",
                historical=legacy, historical_detections=bugs, candidate=current, candidate_issues=issues)


def altered(frame, changes):
    values = list(frame.state.vector)
    for key, value in changes.items():
        values[key] = value
    return replace(frame, state=replace(frame.state, vector=tuple(values)))


def rewards(candidate):
    checks=step_checks
    if candidate.interface_signature().observation_dimension==3127:
        from . import extended as checks
    audit_frame,audit_transition=checks.audit_frame,checks.audit_transition
    journal = original_inputs()
    seed = journal[0]["before"]["raw"]["game_state"]["seed"] % (1 << 64)
    records = read(checked_file(R5, "replay/RESULT.json"))["records"]
    _, _, _, frozen = checkpoint(r5, seed, records)
    engine=candidate.make_engine()
    session=candidate.make_session(engine)
    frame=session.reset(seed)
    for record in records[:128]:
        for action in record["actions_executed"]:
            frame=step(session,frame,action)
    candidate.interface_signature().assert_model_dimensions(len(frame.state.vector),len(frame.supported_actions))
    first = journal[128]
    assert first["index"] == 129
    bugs = compare("missing_reward_actions", first["legal"], view.allowed(frozen))
    assert bugs and not view.allowed(frozen)
    issues, mutations, steps = [], {}, []
    for row in journal[128:133]:
        action = row["aid"]
        native = view.original(row["before"])
        actual = view.model(frame, engine)
        for key, wanted in native.items():
            issues.extend(compare("reward_before_" + key, wanted, actual.get(key)))
        issues.extend(compare("reward_actions", row["legal"], view.allowed(frame)))
        if action not in view.allowed(frame):
            break
        nxt = step(session, frame, action)
        expected = view.original(row["after"])
        observed = view.model(nxt, engine)
        for key, wanted in expected.items():
            issues.extend(compare("reward_after_" + key, wanted, observed.get(key)))
        issues.extend(audit_frame(frame) + audit_transition(frame, action, nxt) + audit_frame(nxt))
        # Corrupt a copy only. The original transaction continues on the real public session.
        if row["index"] == 129:
            changes = {2: frame.state.vector[2]}
        elif row["index"] == 130:
            changes = {17: frame.state.vector[17]}
        elif row["index"] == 132:
            start = 706 + 2 * (len(observed["deck"]) - 1)
            changes = {start: 0, start + 1: 0}
        else:
            changes = {}
        if changes:
            kinds = [d["kind"] for d in audit_transition(frame, action, altered(nxt, changes))]
            assert kinds, (row["index"], changes)
            mutations[str(row["index"])] = kinds
        steps.append(dict(index=row["index"], action=action, expected_actions=row["legal"],
                          gold=observed["resources"][2], belt=observed["potions"], deck_size=len(observed["deck"]),
                          original_before=row["before"]["raw_hash"], original_after=row["after"]["raw_hash"]))
        frame = nxt
    return dict(seed=str(seed), original_reward_rows=view.original(first["before"])["rewards"],
                historical_detections=bugs, candidate_steps=steps, candidate_issues=issues, injected_tests=mutations)


def wall(candidate):
    path = checked_file(R6, "fresh/ACTIONS.jsonl")
    journal = view.rows(path)
    old = read(checked_file(R6, "fresh/REPLAY.json"))
    assert sha(path) == old["original_journal_sha256"]
    event, pick, confirm = journal[30:33]
    state = pick["before"]["raw"]["game_state"]
    cards = state["screen_state"]["cards"]
    ids = [c["uuid"] for c in state["deck"]]
    positions = [ids.index(c["uuid"]) for c in cards]
    assert len(ids) == len(set(ids)) == 15 and len(positions) == len(set(positions)) == 14
    chosen = cards[pick["aid"] - 110]["uuid"]
    remaining = [c["uuid"] for c in confirm["after"]["raw"]["game_state"]["deck"]]
    assert remaining == [uid for uid in ids if uid != chosen] and confirm["aid"] == 172
    assert event["before"]["raw"]["game_state"]["screen_state"]["event_id"] == "Living Wall"
    seed = state["seed"] % (1 << 64)

    def start(version):
        e = version.make_engine()
        s = version.make_session(e)
        f = s.reset(seed)
        for r in old["records"][:31]:
            for a in r["actions_executed"]:
                f = step(s, f, a)
        return e, s, f

    _, _, frozen = start(r6)
    bugs = compare("living_wall_actions", pick["legal"], view.allowed(frozen))
    assert bugs and not view.allowed(frozen)
    e, s, frame = start(candidate)
    options = [(i, [e._source._backend.CARD_IDS[row[1]-1], row[2]])
               for i, row in view.options(frame) if row[0] == 1 and row[5]]
    issues = compare("living_wall_card_list", [[i, view.card(c)] for i, c in enumerate(cards)], [[i, c] for i, c in options])
    issues.extend(compare("living_wall_actions", pick["legal"], view.allowed(frame)))
    details = dict(page=frame.page, offered=view.allowed(frame))
    if pick["aid"] in view.allowed(frame):
        bindings = [int(frame.state.vector[2684+j])-203 for j in range(len(cards))]
        issues.extend(compare("living_wall_permanent_positions", positions, bindings))
        preview = step(s, frame, pick["aid"])
        selected_rows = [j for j in range(len(cards)) if preview.state.vector[325+6*j]]
        idx = pick["aid"] - 110
        issues.extend(compare("living_wall_preview_selected_row", [idx], selected_rows))
        issues.extend(compare("living_wall_confirm_actions", confirm["legal"], view.allowed(preview)))
        details.update(positions=bindings, selected_rows=selected_rows)
        if confirm["aid"] in view.allowed(preview):
            final = step(s, preview, confirm["aid"])
            actual = view.model(final, e)["deck"]
            expected = [view.card(c) for c in confirm["after"]["raw"]["game_state"]["deck"]]
            issues.extend(compare("living_wall_confirmed_deck", expected, actual))
            details.update(final_deck=actual, final_page=final.page)
    # Adjacent identical-looking Strikes must have distinct permanent-slot bindings.
    assert view.card(cards[0]) == view.card(cards[1]) and positions[0] != positions[1]
    corrupted = positions.copy()
    corrupted[0], corrupted[1] = corrupted[1], corrupted[0]
    negative = compare("living_wall_permanent_positions", positions, corrupted)
    assert negative
    return dict(seed=str(seed), raw_sha256=sha(path), native_grid_inputs=[pick["index"], confirm["index"]],
                native_uuids_removed=[chosen], remaining_native_deck=len(remaining), native_deck_positions=positions,
                historical_detections=bugs, candidate=details, candidate_issues=issues,
                injected_tests=["living_wall_swapped_same_face_slots"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default=R7)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-clean", action="store_true", help="also fail on any candidate difference")
    args = parser.parse_args()
    candidate = import_module(args.candidate)
    data = dict(candidate=args.candidate, references="fixed development witnesses",
                tea=tea(candidate), rewards=rewards(candidate), living_wall=wall(candidate))
    data["historical_bugs_caught"] = sum(bool(data[k]["historical_detections"]) for k in ("tea", "rewards", "living_wall"))
    data["candidate_issues"] = sum(len(data[k]["candidate_issues"]) for k in ("tea", "rewards", "living_wall"))
    if args.output:
        write(args.output, data)
    print(json.dumps({k: data[k] for k in ("candidate", "historical_bugs_caught", "candidate_issues")}, ensure_ascii=False))
    if args.require_clean and data["candidate_issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
