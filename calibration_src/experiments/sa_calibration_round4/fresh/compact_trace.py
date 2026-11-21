"""Publish an ordered retail journal with explicitly separated replay interpretations."""
import json
import hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_bytes())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def retail(frame):
    g=frame["raw"]["game_state"];combat=g.get("combat_state") or {}
    return dict(hp=g["current_hp"],max_hp=g["max_hp"],gold=g["gold"],floor=g["floor"],act=g["act"],page=g["screen_type"],
                deck=[[c["id"],c["upgrades"]] for c in g["deck"]],relics=[[x["id"],x["counter"]] for x in g["relics"]],
                potions=[x["id"] for x in g["potions"]],hand=[[x["id"],x["upgrades"],x.get("cost")] for x in combat.get("hand",[])],
                turn=combat.get("turn"),energy=combat.get("player",{}).get("energy"),
                enemies=[[m["id"],m["current_hp"],m["max_hp"],m.get("intent")] for m in combat.get("monsters",[])],
                reward_types=[item["reward_type"] for item in g.get("screen_state",{}).get("rewards",[])])
def comparison(entry):
    item={key:entry[key] for key in ("mapped_aid","status","model_layer","physical_binding","action_set_comparison") if key in entry}
    for phase in ("before","after"):
        if phase not in entry:continue
        pair=entry[phase]
        item[phase]=dict(differences=pair["differences"],representation=pair.get("representation_differences"), model_resources=pair["model"].get("resources"))
    for key in entry:
        if "invocation" in key or "compound" in key or key in {"native_effects","kernel_fallback","missing_public_action","execution_error"}:item[key]=entry[key]
    return item
def main():
    idx=read(HERE/"RESULT.json")
    runs={}
    # Publish only verified or explicitly historical interpretations of the same frozen input.
    selected=[("official_semantic",idx["reconciled_official"]),("diagnostic",idx["diagnostic"]),
              ("first_literal",idx["official_replay"])]
    for name,ref in selected:
        if not ref:continue
        p=HERE/ref["path"]
        assert digest(p)==ref["sha256"]
        d=read(p)
        assert d["signature"]==idx["model_interface"]
        runs[name]=(d,{r["index"]:comparison(r) for r in d["trace"]},ref["sha256"])
    raw=[json.loads(row) for row in (HERE/"ACTIONS.jsonl").read_bytes().splitlines()]
    inputs=[]
    for r in raw:
        inputs.append(dict(index=r["index"],command=r["command"],before_sha256=r["before"]["raw_hash"],after_sha256=r["after"]["raw_hash"],
                           original=retail(r["after"]),comparisons={name:rows[r["index"]] for name,(_,rows,_) in runs.items() if r["index"] in rows}))
    assert [i["index"] for i in inputs]==list(range(1,len(inputs)+1))
    result=dict(original_journal_sha256=digest(HERE/"ACTIONS.jsonl"),original_terminal_sha256=digest(HERE/"TERMINAL.json"),original_seed=str(raw[0]["before"]["raw"]["game_state"]["seed"]),
                evidence_modes={name:dict(source_sha256=sha,inputs_replayed=d["replayed"],stop=d["stopped_at"],diagnostic_used=d["used_kernel"]) for name,(d,_,sha) in runs.items()},
                inputs=inputs)
    (HERE/"PUBLIC_TRACE.json").write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n")
if __name__=="__main__":main()
