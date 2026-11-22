"""Record alternative floor-ten rewards in isolated retail games restored from one real autosave."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from native_pilot import append, bind, libraries
from native_runtime import now, sha, write
from experiments.sa_calibration_round2.live import instance as restored
from experiments.sa_calibration_round3.fresh import instance
from experiments.sa_calibration_round4.fresh import physical
from experiments.sa_calibration_round5.chest.native import ROOT,NATIVE,R4,SEED,read,ledger,backup


BRANCHES = {
    "potion": ("potion","card","discard","flying knee","gold","leave"),
    "skip": ("card","skip","card","skip","leave"),
    "leave": ("leave",),
}
HERE = Path(__file__).resolve().parent
SAVE = NATIVE / "compact_native_r5_chest_key_001/chest_check/chest.autosave"

@contextmanager
def foreground():
    with (NATIVE/"compact_native_r6_reward_potion_001/r6_rewards/keyboard.lock").open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        yield


def stage(dest):
    proof = read(SAVE.with_name("chest_save.json"))
    assert sha(SAVE)==proof["sha256"] and proof["seed"]==SEED and proof["floor"]==9
    instance.ID,instance.DEST=dest.name,dest
    instance.stage()
    out=dest/"r6_rewards"
    out.mkdir()
    target=dest/"game/saves/THE_SILENT.autosave"
    assert not target.exists()
    shutil.copyfile(SAVE,target)
    assert sha(target)==proof["sha256"]
    write(out/"RESTORE_INPUT.json",dict(utc=now(),target_sha256=sha(dest/"target.json"),
          source=SAVE.relative_to(ROOT).as_posix(),saves={target.name:dict(sha256=proof["sha256"])}))


def resume(dest,t,s):
    out=dest/"r6_rewards"
    pid=read(dest/"process.json")["pid"]
    assert read(s/"session.json")["parent_pid"]==pid
    frame=t.read_current()
    if frame.raw["in_game"]:
        return
    driver=ROOT/"experiments/sa_calibration_round2/live/continue_menu"
    with foreground():
        subprocess.run([str(HERE/"raise"),str(pid)],check=True)
        for attempt in range(3):
            if t.read_current().raw["in_game"]:return
            click=subprocess.run([str(driver),str(pid)],capture_output=True,text=True)
            append(out/"continue.jsonl",dict(at=now(),code=click.returncode,output=click.stdout))
            click.check_returncode()
            for i in range(14):
                time.sleep(.45)
                if t.read_current().raw["in_game"]:
                    return
    raise RuntimeError("Continue did not reach the isolated game's save.")


def semantic(g):
    s=g.get("screen_state") or {}
    c=g.get("combat_state") or {}
    return dict(resources=[g[k] for k in ("floor","current_hp","max_hp","gold")],
        page=g["screen_type"],choices=g.get("choice_list") or [],
        deck=[(x["id"],x["upgrades"]) for x in g["deck"]],
        relics=[(x["id"],x["counter"]) for x in g["relics"]],potions=[x["id"] for x in g["potions"]],
        enemies=[(x["id"],x["current_hp"],x["block"]) for x in c.get("monsters",[])],
        hand=[(x["id"],x["upgrades"]) for x in c.get("hand",[])],energy=c.get("player",{}).get("energy"))


def route(dest,t,s,oracle,legal):
    out=dest/"r6_rewards"; data=out/"prefix.jsonl"
    physical.DEST,physical.HERE=dest,out
    shutil.copyfile(R4/"keys",out/"keys") if not (out/"keys").exists() else None
    (out/"keys").chmod(0o700)
    write(out/"GUI_LEASE.json",dict(expires_monotonic=time.monotonic()+600))
    original=ledger(R4/"ACTIONS.jsonl")
    for i in range(96+len(ledger(data)),129):
        record=original[i-1]; aid=record["aid"]
        frame=t.read_current()
        expected=semantic(record["before"]["raw"]["game_state"])
        actual=semantic(frame.raw["game_state"])
        if actual!=expected:
            frame=t.query_state(timeout=12).after
            actual=semantic(frame.raw["game_state"])
        assert actual==expected,(i,{k:(v,actual[k]) for k,v in expected.items() if v!=actual[k]})
        if frame.raw["game_state"]["screen_type"]=="HAND_SELECT":
            with foreground():
                subprocess.run([str(HERE/"raise"),str(read(dest/"process.json")["pid"])],check=True)
                options=physical.options(t,s,oracle,frame)
                physical.apply(t,s,oracle,frame,aid,options,"same floor-ten retail combat",data,i)
        else:
            assert aid in legal(frame.raw),(i,aid,legal(frame.raw))
            result=t.step(aid,expected_snapshot=frame,timeout=24);assert result.status=="observed_transition",result.as_dict()
            append(data,dict(index=i,aid=aid,at=now(),command=result.command,before=frame.as_dict(),after=result.after.as_dict()))
        if i==128:
            backup(dest,out,"after_fight")


def drive(dest,branch):
    out=dest/"r6_rewards";data=out/"choices.jsonl"
    Transport,_,legal,*_=libraries(dest)
    tr,s,oracle,_=bind(dest,Transport)
    resume(dest,tr,s)
    route(dest,tr,s,oracle,legal)
    for label in BRANCHES[branch][len(ledger(data)):]:
        frame=tr.read_current();g=frame.raw["game_state"]
        assert g["seed"]==SEED and g["floor"]==10 and g["class"]=="THE_SILENT" and g["ascension_level"]==20
        if not data.exists():assert g["choice_list"]==["gold","potion","card"] and g["gold"]==237
        aids=legal(frame.raw)
        controls={"discard":105,"leave":171,"skip":177}
        aid=controls[label] if label in controls else 110+g["choice_list"].index(label)
        assert aid in aids,(label,aid,aids,g.get("choice_list"))
        result=tr.step(aid,expected_snapshot=frame,timeout=22)
        assert result.status=="observed_transition",result.as_dict()
        append(data,dict(label=label,aid=aid,legal=aids,at=now(),command=result.command,request=result.request_id,
                         before=frame.as_dict(),after=result.after.as_dict()))
    final=tr.read_current()
    assert final.raw["game_state"]["screen_type"]=="MAP"
    write(out/"END.json",final.as_dict())


def close(dest):
    out=dest/"r6_rewards";end=read(out/"END.json")
    process=read(dest/"process.json")
    session=Path(read(dest/"bridge/active_session.json")["session_dir"])
    assert session.resolve().is_relative_to(dest.resolve()) and read(session/"session.json")["parent_pid"]==process["pid"]
    assert read(session/"current.json")["raw_hash"]==end["raw_hash"] and end["raw"]["game_state"]["screen_type"]=="MAP"
    write(out/"CLOSE.json",dict(at=now(),pid=process["pid"],end_sha256=sha(out/"END.json"),trace_sha256=sha(out/"choices.jsonl")))
    os.kill(process["pid"],signal.SIGTERM)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("op",choices=("stage","launch","drive","close"))
    parser.add_argument("branch",choices=BRANCHES)
    args=parser.parse_args();target=NATIVE/("compact_native_r6_reward_"+args.branch+"_001")
    if args.op=="stage":stage(target)
    elif args.op=="launch":
        restored.HERE=target/"r6_rewards";restored.DEST=target;restored.launch()
    elif args.op=="close":close(target)
    else:drive(target,args.branch)
