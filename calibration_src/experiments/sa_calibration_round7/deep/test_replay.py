"""Independent retail-specific regression for the Act II save and late route projection."""
from tempfile import TemporaryDirectory

import pytest

from experiments.sa_calibration_round6 import release
from experiments.sa_calibration_round7.reward_family import candidate
from .replay import RUNS, compile_parasite, map_studies, parasite, prepared


def test_archived_reward_fails_before_the_patch_and_succeeds_after_it():
    with TemporaryDirectory() as d:
        before=parasite(release,d)
    with TemporaryDirectory() as d:
        after=parasite(candidate,d)
    assert len(before['simulated_commands'])==29 and before['stop']['sequence']==33
    assert before['reward_kernel_comparison']['matches']
    assert before['first_difference']['diff']=={'rewards':{'native':[['GOLD',11],['CARD',None]],'model':[]}}
    assert after['simulated_commands'][:-1]==before['simulated_commands']
    assert len(after['simulated_commands'])==30 and after['stop'] is None
    assert after['first_difference'] is None and after['comparisons'][-1]['sequence']==34
    assert all(r['model_fields_sha256']==r['native_fields_sha256'] for r in after['comparisons'])
    assert after['comparisons'][-1]['original_options']==[['Deflect',0],['Dagger Spray',0],['Backflip',1]]
    assert len(after['simulator_only_reward_branches'])==5
    assert after['simulator_only_continuation']['reason'] in ('loss','win','cap','unsupported')


def test_post_battle_save_cannot_be_used_for_the_predictive_replay():
    with TemporaryDirectory() as d:
        fixture=compile_parasite(d)
        post_save=RUNS.parent/'saves/THE_SILENT.autosave'
        with pytest.raises(ValueError,match='precombat'):
            prepared(release,13655749040571095217,lambda core:fixture.enter(core,str(post_save)))


def test_production_and_fixture_counts_are_distinguished():
    with TemporaryDirectory() as d:
        study,trajectories=map_studies(release,d)
    third=study[0]
    assert third['public_count']==4 and third['fixture_mode_count']==7
    assert third['columns']==[0,3,5,6]
    assert all(r['public_count']==1 for r in study if r['act']==4)
    heart=next(t for t in trajectories if (t['act'],t['previous_y'])==(4,2))
    assert heart['terminal']=='loss' and heart['actions'] and heart['final_public']['done']
