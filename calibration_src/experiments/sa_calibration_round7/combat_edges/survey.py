"""Replay historical no-action combat prefixes to the same decision or first changed step."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
from importlib import import_module
import json
from pathlib import Path
from experiments.sa_calibration_round5.reference import sha
from experiments.sa_calibration_round6.reference import read, write
from experiments.sa_calibration_round7.death_family import session as old
from experiments.sa_calibration_round7.episode import snapshot
from experiments.sa_calibration_round7.death_family.verify import step


def backing(session):
    while not isinstance(session, old.r3.TransitionSession):
        session = vars(session).get("delegate", vars(session).get("base"))
    return session.pages


HERE = Path(__file__).resolve().parent
BASE = "experiments.sa_calibration_round7.decisions"


def inputs():
    selected = []
    hashes = {}
    for p in sorted((HERE.parent / "runs/discovery-r6").glob("shard-*.jsonl.gz")):
        for line in gzip.open(p):
            row = json.loads(line)
            if row["cause"] == ["death_boundary_unknown"]:
                selected.append(
                    {
                        "seed": row["seed"],
                        "strategy": row["strategy"],
                        "actions": row["actions"],
                        "base_final": row["stop"]["after"]["sha256"],
                        "source": p.name,
                    }
                )
                hashes[p.name] = hashes.get(p.name) or sha(p)
                if len(selected) == 72:
                    return dict(rows=selected, files=hashes)
    raise ValueError("72 completed historical death prefixes required")


def classify(frame, raw, w):
    actors = w["rows"]
    public = old.r3.ordinary.rows(frame.state.vector)
    tags = []
    if w["physical_order"] != list(range(len(actors))):
        tags.append("physical_order")
    if (
        w["card_queue"]
        or w["end_queued"]
        or w["turn_ended"]
        or w["queue"]
        and w["input"] == 1
    ):
        tags.append("pending_engine_work")
    if w["has_horn"] or w["has_specimen"]:
        tags.append("kill_trigger_relic")
    for a, z in zip(actors, public):
        if a["id"] not in old.COMPANIONS:
            tags.append("other_companion:" + a["id"])
        if a["half_dead"] or a["will_escape"] or a["escaping"]:
            tags.append("half_dead_or_escape:" + a["id"])
        if not a["targetable"]:
            if a["id"] == "FUNGI_BEAST":
                tags.append("fungal_corpse")
            if a["block"]:
                tags.append("corpse_block")
            extra = sorted(set(a["powers"]) - old.RESIDUAL)
            if extra:
                tags.append("residue:" + ",".join(extra))
            if any(a["powers"].get(k, 0) != z[i] for k, i in old.STATUS.items()):
                tags.append("status_values_differ")
    if frame.action_gaps:
        tags.append("upstream_action_gaps:" + ",".join(frame.action_gaps))
    if frame.policy_mask is None:
        tags.append("partial_source")
    return sorted(set(tags)) or ["other"]


def one(args):
    edition, row = args
    runtime = import_module(edition)
    engine = runtime.make_engine()
    s = runtime.make_session(engine)
    f = s.reset(row["seed"])
    for i, a in enumerate(row["actions"]):
        if not f.supported_actions[a]:
            return dict(
                seed=row["seed"],
                status="prefix_changed",
                at=i,
                old_action=a,
                now=snapshot(f),
            )
        f = step(s, f, a)
    data = dict(seed=row["seed"], at=len(row["actions"]), result=snapshot(f))
    if any(f.supported_actions):
        return dict(data, status="restored_before_candidate")
    if f.action_gaps != ("death_boundary_unknown",):
        return dict(data, status="changed_stop")
    page = backing(s)
    source = page._source
    raw = engine._source._current
    w = old.r3.ordinary.observer().inspect(engine._source._env)
    return dict(
        data,
        status="still_empty",
        witness=w,
        controls=[a.policy_id for a in raw.bindings],
        raw_choices=[(a.policy_id, a.simulator_id, a.operation) for a in raw.bindings],
        allowed_below=[a for a, b in enumerate(source.supported_actions) if b],
        before_gaps=source.action_gaps,
        raw_public_targets=[
            list(r[:10]) for r in old.r3.ordinary.rows(source.state.vector) if r[0]
        ],
        tags=classify(source, raw, w),
    )


def survey(edition, manifest):
    with ProcessPoolExecutor(max_workers=2) as pool:
        rows = list(
            pool.map(one, [(edition, r) for r in manifest["rows"]], chunksize=1)
        )
    return dict(
        edition=edition,
        rows=rows,
        types=dict(Counter(r["status"] for r in rows)),
        tags=dict(Counter(t for r in rows for t in r.get("tags", []))),
    )


if __name__ == "__main__":
    manifest = inputs()
    write(HERE / "CASES.json", manifest)
    result = survey(BASE, manifest)
    write(HERE / "SURVEY.json", result)
    print(result["types"], result["tags"])
