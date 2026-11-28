from tempfile import TemporaryDirectory

import pytest

from experiments.sa_calibration_round7.event_death import verify as v


@pytest.mark.parametrize("case", v.CASES)
def test_lethal_golden_wing_has_no_decision(case):
    result = v.run_row(case)
    assert result["outcome"] == "terminal" and result["after"]["page"] == "GAME_OVER"
    assert result["before"]["hp"] == case["expected_hp"] and result["after"]["hp"] == 0
    assert result["after"]["legal"] == [] and result["after"]["complete"]


@pytest.fixture(scope="module")
def control():
    with TemporaryDirectory() as d:
        yield v.build(d, v.HERE / "directed.cpp", "_r7_event_cost_control")


@pytest.mark.parametrize(
    "hp,fairy,scrap,action,finished,remain",
    [
        (7, False, False, 110, True, 0),
        (8, False, False, 110, False, 1),
        (2, True, False, 110, False, 19),
        (2, False, False, 112, False, 2),
        (2, False, True, 110, True, 0),
    ],
)
def test_boundary_and_revival(control, hp, fairy, scrap, action, finished, remain):
    row = next(x for x in v.CASES if x["expected_hp"] == 2)
    result = v.run_row(row, lambda env: control.set(env, hp, fairy, scrap), action)
    assert result["after"]["done"] == finished and result["after"]["hp"] == remain
    if not finished:
        e, s, f = v.replay(
            v.candidate.parent, row, lambda env: control.set(env, hp, fairy, scrap)
        )
        reference = v.step(s, f, action)
        assert (
            result["after"]["page"] == reference.page
            and result["after"]["legal"] == v.episode.snapshot(reference)["legal"]
        )
    if fairy:
        assert not any(result["potions"])
