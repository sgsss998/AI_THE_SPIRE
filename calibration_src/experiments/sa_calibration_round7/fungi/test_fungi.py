from types import SimpleNamespace
import pytest
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError
from experiments.sa_calibration_round7.fungi import candidate, verify
from experiments.sa_calibration_round7.fungi.session import r3


@pytest.mark.parametrize("action", (23,105,170))
def test_fresh_casualty_accepts_retail_action_never_dead_target(action):
    session, frame = verify.before_death(59)
    assert verify.replay.legal(frame) == [0,1,2,4,23,70,105,170]
    with pytest.raises(UnverifiedSemanticsError):
        verify.replay.step(session,frame,13)
    successor = verify.replay.step(session,frame,action)
    assert successor.engine_steps == frame.engine_steps+1
    if action==23:
        assert (successor.state.vector[1046],successor.state.vector[901]) == (16,2)
    if action==105:
        assert successor.state.vector[17] == 0 and not successor.supported_actions[105]
    if action==170:
        assert successor.state.vector[902] == frame.state.vector[902]+1
    with pytest.raises(StaleFrameError):
        verify.replay.step(session,frame,action)


@pytest.mark.parametrize("fault", ("queued","targetable","wrong_step","order"))
def test_inconsistent_decision_witness_rejects_commands(monkeypatch,fault):
    prefix,_ = verify.source(59)
    session = candidate.make_session()
    frame = session.reset(59)
    for action in prefix[:-1]:
        frame = verify.replay.step(session,frame,action)
    base = r3.ordinary.observer()
    def inspect(engine):
        w = base.inspect(engine)
        if fault=="queued": w["queue"] += 1
        if fault=="targetable": w["rows"][0]["targetable"] = True
        if fault=="wrong_step": w["steps"] -= 1
        if fault=="order": w["physical_order"] = [1,0]
        return w
    monkeypatch.setattr(r3.ordinary,"observer",lambda:SimpleNamespace(inspect=inspect))
    blocked = verify.replay.step(session,frame,prefix[-1])
    assert not any(blocked.supported_actions) and "death_boundary_unknown" in blocked.action_gaps


def test_round4_old_natural_decisions_remain_bound_through_fungus_fight():
    trace = verify.natural_trace()
    assert trace["first_substantive_difference"] is None
    assert trace["completed_inputs"] == 245 and trace["stop"]["index"] == 246
    assert trace["stop"]["page"] == "SHOP_SCREEN"
    rows = {r["index"]: r for r in trace["fungal_steps"]}
    for i in range(143,151):
        assert rows[i]["observed_actions_match"]
    assert rows[152]["action"]==172 and not rows[152]["observed_actions_match"]


def test_discovery_poisoned_corpse_keeps_dead_target_inaccessible():
    row = verify.read(verify.HERE/"poison_case.json")
    session = candidate.make_session()
    frame = session.reset(row["seed"])
    for action in row["actions"]:
        frame = verify.replay.step(session,frame,action)
    assert frame.state.vector[993+18] == 2
    assert verify.replay.legal(frame) == [0,2,3,21,170]
    assert not frame.supported_actions[11]
    successor = verify.replay.step(session,frame,21)
    assert successor.state.vector[993+18] == 0 and successor.state.vector[993+37] == 0
    assert successor.state.vector[1045+18] == 2 and successor.state.vector[1045+37] == 2
