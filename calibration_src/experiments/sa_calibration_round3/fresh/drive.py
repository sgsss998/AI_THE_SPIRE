"""Drive the user's existing retail run one current decision at a time, through its own terminal."""
import json
import os
import sys
import time
import traceback

from native_pilot import append,bind
from native_runtime import now,sha,write
from .instance import HERE,DEST,ROOT
from .policy import choose
SEED=None
sys.path.insert(0,str(DEST/"transport_snapshot"))
from src.core.live_transport import LiveTransport
from src.core.action import Action
from src.core.action_rules import legal_action_ids


def read(p):return json.loads(p.read_bytes())
def records(p):return [json.loads(s) for s in p.read_bytes().splitlines()] if p.exists() else []

def summary(raw):
    g=raw["game_state"];c=g.get("combat_state") or {}
    return dict(seed=g["seed"],floor=g["floor"],act=g["act"],screen=g["screen_type"],hp=g["current_hp"],max_hp=g["max_hp"],gold=g["gold"],
                cards=[(c["id"],c["upgrades"]) for c in g["deck"]],relics=[(r["id"],r["counter"]) for r in g["relics"]],
                belt=[p["id"] for p in g["potions"]],monsters=[(m["id"],m["current_hp"]) for m in c.get("monsters",[])],
                turn=c.get("turn"))

def action(t,b,aid,legal,reason,path,index):
    assert aid in legal and summary(b.raw)["seed"]==SEED
    r=t.step(aid,expected_snapshot=b,timeout=25)
    if r.status!="observed_transition" or r.after is None:
        append(HERE/"INTERRUPTIONS.jsonl",dict(at=now(),index=index,before=b.as_dict(),reason=reason,receipt=r.as_dict()))
        raise RuntimeError((r.status,r.reason))
    row=dict(index=index,aid=aid,command=r.command,request_id=r.request_id,status=r.status,at=now(),reason=reason,legal=legal,
             before=b.as_dict(),after=r.after.as_dict())
    append(path,row)
    return r.after

def query(t,b,note):
    q=t.query_state(timeout=15)
    append(HERE/"QUERIES.jsonl",dict(at=now(),note=note,before=b.as_dict(),result=q.as_dict()))
    if q.status!="query_observation" or not q.after:raise RuntimeError((q.status,q.reason))
    return q.after

