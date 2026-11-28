import pytest
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError
from experiments.sa_calibration_round7.shop import candidate, verify
from experiments.sa_calibration_round7.wall.verify import step, legal


def shelf():
    record = verify.read(verify.HERE/"RESULT.json")
    session = candidate.make_session()
    frame = session.reset(record["purchase"]["seed"])
    for row in record["replay"]["rows"][:245]:
        if row["status"] == "executed":
            frame = step(session,frame,row["public_action"])
            for _,a in row.get("incidental_actions",[]):
                frame = step(session,frame,a)
    assert frame.page == "SHOP_SCREEN"
    return session,frame


@pytest.mark.parametrize("action",range(111,118))
def test_exact_card_debit_and_sale(action):
    session,frame = shelf()
    v = frame.state.vector
    start = 322+6*(action-110)
    _,face,up,price,_,enabled = v[start:start+6]
    assert enabled and action in legal(frame)
    with pytest.raises(UnverifiedSemanticsError):
        step(session,frame,118)
    result = step(session,frame,action)
    w = result.state.vector
    n = 2*int(v[22])
    assert w[2] == v[2]-price and w[22]==v[22]+1
    assert w[706:706+n]==v[706:706+n] and w[706+n:708+n]==(face,up)
    assert result.engine_steps == frame.engine_steps+1
    with pytest.raises(StaleFrameError):
        step(session,frame,action)
    for i in legal(result):
        if 110<=i<170:
            idx=322+6*(i-110)
            assert w[idx+3]<=w[2]


def test_old_original_reaches_terminal_and_retains_last_real_difference():
    evidence = verify.audit()
    replay = evidence["replay"]
    assert replay["completed_inputs"]==replay["total_original_inputs"]==339 and replay["stop"] is None
    assert evidence["purchase"]["price"]==52
    assert evidence["purchase"]["retail_shelf_uuid"]==evidence["purchase"]["retail_deck_added_uuid"]
    assert replay["first_substantive_difference"]==dict(index=339,phase="after",fields={
        "enemy_intents":{"model":[["hexaghost",3]],"original":[["hexaghost",1]]}})
