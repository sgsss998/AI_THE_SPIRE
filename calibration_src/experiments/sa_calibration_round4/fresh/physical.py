"""Use the vanilla hand keyboard shortcut only for an independently captured physical choice."""
from pathlib import Path
import json
import subprocess,time,uuid

from experiments.ordinary_reward_live193.hand_gui import actual
from native_runtime import write,now
from native_pilot import append
from .instance import HERE,DEST

def options(t,session,log,b):
    n=actual(DEST,t,session,log,b)
    capability=n["independent_legal_actions"]
    g=b.raw["game_state"]
    assert g["screen_type"]=="HAND_SELECT"
    rows=capability["semantic_actions"]
    if not capability["boundary"]["admissible"]:raise ValueError(("hand boundary not available",capability))
    choices={}
    for a in rows:
        if a["type"]=="choose" and a.get("object_uuid"):
            j=a["choice_index"]
            assert g["screen_state"]["hand"][j]["uuid"]==a["object_uuid"]
            choices[110+j]=a
        if a["type"]=="confirm":
            choices[172]=a
    return choices

def apply(t,session,log,b,aid,legal,reason,path,index):
    lease=json.loads((HERE/"GUI_LEASE.json").read_text()) if (HERE/"GUI_LEASE.json").exists() else {}
    if lease.get("expires_monotonic",0)<time.monotonic():raise RuntimeError("Awaiting coordinated foreground keyboard lease; no input sent")
    selected=b.raw["game_state"]["screen_state"]["selected"]
    proof=options(t,session,log,b)[aid]
    pref=json.loads((DEST/"game/preferences/STSInputSettings").read_bytes())
    if aid==172:
        assert pref["CONFIRM"]=="66" and selected
        uid=None;key=36
    else:
        j=aid-110;uid=proof["object_uuid"]
        assert pref[f"CARD_{j+1}"]==str(8+j)
        key=(18,19,20,21,23,22,26,28,25,29)[j]
    pid=json.loads((DEST/"process.json").read_bytes())["pid"]
    assert json.loads((session/"session.json").read_bytes())["parent_pid"]==pid and not (DEST/"process_exit.json").exists()
    identifier=str(uuid.uuid4())
    rec=dict(at=now(),request_id=identifier,index=index,before=b.sequence,aid=aid,uuid=uid,proof=proof,mac_key=key,pid=pid)
    append(HERE/"PHYSICAL.jsonl",dict(**rec,event="physical_dispatch_intent"))
    res=subprocess.run([str(HERE/"keys"),str(pid),str(key)],capture_output=True,text=True)
    append(HERE/"PHYSICAL.jsonl",dict(**rec,event="physical_os_return",code=res.returncode,output=res.stdout))
    res.check_returncode()
    time.sleep(.5)
    after=t.read_current()
    if after.sequence==b.sequence:
        r=t.query_state(timeout=8)
        assert r.status=="query_observation" and r.after
        after=r.after
        append(HERE/"QUERIES.jsonl",dict(at=now(),note="physical hand input witness",before=b.as_dict(),result=r.as_dict()))
    g=after.raw["game_state"]
    if aid==172:
        assert g["screen_type"]!="HAND_SELECT" and all(c["uuid"] in {q["uuid"] for q in g.get("combat_state",{}).get("discard_pile",[])} for c in selected)
    else:
        assert g["screen_type"]=="HAND_SELECT" and uid in [c["uuid"] for c in g["screen_state"]["selected"]]
    append(path,dict(index=index,aid=aid,command=("confirm" if aid==172 else "choose "+str(aid-110)),request_id=identifier,
           wire_type="physical_hand_key",status="observed_transition",at=now(),reason=reason,legal=list(legal),before=b.as_dict(),after=after.as_dict()))
