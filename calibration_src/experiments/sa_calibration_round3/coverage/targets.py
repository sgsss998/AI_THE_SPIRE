"""Pin the 53 R2 endpoints by their recorded context, before evaluating an R3 candidate."""
from collections import Counter
from hashlib import sha256
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
R2 = ROOT / "experiments/sa_calibration_round2"


def collect():
    reg = R2 / "regression"
    baseline = json.loads((reg / "RESULT.json").read_bytes())["public"]["full"]
    batch_data = (reg / baseline["path"]).read_bytes()
    assert sha256(batch_data).hexdigest() == baseline["sha256"]
    enums = json.loads((ROOT / "contracts/state_schema.json").read_bytes())["enums"]
    targets = []
    for run in json.loads(batch_data)["runs"]:
        ep = run["episode"]
        if run["cohort"] != "fixed":
            continue
        is_grid = ep["page"] == "GRID_UNVERIFIED"
        if not is_grid and ep["cause"] != ["death_boundary_unknown"]:
            continue
        path = reg / Path(baseline["path"]).parent / "traces" / (str(run["seed"]) + ".json.gz")
        data = path.read_bytes()
        assert sha256(data).hexdigest() == run["trace"]["sha256"]
        trace = json.loads(gzip.decompress(data))
        before, final = (frame["state"] for frame in trace[-2:])
        if is_grid:
            task = (int(final[26]), int(final[27]), int(before[9]))
            if task == (1, 1, enums["Event"]["NEOW"] + 1):
                kind = "neow_transform"
            elif task == (4, 1, enums["Event"]["WING_STATUE"] + 1):
                kind = "wing_remove"
            else:
                continue
        else:
            dead = [int(final[i]) for i in range(993, 1253, 52) if final[i] and final[i+1] == 0]
            if dead != [enums["MonsterId"]["FUNGI_BEAST"] + 1]:
                continue
            kind = "fungus_death"
        targets.append(dict(seed=run["seed"], group=kind, floor=ep["engine_floor"],
                            actions_before_stop=len(ep["actions"]), trace_sha256=run["trace"]["sha256"]))
    counts = Counter(r["group"] for r in targets)
    assert counts == dict(neow_transform=18, wing_remove=15, fungus_death=20)
    return dict(source_full_sha256=baseline["sha256"], counts=dict(counts), targets=targets)


if __name__ == "__main__":
    result = collect()
    (HERE / "TARGETS.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result["counts"])
