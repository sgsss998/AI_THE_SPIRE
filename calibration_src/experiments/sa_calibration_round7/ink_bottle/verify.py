"""Check every tenth-card trigger in a natural retail game, including a trigger that must shuffle."""
from pathlib import Path
import json

from experiments.ordinary_reward_hooks193.audit import JAR,RETAIL,dump
from experiments.sa_calibration_round5.replay import original_inputs
from experiments.sa_calibration_round5.reference import write,sha
from .. import transactions
from ..shop.verify import view
from ..wall.verify import step

HERE=Path(__file__).resolve().parent


def counter(relics):
    return next((r["counter"] for r in relics if r["id"]=="InkBottle"),None)


def run():
    journal=original_inputs()
    sig=transactions.interface_signature().metadata()
    path=HERE.parent/"retail"/sig["state_sha256"]/"r4-natural.json"
    trail=json.loads(path.read_bytes())
    engine=transactions.make_engine()
    session=transactions.make_session(engine)
    frame=session.reset(trail["seed"])
    checks=[]
    for row,route in zip(journal,trail["rows"],strict=True):
        before=frame
        if route["status"]=="executed":
            frame=step(session,before,route["public_action"])
            for _,a in route.get("incidental_actions",[]):
                frame=step(session,frame,a)
        raw=[row[k]["raw"]["game_state"] for k in ("before","after")]
        if [counter(g["relics"]) for g in raw]!=[9,0]:
            continue
        assert not route.get("incidental_actions") and row["command"].startswith("play ")
        native=[view.NATIVE[row[k]["session"],row[k]["sequence"]] for k in ("before","after")]
        assert [counter(n["relics"]) for n in native]==[9,0]
        for f,g,n,wanted in zip((before,frame),raw,native,(9,0),strict=True):
            comp=g["combat_state"]
            real_hand=comp["hand"]
            assert [(x["id"],x["uuid"]) for x in real_hand]==[(x["id"],x["uuid"]) for x in n["hand"]]
            model=view.model(f,engine)
            assert model["hand"]==[view.card(x) for x in real_hand] and ["inkbottle",wanted] in model["relics"]
            assert model["pile_counts"]==[len(comp[k]) for k in ("draw_pile","discard_pile","exhaust_pile")]
        a,b=(g["combat_state"] for g in raw)
        old_ids={x["uuid"] for x in a["hand"]}
        newly_held=[x for x in b["hand"] if x["uuid"] not in old_ids]
        drawn=[x for x in newly_held if any(d["uuid"]==x["uuid"] for d in a["draw_pile"])]
        exact=None
        if len(drawn)==1 and len(a["draw_pile"])==len(b["draw_pile"])+1:
            face=before.state.vector[3118:3121]
            assert face[2]==2 and [engine._source._backend.CARD_IDS[int(face[0])-1],int(face[1])]==view.card(drawn[0])
            exact=dict(uuid=drawn[0]["uuid"],card=drawn[0]["id"],upgraded=drawn[0]["upgrades"])
        shuffled=not a["draw_pile"] and bool(b["draw_pile"])
        if shuffled:
            assert before.state.vector[3118:3121]==(0,0,1) and any(
                x["uuid"] in {old["uuid"] for old in a["discard_pile"]} for x in newly_held)
        checks.append(dict(index=row["index"],floor=raw[0]["floor"],real_before=row["before"]["raw_hash"],
            real_after=row["after"]["raw_hash"],original_counter=[9,0],model_counter=[9,0],
            prior_draw=len(a["draw_pile"]),next_draw=len(b["draw_pile"]),new_hand_cards=[view.card(c) for c in newly_held],
            identified_preexisting_top=exact,reshuffle=shuffled))
    bytecode=dump(("relics.InkBottle#onUseCard",))["relics.InkBottle"]
    lines=next(v for k,v in bytecode.items() if k.startswith("onUseCard"))
    assert sha(JAR)==RETAIL and any("DrawCardAction" in line for line in lines)
    assert len(checks)==14 and any(c["reshuffle"] for c in checks)
    result=dict(seed=trail["seed"],original_steps=len(journal),verified_tenth_card_triggers=len(checks),archive_sha256=trail["journal_sha256"],
        top_predictions=sum(c["identified_preexisting_top"] is not None for c in checks),reshuffle_triggers=sum(c["reshuffle"] for c in checks),
        native_rule=RETAIL,cases=checks)
    write(HERE/"RESULT.json",result)
    print(len(checks),"original triggers;",result["top_predictions"],"top predictions;",result["reshuffle_triggers"],"reshuffle")


if __name__=="__main__":
    run()
