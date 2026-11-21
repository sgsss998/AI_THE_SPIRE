"""Locate the first different choice in each game whose end category changed."""
from experiments.sa_calibration_round4 import release as prior
from . import release
from .reference import HERE,R4,read,source,write


def at(version,seed,actions):
    game = version.make_engine()
    model = version.make_session(game)
    frame = model.reset(seed,ascension=20,final_act=True)
    menus=[]
    for aid in actions:
        menus.append((frame.page,[i for i,bit in enumerate(frame.supported_actions) if bit]))
        assert frame.supported_actions[aid]
        frame = model.step(aid,frame_id=frame.frame_id,action_version=frame.action_version)
    menus.append((frame.page,[i for i,bit in enumerate(frame.supported_actions) if bit]))
    return frame,menus


def compare():
    current = read(HERE/"regression/RESULT.json")
    old_runs = read(source(R4/"regression", read(R4/"regression/RESULT.json")))["runs"]
    old = {r["seed"]:r["episode"] for r in old_runs}
    changes=[]
    for row in current["records"]:
        if row["reason"] == row["previous"]:
            continue
        seed=row["seed"]
        pos=row["first_different_action"]-1
        prev=old[seed]
        prefix=prev["actions"][:pos]
        assert prefix == row["actions"][:pos]
        simulations=[at(ver,seed,prefix) for ver in (prior,release)]
        frames=[r[0] for r in simulations]
        first_menu=next((dict(decision=i,r4=a,r5=b) for i,(a,b) in enumerate(
            zip(simulations[0][1],simulations[1][1]),1) if a!=b),None)
        aids=[f["actions"][pos] if len(f["actions"])>pos else None for f in (prev,row)]
        sides=[]
        for f,a,ep in zip(frames,aids,(prev,row)):
            opts=[i for i,bit in enumerate(f.supported_actions) if bit]
            assert a in opts or a is None
            sides.append(dict(page=f.page,resources=f.state.vector[:6],offered=opts,chosen=a,
                              selected_row=f.state.vector[322+6*(a-110):328+6*(a-110)] if a is not None and 110<=a<170 else None,
                              endpoint=ep["reason"],endpoint_floor=ep["engine_floor"],endpoint_page=ep["page"]))
        changes.append(dict(seed=seed,decision=pos+1,first_different_menu=first_menu,r4=sides[0],r5=sides[1]))
    return dict(signature=current["signature"],changes=changes)


if __name__=="__main__":
    write(HERE/"regression/CHANGES.json",compare())
