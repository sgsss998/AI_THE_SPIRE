"""Bind actual original seed 54072726's offered discard, then test the alternative transaction."""
from pathlib import Path
from experiments.sa_calibration_round4.events import verify as history
from experiments.sa_calibration_round5.reference import write
from silent_env.runtime import StaleFrameError
from .. import transactions
from ..wall.verify import step,legal
from .session import attach

HERE=Path(__file__).resolve().parent


def run():
    seed=54072726
    original={p["sequence"]:p for p in history.replay.rows(history.OLDER/"raw.jsonl")
              if p.get("raw",{}).get("game_state",{}).get("seed")==seed}
    receipt=original[263]
    game=receipt["raw"]["game_state"]
    assert game["choice_list"] and len(game["choice_list"])==1 and game["potions"][0]["id"]=="Explosive Potion"
    assert game["potions"][0]["can_discard"] and not game["potions"][0]["can_use"]
    cases=[]
    for discard in (False,True):
        engine=transactions.make_engine()
        session=attach(transactions.make_session(engine))
        f=session.reset(seed)
        for row in history.read(history.old.R1/"fidelity/supplement/RESULT.json")["multi"]["prefix"]:
            raw=original[row["output"]]
            assert history.digest(history.OLDER/"results"/(raw["pending_request_id_at_receipt"]+".json"))==row["receipt_sha256"]
            f=step(session,f,row["action"])
        assert f.page=="SERPENT_LEAVE" and legal(f)==[105,110]
        assert f.state.vector[:3]==(66,66,128) and f.state.vector[22]==16
        initial=f
        if discard:
            f=step(session,f,105)
            assert f.page==initial.page and legal(f)==[110] and f.state.vector[17]==0 and f.state.vector[18:22]==initial.state.vector[18:22]
            try:
                step(session,initial,105)
            except StaleFrameError:
                pass
            else:
                raise AssertionError("Old drop accepted twice")
        after=step(session,f,110)
        assert after.state.vector[6]==5 and after.state.vector[:3]==initial.state.vector[:3] and after.state.vector[706:898]==initial.state.vector[706:898]
        if not discard:
            history.check_frame(after,original[264],engine)
        assert after.state.vector[17]==(0 if discard else initial.state.vector[17])
        cases.append(dict(simulated_discard=discard,belt=list(after.state.vector[17:19]),gold=int(after.state.vector[2]),
            deck_size=int(after.state.vector[22]),real_action_taken="leave"))
    write(HERE/"RESULT.json",dict(seed=seed,frame=263,source_sha256=receipt["raw_hash"],
        real_potion=game["potions"][0],real_options=game["choice_list"],model_menu=[105,110],branches=cases))
    print("Replayed the original decline/leave and the alternative slot-only discard.")


if __name__=="__main__":
    run()
