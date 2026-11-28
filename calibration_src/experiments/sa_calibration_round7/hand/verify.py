"""Use real card UUIDs and the original method to check one-click replacements."""
from pathlib import Path
from experiments.sa_calibration_round5.reference import write
from silent_env.runtime import StaleFrameError
from .. import battle,choices
from ..potions.verify import at
from ..wall.verify import loaded,step
from .ledger import bind
from .original import run as game_rule

HERE=Path(__file__).resolve().parent


def run():
    journal,calls,_=loaded()
    row=journal[113]
    native=row["before"]["raw"]["game_state"]["screen_state"]
    assert row["index"]==114 and row["legal"]==[110,111,172] and len(native["selected"])==1
    old_session,old=at(choices,journal,calls,114)
    assert not old.supported_actions[110] and not old.supported_actions[111]
    cases=[]
    for a in (110,111):
        session,frame=at(battle,journal,calls,114)
        engine=session.delegate.engine
        assert frame.supported_actions[a] and session.real_action_mask(frame_id=frame.frame_id)[a]
        aid,ref=bind(dict(row,aid=a),frame,engine)
        assert aid==a and ref["uuid"]==native["hand"][a-110]["uuid"]
        v=frame.state.vector
        physical=ref["physical_model_slot"]
        next_frame=step(session,frame,a)
        end=engine._source._current.hand_order
        assert end.selected==(physical,) and len(end.remaining)==len(native["hand"])
        assert next_frame.state.vector[:26]==v[:26] and next_frame.state.vector[706:898]==v[706:898]
        assert next_frame.state.vector[2684+physical]==-1
        assert next_frame.supported_actions[172]
        try:
            step(session,frame,a)
        except StaleFrameError:
            pass
        else:
            raise AssertionError("Repeated old decision accepted")
        confirmed=step(session,next_frame,172)
        assert confirmed.state.vector[0:6]==v[0:6] and not engine._source._current.hand_order.active
        cases.append(dict(action=a,uuid=ref["uuid"],face=ref["face"],physical_slot=physical,
                          public_steps=1,backing_selection_steps=next_frame.engine_steps-frame.engine_steps))
    result=dict(original_rule=game_rule(),original_capture=row["before"]["raw_hash"], cases=cases,
                evidence="Two archived real options; alternate input results tested in the simulator and separately against the retail selection method.")
    write(HERE/"RESULT.json",result)
    print("Verified both offered replacement actions and 45 original-method physical card cases.")

if __name__=="__main__":
    run()
