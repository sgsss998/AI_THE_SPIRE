"""Exercise the two different native Cancel outcomes at two original campfires."""
import json
from pathlib import Path
from hashlib import sha256

from experiments.ordinary_reward_hooks193.audit import JAR,RETAIL,dump
from experiments.sa_calibration_round5.reference import write,sha
from experiments.sa_calibration_round5.replay import original_inputs
from .. import events_and_grids as candidate
from ..wall.verify import step,legal
from .session import install

HERE=Path(__file__).resolve().parent


def run():
    original=original_inputs()
    sig=candidate.interface_signature().metadata()
    trail=json.loads((HERE.parent/"retail"/sig["state_sha256"]/"r4-natural.json").read_bytes())
    code=dump(("ui.buttons.CancelButton","screens.select.GridCardSelectScreen#cancelUpgrade","vfx.campfire.CampfireSmithEffect#update"))
    click=code["ui.buttons.CancelButton"]["update()V"]
    actions=[line for line in click if any(word in line for word in ("forUpgrade","confirmScreenUp","cancelUpgrade","closeCurrentScreen","CampfireUI.reopen"))]
    assert sha(JAR)==RETAIL and any("cancelUpgrade()" in line for line in actions) and any("CampfireUI.reopen()" in line for line in actions)
    cases=[]
    for index in (57,92):
        engine=install(candidate.make_engine())
        session=candidate.make_session(engine)
        f=session.reset(trail["seed"])
        for row in trail["rows"][:index-2]:
            if row["status"]=="executed":
                f=step(session,f,row["public_action"])
                for _,a in row.get("incidental_actions",[]):
                    f=step(session,f,a)
        rest=original[index-2]
        assert rest["before"]["raw"]["game_state"]["screen_type"]=="REST" and f.state.vector[6]==7
        starting=f
        f=step(session,starting,111)
        grid=f
        assert legal(grid)==original[index-1]["legal"],(legal(grid),original[index-1]["legal"])
        chosen=original[index-1]["aid"]
        selecting=step(session,grid,chosen)
        assert legal(selecting)==original[index]["legal"]==[172,173]
        grid=step(session,selecting,173)
        assert grid.state.vector==f.state.vector and legal(grid)==legal(f)
        reopened=step(session,grid,173)
        assert reopened.state.vector==starting.state.vector and legal(reopened)==rest["legal"]
        retry=step(session,reopened,111)
        assert retry.state.vector==f.state.vector and legal(retry)==legal(f)
        confirmed=step(session,step(session,retry,chosen),172)
        before=original[index]["before"]["raw"]["game_state"]["deck"]
        after=original[index]["after"]["raw"]["game_state"]["deck"]
        assert [c["uuid"] for c in before]==[c["uuid"] for c in after]
        upgraded=[i for i,(a,b) in enumerate(zip(before,after)) if b["upgrades"]==a["upgrades"]+1]
        assert len(upgraded)==1
        target=upgraded[0]
        v=confirmed.state.vector
        assert f.state.vector[2684+chosen-110]-203==target
        assert v[706+target*2+1]==after[target]["upgrades"] and sum(v[707:898:2])==sum(f.state.vector[707:898:2])+1
        cases.append(dict(first_grid_input=index,raw_before=original[index-1]["before"]["raw_hash"],
            raw_preview=original[index]["before"]["raw_hash"],native_grid=original[index-1]["legal"],
            native_preview=original[index]["legal"],native_actual_confirm_uuid=after[target]["uuid"],
            simulated_cancel_order=["preview to list","list to original rest menu"],reselected=chosen,permanent_deck_index=target))
    write(HERE/"RESULT.json",dict(retail_jar=RETAIL,cancel_method_hash=sha256("\n".join(click).encode()).hexdigest(),
        cancel_operations=actions,scope="Original menus and actual confirmation; both cancel branches are simulator alternatives checked against the original method.",
        cases=cases))
    print("Both cancel branches, re-entry and exact real upgrade matched at both campfires.")


if __name__=="__main__":
    run()
