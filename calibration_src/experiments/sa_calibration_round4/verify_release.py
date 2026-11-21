"""Seal an R4 edition once, and verify the raw per-seed evidence and frozen source on demand."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path

from experiments.sa_calibration_round3 import verify_release as r3_verifier
from . import release
from .verify_public import verify_fresh_receipts

HERE = release.HERE
R3 = release.R3
def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
def read(path):
    return json.loads(path.read_bytes())
def verify_ref(folder, receipt):
    p=(folder/receipt["path"]).resolve()
    assert p.is_relative_to(folder.resolve()), receipt["path"]
    assert digest(p)==receipt["sha256"], receipt["path"]
    return p

def verify_original_and_replays(fresh,interface):
    folder=HERE/"fresh"
    trace=read(folder/"PUBLIC_TRACE.json")
    mechanisms=read(folder/"MECHANISMS.json")
    verify_fresh_receipts(fresh,trace,mechanisms,interface)
    root=HERE.parents[1]
    for name,expected in fresh["source_sha256"].items():
        assert digest(root/name)==expected, name
    assert digest(folder/"mechanisms.py")==mechanisms["script_sha256"]
    original=[json.loads(line) for line in (folder/"ACTIONS.jsonl").read_bytes().splitlines()]
    record_hashes={str(row["index"]):hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":")).encode()).hexdigest() for row in original}
    start=read(folder/"START_OUTPUT.json")
    intent=read(folder/"START_INPUT.json")
    terminal=read(folder/"TERMINAL.json")
    before=read(folder/"SEEDS_BEFORE.json")
    seed=read(folder/"SEED.json")
    moment=lambda value:datetime.fromisoformat(value)
    assert moment(read(HERE/"FREEZE.json")["utc"]) <= moment(intent["utc"]) < moment(terminal["at"]) < moment(read(folder/"FIRST_SIMULATOR_START.json")["at"])
    assert moment(before["as_of"]) < moment(intent["utc"])
    assert intent["interface_sha256"]==digest(HERE/"INTERFACE.json") and intent["seed"] is None
    assert start["status"]=="observed_start" and start["command"]=="start THE_SILENT 20"
    assert seed["unsigned"] not in before["seeds_u64"] and len(before["seeds_u64"]) == len(set(before["seeds_u64"])) == fresh["known_before"]
    assert read(folder/"AUTOSAVE_SEED.json")["seed_set"] is False
    native=root/"native_runtime"/read(folder/"CLOSE.json")["instance"]
    assert read(native/"process_exit.json")["pid"]==read(folder/"CLOSE.json")["pid"]
    oracle,=(native/"native_oracle").glob("*/native_oracle.jsonl")
    assert digest(oracle)==mechanisms["oracle_sha256"]
    assert terminal["summary"]["monsters"]==[["Hexaghost",107]] and terminal["terminal"]=={"score":184,"victory":False}
    assert terminal["receipt"]["pending"] is None and terminal["receipt"]["quarantine"] is None
    for orig,row in zip(original,trace["inputs"],strict=True):
        assert orig["index"]==row["index"] and orig["command"]==row["command"]
        for side in ("before","after"):
            assert orig[side]["raw_hash"]==row[side+"_sha256"]
            assert orig[side]["raw"]["game_state"]["seed"]==seed["signed"]
    for key in ("official_replay","reconciled_official","diagnostic"):
        run=read(verify_ref(folder,fresh[key]))
        assert run["signature"]==interface and run["signature_unchanged"] and run["input_record_sha256"]==record_hashes
        assert run["seed_unsigned"]==seed["unsigned"] and run["original_actions_available"]==len(original)
        assert run["used_kernel"]==(key=="diagnostic") and run["diagnostic_allowed"]==(key=="diagnostic")
        assert run["reconciled_native_physical_effects"]==(key!="official_replay")
        assert [row["index"] for row in run["trace"]]==list(range(1,(run["stopped_at"] or len(original))+1))
        assert run["frame_statistics"]["all_actual_frames"]==(fresh["quality"] if key=="official_replay" else fresh[key]["quality"])
        for name,expected in run["source_sha256"].items():assert digest(root/name)==expected,name
        if key=="diagnostic":
            for field in ("resources","enemies","relics","deck","potions"):
                assert run["original_endpoint"][field]==run["model_endpoint"][field],field

def build():
    assert r3_verifier.build()==read(R3/"RELEASE.json")
    interface=release.interface_signature().metadata()
    assert interface==read(HERE/"INTERFACE.json")
    assert release.source_hashes()==read(HERE/"FREEZE.json")["components"]
    baseline=read(HERE/"BASELINE.json")
    for name,h in baseline["source_sha256"].items():assert digest(R3/name)==h, name
    for key,path in (("trace_index_sha256","STOPS.json"),("csv_sha256","GROUPS.csv")):
        assert digest(HERE/"coverage"/path)==baseline["taxonomy"][key]
    groups=read(HERE/"coverage/STOPS.json")
    assert len(groups["groups"])==23 and len(groups["cases"])==len({r["seed"] for r in groups["cases"]})==129
    neow=read(HERE/"neow/RESULT.json")
    death=read(HERE/"death/RESULT.json")
    snake=read(HERE/"events/RESULT.json")
    assert interface==neow["interface"]==death["interface"]==snake["signature"]
    assert neow["runtime_sha256"]==digest(HERE/"neow/session.py") and neow["formal_release_file"]==digest(HERE/"release.py")
    assert [x["seed"] for x in neow["retail_pairs"]]==[46,48]
    assert neow["affirmed_curse_ordered_pairs"]==264 and neow["previous_noncursed_ordered_pairs"]==1452
    assert death["source_sha"]==digest(HERE/"death/session.py") and death["final_interface"] and len(death["rows"])==21
    assert sum(bool(r["advanced"]) for r in death["rows"] if r["cohort"]=="fixed")==6
    assert snake["module_sha256"]==digest(HERE/"events/serpent.py") and not snake["wrapped_on_r3"]
    assert snake["accepted"]["real_model_actions"]==92
    regr=read(HERE/"regression/RESULT.json")
    source=verify_ref(HERE/"regression",regr)
    archive=read(source)
    assert archive["signature"]==interface and archive["summary"]==regr["summary"]
    assert len(archive["runs"])==len({item["seed"] for item in archive["runs"]})==704
    for row in archive["runs"]:
        assert "error" not in row
        assert digest(source.parent/"traces"/f'{row["seed"]}.json.gz')==row["trace"]["sha256"]
        if "trace" in row["forced"]:
            assert digest(source.parent/"forced_traces"/f'{row["seed"]}.json.gz')==row["forced"]["trace"]["sha256"]
    for c in ("fixed","additional"):
        selection=[r for r in archive["runs"] if r["cohort"]==c]
        assert Counter(r["episode"]["reason"] for r in selection)==regr["summary"][c]["outcomes"]
    fresh=read(HERE/"fresh/RESULT.json")
    verify_original_and_replays(fresh,interface)
    for info in fresh.values():
        if isinstance(info,dict) and {"path","sha256"}<=set(info):verify_ref(HERE/"fresh",info)
    for info in fresh["source_files"].values():verify_ref(HERE/"fresh",info)
    terminal=read(HERE/"fresh/TERMINAL.json")
    assert terminal["trace_sha256"]==digest(HERE/"fresh/ACTIONS.jsonl")
    assert terminal["snapshot"]["raw"]["game_state"]["screen_type"]=="GAME_OVER"
    assert not read(HERE/"fresh/SEED.json")["in_previous_inventory"]
    state=read(HERE/"coverage/STATE.json")
    assert state["interface_sha256"]==digest(HERE/"INTERFACE.json")
    for name,expected in state["input_hashes"].items():assert digest(HERE/name)==expected,name
    assert state["paired_decisions"]==15 and state["distinct_vectors"]==13 and not state["identical_state_different_known_controls"]
    for case in death["cases"]:
        for name,expected in case["archive_hashes"].items():assert digest(HERE.parents[1]/name)==expected,name
    assert neow["freeze_sha256"]==digest(HERE/"FREEZE.json") and neow["frozen_interface_sha256"]==digest(HERE/"INTERFACE.json")
    assert read(HERE/"neow/TEMPO.json")["interface"]==interface
    assert read(HERE/"events/FROZEN_REPLAY.json")["interface_sha256"]==digest(HERE/"INTERFACE.json")
    changes=read(HERE/"regression/ATTRIBUTION.json")
    assert changes["r4_full_sha256"]==digest(source) and changes["old_prefix_still_interrupted_after_alignment"]==0
    for name in ("coverage/STATE.json","regression/ATTRIBUTION.json","fresh/REPORT.md","README.md"):
        assert (HERE/name).is_file(),name
    paths={source}
    for group in (".","neow","death","events","coverage","regression","fresh"):
        for file in (HERE/group).iterdir():
            if file.name!="RELEASE.json" and file.is_file() and file.suffix in {".py",".md",".json",".jsonl",".tsv",".csv",".java",".swift"}:
                paths.add(file)
    for ref in fresh.values():
        if isinstance(ref,dict) and {"path","sha256"}<=set(ref):
            paths.add(HERE/"fresh"/ref["path"])
    return dict(version="silent-a20-sa-20261122-r4",parent_sha256=digest(R3/"RELEASE.json"),interface=interface,
                frozen_source=release.source_hashes(),training_updates=0,regression=regr["summary"],
                evidence={f.relative_to(HERE).as_posix():digest(f) for f in sorted(paths)})
def main():
    p=argparse.ArgumentParser();p.add_argument("--freeze",action="store_true");args=p.parse_args()
    result=build()
    manifest=HERE/"RELEASE.json"
    if args.freeze:
        with manifest.open("x") as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")
    else:assert result==read(manifest)
    print(f'R4 validated {len(result["evidence"])} inputs, 704 free trajectories and all archived forced replays.')
if __name__=="__main__":main()
