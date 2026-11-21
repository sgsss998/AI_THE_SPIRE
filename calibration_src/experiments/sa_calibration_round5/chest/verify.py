"""Compare retail branch captures with the full R5 interface, including refusal of a used frame."""
from pathlib import Path
from hashlib import sha256
import json

from native_pilot import libraries
from .native import NATIVE, ROOT, HERE, SEED, read, ledger
from .. import release
from ..reference import sha, write
from ..shop.prefix import prefix, advance
from experiments.sa_calibration_round3.fresh import replay as views
from experiments.sa_calibration_round4.fresh.instance import DEST
from silent_env.runtime import StaleFrameError

def capture(dest, frame):
    from silent_env.native_compare import verify_capture_record
    tag=frame["raw"]["capture_alignment"]
    oracle=dest/"native_oracle"/tag["native_session"]/"native_oracle.jsonl"
    native,=[r for r in ledger(oracle) if r.get("data",{}).get("capture_id")==tag["capture_id"]]
    cap=verify_capture_record(native,bridge_row=frame,scope=dict(native_session=tag["native_session"],
         bridge_session=frame["session"],bridge_sequence=frame["sequence"],native_after_sequence=0,
         native_through_sequence=tag["native_record_sequence"]))
    assert cap.evidence["exact_capture_binding"] and cap.evidence["bridge_raw_sha256"]==frame["raw_hash"]
    views.NATIVE[frame["session"],frame["sequence"]]=cap.payload
    return views.original(frame)

def subset(model,original, delayed_key=False):
    fields=("resources","keys","deck","relics","potions","page")+tuple(k for k in ("rewards","map_xy","next_x") if k in original)
    for k in fields:
        if delayed_key and k=="keys":
            assert model[k]==[False,False,True] and original[k]==[False,False,False]
        else:
            assert model.get(k)==original[k],(k,model.get(k),original[k])
    return {k:original[k] for k in fields}

def stale(session,frame,aid):
    try:advance(session,frame,aid)
    except StaleFrameError:return True
    raise AssertionError("used chest action token was accepted")

