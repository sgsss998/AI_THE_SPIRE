"""Compare a candidate with the frozen 704 R6 games on their original policy and caps."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import gzip
import importlib
import json
from pathlib import Path
from time import monotonic

from experiments.episode_outcomes193.rollout import run_episode
from experiments.sa_calibration_round5.reference import read, sha, write
from experiments.sa_calibration_round5.regression import Observation, summarize
from experiments.sa_calibration_round6.cohort.audit import digest

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "sa_calibration_round6"
NATURAL = {"loss", "act3_win", "heart_win"}


def replay(task):
    edition, old = task
    module = importlib.import_module(edition)

    def adapter(engine):
        observation = object.__new__(Observation)
        observation.session = module.make_session(engine)
        return observation

    row = asdict(run_episode(old["seed"], cap=old["cap"], engine_factory=module.make_engine, wrap=adapter))
    before, after = old["actions"], row["actions"]
    first = next((i for i, (a,b) in enumerate(zip(before, after)) if a != b), None)
    if first is None and len(before) != len(after):
        first = min(len(before), len(after))
    return dict(**row, cohort=old["cohort"], previous=old["reason"], previous_page=old["page"],
                previous_floor=old["engine_floor"], cap=old["cap"], action_sha256=digest(after),
                previous_action_sha256=old["action_sha256"], first_different_decision=None if first is None else first+1,
                previous_at_difference=before[first:first+1] if first is not None else [],
                candidate_at_difference=after[first:first+1] if first is not None else [])


def run(edition, workers):
    module = importlib.import_module(edition)
    sig = module.interface_signature().metadata()
    path = PARENT / "regression/RESULT.json"
    parent_digest = read(PARENT/"RELEASE.json")["files"]["regression/RESULT.json"]
    assert sha(path) == parent_digest
    old = read(path)["records"]
    assert len(old) == len({r["seed"] for r in old}) == 704
    assert all(r["action_sha256"] == digest(r["actions"]) for r in old)
    started = monotonic()
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(replay, ((edition, row) for row in old), chunksize=2))
    assert sig == module.interface_signature().metadata()
    folder = HERE/"regression"/sig["state_sha256"]
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder/"games.jsonl.gz"
    data = "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":"))+"\n" for r in rows)
    archive.write_bytes(gzip.compress(data.encode(), compresslevel=5, mtime=0))
    changed = [r for r in rows if r["first_different_decision"] or (r["reason"],r["page"],r["engine_floor"]) !=
               (r["previous"],r["previous_page"],r["previous_floor"])]
    details = [{k:v for k,v in r.items() if k != "actions"} for r in changed]
    lost = [r["seed"] for r in rows if r["previous"] in NATURAL and r["reason"] not in NATURAL]
    recovered = [r["seed"] for r in rows if r["reason"] in NATURAL and r["previous"] not in NATURAL]
    result = dict(interface=sig, edition=edition, reference_sha256=parent_digest,
                  archive_sha256=sha(archive), summary=summarize(rows), changed=details,
                  lost_natural_end=lost, newly_natural_end=recovered,
                  transitions=dict(Counter(f'{r["previous_page"]} -> {r["page"]}' for r in changed)),
                  elapsed_seconds=round(monotonic()-started,2))
    write(folder/"RESULT.json", result)
    print(json.dumps({k:result[k] for k in ("summary","lost_natural_end","newly_natural_end","elapsed_seconds")}),flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", default="experiments.sa_calibration_round7.release")
    parser.add_argument("--workers", type=int, choices=range(1,17), default=4)
    args = parser.parse_args()
    run(args.edition, args.workers)
