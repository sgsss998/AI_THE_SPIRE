from copy import deepcopy
import pytest
from experiments.sa_calibration_round7.combat_edges import (
    original,
    session,
    survey,
    verify,
)

REPORT = survey.read(verify.HERE / "SURVEY.json")
CASES = {r["seed"]: r for r in survey.read(verify.HERE / "CASES.json")["rows"]}
TWO = next(r for r in REPORT["rows"] if r.get("tags") == ["physical_order"])


def test_unchanged_real_right_target_is_original_slot_two():
    rows = original.clip()["paired_inputs"]
    assert [r["before_hp"][2] - r["after_hp"][2] for r in rows] == [9, 6, 6]
    assert all(r["native_target"]["monster_position"]["index"] == 2 for r in rows)


@pytest.mark.parametrize(
    "key,alternate",
    [
        ("physical_order", [1, -1, 0]),
        ("physical_order", [-1, 0, 1]),
        ("physical_order", [0, 1, -1]),
        ("physical_order", [0, -1, 1, 1]),
        ("alive", 2),
    ],
)
def test_overlaid_parent_position_cannot_be_guessed(key, alternate):
    w = deepcopy(TWO["witness"])
    assert session.split_slots(w) == (0, 2)
    w[key] = alternate
    assert session.split_slots(w) is None


def test_spawning_parent_or_reviving_foe_remains_unverified():
    for key, value in [
        ("id", "DARKLING"),
        ("half_dead", True),
        ("escaping", True),
        ("max", 999),
    ]:
        w = deepcopy(TWO["witness"])
        w["rows"][1][key] = value
        assert session.split_slots(w) is None


@pytest.mark.parametrize("seed", [8323056033720579327, 8542689634703930831])
def test_both_living_child_positions_accept_their_own_attack(seed):
    result = verify.check_case(CASES[seed])
    live = 1 - result["dead_compact"]
    assert (
        result["hp_before"][live] > result["hp_after"][live]
        and result["hp_after"][1 - live] == 0
    )
