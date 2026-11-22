"""Archive actual retail branches and replay them with the frozen R6 public interface."""
import argparse
import gzip
import json
from hashlib import sha256
from pathlib import Path

from silent_env.native_compare import verify_capture_record
from silent_env.runtime import StaleFrameError
from experiments.sa_calibration_round3.fresh import replay as views
from experiments.sa_calibration_round5.shop.prefix import advance
from experiments.sa_calibration_round6 import release
from experiments.sa_calibration_round6.reference import HERE as R6, read, sha, write
from .native import BRANCHES, NATIVE, ROOT, R4, SAVE, SEED, ledger

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "SOURCE.json.gz"


def collect():
    from native_pilot import libraries
    saved = {"save_sha256": sha(SAVE), "branches": {}}
    archived = ledger(R4 / "ACTIONS.jsonl")
    from .native import semantic
    for name in BRANCHES:
        dest = NATIVE / ("compact_native_r6_reward_" + name + "_001")
        out = dest / "r6_rewards"
        _, _, legal, *_ = libraries(dest)
        restore = read(out / "RESTORE_INPUT.json")
        assert restore["saves"]["THE_SILENT.autosave"]["sha256"] == saved["save_sha256"]
        route = ledger(out / "prefix.jsonl")
        assert [r["index"] for r in route] == list(range(96, 129))
        for r in route:
            old = archived[r["index"] - 1]
            for phase in ("before", "after"):
                assert semantic(r[phase]["raw"]["game_state"]) == semantic(old[phase]["raw"]["game_state"])
        oracle_file, = (dest / "native_oracle").glob("*/*.jsonl")
        oracle_rows = ledger(oracle_file)
        native = {r["data"]["capture_id"]: r for r in oracle_rows if r["kind"] == "native_capture"}
        hand = []
        for r in route:
            if r.get("wire_type") != "physical_hand_key":
                continue
            lo, hi = [r[k]["raw"]["capture_alignment"]["native_record_sequence"] for k in ("before", "after")]
            uses = [x["data"] for x in oracle_rows if lo < x["seq"] <= hi and x["kind"] == "native_card_invoked"]
            before, after = [r[k]["raw"]["game_state"] for k in ("before", "after")]
            if r["aid"] == 172:
                expected = [c["uuid"] for c in before["screen_state"]["selected"]]
                assert expected and all(u in [c["uuid"] for c in after["combat_state"]["discard_pile"]] for u in expected)
                assert after["screen_type"] != "HAND_SELECT"
            else:
                expected = [before["screen_state"]["hand"][r["aid"] - 110]["uuid"]]
                assert expected == [c["uuid"] for c in after["screen_state"]["selected"]]
            hand.append(dict(index=r["index"], aid=r["aid"], card_uuids=expected, use_card=uses))
        assert len(hand) == 2 and hand[0]["card_uuids"] == hand[1]["card_uuids"]
        assert not any(h["use_card"] for h in hand)
        source_frames, choices = {}, []
        for r in ledger(out / "choices.jsonl"):
            assert r["legal"] == legal(r["before"]["raw"])
            receipt = {k: r[k] for k in ("label", "aid", "command", "request", "at")}
            for phase in ("before", "after"):
                snap = r[phase]
                key = snap["raw_hash"]
                cap_id = snap["raw"]["capture_alignment"]["capture_id"]
                source_frames[key] = dict(bridge=snap, oracle=native[cap_id], reported_mask=legal(snap["raw"]))
                receipt[phase] = key
            choices.append(receipt)
        end = read(out / "END.json")
        assert choices[-1]["after"] == end["raw_hash"] and end["raw"]["game_state"]["screen_type"] == "MAP"
        assert route[-1]["after"]["raw_hash"] == choices[0]["before"]
        start = source_frames[choices[0]["before"]]["bridge"]
        session_dir = dest / "bridge/sessions" / start["session"]
        closed = read(out / "CLOSED.json")
        assert not closed["input_dispatched"] and closed["game_exit"] == read(dest / "process_exit.json")
        assert closed["unchanged_evidence"] == {k: sha(out / k) for k in ("END.json", "choices.jsonl", "prefix.jsonl", "PHYSICAL.jsonl")}
        paths = [dest / "target.json", dest / "process_exit.json", oracle_file, session_dir / "raw.jsonl", session_dir / "attempts.jsonl"]
        paths.extend(out / x for x in ("RESTORE_INPUT.json", "prefix.jsonl", "PHYSICAL.jsonl", "choices.jsonl", "END.json", "CLOSE.json", "CLOSED.json"))
        saved["branches"][name] = dict(prefix_inputs=33, hand=hand, choices=choices, frames=source_frames,
                original_files={q.relative_to(ROOT).as_posix(): sha(q) for q in paths}, closed=closed)
    SOURCE.write_bytes(gzip.compress(json.dumps(saved, separators=(",", ":"), ensure_ascii=False).encode(), mtime=0))


