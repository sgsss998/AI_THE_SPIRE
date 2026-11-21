"""Freeze or verify R3 without overwriting any captured game or frozen manifest."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from experiments.sa_calibration_round2 import verify_release as parent
from . import release

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_batch():
    base = HERE / "regression"
    batch = read(base / "RESULT.json")
    for value in batch.values():
        if isinstance(value, dict) and {"path", "sha256"} <= value.keys():
            assert digest(base / value["path"]) == value["sha256"], value["path"]
    native = read(base / batch["run"]["path"])
    assert native["valid"] and native["signature_unchanged"]
    assert read(HERE / "INTERFACE.json") == native["current_interface"] == batch["interface"]
    full = read(base / batch["full"]["path"])
    assert len(full["runs"]) == 704
    assert batch["summary"]["fixed"]["outcomes"] == {"loss":350, "unsupported":290}
    assert batch["summary"]["additional"]["outcomes"] == {"loss":24, "unsupported":40}
    groups = batch["focused_groups"].values()
    assert sum(item["old_prefix_complete"] for item in groups) == 53
    assert sum(item["actual_public_followup"] for item in groups) == 34
    assert batch["semantic_prefix_reconciliation"]["strict_unmodified_complete"] == 702
    assert batch["semantic_prefix_reconciliation"]["endpoints_all_3122_equal"]
    return batch


def verify_coverage():
    base = HERE / "coverage"
    result = read(base / "RESULT.json")
    for name, expected in result["outputs"].items():
        assert digest(base / name) == expected, name
    for name, expected in result["independent_source_files"].items():
        path = PROJECT / name
        assert digest(path) == expected, name
    with (base / "QUESTIONS.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len({row["编号"] for row in rows}) == result["total_versioned_rows"]
    assert result["historical_R1"]["questions"] == 71
    assert result["scenes"] == 18
    assert sum(group["entries"] for group in result["native_reference_only"].values()) == result["native_catalog_ids"]


def build():
    old = parent.build()
    assert old == read(parent.HERE / "RELEASE.json")
    current = release.interface_signature()
    current.assert_matches(read(HERE / "INTERFACE.json"))
    session = release.make_session()
    frame = session.reset(2000014)
    for aid in (110, 110, 111, 172, None):
        current.assert_model_dimensions(len(frame.state.vector), len(frame.supported_actions))
        assert frame.state.state_version == current.state_version
        if aid is not None:
            assert frame.supported_actions[aid]
            frame = session.step(aid, frame_id=frame.frame_id, action_version=frame.action_version)
    grid = read(HERE / "grid/RESULT.json")
    assert grid["formal_release_file"] == digest(HERE / "release.py")
    assert grid["frozen_grid_code"] == digest(HERE / "grid/session.py")
    assert grid["verified_targeted_retail_games"] == 2 and grid["formal_representative_checks"] == 33
    assert grid["cohort_receipt"] == digest(HERE / "grid/COHORT.json")
    hand = read(HERE / "coverage/hand_terms/RESULTS.json")
    assert hand["formal_source_sha"] == digest(HERE / "release.py") and len(hand["cases"]) == 3
    official = read(HERE / "death/OFFICIAL.json")
    assert official["signature_sha256"] == digest(HERE / "INTERFACE.json")
    assert [x["sequence"] for x in official["anchors"]] == [335, 526]
    compat = read(HERE / "compat/RESULT.json")
    assert compat["R3_interface_sha256"] == digest(HERE / "INTERFACE.json")
    assert compat["R2_manifest_sha256"] == digest(parent.HERE / "RELEASE.json")
    assert compat["draw"]["eligible"] == 18 and compat["draw"]["equal_observations"] == 347
    batch = verify_batch()
    verify_coverage()
    seed = read(HERE / "fresh/SEED.json")
    terminal = read(HERE / "fresh/TERMINAL.json")
    assert seed["seed_argument"] is None and not seed["in_previous_inventory"]
    assert terminal["index"] == 93 and terminal["summary"]["floor"] == 7
    assert not terminal["terminal"]["victory"]
    assert terminal["trace_sha256"] == digest(HERE / "fresh/ACTIONS.jsonl")
    fresh = read(HERE / "fresh/RESULT.json")
    assert fresh["valid"] and fresh["interface"] == current.metadata()
    assert fresh["seed"]["original_terminal_before_first_model"] and fresh["seed"]["actual_start_dispatches"] == 1
    assert fresh["summary"]["kernel_bypass_actions"] == 0 and fresh["summary"]["model_public_actions"] == 90
    assert fresh["summary"]["first_action_set_difference"]["missing_action"] == 112
    assert fresh["summary"]["first_content_snapshot_difference"]["index"] == 52
    assert fresh["summary"]["strict_equal_field_groups"] == 1182 and fresh["summary"]["compared_field_groups"] == 1187
    for obj in (*fresh.values(), *fresh["files"].values()):
        if isinstance(obj, dict) and {"path","sha256"} <= obj.keys():
            path = Path(obj["path"])
            if path.is_absolute():
                assert digest(path) == obj["sha256"]
            else:
                assert digest(HERE / "fresh" / path) == obj["sha256"], path
    paths = {HERE / "README.md", HERE / "release.py", HERE / "verify_release.py", HERE / "verify_public.py", HERE / "public_snapshot.py", HERE / "INTERFACE.json"}
    for group in ("grid","death","coverage","coverage/hand_terms","compat","regression","fresh"):
        for path in (HERE / group).iterdir():
            if path.is_file() and path.suffix in (".py",".java",".swift",".json",".jsonl",".csv",".md",".tsv"):
                paths.add(path)
    for group in ("regression","fresh"):
        for item in read(HERE / group / "RESULT.json").values():
            if isinstance(item, dict) and {"path","sha256"} <= item.keys():
                named = HERE / group / item["path"]
                if named.is_relative_to(HERE):
                    paths.add(named)
    return {"version":"silent-a20-sa-20261122-r3", "parent_release_sha256":digest(parent.HERE / "RELEASE.json"),
            "interface":current.metadata(), "focused_previous_stops":53, "advanced":34,
            "regression_outcomes":{key:value["outcomes"] for key,value in batch["summary"].items()},
            "fresh_seed":str(seed["unsigned"]), "fresh_terminal_floor":terminal["summary"]["floor"],
            "training_updates":0, "files":{p.relative_to(HERE).as_posix():digest(p) for p in sorted(paths)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    manifest = build()
    dst = HERE / "RELEASE.json"
    if args.freeze:
        with dst.open("x") as stream:
            json.dump(manifest, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    elif read(dst) != manifest:
        raise ValueError("R3 no longer matches its frozen edition")
    print(f'{manifest["version"]}: verified {len(manifest["files"])} artifacts')

if __name__ == "__main__":
    main()
