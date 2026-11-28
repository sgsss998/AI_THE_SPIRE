"""Check the three retail menu receipts and branch from each frame to discard the identified potion."""
from pathlib import Path
from experiments.sa_calibration_round3.fresh import replay as view
from experiments.sa_calibration_round4.fresh import invocations
from experiments.sa_calibration_round5.reference import sha, write
from .. import combined as old
from silent_env.runtime import StaleFrameError
from .. import choices
from ..wall import verify as wall

HERE = Path(__file__).resolve().parent


def at(module, journal, calls, index):
    engine = module.make_engine()
    session = module.make_session(engine)
    frame = session.reset(wall.SEED)
    for row in journal[:index-1]:
        aid, _ = view.map_action(row,frame,engine)
        if aid is None:
            assert row["command"] in ("proceed","confirm")
            continue
        frame = wall.step(session,frame,aid)
        for _, event in invocations.received(row,calls):
            aid, _ = invocations.binding(row,event,frame,engine)
            frame = wall.step(session,frame,aid)
    return session,frame


def run():
    journal,calls,_ = wall.loaded()
    cases=[]
    for index in (94,95,96):
        row=journal[index-1]
        snap=row["before"]["raw"]["game_state"]
        assert snap["potions"][0]["id"] == "SteroidPotion" and snap["potions"][0]["can_discard"]
        assert 105 in row["legal"]
        _, broken=at(old,journal,calls,index)
        assert not broken.supported_actions[105]
        session,frame=at(choices,journal,calls,index)
        assert wall.legal(frame) == row["legal"]
        after=wall.step(session,frame,105)
        before_v,after_v=frame.state.vector,after.state.vector
        assert frame.page==after.page and not after.supported_actions[105]
        assert (before_v[17],after_v[17])==(25,0)
        assert before_v[:17]==after_v[:17] and before_v[18:1761]==after_v[18:1761]
        assert after.engine_steps == frame.engine_steps+1
        try:
            wall.step(session,frame,105)
        except StaleFrameError:
            pass
        else:
            raise AssertionError("Discard accepted twice on the old frame")
        cases.append(dict(input=index,source=row["before"]["raw_hash"],page=frame.page,observed_legal=row["legal"],
                          simulated_discard_only=True,belt_before=list(before_v[17:19]),belt_after=list(after_v[17:19])))
    write(HERE/"RESULT.json",dict(edition=choices.interface_signature().metadata(),cases=cases,
                                  original_journal_sha256=sha(wall.R6/"fresh/ACTIONS.jsonl"),
                                  related_actual_discard=sha(wall.R6/"branches/RESULT.json")))
    print("Verified three retail discard offers and three simulated slot-only transactions.")

if __name__ == "__main__":
    run()
