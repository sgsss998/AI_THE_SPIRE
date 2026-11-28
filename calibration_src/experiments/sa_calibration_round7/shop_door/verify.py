"""Verify both actual shop doors and each alternative belt-discard transaction."""
import json
from pathlib import Path

from experiments.sa_calibration_round5.replay import original_inputs
from experiments.sa_calibration_round5.reference import write
from silent_env.runtime import StaleFrameError
from .. import decisions
from ..wall.verify import step, legal
from .session import install

HERE = Path(__file__).resolve().parent


def run():
    journal = original_inputs()
    signed = decisions.interface_signature().metadata()
    trail = json.loads((HERE.parent/"retail"/signed["state_sha256"]/"r4-natural.json").read_bytes())
    cases = []
    for index in (245,248):
        receipt = journal[index-1]
        game = receipt["before"]["raw"]["game_state"]
        assert game["screen_type"] == "SHOP_ROOM" and receipt["legal"] == [105,106,110,171]
        assert all(p["can_discard"] and not p["can_use"] for p in game["potions"])
        for aid in (105,106):
            engine = install(decisions.make_engine())
            session = decisions.make_session(engine)
            frame = session.reset(trail["seed"])
            for rec in trail["rows"][:index-1]:
                if rec["status"]=="executed":
                    frame=step(session,frame,rec["public_action"])
                    for _,extra in rec.get("incidental_actions",[]):
                        frame=step(session,frame,extra)
            assert frame.page=="SHOP_ROOM" and legal(frame)==receipt["legal"]
            before = frame.state.vector
            after = step(session,frame,aid)
            v = after.state.vector
            slot = 17+aid-105
            assert before[slot]>0 and v[slot]==0 and v[:slot]==before[:slot] and v[slot+1:112]==before[slot+1:112]
            assert v[322:898]==before[322:898] and after.page==frame.page and after.engine_steps==frame.engine_steps+1
            assert legal(after)==[i for i in receipt["legal"] if i!=aid]
            try:
                step(session,frame,aid)
            except StaleFrameError:
                pass
            else:
                raise AssertionError("Second discard accepted on stale shop frame")
            reopened = step(session,after,110)
            assert reopened.page=="SHOP_SCREEN" and reopened.state.vector[17:19]==v[17:19]
            cases.append(dict(input=index,raw_sha256=receipt["before"]["raw_hash"],real_belt=game["potions"],real_actions=receipt["legal"],
                model_actions=legal(frame),discard=aid,after_belt=v[17:19],model_end=after.page,
                before_remembered_shop_entries=sum(bool(before[i]) for i in range(322,706,6)),
                certified_before=frame.policy_mask==frame.supported_actions))
    write(HERE/"RESULT.json",dict(source_journal=trail["journal_sha256"],cases=cases))
    print("Compared two actual shop-room menus and four slot-only simulator discards.")


if __name__ == "__main__":
    run()
