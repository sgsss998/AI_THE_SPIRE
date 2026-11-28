from copy import deepcopy
from tempfile import TemporaryDirectory

import pytest
from silent_env.interface import InterfaceMismatch
from experiments.sa_calibration_round7 import battle
from experiments.sa_calibration_round7.death_family.thief_rewards import verify
from experiments.sa_calibration_round7.death_family.thief_rewards.session import (
    one_escaped,
)
from experiments.sa_calibration_round7.death_family.thief_rewards.observation import (
    release,
)


def test_same_s_and_same_a_can_repay_different_amounts():
    with TemporaryDirectory() as d:
        choices, collision = verify.branches(d)
    assert [case["branch"] for case in choices] == [
        "native-order",
        "stolen-first",
        "exit",
    ]
    assert collision["original_rewards"] == [60, 15] and collision[
        "swapped_rewards"
    ] == [40, 15]


def test_other_thief_endings_do_not_take_this_reward_path():
    actor = dict(half_dead=False, targetable=False, escaping=False, hp=0)
    w = dict(
        steps=10,
        in_battle=False,
        undecided=False,
        alive=0,
        queue=0,
        card_queue=0,
        physical_order=[0, 1],
        rows=[dict(actor, id="LOOTER"), dict(actor, id="MUGGER", hp=33, escaping=True)],
    )
    assert one_escaped(w, 10)
    for slot, values in [
        (1, dict(hp=0, escaping=False)),
        (0, dict(id="REPULSOR")),
        (0, dict(hp=-1)),
        (1, dict(half_dead=True)),
    ]:
        other = deepcopy(w)
        other["rows"][slot].update(values)
        assert not one_escaped(other, 10)
    assert not one_escaped(w, 11)


def test_3127_and_3122_observations_require_distinct_checkpoint_dimensions():
    old = battle.interface_signature()
    new = release.interface_signature()
    assert (
        old.actions == new.actions == 193
        and old.action_source_sha256 == new.action_source_sha256
    )
    assert (
        old.state_sha256 != new.state_sha256 and old.state_version != new.state_version
    )
    with pytest.raises(InterfaceMismatch):
        new.assert_model_dimensions(3122, 193)
    new.assert_model_dimensions(3127, 193)
