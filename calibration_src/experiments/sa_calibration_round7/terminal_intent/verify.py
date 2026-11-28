"""Verify the full original boss run and two independent game-over receipts."""
from dataclasses import replace
from pathlib import Path
from experiments.sa_calibration_round4.fresh import invocations
from experiments.sa_calibration_round5.replay import original_inputs
from experiments.sa_calibration_round6.reference import R4, read, sha, write
from ..shop import verify as shop
from ..wall import verify as wall
from . import candidate

HERE=Path(__file__).resolve().parent


def underlying(frame):
    assert frame.state.state_version.endswith(candidate.TAG)
    return replace(frame,state=replace(frame.state,state_version=frame.state.state_version.removesuffix(candidate.TAG)))


def compare(engine,frame,snap):
    return shop.compare(engine,underlying(frame),snap)


def attack(frame):
    return list(map(int,frame.state.vector[1000:1003]))


def original_attack(game):
    enemy, = game["combat_state"]["monsters"]
    return [shop.schema()["enums"]["Intent"][enemy["intent"]]+1, enemy["move_adjusted_damage"],enemy["move_hits"]]


def audit():
    full=original_inputs()
    r6,calls,_=wall.loaded()
    # The capture verifier maintains one bound native index per original game.
    cases=[]
    for journal,invoked,compare_func in [(r6,calls,compare),(full,None,compare)]:
        if invoked is None:
            journal=original_inputs()
            invoked=invocations.captures()
        seed=journal[0]["before"]["raw"]["game_state"]["seed"]%(1<<64)
        last=journal[-1]["index"]
        result,frames=wall.retail_replay(journal,invoked,seed=seed,session_factory=candidate.make_session,
                compare_frame=compare_func,map_input=shop.map_input,watch=(last-1,last))
        before,after=(journal[-1][k]["raw"]["game_state"] for k in ("before","after"))
        assert last==result["completed_inputs"] and result["stop"] is None
        assert result["first_substantive_difference"] is None
        assert original_attack(before)==original_attack(after)==attack(frames[last-1])==attack(frames[last])
        cases.append(dict(seed=seed,inputs=last,first_substantive_difference=result["first_substantive_difference"],
                          stop=result["stop"],original_before=journal[-1]["before"]["raw_hash"],
                          original_after=journal[-1]["after"]["raw_hash"],enemy=after["combat_state"]["monsters"][0]["id"],
                          original_attack=original_attack(after),model_attack=attack(frames[last]),
                          final_floor=after["floor"],hp=after["current_hp"]))
    # The older R3 baseline supplies another independent recorded dying attack.
    path=R4.parent/"sa_calibration_round3/fresh/ACTIONS.jsonl"
    d=wall.archive.view.rows(path)[-1]
    first,last=[d[k]["raw"]["game_state"] for k in ("before","after")]
    assert d["aid"]==170 and original_attack(first)==original_attack(last) and last["current_hp"]==0
    return dict(runtime={p.name:sha(p) for p in (HERE/"session.py",HERE/"candidate.py")},replayed=cases,
                extra_retail_only=dict(journal=sha(path),enemy=last["combat_state"]["monsters"][0]["id"],
                    before_hash=d["before"]["raw_hash"],after_hash=d["after"]["raw_hash"],attack=original_attack(last)))


if __name__=="__main__":
    result=audit()
    write(HERE/"RESULT.json",result)
    print(result)
