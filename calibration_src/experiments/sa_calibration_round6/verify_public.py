"""Verify the R6 distribution with Python's standard library."""
from collections import Counter
from hashlib import sha256
import csv
import json
from pathlib import Path

def read(path):
    return json.loads(path.read_bytes())

def digest(path):
    return sha256(path.read_bytes()).hexdigest()

def verify(docs):
    root=docs.parents[2]
    hashes=read(docs/"SHA256.json")
    for name,expected in hashes["files"].items():
        path=(root/name).resolve()
        assert path.is_relative_to(root.resolve()) and digest(path)==expected,name
    frozen=read(docs/"FREEZE.json")
    assert frozen["state_space"]==3122 and frozen["action_space"]==193 and frozen["training_updates"]==0
    assert frozen["interface_sha256"]==digest(docs/"INTERFACE.json")
    for name,expected in frozen["runtime"].items():
        assert digest(root/"calibration_src/experiments/sa_calibration_round6"/name)==expected
    base=read(docs/"BASELINE.json")
    assert base["original_r5_replay_sha256"] and base["reproduced_identical"] and base["inputs"]==128 and base["stop"]["index"]==129
    old=read(docs/"replay/RESULT.json")
    assert old["signature"]==read(docs/"INTERFACE.json") and old["completed_inputs"]==142 and old["stop"]["index"]==143
    assert old["first_content"] is None and not old["used_kernel_fallback"]
    checked=old["records"][128:133]
    assert [r["actions_executed"] for r in checked]==[[110],[110],[110],[112],[171]]
    assert all(r["offered"]==r["actual_reported"] for r in checked)
    for side in ("model","original"):
        final=checked[-1]["after"][side]
        assert final["resources"][2]==257 and len(final["deck"])==19 and final["deck"][-1]==["Backflip",0]
        assert final["potions"][0]=="regenpotion" and final["page"]==5
    branches=read(docs/"branches/RESULT.json")
    assert digest(docs/"branches/SOURCE.json.gz")==branches["source_bundle_sha256"]
    assert branches["original_actions"]==branches["stale_rejected"]==branches["matched_reward_masks"]==12
    for key in ("R5","R6"):
        ds=read(docs/f"cohort/{key}.json")
        assert len({r["seed"] for r in ds["records"]})==len(ds["records"])==58
        opened=[row["seed"] for row in ds["records"] if row["endpoint"]["actions"]]
        assert opened==([9000033] if key=="R6" else [])
    other=read(docs/"cohort/INDEPENDENT.json")
    assert other["seed"]==9000033 and other["genuine_original"] and not other["unseen_random_holdout"]
    assert other["checked_frames"]==other["equal_frames"]==22 and other["completed_inputs"]==21 and other["stop"] is None
    with (docs/"regression/seeds.csv").open(newline="") as stream:
        seeds=list(csv.DictReader(stream))
    batch=read(docs/"regression/RESULT.json")["combined"]
    assert len({r["seed"] for r in seeds})==len(seeds)==704 and dict(Counter(r["reason"] for r in seeds))==batch["outcomes"]=={"loss":372,"unsupported":332}
    assert [r["seed"] for r in seeds if r["action_sha256"]!=r["previous_action_sha256"]]==["9000033"]
    assert sum(int(r["decisions"]) for r in seeds)==batch["decisions"]==62413
    blind=read(docs/"fresh/RESULT.json"); R=blind["replay"]
    assert blind["blank_start"] and blind["original_completed_before_model"] and blind["original_ended_at"]<blind["first_simulator_start"]
    assert blind["original_inputs"]==120 and blind["original_final"]["floor"]==6 and blind["original_final"]["hp"]==0
    assert R["completed_inputs"]==31 and R["stop"]["index"]==32 and R["first_content"] is None and R["equal_frames"]==32
    assert digest(docs/"fresh/REPLAY.json")==blind["replay_sha256"]
    ledger=read(docs/"fresh/original-inputs.json")["records"]
    assert list(range(1,121))==[r["index"] for r in ledger] and ledger[31]["alignment"]=="stopped"
    for side in ("S","A"):
        table=read(docs/"coverage/CURRENT.json")
        expected=table["state" if side=="S" else "action"]
        assert dict(Counter(r[side] for r in table["branches"]))==expected["counts"]
    assert len(table["branches"])==43 and table["r6_open"]==16
    return f'{len(hashes["files"])} verified files; 704 fixed runs; 58 old reward stops; 3 reward branches; 120 original holdout inputs.'

if __name__=="__main__":print(verify(Path(__file__).resolve().parent))
