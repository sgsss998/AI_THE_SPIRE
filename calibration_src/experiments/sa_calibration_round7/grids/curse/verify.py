"""Reproduce original wrong draws; verify the exact corrected physical deck, RNG and subsequent map."""
from pathlib import Path

from experiments.sa_calibration_round6.reference import read,sha,write
from experiments.wing_removal_640.session import current_deck
from silent_env.action193 import choice_action
from silent_env.runtime import StaleFrameError
from ..colors_verify import examples
from ..original import transformations
from ..verify import probe,step
from . import candidate
from .session import BUILD,kernel

HERE=Path(__file__).resolve().parent


def check(seed,card,actions):
    e=candidate.make_engine();s=candidate.make_session(e);f=s.reset(seed)
    for a in actions:
        if not f.supported_actions[a]:return None
        f=step(s,f,a)
    if f.page!="PERMANENT_CARD_GRID":return None
    p=e._r7_picker
    ids=e._source._backend.CARD_IDS
    option=next(i for i,pos in enumerate(p.positions) if ids[p.cards[pos][0]-1]==card)
    aid=choice_action(option)
    if not f.supported_actions[aid]:return None
    pos=p.positions[option]
    physical=current_deck(e)
    audit=probe().audit(e._source._env)
    receipt=kernel().prepare(e._source._env,option,pos)
    try:
        kernel().settle(e._source._env,receipt)
    except RuntimeError:
        pass
    else:
        raise AssertionError("An uncommitted draw must reject its receipt")
    hp,maximum,wallet=f.state.vector[:3]
    f=step(s,f,aid);f=step(s,f,173)
    assert current_deck(e)==physical
    f=step(s,f,aid);past=f;f=step(s,f,172)
    assert f.page=="PERMANENT_CARD_LEAVE"
    new=current_deck(e)
    assert new[:-1]==physical[:pos]+physical[pos+1:] and new[-1][1:]==(0,0,False)
    nh=max(1,maximum-3) if card=="Parasite" else maximum
    assert f.state.vector[:3]==(min(hp,nh),nh,wallet)
    try:
        step(s,past,172)
    except StaleFrameError:
        pass
    else:
        raise AssertionError("Expired curse confirmation accepted twice")
    f=step(s,f,110)
    assert f.state.vector[6]==5 and current_deck(e)==new
    assert id(new)!=id(physical) and ids[new[-1][0]-1]!=card
    return dict(seed=seed,floor=audit["floor"],rng=[int(x)%(1<<64) for x in audit["all_rng"][6]],
                chosen=card,color="curse",deck_position=pos,corrected=ids[new[-1][0]-1],map=True)


def main():
    known=read(HERE.parent/"COLORS.json")["results"]
    earlier={(r["seed"],r["chosen"]):r for r in known if r["color"]=="curse"}
    result=[]
    for _,seed,name,acts in examples()["curse"]:
        record=check(seed,name,acts)
        if record:
            result.append(record)
    expected=transformations(result)
    for r,truth in zip(result,expected,strict=True):
        assert r["corrected"]==truth
        r["original"]=truth
        r["previous"]=earlier[(r["seed"],r["chosen"])]["result"]
    fixed=[r for r in result if r["original"]!=r["previous"]]
    assert len(fixed)>=2
    report=dict(kernel=sha(BUILD),retail_reference=sha(HERE.parent/"COLORS.json"), physically_tested=len(result),
                reproduced_incorrect_draws_corrected=len(fixed),cases=result)
    write(HERE/"RESULT.json",report)
    print(len(result),len(fixed))


if __name__=="__main__":
    main()
