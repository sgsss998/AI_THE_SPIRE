"""Compare a candidate with the frozen 704 R6 games on their original policy and caps."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import gzip
import importlib
import json
from pathlib import Path
from time import monotonic

from experiments.episode_outcomes193.rollout import run_episode
from experiments.sa_calibration_round5.reference import read, sha, write
from experiments.sa_calibration_round5.regression import summarize
from experiments.sa_calibration_round6.cohort.audit import digest

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "sa_calibration_round6"
NATURAL = {"loss", "act3_win", "heart_win"}


class EndpointView:
    """The historical selector uses only A. Give its original endpoint check the original prefix."""
    def __init__(self, module, engine, width):
        self.engine = engine
        self.session = module.make_session(engine)
        self.width = width
        self.actions = []
        self.partial = self.ui_only = 0

    def observe(self, frame):
        if len(frame.state.vector) != self.width or len(frame.supported_actions) != 193:
            raise ValueError("Candidate returned a different interface from its signature")
        self.frame = frame
        return replace(frame, state=replace(frame.state, vector=frame.state.vector[:3118]))

    def reset(self, *args, **kwargs):
        return self.observe(self.session.reset(*args, **kwargs))

    def step(self, action, **kwargs):
        before = self.frame
        after = self.session.step(action, **kwargs)
        self.actions.append(action)
        self.partial += int(before.policy_mask is None)
        self.ui_only += int(before.engine_steps == after.engine_steps)
        return self.observe(after)

def replay(task):
    edition, width, old = task
    module = importlib.import_module(edition)
    observation = None
    def adapter(engine):
        nonlocal observation
        observation = EndpointView(module, engine, width)
        return observation

    try:
        row = asdict(run_episode(old["seed"], cap=old["cap"], engine_factory=module.make_engine, wrap=adapter))
    except ValueError as error:
        if str(error) != "A terminal cannot have pending decisions" or observation is None:
            raise
        core, frame = observation.engine._source._env, observation.frame
        row = dict(seed=old["seed"], actions=observation.actions, reason="endpoint_error", page=frame.page,
                   engine_floor=core.floor, engine_steps=core.steps, ui_only_actions=observation.ui_only,
                   incomplete_action_sets=observation.partial, act3_cleared=None, heart_killed=None,
                   summary_floor=None, cause=[str(error)], terminal_evidence=dict(done=core.done,
                   won=core.won, lost=core.lost, hp=int(frame.state.vector[0]), core_choices=sum(map(int,core.mask())),
                   public_choices=[i for i,b in enumerate(frame.supported_actions) if b],
                   mask_reported=frame.policy_mask is not None))
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
        rows = list(pool.map(replay, ((edition, sig["observation_dimension"], row) for row in old), chunksize=2))
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
