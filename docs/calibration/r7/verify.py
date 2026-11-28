"""Verify the published pilot and candidate evidence without a game installation."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import gzip
import json

root = Path(__file__).resolve().parent
def read(name):
    return json.loads((root/name).read_bytes())

result = read("pilot/RESULT.json")
manifest = root/"pilot/manifest.json"
assert sha256(manifest.read_bytes()).hexdigest() == result["manifest_sha256"]
jobs = json.loads(manifest.read_bytes())["jobs"]
episodes = []
for name, digest in sorted(result["shards"].items()):
    data = (root/"pilot"/name).read_bytes()
    assert sha256(data).hexdigest() == digest
    episodes.extend(json.loads(s) for s in gzip.decompress(data).splitlines())
assert len(episodes) == len({r["seed"] for r in episodes}) == 200
assert [(j["seed"],j["strategy"]) for j in jobs] == [(r["seed"],r["strategy"]) for r in episodes]
assert Counter(r["reason"] for r in episodes) == result["outcomes"]
assert all(r["determinism"]["matched"] is True for r in episodes)
assert sum(len(r["actions"]) for r in episodes) == 16755
triage = read("pilot/TRIAGE.json")
assert triage["counts"]["natural"] == 70 and triage["counts"]["natural_with_issue"] == 63
assert triage["counts"]["unfinished"] == 130
discovery = read("discovery.json")
assert discovery["policies"] == {"fixed":4000,"survival":4000,"explore":2000}
wall = read("wall/RESULT.json")
assert wall["retail"]["completed_inputs"] == wall["retail"]["total_original_inputs"] == 120
assert wall["retail"]["first_substantive_difference"] is None and wall["retail"]["stop"] is None
assert len(wall["wall"]["grid_uuids"]) == len(wall["wall"]["positions_zero_based"]) == 14
assert wall["wall"]["chosen_uuid"] not in wall["wall"]["remaining_deck_uuids"]
assert wall["wall"]["deck_counts"] == [15,15,14]
for version, count in [("R6",1),("R7",0)]:
    checks = read(f"oracles/{version}.json")
    assert checks["historical_bugs_caught"] == 3 and checks["candidate_issues"] == count
print("Verified 200 pilot seeds, 200 repeat traces, 120 retail inputs and three regression oracles.")
