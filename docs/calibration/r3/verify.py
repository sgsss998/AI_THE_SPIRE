"""Verify the exported snapshot with standard Python, without a native game installation."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

def read(name):
    return json.loads((HERE / name).read_bytes())

def table(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def main():
    hashes = read("SHA256.json")
    for name, expected in hashes["files"].items():
        assert hashlib.sha256((REPO / name).read_bytes()).hexdigest() == expected, name
    coverage = read("coverage/RESULT.json")
    assert len(table("coverage/QUESTIONS.csv")) == coverage["total_versioned_rows"]
    assert len(table("coverage/SCENES.csv")) == coverage["scenes"]
    assert len(table("coverage/OBJECT_IDS.csv")) == coverage["native_catalog_ids"]
    layout, abi = read("layout.json"), read("interface.json")
    assert sum(row["size"] for row in layout["observation"]) == abi["observation_dimension"] == 3122
    assert layout["action_count"] == abi["actions"] == 193
    data, batch = table("seeds.csv"), read("batch.json")
    assert len(data) == len({row["seed"] for row in data}) == 704
    for group, stats in batch["summary"].items():
        rows = [item for item in data if item["cohort"] == group]
        assert len(rows) == stats["seeds"], group
        assert dict(Counter(row["outcome"] for row in rows)) == stats["outcomes"]
        assert sum(int(row["literal_complete"]) for row in rows) == stats["forced_prefix_complete"]
    stages = batch["focused_groups"].values()
    assert sum(s["seeds"] for s in stages) == 53
    assert sum(s["actual_public_followup"] for s in stages) == 34
    fresh = read("fresh.json")
    assert [row["index"] for row in fresh["decisions"]] == list(range(1,94))
    assert (fresh["replayed"],fresh["native_only_acknowledgements"]) == (90,3)
    assert len(fresh["decisions"]) == sum((fresh["replayed"],fresh["native_only_acknowledgements"]))
    assert fresh["model_endpoint"]["resources"] == fresh["original_endpoint"]["resources"] == [0,66,152,7,1,20]
    assert fresh["model_endpoint"]["enemies"] == fresh["original_endpoint"]["enemies"]
    assert fresh["model_endpoint"]["lost"] and fresh["first_action_set_difference"]["missing_in_model"] == [112]
    print(f'{len(hashes["files"])} published files verified; 704 regression seeds and 93 real-game inputs checked.')

if __name__ == "__main__":
    main()
