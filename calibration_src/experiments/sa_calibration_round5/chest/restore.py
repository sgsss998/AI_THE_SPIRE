"""Fork the exact experimental original save; use the game's normal Continue button."""
import argparse
from pathlib import Path
import shutil
import subprocess
import time

from native_pilot import append, bind, libraries
from native_runtime import now, sha, write, verify
from experiments.sa_calibration_round2.live import instance as previous
from .native import HERE, ROOT, NATIVE, SEED, read, backup

def target(branch):
    return NATIVE/("compact_native_r5_chest_"+branch+("_001" if branch=="leave" else "_002"))

def stage(branch):
    dest=target(branch);cfg=verify(dest)
    src=NATIVE/"compact_native_r5_chest_key_001/chest_check/chest.autosave"
    proof=read(src.with_name("chest_save.json"))
    assert sha(src)==proof["sha256"] and proof["seed"]==SEED and proof["floor"]==9
    assert not cfg["fixture_mod_enabled"] and not (dest/"process.json").exists()
    out=dest/"chest_check";out.mkdir(exist_ok=True)
    dst=dest/"game/saves/THE_SILENT.autosave"
    assert not dst.exists()
    shutil.copyfile(src,dst)
    assert sha(dst)==sha(src)
    write(out/"RESTORE_INPUT.json",dict(target_sha256=sha(dest/"target.json"),source=str(src.relative_to(ROOT)),
        saves={dst.name:dict(sha256=sha(dst))},stage_utc=now()))

def drive(branch):
    dest=target(branch);out=dest/"chest_check"
    Transport,_,legal,_,*_=libraries(dest)
    t,s,oracle,_=bind(dest,Transport)
    b=t.read_current()
    if not b.raw["in_game"]:
        assert not (out/"CONTINUE.json").exists()
        pid=read(dest/"process.json")["pid"]
        assert read(s/"session.json")["parent_pid"]==pid
        proc=subprocess.run([str(ROOT/"experiments/sa_calibration_round2/live/continue_menu"),str(pid)],text=True,capture_output=True)
        write(out/"CONTINUE.json",dict(at=now(),pid=pid,code=proc.returncode,output=proc.stdout))
        proc.check_returncode()
        for _ in range(30):
            time.sleep(.45)
            b=t.read_current()
            if b.raw["in_game"]:break
    assert b.raw["game_state"]["screen_type"]=="CHEST",b.raw
    actions=[(96,110),(97,110),(98,{"ink":110,"leave":171,"key":111}[branch])]
    if branch!="leave":actions.append((99,171))
    for i,aid in actions:
        b=t.read_current();g=b.raw["game_state"]
        assert g["seed"]==SEED and g["floor"]==9 and g["class"]=="THE_SILENT" and g["ascension_level"]==20 and g["current_hp"]==56
        if i==98:assert g["gold"]==237 and g["screen_state"]["rewards"][0]["relic"]["id"]=="InkBottle"
        write(out/f"before_{i}.json",b.as_dict())
        assert aid in legal(b.raw)
        rec=t.step(aid,expected_snapshot=b,timeout=22);assert rec.status=="observed_transition"
        append(out/"actions.jsonl",dict(index=i,aid=aid,at=now(),before=b.as_dict(),after=rec.after.as_dict(),command=rec.command))
        if i==98 and branch=="key":
            first=time.monotonic()
            for elapsed in (.10,.35,.75,1.25,2.0):
                time.sleep(max(0,elapsed-(time.monotonic()-first)))
                query=t.query_state(timeout=12)
                assert query.status=="query_observation"
                append(out/"queries.jsonl",dict(after_action=98,seconds_after_receipt=time.monotonic()-first,
                    snapshot=query.after.as_dict()))
    b=t.read_current();assert b.raw["game_state"]["screen_type"]=="MAP"
    write(out/"END.json",b.as_dict())

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("op",choices=["stage","launch","drive"]);p.add_argument("branch",choices=["ink","leave","key"]);a=p.parse_args()
    if a.op=="stage":stage(a.branch)
    elif a.op=="drive":drive(a.branch)
    else:
        previous.HERE=target(a.branch)/"chest_check";previous.DEST=target(a.branch);previous.launch()
