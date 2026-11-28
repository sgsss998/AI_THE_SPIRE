"""Keep R6's registered S/A questions and attach narrower, source-bound R7 answers."""
from pathlib import Path
from experiments.sa_calibration_round6.reference import read,write,sha

HERE=Path(__file__).resolve().parent
R7=HERE.parent
R6=R7.parent/"sa_calibration_round6"

# Each new observation describes a specific question in the old register.
# No whole category is promoted on the strength of one example.
ITEMS={
    "corpse":("S","One defeated Fungi Beast retained its two spores and five strength on the immediate native receipt; both cleared on refresh. The later settled model frame matches.","fungi/RESULT.json"),
    "fungus_opts":("A","In the old natural game the seven native buttons at input 143 are now offered. The recorded upgraded defensive card, end turn and potion execute.","fungi/RESULT.json"),
    "handreplace":("S/A","Original single-card selection rule checked in 45 physical-target cases. Two alternate cards were displayed on the archived move; the simulator replaces the selected card in one policy step.","hand/RESULT.json"),
    "inkcount":("S","Across 14 real tenth-card triggers the counter, resulting hand and three pile sizes matched. Twelve actual draws revealed the predicted top card; one trigger required a shuffle.","ink_bottle/RESULT.json"),
    "grid_other":("S/A","Fourteen concrete living-wall choices and the original deletion are verified. Three additional native samples cover transformation and upgrading. Multiple-card relic choices remain a separate scope.","grids/RETAIL.json"),
    "map23":("S/A","Native Act III entrance and map layout compared; all four map entries tested on the simulator. One continuous native run from the start to this point is still missing.","deep/RESULT.json"),
    "act4":("S/A","Native Act IV entrance compared. Subsequent campfire, shop, elites and Heart entrances tested as directed simulator branches.","deep/RESULT.json"),
    "boss":("S","The first-act Hexaghost's final attack matches the old real game on death. This sample does not cover all three boss battles.","terminal_intent/RESULT.json"),
    "snakedrop":("A","Seed 54072726 offered discard on the original leave page. The updated adapter discards the explosive potion once and keeps the event settled. The player actually chose Leave.","snake_belt/RESULT.json"),
}


def run():
    old=read(R6/"coverage/CURRENT.json")
    rows=old["branches"]
    assert len(rows)==len({x["id"] for x in rows})==43
    assert set(ITEMS)<={r["id"] for r in rows}
    items=[]
    for row in rows:
        update=None
        if row["id"] in ITEMS:
            side,claim,p=ITEMS[row["id"]]
            update=dict(side=side,measured_scope=claim,evidence=p,sha256=sha(R7/p))
        items.append(dict(id=row["id"],scene=row["场景"],question=row["分支"],r6_S=row["S"],r6_A=row["A"],
            earlier_sample=row["核对内容与未核范围"],r7=update))
    new=[]
    for question,side,p in (
        ("Two thieves carrying different amounts","S","death_family/thief_rewards/RESULT.json"),
        ("Acid/Spike Slime split: which child receives a targeted attack","S/A","combat_edges/RESULT.json"),
        ("Shop room potion disposal before opening or after closing the merchant","A","shop_door/RESULT.json"),
        ("Curse transformations whose result depended on the wrong excluded index","rules","grids/curse/RESULT.json"),
        ("Death from the event's HP cost versus a surviving selection or revival","S/A","event_death/RESULT.json"),
        ("Return to campfire before smithing and cancel the card preview","A","smith/RESULT.json")):
        new.append(dict(question=question,side=side,evidence=p,sha256=sha(R7/p)))
    write(HERE/"REGISTER.json",dict(reference_sha256=sha(R6/"coverage/CURRENT.json"),registered_questions=43,
        prior_state=old["state"],prior_action=old["action"],updated_questions=len(ITEMS),game_wide_percentage=None,
        previous=items,new_questions=new,note="A question without a new observation retains the historical evidence only. Read each measured scope."))
    print(len(items),"registered questions;",len(ITEMS),"evidence updates;",len(new),"additional tested examples")


if __name__=="__main__":
    run()
