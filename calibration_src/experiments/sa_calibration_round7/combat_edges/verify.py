"""Verify old prefixes, physical target identity, permanent negative cases and next commands."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path
from experiments.sa_calibration_round7 import decisions
from experiments.sa_calibration_round7.death_family.verify import step, to
from experiments.sa_calibration_round7.episode import snapshot
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError
from . import candidate, original, session, survey

HERE = Path(__file__).resolve().parent


def witness(core):
    return session.prev.r3.ordinary.observer().inspect(core)


def check_case(row):
    e, owner, f = to(candidate, row["seed"], row["actions"])
    e0, _, old = to(decisions, row["seed"], row["actions"])
    core = e._source._env
    w = witness(core)
    raw = e._source._current
    assert not any(old.supported_actions) and old.action_gaps == (
        "death_boundary_unknown",
    )
    assert (
        f.policy_mask == f.supported_actions
        and any(f.supported_actions)
        and not f.action_gaps
    )
    dead = next(i for i, a in enumerate(w["rows"]) if a["hp"] == 0)
    live = 1 - dead
    controls = {b.policy_id: b.simulator_id for b in raw.bindings}
    moves = [i for i, x in enumerate(f.supported_actions) if x]
    assert sorted(controls) == moves and set(controls.values()) == {
        i for i, x in enumerate(core.mask()) if x
    }
    assert (
        session.native_target(w, dead) is None
        and session.native_target(w, live) == (0, 2)[live]
    )
    mappings = [(a, session.native_action(w, a), controls[a]) for a in moves]
    targets = [a for a in moves if 10 <= a < 60]
    assert not any((a // 10 - 1) == dead for a in targets)
    for a in targets:
        assert (
            controls[a] % 5 == live
            and session.native_action(w, a) // 10 - 1 == (0, 2)[live]
        )
    aid = next(iter(targets), 170)
    before = snapshot(f)
    hp = [a["hp"] for a in w["rows"]]
    current = step(owner, f, aid)
    post = witness(core)
    assert current.engine_steps == f.engine_steps + 1
    assert post["rows"][dead]["hp"] == 0 and not post["rows"][dead]["targetable"]
    if targets:
        assert post["rows"][live]["hp"] < hp[live]
    try:
        step(owner, f, aid)
    except StaleFrameError:
        pass
    else:
        raise AssertionError("Old combat frame still accepted")
    return dict(
        seed=row["seed"],
        before=before,
        prior_terminal=snapshot(old),
        public_native_and_kernel=mappings,
        offered_targeted_cards=targets,
        actor_ids=[a["id"] for a in w["rows"]],
        dead_compact=dead,
        chosen=aid,
        original_coordinate=session.native_action(w, aid),
        hp_before=hp,
        hp_after=[a["hp"] for a in post["rows"]],
        after=snapshot(current),
    )


def verify():
    manifest = survey.read(HERE / "CASES.json")
    old = survey.read(HERE / "SURVEY.json")
    tags = {r["seed"]: r.get("tags", []) for r in old["rows"]}
    sets = [r for r in manifest["rows"] if "physical_order" in tags[r["seed"]]]
    with ProcessPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(check_case, sets, chunksize=1))
    new = survey.survey(candidate.__name__, manifest)
    before = {r["seed"]: r for r in old["rows"]}
    gained = [
        r["seed"]
        for r in new["rows"]
        if r["status"] == "restored_before_candidate"
        and before[r["seed"]]["status"] == "still_empty"
    ]
    assert set(gained) == {r["seed"] for r in sets}
    for r in new["rows"]:
        if r["seed"] not in gained:
            assert r["status"] == before[r["seed"]]["status"]
            assert r["result"]["legal"] == before[r["seed"]]["result"]["legal"]
    return dict(
        frozen_v5=old["types"],
        edition=candidate.__name__,
        checked=len(manifest["rows"]),
        post=new["types"],
        still_empty=new["tags"],
        restored=gained,
        next_inputs=outcomes,
        true_game=original.clip(),
        rules=original.rules(),
        signature=candidate.interface_signature().state_sha256,
        sources={p.name: survey.sha(p) for p in HERE.glob("*.py")},
    )


if __name__ == "__main__":
    data = verify()
    survey.write(HERE / "RESULT.json", data)
    print(data["post"], data["still_empty"])
