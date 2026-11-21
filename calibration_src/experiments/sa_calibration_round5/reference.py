"""R5 inputs pinned to the sealed R4 local edition and its public Git revision."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R4 = HERE.parent / "sa_calibration_round4"
PARENT = "c165cd0ee4c84e5f85ffeb720938007c7e8d532d"
PARENT_MANIFEST = "d2e2ed2b0ef3adff609a1b8162c429074a3e7f255b563ae6a225cbc025ccff3f"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    pending.replace(path)


def source(folder, ref):
    path = (folder / ref["path"]).resolve()
    assert path.is_relative_to(folder.resolve()) and sha(path) == ref["sha256"], path
    return path


def baseline():
    assert sha(R4 / "RELEASE.json") == PARENT_MANIFEST
    sealed = read(R4 / "RELEASE.json")["evidence"]
    for name in ("INTERFACE.json","regression/RESULT.json","fresh/RESULT.json","fresh/ACTIONS.jsonl","coverage/STATE.json"):
        assert sha(R4 / name) == sealed[name]
    batch = source(R4 / "regression", read(R4 / "regression/RESULT.json"))
    episodes = [row["episode"] for row in read(batch)["runs"]]
    assert len({ep["seed"] for ep in episodes}) == len(episodes) == 704
    prior = read(R4 / "fresh/RESULT.json")
    return dict(parent_commit=PARENT, parent_manifest=PARENT_MANIFEST, sources={name:sealed[name] for name in (
        "INTERFACE.json","regression/RESULT.json","fresh/RESULT.json","fresh/ACTIONS.jsonl","coverage/STATE.json")},
        cohort=len(episodes), outcomes=dict(Counter(ep["reason"] for ep in episodes)),
        max_floor=max(ep["engine_floor"] for ep in episodes),
        deaths_with_partial_action_sets=sum(ep["reason"]=="loss" and ep["incomplete_action_sets"]>0 for ep in episodes),
        recorded_original=dict(seed=prior["display"],signed=prior["seed_signed"],receipts=prior["original_inputs"],end=prior["original_final"],
                               status="R4 holdout reused as R5 development material",first_unavailable=prior["reconciled_official"]["stopped_at"]))


if __name__ == "__main__":
    write(HERE / "BASELINE.json", baseline())
