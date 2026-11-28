from copy import deepcopy
from dataclasses import replace

import pytest
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError

from experiments.sa_calibration_round7 import combined
from experiments.sa_calibration_round7.death_family import candidate, verify
from experiments.sa_calibration_round7.death_family.session import (
    casualties,
    checked_bindings,
    r3,
)

CASES = verify.read(verify.HERE / "EXAMPLES.json")
MENUS = (
    [0, 1, 2, 170],
    [0, 1, 12, 13, 22, 23, 170],
    [2, 21, 170],
    [110, 111, 112],
    [1, 3, 20, 30, 170],
)


def backing(session):
    while not isinstance(session, r3.TransitionSession):
        session = vars(session).get("delegate", vars(session).get("base"))
    return session.pages


@pytest.mark.parametrize("row,expected", list(zip(CASES, MENUS, strict=True)))
def test_discovery_cases_restore_existing_actions(row, expected):
    _, _, old = verify.to(combined, row["seed"], row["actions"])
    assert old.action_gaps == ("death_boundary_unknown",) and not any(
        old.supported_actions
    )
    _, session, frame = verify.to(candidate, row["seed"], row["actions"])
    assert verify.deep.allowed(frame) == expected
    pages = backing(session)
    raw = pages._backing._raw
    kernel = pages._backing._source._env
    witness = r3.ordinary.observer().inspect(kernel)
    dead, escaped = casualties(pages._source, witness)
    for j in dead + escaped:
        assert not any(
            frame.supported_actions[a]
            for a in (*range(10 + 10 * j, 20 + 10 * j), *range(75 + 5 * j, 80 + 5 * j))
        )
    assert checked_bindings(
        pages._source, raw, kernel, set(dead + escaped), raw.hand_order.active
    )
    bad = replace(raw, bindings=raw.bindings[:-1])
    assert not checked_bindings(
        pages._source, bad, kernel, set(dead + escaped), raw.hand_order.active
    )
    if raw.hand_order.active:
        wrong = replace(
            raw, bindings=(replace(raw.bindings[0], choice_row=10), *raw.bindings[1:])
        )
        assert not checked_bindings(
            pages._source, wrong, kernel, set(dead + escaped), True
        )
    else:
        with pytest.raises(UnverifiedSemanticsError):
            session.step(
                10 + 10 * dead[0],
                frame_id=frame.frame_id,
                action_version=frame.action_version,
            )
    advanced = verify.step(session, frame, expected[0])
    assert advanced.engine_steps == frame.engine_steps + 1
    with pytest.raises(StaleFrameError):
        session.step(
            expected[0], frame_id=frame.frame_id, action_version=frame.action_version
        )


def test_unsettled_dead_actor_and_escape_flags():
    row = CASES[1]
    _, session, _ = verify.to(candidate, row["seed"], row["actions"])
    pages = backing(session)
    frame = pages._source
    w = r3.ordinary.observer().inspect(pages._backing._source._env)
    assert casualties(frame, w) == ([2], [])
    for key, value in [
        ("will_escape", True),
        ("half_dead", True),
        ("escaping", True),
        ("targetable", True),
        ("hp", 1),
        ("id", "DARKLING"),
    ]:
        changed = deepcopy(w)
        changed["rows"][2][key] = value
        assert casualties(frame, changed) is None
    for key, value in [
        ("steps", w["steps"] - 1),
        ("physical_order", [2, 1, 0]),
        ("card_queue", 1),
        ("has_horn", True),
        ("has_specimen", True),
    ]:
        changed = deepcopy(w)
        changed[key] = value
        assert casualties(frame, changed) is None
    # Escape retains positive HP, but target and death powers must not be republished.
    from experiments.sa_calibration_round7.death_family.session import MONSTERS

    changed = deepcopy(w)
    a = changed["rows"][2]
    a.update(id="MUGGER", hp=17, escaping=True)
    v = list(frame.state.vector)
    v[1097:1099] = [MONSTERS["MUGGER"] + 1, 17]
    updated = replace(frame, state=replace(frame.state, vector=tuple(v)))
    assert casualties(updated, changed) == ([], [2])
    a["id"] = "GREEN_LOUSE"
    v[1097] = MONSTERS["GREEN_LOUSE"] + 1
    updated = replace(frame, state=replace(frame.state, vector=tuple(v)))
    assert casualties(updated, changed) is None
