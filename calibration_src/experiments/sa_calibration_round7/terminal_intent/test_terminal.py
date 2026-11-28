import pytest
from experiments.sa_calibration_round7.terminal_intent import session,verify


@pytest.mark.parametrize("multi,action,hp",[(True,170,3),(False,0,3),(False,170,40)])
def test_preserving_attack_requires_a_lethal_single_enemy_end(multi,action,hp):
    from dataclasses import make_dataclass
    S=make_dataclass("S",["vector"],frozen=True)
    F=make_dataclass("F",["state","done","engine_steps","supported_actions"],frozen=True)
    v=[0]*3122
    v[0]=hp;v[3:8]=[10,1,20,9,1];v[993:1003]=[33,20,40,0,0,0,1,1,8,1]
    if multi:v[1045:1055]=v[993:1003]
    f=F(S(tuple(v)),False,10,tuple(i==170 for i in range(193)))
    v[0]=0;v[31]=session.LOSS;v[1000]=3
    g=F(S(tuple(v)),True,11,(False,)*193)
    assert session.published_intent(f,action,g) is g


def test_both_retail_runs_to_actual_gameover():
    docs=verify.audit()
    assert [(q["inputs"],q["model_attack"]) for q in docs["replayed"]]==[(120,[3,24,1]),(339,[1,12,2])]
