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

for subset, losses in (("combined-regression",397),("choices-regression",405),("battle-regression",416)):
    fixed = read(subset+"/RESULT.json")
    payload = (root/subset/"games.jsonl.gz").read_bytes()
    assert sha256(payload).hexdigest()==fixed["archive_sha256"]
    games = [json.loads(line) for line in gzip.decompress(payload).splitlines()]
    assert len(games)==len({g["seed"] for g in games})==704
    assert Counter(g["reason"] for g in games)==fixed["summary"]["outcomes"]
    assert sum(g["reason"]=="loss" for g in games)==losses
assert fixed["summary"]["outcomes"]=={"loss":416,"unsupported":283,"endpoint_error":3,"cap":2}
assert len(fixed["newly_natural_end"])==119 and len(fixed["lost_natural_end"])==75
for name,count,matches in (("r4-natural",339,331),("r6-natural",120,120)):
    evidence=json.loads(gzip.decompress((root/"decisions-menus"/(name+".json.gz")).read_bytes()))
    assert evidence["interface"]["observation_dimension"]==3127
    assert evidence["stop"] is evidence["first_substantive_difference"] is None
    assert evidence["completed_inputs"]==evidence["total_original_inputs"]==count
    assert evidence["menu_counts"]["all_choices_bound_and_equal"]==matches
purses=read("death_family/thief_rewards/RESULT.json")
pair=purses["same_state_collision"]
assert pair["original_rewards"]==[60,15] and pair["swapped_rewards"]==[40,15]
assert len(purses["single_thief_original_game"]["records"])==21
continuation=read("death_family/thief_rewards/CONTINUATION.json")
assert continuation["real_inputs"]==30 and continuation["first_real_difference"] is None
forward=continuation["simulator_only_continuation"]
assert len(forward["actions"])==62 and forward["kernel_end_floor"]==20 and forward["reason"]=="loss"
print("Verified the S3127 counterexample, both original-game action comparisons, continued Act II and three 704-game releases.")

for name,total in (("decisions-regression",413),("event-grid-regression",508),("transactions-regression",519)):
    report=read(name+"/RESULT.json")
    packed=(root/name/"games.jsonl.gz").read_bytes()
    assert sha256(packed).hexdigest()==report["archive_sha256"]
    games=[json.loads(line) for line in gzip.decompress(packed).splitlines()]
    assert len({g["seed"] for g in games})==704
    assert Counter(g["reason"] for g in games)==report["summary"]["outcomes"] and report["summary"]["outcomes"]["loss"]==total
for name,n in (("battle-regression",75),("decisions-regression",79),("transactions-regression",36)):
    cases=read(name+"/FORMER_TERMINALS.json")["checked"]
    assert len(cases)==n==sum(bool(c["earlier_terminal_reached"]) for c in cases)
paired=read("paired-old-pilot/RESULT.json")
assert Counter(x["status"] for x in paired["records"])=={"same_natural_loss":70,"old_stop_has_choices":93,"still_no_choices":36,"candidate_natural_loss":1}
for name,n,complete in (("r4-natural",339,337),("r6-natural",120,120)):
    study=json.loads(gzip.decompress((root/"transactions-menus"/(name+".json.gz")).read_bytes()))
    assert study["completed_inputs"]==study["total_original_inputs"]==n and study["first_substantive_difference"] is None
    assert study["menu_counts"]["all_choices_bound_and_equal"]==complete
registry=read("coverage/REGISTER.json")
assert len(registry["previous"])==43 and registry["updated_questions"]==9
for witness in [*(r["r7"] for r in registry["previous"] if r["r7"]),*registry["new_questions"]]:
    assert sha256((root/witness["evidence"]).read_bytes()).hexdigest()==witness["sha256"]
ink=read("ink_bottle/RESULT.json")
assert len(ink["cases"])==14 and ink["top_predictions"]==12 and ink["reshuffle_triggers"]==1
print("Verified releases five through seven, paired pilot paths, the S/A register and the original Ink Bottle observations.")
