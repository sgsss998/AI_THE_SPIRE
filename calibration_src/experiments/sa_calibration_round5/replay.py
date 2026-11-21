"""Replay the sealed R4 retail journal on the selected public S/A interface."""
import argparse
from dataclasses import replace
from importlib import import_module

from experiments.sa_calibration_round3.fresh import replay as view
from experiments.sa_calibration_round4.fresh import invocations
from experiments.sa_calibration_round4.fresh import replay as old
from experiments.sa_calibration_round4.fresh.instance import DEST
from .reference import HERE, R4, ROOT, baseline, read, sha, source, write


def original_inputs():
    from native_pilot import libraries
    libraries(DEST)
    from silent_env.native_compare import verify_capture_record
    prior = read(R4 / "fresh/RESULT.json")
    sealed = read(source(R4 / "fresh", prior["reconciled_official"]))
    for name, digest in sealed["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    journal = view.rows(R4 / "fresh/ACTIONS.jsonl")
    assert [r["index"] for r in journal] == list(range(1, prior["original_inputs"] + 1))
    oracle_file, = [ROOT / name for name in sealed["source_sha256"] if name.endswith("/native_oracle.jsonl")]
    native = {r["data"]["capture_id"]:r for r in view.rows(oracle_file) if r["kind"] == "native_capture"}
    view.NATIVE.clear()
    for row in journal:
        for phase in ("before","after"):
            frame = row[phase]
            key = frame["session"], frame["sequence"]
            if key in view.NATIVE:
                continue
            tag = frame["raw"]["capture_alignment"]
            cap = verify_capture_record(native[tag["capture_id"]], bridge_row=frame, scope=dict(
                native_session=tag["native_session"],bridge_session=key[0],bridge_sequence=key[1],
                native_after_sequence=0,native_through_sequence=tag["native_record_sequence"]))
            assert cap.evidence["exact_capture_binding"] and cap.evidence["bridge_raw_sha256"] == frame["raw_hash"]
            view.NATIVE[key] = cap.payload
    return journal


def unique_ack(row):
    choices = row["before"]["raw"]["game_state"].get("choice_list", [])
    return row["command"] in ("proceed","leave","confirm") or (row["command"] == "choose 0" and len(choices) == 1)


def run(module):
    pinned = baseline()
    journal = original_inputs()
    version = import_module(module)
    signature = version.interface_signature().metadata()
    original_version = read(R4 / "INTERFACE.json")["state_version"]
    assert signature["state_version"].startswith(original_version)
    engine = version.make_engine()
    session = version.make_session(engine)
    frame = session.reset(int(pinned["recorded_original"]["signed"]) % (1 << 64))
    calls = invocations.captures()
    def compare(snapshot):
        assert frame.state.state_version == signature["state_version"]
        projected = replace(frame, state=replace(frame.state, state_version=original_version))
        return old.compare(projected, engine, snapshot)

    records = []
    stop = first_content = None
    for pos, row in enumerate(journal):
        before = compare(row["before"])
        aid, binding = view.map_action(row, frame, engine)
        record = dict(index=row["index"], command=row["command"], action=aid, binding=binding,
                      page=frame.page, offered=view.allowed(frame), actual_reported=row.get("legal",[]),
                      original_before=row["before"]["raw_hash"], original_after=row["after"]["raw_hash"],
                      before=before, actions_executed=[])
        records.append(record)
        if aid is None:
            after = compare(row["after"])
            matched_ack = unique_ack(row) and not after["differences"]
            if unique_ack(row) and set(after["differences"]) == {"page"} and pos+1 < len(journal):
                following = journal[pos+1]
                matched_ack = (unique_ack(following) and row["after"]["raw_hash"]==following["before"]["raw_hash"]
                               and not compare(following["after"])["differences"])
            if matched_ack:
                record.update(status="original_only_confirmation", after=after)
            else:
                stop = dict(index=row["index"],reason="original_choice_not_mapped",floor=before["original"]["resources"][3],
                            page=frame.page,requested=binding,offered=view.allowed(frame),gaps=list(frame.action_gaps))
        elif aid not in view.allowed(frame):
            stop = dict(index=row["index"],reason="missing_public_action",floor=before["original"]["resources"][3],
                        page=frame.page,requested=binding,action=aid,offered=view.allowed(frame),gaps=list(frame.action_gaps))
        else:
            frame = session.step(aid, frame_id=frame.frame_id, action_version=frame.action_version)
            record["actions_executed"].append(aid)
            for seq, event in invocations.received(row, calls):
                extra, details = invocations.binding(row,event,frame,engine)
                assert extra in view.allowed(frame), (row["index"], extra)
                frame = session.step(extra,frame_id=frame.frame_id,action_version=frame.action_version)
                record["actions_executed"].append(extra)
                record.setdefault("incidental_card", []).append(dict(record=seq, binding=details))
            record.update(status="public_action", after=compare(row["after"]))
        for phase in ("before","after"):
            differences = {k:v for k,v in record.get(phase,{}).get("differences",{}).items() if k!="page"}
            if first_content is None and differences:
                first_content = dict(index=row["index"], phase=phase, fields=differences)
        if stop is not None:
            record.update(status="stopped",stop=stop)
            break
    assert signature == version.interface_signature().metadata()
    checkpoints = {}
    for event, receipt in zip(records,journal):
        for phase in ("before","after"):
            if phase in event:
                snap = receipt[phase]
                checkpoints[snap["session"],snap["sequence"]] = event[phase]
    return dict(signature=signature, version=module, seed=pinned["recorded_original"]["seed"],
                original_journal_sha256=sha(R4/"fresh/ACTIONS.jsonl"), independent_holdout=False,
                used_kernel_fallback=False, completed_inputs=sum(r["status"]!="stopped" for r in records),
                official_actions=sum(len(r["actions_executed"]) for r in records), first_content=first_content, stop=stop,
                checked_frames=len(checkpoints),equal_frames=sum(not r["differences"] for r in checkpoints.values()),
                final=view.model(frame,engine), records=records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", action="store_true")
    args = parser.parse_args()
    generation = "round4" if args.control else "round5"
    result = run("experiments.sa_calibration_" + generation + ".release")
    write(HERE / "replay" / ("CONTROL.json" if args.control else "RESULT.json"),result)
    print({k:result[k] for k in ("completed_inputs","official_actions","first_content","stop")})
