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
fixed = read("wall-regression/RESULT.json")
archive = (root/"wall-regression/games.jsonl.gz").read_bytes()
assert sha256(archive).hexdigest() == fixed["archive_sha256"]
games = [json.loads(line) for line in gzip.decompress(archive).splitlines()]
assert len(games) == len({r["seed"] for r in games}) == 704
assert Counter(r["reason"] for r in games) == {"loss":376,"unsupported":328}
assert sum(r["reason"]=="loss" and r["previous"]=="unsupported" for r in games) == 4
assert all(r["reason"]=="loss" for r in games if r["previous"]=="loss")
for name,n,m in [("r4-natural",339,310),("r6-natural",120,119)]:
    record = json.loads(gzip.decompress((root/"menus"/(name+".json.gz")).read_bytes()))
    assert record["total_original_inputs"] == record["completed_inputs"] == n and record["stop"] is None
    assert record["menu_counts"]["all_choices_bound_and_equal"] == m
deep = read("deep/REWARD_CANDIDATE.json")["act2_same_fight"]
assert len(deep["simulated_commands"]) == deep["real_commands"] == 30
assert deep["first_difference"] is None
print("Verified 200 pilot seeds, 704 fixed games, both retail runs (120 and 339 inputs), 30 Act II inputs and three regression oracles.")