def measure_frame(entry, frame, engine):
    snap = entry["bridge"]
    tag = snap["raw"]["capture_alignment"]
    scope = dict(native_session=tag["native_session"], bridge_session=snap["session"],
                 bridge_sequence=snap["sequence"], native_after_sequence=0,
                 native_through_sequence=tag["native_record_sequence"])
    capture = verify_capture_record(entry["oracle"], bridge_row=snap, scope=scope)
    assert capture.evidence["exact_capture_binding"] and capture.evidence["bridge_raw_sha256"] == snap["raw_hash"]
    views.NATIVE[(snap["session"], snap["sequence"])] = capture.payload
    actual, model = views.original(snap), views.model(frame, engine)
    assert all(model.get(k) == v for k, v in actual.items()), (actual,model)
    native_actions, public_actions = entry["reported_mask"], model["supported"]
    if snap["raw"]["game_state"]["screen_type"] == "MAP":
        assert set(native_actions) == set(public_actions) | {176} and 176 not in public_actions
    else:
        assert native_actions == public_actions, (native_actions, public_actions)
    return dict(capture=snap["raw_hash"], state_sha256=sha256(json.dumps(frame.state.vector).encode()).hexdigest(),
                values=actual, original_actions=native_actions, model_actions=public_actions)


def verify():
    source = json.loads(gzip.decompress(SOURCE.read_bytes()))
    freeze = read(R6 / "FREEZE.json")
    assert release.source_hashes() == freeze["runtime"] and sha(R6 / "INTERFACE.json") == freeze["interface_sha256"]
    replay = read(R6 / "replay/RESULT.json")
    assert replay["signature"] == release.interface_signature().metadata()
    prefix = replay["records"][:128]
    assert [r["index"] for r in prefix] == list(range(1, 129)) and all(r["status"] != "stopped" for r in prefix)
    result = dict(seed=replay["seed"], floor=10, shared_development_save=True, heldout=False,
                  freeze_sha256=sha(R6 / "FREEZE.json"), source_bundle_sha256=sha(SOURCE),
                  source_save_sha256=source["save_sha256"], branches={})
    for branch, case in source["branches"].items():
        engine = release.make_engine()
        session = release.make_session(engine)
        frame = session.reset(SEED % (1 << 64))
        for row in prefix:
            for aid in row["actions_executed"]:
                frame = advance(session, frame, aid)
        assert [r["label"] for r in case["choices"]] == list(BRANCHES[branch])
        steps, frames = [], {}
        for r in case["choices"]:
            b, a = [case["frames"][r[x]] for x in ("before", "after")]
            frames[r["before"]] = measure_frame(b, frame, engine)
            aid, binding = views.map_action(dict(aid=r["aid"], before=b["bridge"]), frame, engine)
            assert aid is not None and aid in views.allowed(frame) and r["aid"] in b["reported_mask"]
            old = frame
            frame = advance(session, frame, aid)
            try:
                advance(session, old, aid)
            except StaleFrameError:
                pass
            else:
                raise AssertionError("Repeated input on an old reward frame was accepted")
            frames[r["after"]] = measure_frame(a, frame, engine)
            steps.append(dict(**r, model_action=aid, binding=binding, stale_rejected=True))
        result["branches"][branch] = dict(steps=steps, frames=frames, hand=case["hand"], checked_prefix=case["prefix_inputs"], closed=case["closed"],
                                          final=frames[steps[-1]["after"]]["values"])
    first = [b["frames"][b["steps"][0]["before"]] for b in result["branches"].values()]
    assert len({f["state_sha256"] for f in first}) == 1
    assert first[0]["values"]["rewards"] == [["GOLD",20],["POTION","regenpotion"],["CARD",None]]
    final = {k: v["final"] for k,v in result["branches"].items()}
    assert final["skip"] == final["leave"] and final["leave"]["resources"][2] == 237
    assert final["potion"]["resources"][2] == 257 and final["potion"]["deck"] == final["leave"]["deck"] + [["Flying Knee",0]]
    assert all(x["next_x"] == [1,3] and x["potions"] == [None,None] for x in final.values())
    # Each decision's mask is checked before its chosen input, including revisits.
    steps = [step for b in result["branches"].values() for step in b["steps"]]
    matched_masks = sum(
        b["frames"][r["before"]]["original_actions"] == b["frames"][r["before"]]["model_actions"]
        for b in result["branches"].values() for r in b["steps"]
    )
    result.update(original_actions=len(steps), stale_rejected=sum(r["stale_rejected"] for r in steps),
                  matched_reward_masks=matched_masks, map_control_gap=176)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true", help="Rebuild the portable input archive from local retail recordings")
    if parser.parse_args().collect:
        collect()
    result = verify()
    write(HERE / "RESULT.json", result)
    print(result["original_actions"], "native actions, three final maps,", result["stale_rejected"], "stale inputs rejected")
