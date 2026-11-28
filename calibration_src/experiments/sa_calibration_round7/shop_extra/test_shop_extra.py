import pytest
from silent_env.runtime import StaleFrameError
from experiments.sa_calibration_round7.shop_extra import verify


def test_same_shop_index_money_stock_and_exact_instance():
    report=verify.cases()
    assert len(report["verified_shop_actions"])==17
    assert len(report["model_branches"])==12


def test_rejected_full_purchase_preserves_state_but_expires_old_decision():
    s,f,_=verify.shelf()
    unchanged=verify.step(s,f,123)
    assert f.state.vector==unchanged.state.vector and unchanged.engine_steps==f.engine_steps
    assert unchanged.frame_id!=f.frame_id
    with pytest.raises(StaleFrameError):
        verify.step(s,f,105)
    assert s.real_action_mask(frame_id=unchanged.frame_id)==unchanged.supported_actions
