"""Reconcile the full raw retail card/leave menus with their exact native capture and deck settlement."""
import json
from pathlib import Path

from experiments.reward_resolution193.mask_verify import observed_actions
from experiments.sa_calibration_round5.reference import read,write
from silent_env.native_compare import load_native_capture
from .. import battle
from ..wall.verify import step,legal
from .session import install,OpeningMenus

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parents[2]/"native_runtime"


def actual(path):
    raw=read(path/"bridge_snapshot.json")
    info=(read(path/"evidence.json")["native"] if (path/"evidence.json").exists()
          else read(path/"comparison.json")["exact_native_capture"])
    bound=load_native_capture(path/"native_prefix.jsonl",info["capture_id"],
        bridge_log=path/"bridge_prefix.jsonl",scope=info["source_scope"])
    assert raw["raw_hash"]==bound.evidence["bridge_raw_sha256"] and bound.evidence["exact_capture_binding"]
    actions=observed_actions(raw["raw"],bound.payload)
    return dict(seed=raw["raw"]["game_state"]["seed"],raw_sha256=raw["raw_hash"],targets=list(actions),
                native_id=info["capture_id"],screen=raw["raw"]["game_state"]["screen_type"])


def setup(seed):
    engine=install(battle.make_engine())
    session=OpeningMenus(battle.make_session(engine))
    return session,step(session,session.reset(seed),110)


def run():
    root=NATIVE/"compact_native_004/pilot/points"
    direct=[actual(root/f"{i:04d}") for i in (2,3)]
    assert [x["targets"] for x in direct]==[[110,111,112,177],[110]]
    pairs=[]
    for gift in (110,111,112,177):
        session,offer=setup(1)
        frame=step(session,offer,110)
        before=frame.state.vector
        assert legal(frame)==direct[0]["targets"] and frame.policy_mask == frame.supported_actions
        after=step(session,frame,gift)
        assert legal(after)==direct[1]["targets"] and after.policy_mask==after.supported_actions
        v=after.state.vector
        size=2*int(before[22])
        assert before[:3]==v[:3] and before[706:706+size]==v[706:706+size]
        assert v[22]==before[22]+int(gift!=177)
        name=None
        if gift!=177:
            face=before[323+(gift-110)*6:325+(gift-110)*6]
            assert v[706+size:708+size]==face
            name=session.delegate.delegate.engine._source._backend.CARD_IDS[int(face[0])-1]
        back=step(session,after,110)
        assert back.state.vector[6]==5 and back.state.vector[706:898]==v[706:898]
        pairs.append(dict(action=gift,card=name,new_deck_size=int(v[22])))
    leaves=[]
    for name in ("compact_fixture_neow_common_seed35","compact_fixture_neow_maxhp_seed25",
                 "compact_fixture_neow_choker_seed1000017"):
        path=NATIVE/name/"fixture_control/observations"
        receipt=actual(path/"0002")
        assert receipt["targets"]==[110]
        session,start=setup(receipt["seed"])
        actions=[json.loads(line) for line in (path.parent/"actions.jsonl").read_text().splitlines()]
        select=actions[1]["action_id"]
        frame=step(session,start,select)
        assert frame.page=="NEOW_RESULT" and legal(frame)==receipt["targets"] and frame.policy_mask==frame.supported_actions
        receipt["chosen_gift"]=select
        leaves.append(receipt)
    write(HERE/"RESULT.json",dict(original_menus=direct+leaves,simulated_colorless_results=pairs,
                                  acquisition_scope="Retail skip on seed 1. Three alternate acquisitions checked against the displayed card and full deck."))
    print("Verified the retail colorless menu, three alternative choices, skip and original leave receipts.")

if __name__=="__main__":run()