def run():
    t,session,oracle,_=bind(DEST,LiveTransport)
    stop=HERE/"TERMINAL.json"
    assert not stop.exists()
    global SEED
    b=t.read_current()
    if not (HERE/"START_OUTPUT.json").exists():
        assert not b.raw["in_game"] and "start" in b.raw["available_commands"]
        write(HERE/"START_INPUT.json",dict(utc=now(),player_class="THE_SILENT",ascension=20,seed=None,pre_game=b.as_dict(),policy_sha256=sha(HERE/"policy.py"),seed_inventory_sha256=sha(HERE/"SEEDS_BEFORE.json")))
        write(HERE/"RESERVATION.json",dict(round="R3",authorized_natural_starts=1,instance=DEST.name,reserved_at=now(),previous_ledger_sha256=sha(ROOT/"reports/NATIVE_BUDGET.json"),authorization="User approved one new R3 natural random game; parent confirmed separate round reservation",uncertain_start_consumes_reservation=True))
        started=t.start("THE_SILENT",20,timeout=45)
        write(HERE/"START_OUTPUT.json",started.as_dict())
        assert started.status=="observed_start" and started.command=="start THE_SILENT 20"
        b=started.after
    start=read(HERE/"START_OUTPUT.json")
    SEED=start["after"]["raw"]["game_state"]["seed"]
    inventory=read(HERE/"SEEDS_BEFORE.json")
    assert SEED%(1<<64) not in inventory["seeds_u64"]
    write(HERE/"SEED.json",dict(signed=SEED,unsigned=SEED%(1<<64),seed_argument=None,in_previous_inventory=False,inventory_sha256=sha(HERE/"SEEDS_BEFORE.json"),before_simulator=True))
    assert b.raw["in_game"]
    journal=HERE/"ACTIONS.jsonl"
    existing=records(journal)
    previous=existing[-1] if existing else None
    recent=[(row["before"]["decision_hash"],row["aid"]) for row in existing[-6:]]
    idx=1+len(existing)
    floor=-1
    while True:
        b=t.read_current()
        if not b.raw.get("game_state"):
            raise RuntimeError(("Unexpected exit before game-over witness",idx))
        g=b.raw["game_state"]
        auto=DEST/"game/saves/THE_SILENT.autosave"
        if auto.exists() and not (HERE/"AUTOSAVE_SEED.json").exists():
            import base64
            x=base64.b64decode(auto.read_bytes());z=json.loads(bytes(v^b"key"[i%3] for i,v in enumerate(x)))
            assert z["seed"]==SEED and z["seed_set"] is False
            write(HERE/"AUTOSAVE_SEED.json",dict(at=now(),seed=z["seed"],seed_set=z["seed_set"],metric_seed_played=z["metric_seed_played"],sha256=sha(auto)))
        assert (g["seed"],g["class"],g["ascension_level"])==(SEED,"THE_SILENT",20)
        if g["screen_type"]=="GAME_OVER":
            try: native_seq=b.raw["capture_alignment"]["native_record_sequence"]
            except KeyError: native_seq=None
            write(stop,dict(at=now(),index=idx-1,summary=summary(b.raw),terminal=g["screen_state"],snapshot=b.as_dict(),
                            receipt=read(session/"status.json"),last_native_record=native_seq,trace_sha256=sha(journal)))
            print("terminal",idx-1,g["floor"],g["screen_state"],flush=True)
            return
        if g["current_hp"]<=0 or g["screen_type"]=="NONE" and g.get("combat_state") and not any(m["current_hp"]>0 and not m["is_gone"] for m in g["combat_state"]["monsters"]):
            time.sleep(.7);b=query(t,b,"wait for victory/death UI after final damage");g=b.raw["game_state"]
            if g["screen_type"]=="GAME_OVER" or g["current_hp"]<=0:continue
        if floor!=g["floor"]:
            print("retail",idx,g["floor"],g["screen_type"],g["current_hp"],g["max_hp"],g["gold"],flush=True);floor=g["floor"]
        hand=g["screen_type"]=="HAND_SELECT"
        if hand:
            from .physical import options,apply
            legal=list(options(t,session,oracle,b))
        else:
            legal=legal_action_ids(b.raw)
        if not legal:
            b=query(t,b,"read current controls after UI settlement");g=b.raw["game_state"];legal=legal_action_ids(b.raw)
            if not legal:raise RuntimeError(("no current native action",g["screen_type"],g.get("choice_list"),b.raw["available_commands"]))
        declined=previous and previous["before"]["raw"]["game_state"]["screen_type"]=="CARD_REWARD" and previous["aid"]==177
        left_shop=previous and previous["before"]["raw"]["game_state"]["screen_type"]=="SHOP_SCREEN" and previous["aid"]==178
        if left_shop and g["screen_type"]=="SHOP_ROOM" and 171 in legal:
            aid,reason=171,"proceed after leaving the already visited shop"
        elif declined and g["screen_type"]=="COMBAT_REWARD" and 171 in legal:
            items=g["screen_state"].get("rewards",[])
            alternatives=[110+j for j,r in enumerate(items) if r["reward_type"] not in ("CARD","SAPPHIRE_KEY") and 110+j in legal]
            aid=alternatives[0] if alternatives else 171
            reason="collect another reward or leave the card offer already declined"
        else:
            aid,reason=choose(g,Action,legal)
        key=(b.decision_hash,aid)
        if key in recent and g["screen_type"] not in ("NONE","HAND_SELECT") and not (g["screen_type"]=="SHOP_SCREEN" and aid==178):
            raise RuntimeError(("repeat prevented before sending",idx,key,g["screen_type"],g.get("choice_list")))
        recent=(recent+[key])[-6:]
        previous={"aid":aid,"before":b.as_dict()}
        if hand:
            apply(t,session,oracle,b,aid,legal,reason,journal,idx)
        else:
            action(t,b,aid,legal,reason,journal,idx)
        idx+=1

if __name__=="__main__":
    try:run()
    except Exception as e:
        append(HERE/"DRIVER_STOPS.jsonl",dict(at=now(),err=repr(e),trace=traceback.format_exc()))
        raise
