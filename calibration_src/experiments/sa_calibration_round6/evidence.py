"""Portable retail input records and first differences on the frozen interface."""
from collections import Counter
from experiments.sa_calibration_round3.fresh import replay as view
from experiments.sa_calibration_round5.receipts import compact
from .reference import HERE,R4,read,write,sha

def receipt_summary(path):
    full=read(path)
    report=compact(path)
    counts=Counter()
    for short,row in zip(report["records"],full["records"]):
        assert short["index"]==row["index"]
        change={}
        for phase in ("before","after"):
            if phase not in row:continue
            ev=row[phase]
            counts.update(ev["differences"].keys())
            short[phase]["fields_checked"]=list(ev["original"])
            if any(k in ev["original"] for k in ("rewards","offered_cards","fungus_hp_spores_strength")):
                change[phase]={s:{k:ev[s][k] for k in ("rewards","offered_cards","fungus_hp_spores_strength","player_vulnerable") if k in ev[s]} for s in ("original","model")}
        if change:short["inspected_values"]=change
    report["differences_counted_by_phase_and_field"]=dict(counts)
    return report

def original_records():
    journal=view.rows(HERE/"fresh/ACTIONS.jsonl")
    native=read(HERE/"fresh/RESULT.json")
    observed=read(HERE/"fresh/REPLAY.json")["records"]
    paired={r["index"]:r for r in observed}
    def project(snapshot):
        g=snapshot["raw"]["game_state"]
        c=g.get("combat_state") or {}
        ss=g["screen_state"] or {}
        return dict(hash=snapshot["raw_hash"],page=g["screen_type"],floor=g["floor"],hp=g["current_hp"],gold=g["gold"],
            deck=[view.card(x) for x in g["deck"]],relics=[[r["id"],r["counter"]] for r in g["relics"]],potions=[p["id"] for p in g["potions"]],
            turn=c.get("turn"),hand=[view.card(x) for x in c.get("hand",[])],enemies=[[m["id"],m["current_hp"],m["intent"]] for m in c.get("monsters",[])],
            rewards=[r for r in ss.get("rewards",[])],event=ss.get("event_id"),choices=g.get("choice_list",[]))
    return dict(seed=native["seed"],original_inputs=len(journal),source_sha256=sha(HERE/"fresh/ACTIONS.jsonl"),
        records=[dict(index=r["index"],command=r["command"],action=r["aid"],legal=r["legal"],
                      alignment=paired.get(r["index"],{}).get("status","original_only_after_model_stop"),
                      before=project(r["before"]),after=project(r["after"])) for r in journal])

def generate():
    for folder,name in (("replay","RESULT.json"),("fresh","REPLAY.json")):
        write(HERE/folder/"receipts.json",receipt_summary(HERE/folder/name))
    write(HERE/"fresh/original-inputs.json",original_records())
    r3=read(R4.parent/"sa_calibration_round3/fresh/RESULT.json")
    old=read(R4/"fresh/RESULT.json")
    dev=read(HERE/"replay/RESULT.json")
    new=read(HERE/"fresh/RESULT.json")
    write(HERE/"replay/history.json",dict(scope="Three distinct naturally generated retail seeds from rounds 3, 4 and 6. R4 seed reused for R5 and R6 development. Earlier edition checks stay edition-specific.",
        original_seeds=[dict(seed=r3["seed"]["display"],version="R3",status="holdout",original_inputs=r3["summary"]["original_raw_inputs"],original_floor=r3["summary"]["floor"],
                             reached_same_terminal=r3["summary"]["public_endpoint_equal"],first_content=r3["summary"]["first_content_snapshot_difference"]),
                        dict(seed=old["display"],version="R6",status="development; original R4 holdout",original_inputs=old["original_inputs"],original_floor=old["original_final"]["floor"],
                             reached_same_terminal=dev["stop"] is None,completed_inputs=dev["completed_inputs"],first_content=dev["first_content"],stop=dev["stop"]),
                        dict(seed=new["seed"],version="R6",status="new holdout",original_inputs=new["original_inputs"],original_floor=new["original_final"]["floor"],
                             reached_same_terminal=new["replay"]["stop"] is None,completed_inputs=new["replay"]["completed_inputs"],first_content=new["replay"]["first_content"],stop=new["replay"]["stop"])]))

if __name__ == "__main__":generate()
