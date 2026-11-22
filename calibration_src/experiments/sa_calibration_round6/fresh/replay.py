"""Verify the retail run and compare its recorded actions only after original game-over."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import re
import subprocess

from native_runtime import now
from native_pilot import libraries
from experiments.sa_calibration_round3.fresh import replay as view
from .. import release
from ..replay import run
from .instance import HERE,R6,ROOT,DEST,read,write,sha

def capture(journal, end):
    libraries(DEST)
    from silent_env.native_compare import verify_capture_record,json_hash
    sources,streams,oracles,attempts,calls=set(),{},{},{},[]
    view.NATIVE.clear()
    physical_file=HERE/"PHYSICAL.jsonl"
    key_events=view.rows(physical_file)
    for snap in [s for row in journal for s in (row["before"],row["after"])] + [end["snapshot"]]:
        sid,seq=snap["session"],snap["sequence"]
        if (sid,seq) in view.NATIVE:continue
        tag=snap["raw"]["capture_alignment"]
        native_id=tag["native_session"]
        if sid not in streams:
            raw=DEST/"bridge/sessions"/sid/"raw.jsonl"
            attempted=raw.parent/"attempts.jsonl"
            streams[sid]={v["sequence"]:v for v in view.rows(raw) if v.get("raw",{}).get("capture_alignment")}
            attempts[sid]=view.rows(attempted)
            sources.update((raw,attempted))
        if native_id not in oracles:
            archive=DEST/"native_oracle"/native_id/"native_oracle.jsonl"
            data=view.rows(archive)
            oracles[native_id]={v["data"]["capture_id"]:v for v in data if v["kind"]=="native_capture"}
            calls.extend((v["seq"],v["data"]) for v in data if v["kind"]=="native_card_invoked")
            sources.add(archive)
        record=streams[sid][seq]
        result=verify_capture_record(oracles[native_id][tag["capture_id"]],bridge_row=record,scope=dict(
            native_session=native_id,bridge_session=sid,bridge_sequence=seq,native_after_sequence=0,
            native_through_sequence=tag["native_record_sequence"]))
        assert result.evidence["exact_capture_binding"] and result.evidence["bracket_verified"]
        assert result.evidence["bridge_raw_sha256"]==snap["raw_hash"]==json_hash(snap["raw"])
        view.NATIVE[sid,seq]=result.payload
    for row in journal:
        assert row["status"]=="observed_transition"
        if row.get("wire_type")=="physical_hand_key":
            events=[x for x in key_events if x.get("request_id")==row["request_id"]]
            send,done=events
            assert send["event"]=="physical_dispatch_intent" and done["event"]=="physical_os_return" and done["code"]==0
            assert send["aid"]==row["aid"] and send["index"]==row["index"]
            if send.get("uuid"):
                assert row["before"]["raw"]["game_state"]["screen_state"]["hand"][row["aid"]-110]["uuid"]==send["uuid"]
            sources.add(physical_file)
        else:
            intent,=[a for a in attempts[row["before"]["session"]] if a.get("request_id")==row["request_id"] and a["event"]=="dispatch_intent"]
            assert intent["command"]==row["command"]
    starts=[a for data in attempts.values() for a in data if a["event"]=="dispatch_intent" and a["command"].startswith("start")]
    assert len(starts)==1 and starts[0]["request_id"]==read(HERE/"START_OUTPUT.json")["request_id"]
    return calls,{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(sources)}

def mechanics(journal,records):
    events={k:[] for k in ("shuffle","targeted_in_multi_enemy_fight","simultaneous_multi_enemy_damage","boss","relic_counter","random_event","reward","potion")}
    for r in journal:
        i=r["index"]
        a,b=[r[x]["raw"]["game_state"] for x in ("before","after")]
        c,z=a.get("combat_state") or {},b.get("combat_state") or {}
        keys=[]
        if c and z and a["floor"]==b["floor"]:
            gone={x["uuid"] for x in c["discard_pile"]}; returned={x["uuid"] for x in z["draw_pile"]}
            if gone & returned:keys.append("shuffle")
            live=[m for m in c["monsters"] if m["current_hp"]>0 and not m["is_gone"]]
            if len(live)>1 and len(r["command"].split())==3 and r["command"].startswith("play "):keys.append("targeted_in_multi_enemy_fight")
            if len(live)>1 and sum(x["current_hp"]>y["current_hp"] for x,y in zip(c["monsters"],z["monsters"]))>1:keys.append("simultaneous_multi_enemy_damage")
            if any((x["id"],x["counter"])!=(y["id"],y["counter"]) for x,y in zip(a["relics"],b["relics"])):keys.append("relic_counter")
        if a["room_type"]=="MonsterRoomBoss" and c:keys.append("boss")
        if a["screen_type"]=="EVENT":keys.append("random_event")
        if a["screen_type"] in ("COMBAT_REWARD","CARD_REWARD","BOSS_REWARD"):keys.append("reward")
        if r["command"].startswith("potion"):keys.append("potion")
        for k in keys:events[k].append(i)
    paired={x["index"] for x in records if x["status"]=="public_action"}
    return {k:dict(original_indices=idx,officially_replayed_indices=[i for i in idx if i in paired]) for k,idx in events.items()}

def main():
    end=read(HERE/"TERMINAL.json")
    journal=view.rows(HERE/"ACTIONS.jsonl")
    assert end["snapshot"]["raw"]["game_state"]["screen_type"]=="GAME_OVER" and end["trace_sha256"]==sha(HERE/"ACTIONS.jsonl")
    assert [x["index"] for x in journal]==list(range(1,end["index"]+1))
    assert end["receipt"]["pending"] is None and end["receipt"]["quarantine"] is None
    first=HERE/"FIRST_SIMULATOR_START.json"
    if not first.exists():write(first,dict(at=now(),original_terminal_sha256=sha(HERE/"TERMINAL.json")))
    start=read(HERE/"START_INPUT.json");frozen=read(R6/"FREEZE.json");opened=read(HERE/"START_OUTPUT.json")
    assert datetime.fromisoformat(frozen["created_utc"])<datetime.fromisoformat(start["utc"])<datetime.fromisoformat(end["at"])<datetime.fromisoformat(read(first)["at"])
    assert start["seed"] is None and opened["command"]=="start THE_SILENT 20" and opened["status"]=="observed_start"
    assert frozen["runtime"]==release.source_hashes() and start["interface_sha256"]==sha(R6/"INTERFACE.json")
    assert read(first)["original_terminal_sha256"]==sha(HERE/"TERMINAL.json")
    signed=opened["after"]["raw"]["game_state"]["seed"]
    seed=signed%(1<<64)
    assert seed not in read(HERE/"SEEDS_BEFORE.json")["seeds_u64"]
    autosave=read(HERE/"AUTOSAVE_SEED.json")
    assert autosave["seed"]==signed and autosave["seed_set"] is False
    for r in journal:
        assert all((g["seed"],g["class"],g["ascension_level"])==(signed,"THE_SILENT",20) for g in (r["before"]["raw"]["game_state"],r["after"]["raw"]["game_state"]))
    jar=DEST/"game/desktop-1.0.jar"
    target=read(DEST/"target.json")
    assert not any(target[k] for k in ("fixture_mod_enabled","saves_copied","runs_copied"))
    assert sha(jar)==target["files"]["game/desktop-1.0.jar"]["sha256"]
    cp=str(ROOT/"experiments/ordinary_death193/fixture_build_v2/seed_classes")+":"+str(jar)
    code=subprocess.check_output([str(DEST/"game/jre/bin/java"),"-cp",cp,"SeedRoundTrip",str(signed)],text=True).strip()
    left,display,right=code.split("=");assert int(left)==signed==int(right)
    logs=(DEST/"launch.log").read_text(errors="replace")
    assert "Generating seeds: "+str(signed) in logs
    calls,sources=capture(journal,end)
    official=run(journal,calls,seed)
    assert official["signature"]==read(R6/"INTERFACE.json")
    official.update(seed=display,independent_holdout=True,original_journal_sha256=sha(HERE/"ACTIONS.jsonl"))
    write(HERE/"REPLAY.json",official)
    g=end["snapshot"]["raw"]["game_state"]
    details=dict(seed=display,version=re.search(r"DesktopLauncher> version: (.*)",logs).group(1),
        original_game_sha256=target["files"]["game/desktop-1.0.jar"]["original_source_sha256"],seed_signed=str(signed),
        blank_start=True,original_completed_before_model=True,original_ended_at=end["at"],first_simulator_start=read(first)["at"],
        original_inputs=len(journal),original_final=dict(floor=g["floor"],hp=g["current_hp"],max_hp=g["max_hp"],gold=g["gold"],victory=end["terminal"]["victory"]),
        original_screens=dict(Counter(r["before"]["raw"]["game_state"]["screen_type"] for r in journal)),mechanics=mechanics(journal,official["records"]),
        replay_sha256=sha(HERE/"REPLAY.json"),replay={k:official[k] for k in ("completed_inputs","official_actions","checked_frames","equal_frames","substance_equal_frames","first_content","stop","final")},
        source_sha256=sources)
    write(HERE/"RESULT.json",details)
    print(display,details["original_final"],official["completed_inputs"],official["first_content"],official["stop"])

if __name__=="__main__":main()
