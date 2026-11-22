"""Pinned R5 reference and immutable inputs used for R6 comparisons."""
from pathlib import Path
from experiments.sa_calibration_round5.reference import read, sha, write

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
R5=HERE.parent/"sa_calibration_round5"
R4=HERE.parent/"sa_calibration_round4"
COMMIT="c7f34b38fa7d4003bb7c2726b5b5286dbc5904ec"
PARENT_SHA="96b2e043c2fe1f75b7fe75adf45ba58dcd0bce5b4c6fffa5430b311f47af4b4e"

def baseline():
    assert sha(R5/"RELEASE.json")==PARENT_SHA
    manifest=read(R5/"RELEASE.json")
    for name in ("regression/RESULT.json","replay/RESULT.json","INTERFACE.json","coverage/CURRENT.json"):
        assert sha(R5/name)==manifest["files"][name]
    replay=read(R5/"replay/RESULT.json")
    batch=read(R5/"regression/RESULT.json")["combined"]
    return dict(parent_commit=COMMIT,parent_manifest=PARENT_SHA,interface=sha(R5/"INTERFACE.json"),
                original_journal=sha(R4/"fresh/ACTIONS.jsonl"),seed=replay["seed"],version=read(R4/"fresh/RESULT.json")["original_version"],
                first_content=replay["first_content"],stop=replay["stop"],regression=batch,
                coverage={k:read(R5/"coverage/CURRENT.json")[k] for k in ("branch_count","state","action","r5_open")})