def check():
    libraries(DEST)
    original=read(ROOT/"experiments/sa_calibration_round4/fresh/RESULT.json")
    branches={}
    shared_save=sha(NATIVE/"compact_native_r5_chest_key_001/chest_check/chest.autosave")
    for branch,suffix,aid in (("ink","ink_002",110),("key","key_001",111),("leave","leave_001",171)):
        dest=NATIVE/("compact_native_r5_chest_"+suffix);out=dest/"chest_check"
        if branch!="key":
            claim=read(out/"RESTORE_INPUT.json")["saves"]["THE_SILENT.autosave"]
            assert claim["sha256"]==shared_save
        g,session,f=prefix(release,96)
        rows=ledger(out/"actions.jsonl"); rows=[r for r in rows if r["index"]>=97]
        actions=[];refs={}
        for r in rows:
            for stage in ("before","after"):
                if stage=="after":
                    old=f;f=advance(session,f,r["aid"])
                    assert stale(session,old,r["aid"])
                projected=views.model(f,g)
                reading=capture(dest,r[stage])
                later = branch=="key" and (r["index"]>98 or (r["index"]==98 and stage=="after"))
                normalized=subset(projected,reading,later)
                assert normalized["resources"][3:]==[9,1,20]
                actions.append(dict(input=r["index"],stage=stage,aid=r["aid"],supported=projected["supported"],
                    captured_sha256=r[stage]["raw_hash"],state_sha256=sha256(json.dumps(f.state.vector).encode()).hexdigest(),values=normalized,
                    model_keys=projected["keys"],immediate_keys_equal=projected["keys"]==normalized["keys"]))
            if r["index"]==98:assert r["aid"]==aid
        assert actions[2]["values"]["rewards"]==[["RELIC","inkbottle"],["SAPPHIRE_KEY","inkbottle"]]
        before=actions[2]["values"];after=actions[3]["values"]
        assert before["resources"]==after["resources"]==[56,66,237,9,1,20]
        assert after["keys"]==[False,False,False]
        assert after["relics"]==before["relics"]+([["inkbottle",0]] if branch=="ink" else [])
        assert not after.get("rewards")
        final=capture(dest,read(out/"END.json")); assert final["map_xy"]==actions[-1]["values"]["map_xy"]
        a=rows[0]["before"];tag=a["raw"]["capture_alignment"]
        for q in (out/"actions.jsonl",out/"END.json",out/"CLOSE.json",dest/"target.json",
                  dest/"native_oracle"/tag["native_session"]/"native_oracle.jsonl",
                  dest/"bridge/sessions"/a["session"]/"raw.jsonl",
                  dest/"bridge/sessions"/a["session"]/"attempts.jsonl"):
            refs[q.relative_to(ROOT).as_posix()]=sha(q)
        branches[branch]=dict(actions=actions,source_sha256=refs,original_same_seed=SEED,map=final)
        if branch=="key":
            end=read(out/"END.json")["raw"]["capture_alignment"]["native_record_sequence"]
            oracle=dest/"native_oracle"/tag["native_session"]/"native_oracle.jsonl"
            later=[r for r in ledger(oracle) if r["seq"]>end]
            first=next(r for r in later if r["kind"]=="native_state" and r["data"]["payload"]["public_run_keys"]["sapphire"])
            assert all(r["kind"]!="native_control_consumed" for r in later if r["seq"]<=first["seq"])
            value=first["data"]["payload"]
            assert value["screen"]=="MAP" and value["floor"]==9 and value["gold"]==237
            assert value["public_run_keys"]["sapphire"]==actions[-1]["model_keys"][2]
            branches[branch]["passive_key"]=dict(last_action_capture=end,native_record=first["seq"],
                screen=value["screen"],gold=value["gold"],keys=value["public_run_keys"],additional_inputs=0)
    before=[b["actions"][2]["values"] for b in branches.values()]
    assert before[0]==before[1]==before[2]
    assert len({b["actions"][2]["state_sha256"] for b in branches.values()})==1
    slow=NATIVE/"compact_native_r5_chest_key_002"; out=slow/"chest_check"
    assert read(out/"RESTORE_INPUT.json")["saves"]["THE_SILENT.autosave"]["sha256"]==shared_save
    slow_rows=ledger(out/"actions.jsonl");click,=[r for r in slow_rows if r["index"]==98]
    stable=[dict(seconds_after_receipt=0,snapshot=click["after"]),*ledger(out/"queries.jsonl")]
    measurements=[]
    for index,entry in enumerate(stable):
        snap=entry["snapshot"]; raw=snap["raw"]; v=capture(slow,snap)
        assert v["keys"]==[False,False,bool(index)] and v["relics"]==before[0]["relics"]
        assert v["rewards"]==[] and v["potions"]==[None,None] and v["resources"]==[56,66,237,9,1,20]
        assert set(raw["available_commands"])-{"key","click","wait","state"}=={"proceed"}
        measurements.append(dict(elapsed=entry["seconds_after_receipt"],sapphire=v["keys"][2],capture=snap["raw_hash"]))
    slow_map=capture(slow,read(out/"END.json"))
    actual_fast=branches["key"]["map"]; asserted_final={**actual_fast,"keys":[False,False,True]}
    assert asserted_final==slow_map
    tag=click["before"]["raw"]["capture_alignment"]
    wait_evidence=dict(elapsed_from_first_receipt=measurements,final=slow_map,only_menu_choice="proceed",files={
        q.relative_to(ROOT).as_posix():sha(q) for q in (out/"queries.jsonl",out/"actions.jsonl",out/"CLOSE.json",out/"END.json",
        out/"RESTORE_INPUT.json",slow/"native_oracle"/tag["native_session"]/"native_oracle.jsonl",
        slow/"bridge/sessions"/click["before"]["session"]/"raw.jsonl")})
    e,s,f=prefix(release,96); before=views.model(f,e);f=advance(s,f,111);after=views.model(f,e)
    assert before["rewards"]==[["GOLD",81],["RELIC","inkbottle"],["SAPPHIRE_KEY","inkbottle"]]
    assert after["resources"]==before["resources"] and after["rewards"]==[["GOLD",81]] and after["keys"]==before["keys"]
    assert after["relics"]==before["relics"]+[["inkbottle",0]]
    return dict(release=release.interface_signature().metadata(),runtime_sha256=sha(HERE/"session.py"),
        seed=original["display"],round4_journal=original["source_files"]["ACTIONS.jsonl"]["sha256"],chest_save_sha256=shared_save,
        branches=branches,blue_key_wait=wait_evidence,model_only_relic_before_gold=dict(source_action=111,before=before["rewards"],remaining=after["rewards"]),
        first_attempt=dict(stop_input=33,reason="no incidental Strike on HAND_CONFIRM; later replay applied it when absent",
        close_receipt=sha(NATIVE/"compact_native_r5_chest_ink_001/chest_check/CLOSE.json")))
if __name__=="__main__":
    result=check();write(HERE/"RESULT.json",result);print("Verified 3 retail decisions, 3 resulting maps, and different reward slot",sha(HERE/"RESULT.json"))
