"""Run against already published R6 development seeds, never an acceptance cohort."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.sa_calibration_round6 import release
from .episode import fingerprint, trial


@pytest.mark.parametrize('seed', [19, 46])
def test_fixed_policy_matches_archived_r6_episode(seed):
    reference = Path(release.__file__).parent / 'regression/RESULT.json'
    old = next(r for r in json.loads(reference.read_text())['records'] if r['seed'] == seed)
    run = trial(seed, 'fixed', old['cap'])
    for key in ('reason', 'page', 'engine_floor', 'actions', 'cause', 'engine_steps', 'summary_floor',
                'act3_cleared', 'heart_killed', 'incomplete_action_sets', 'ui_only_actions'):
        assert old[key] == run[key]
    assert sum(run['scene_counts'].values()) == len(run['actions']) + 1
    assert run['determinism']['matched'] is True
    assert json.loads(json.dumps(run))['actions'] == old['actions']
    if old['reason'] == 'unsupported':
        assert run['stop']['after']['legal'] == []
        assert run['stop']['step'] == len(old['actions'])


def test_three_strategies_exercise_distinct_actions_and_reproduce():
    runs = [trial(19, name, cap=12) for name in ('fixed', 'survival', 'explore')]
    assert len({tuple(row['actions']) for row in runs}) == 3
    assert all(row['reason'] == 'cap' and row['determinism']['matched'] for row in runs)


def test_hidden_tail_and_masks_are_part_of_the_fingerprint():
    f = release.make_session().reset(19, ascension=20, final_act=True)
    values = tuple(f.state.vector) + (0,)
    first = replace(f, state=replace(f.state, vector=values))
    next_tail = replace(first, state=replace(first.state, vector=values[:-1] + (1,)))
    assert fingerprint(f) != fingerprint(first) != fingerprint(next_tail)
    assert fingerprint(replace(f, policy_mask=None)) != fingerprint(replace(f, policy_mask=f.supported_actions))


def test_oracle_can_flag_a_semantic_failure_without_blocking_play():
    def damaged_session(engine):
        backing = release.make_session(engine)
        def reset(*args, **kwargs):
            f = backing.reset(*args, **kwargs)
            values = list(f.state.vector)
            values[0] = values[1] + 1
            return replace(f, state=replace(f.state, vector=tuple(values)))
        return SimpleNamespace(reset=reset, step=backing.step)
    runtime = SimpleNamespace(make_engine=release.make_engine, make_session=damaged_session)
    row = trial(19, 'fixed', cap=3, runtime=runtime)
    assert len(row['actions']) == 3
    assert row['first_semantic']['step'] == 0
    assert row['semantic_counts']['hp_exceeds_maximum'] == 1
    assert row['first_semantic']['after']['state_nonzero']


def test_repeat_reports_the_first_different_state_without_changing_actions():
    calls = []
    def versioned_session(engine):
        backing = release.make_session(engine)
        calls.append(None)
        version = str(len(calls))
        def reset(*args, **kwargs):
            f = backing.reset(*args, **kwargs)
            return replace(f, state=replace(f.state, state_version=f.state.state_version + version))
        return SimpleNamespace(reset=reset, step=backing.step)
    runtime = SimpleNamespace(make_engine=release.make_engine, make_session=versioned_session)
    row = trial(19, 'fixed', cap=2, runtime=runtime)
    assert not row['determinism']['matched']
    assert row['determinism']['first_different_frame'] == 0
    assert row['determinism']['first_different_action'] is None
