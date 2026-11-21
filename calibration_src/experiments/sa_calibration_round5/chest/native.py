"""Revisit the R4 game in a clean retail process, record alternative chest decisions."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import signal
import time

from native_pilot import append, bind, libraries
from native_runtime import now, sha, write
from experiments.sa_calibration_round3.fresh import instance
from experiments.sa_calibration_round4.fresh import physical

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
R4 = ROOT/"experiments/sa_calibration_round4/fresh"
NATIVE = ROOT/"native_runtime"
SEED = -8683615973261774583

def read(path):
    return json.loads(path.read_bytes())

def ledger(path):
    return [json.loads(row) for row in path.read_bytes().splitlines()] if path.exists() else []

def compare(g, expected):
    fields = ("floor","screen_type","current_hp","max_hp","gold")
    return {f:(g.get(f),expected.get(f)) for f in fields if g.get(f)!=expected.get(f)}

def backup(dest, out, label):
    p=dest/"game/saves/THE_SILENT.autosave"
    data=p.read_bytes()
    buf=base64.b64decode(data); decoded=json.loads(bytes(c^b"key"[i%3] for i,c in enumerate(buf)))
    assert decoded["seed"]==SEED
    copy=out/(label+".autosave")
    if not copy.exists():
        copy.write_bytes(data)
        write(out/(label+"_save.json"),dict(sha256=sha(copy),seed=decoded["seed"],floor=decoded.get("floor_num"),hp=decoded.get("current_health"),gold=decoded.get("gold")))

def drive(dest,branch):
    Transport,_,legal,_,*_=libraries(dest)
    t,s,oracle,_=bind(dest,Transport)
    out=dest/"chest_check";out.mkdir(exist_ok=True)
    physical.DEST=dest; physical.HERE=out
    keybin=out/"keys"
    if not keybin.exists():shutil.copy2(R4/"keys", keybin)
    write(out/"GUI_LEASE.json",dict(expires_monotonic=time.monotonic()+900))
    orig=ledger(R4/"ACTIONS.jsonl"); data=out/"actions.jsonl"
    b=t.read_current()
    if not b.raw.get("in_game"):
        assert not (out/"start.json").exists()
        start=t.start("THE_SILENT",20,seed="2W47ZBJ8TBFMD",timeout=40)
        write(out/"start.json",start.as_dict());assert start.status=="observed_start"
    for i in range(len(ledger(data))+1,100):
        b=t.read_current();g=b.raw["game_state"]; r=orig[i-1];expected=r["before"]["raw"]["game_state"]
        assert g["seed"]==SEED and g["ascension_level"]==20 and g["class"]=="THE_SILENT"
        differ=compare(g,expected)
        if differ and i<=98:
            time.sleep(.75);q=t.query_state(timeout=10);b=q.after;g=b.raw["game_state"];differ=compare(g,expected)
        if differ and i<=98:raise RuntimeError((i,differ))
        if i in (51,96):backup(dest,out,"shop" if i==51 else "chest")
        if i in (96,97,98,99):write(out/f"before_{i}.json",b.as_dict())
        if i==99 and branch=="leave":break
        aid=r["aid"] if i!=98 else {"ink":110,"key":111,"leave":171}[branch]
        if g["screen_type"]=="HAND_SELECT":
            options=physical.options(t,s,oracle,b)
            physical.apply(t,s,oracle,b,aid,options,"retail R4 replay",data,i)
            extras = {e["input"]:e["actions"][0] for e in read(R4/"RESULT.json")["reconciled_official"]["extra_card_actions"]}
            if i in extras:
                target = r["after"]["raw"]["game_state"]["combat_state"]
                b=t.read_current(); current=b.raw["game_state"]["combat_state"]
                if current["player"]["energy"] == target["player"]["energy"]+1:
                    event = extras[i]
                    proof = event["binding"]
                    assert current["hand"][proof["hand_index"]]["id"]==proof["card"][0]
                    assert current["monsters"][proof["target_row"]]["id"]==proof["target"]
                    receipt=t.step(event["model_action"],expected_snapshot=b,timeout=20)
                    assert receipt.status=="observed_transition"
                    append(out/"ADDITIONAL.jsonl",dict(index=i,aid=event["model_action"],before=b.as_dict(),receipt=receipt.as_dict()))
                    current=receipt.after.raw["game_state"]["combat_state"]
                assert current["player"]["energy"]==target["player"]["energy"]
                assert [(m["id"],m["current_hp"],m["block"]) for m in current["monsters"]]==[(m["id"],m["current_hp"],m["block"]) for m in target["monsters"]]
        else:
            assert aid in legal(b.raw),(i,aid,legal(b.raw))
            receipt=t.step(aid,expected_snapshot=b,timeout=24)
            assert receipt.status=="observed_transition",receipt.as_dict()
            append(data,dict(index=i,aid=aid,at=now(),command=receipt.command,before=b.as_dict(),after=receipt.after.as_dict()))
        if i%15==0 or i>=96:print("step",i,flush=True)
    b=t.read_current(); state=b.raw["game_state"]
    assert state["screen_type"]=="MAP"
    write(out/"END.json",b.as_dict())
    print("observed map",branch,state["gold"],state["relics"],flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("operation",choices=["stage","drive","close"]);p.add_argument("branch",choices=["ink","key","leave"]);args=p.parse_args()
    name="compact_native_r5_chest_"+args.branch+"_001";dest=NATIVE/name
    if args.operation=="stage":
        instance.ID=name;instance.DEST=dest;instance.stage()
    elif args.operation=="drive":drive(dest,args.branch)
    else:
        assert (dest/"chest_check/END.json").exists()
        pid=read(dest/"process.json")["pid"]; session=Path(read(dest/"bridge/active_session.json")["session_dir"])
        assert read(session/"session.json")["parent_pid"]==pid
        os.kill(pid,signal.SIGTERM)
