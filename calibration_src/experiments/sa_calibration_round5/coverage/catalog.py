"""Join the retail registration ID lists to exact entities observed in historical retail frames."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from experiments.ordinary_reward_hooks193.audit import dump, JAR
from .inventory import EXPERIMENTS, HERE, R3, R4, read, sha, table


PROJECT = EXPERIMENTS.parent
OLDER = PROJECT.parent / "AI_THE_SPIRE_实机验证"
DUNGEONS = tuple("dungeons."+name for name in ("Exordium","TheCity","TheBeyond","TheEnding","AbstractDungeon"))
FAMILIES=("cards","relics","potions","monsters","events","powers")


def read_registrations(catalog):
    out=defaultdict(lambda:defaultdict(list))
    classes=dump(DUNGEONS+("helpers.CardLibrary",))
    for cls in DUNGEONS:
        for method,ops in classes[cls].items():
            if method not in ("initializeEventList()V","initializeShrineList()V","initializeSpecialOneTimeEventList()V","initializeBoss()V"):
                continue
            family="boss_encounters" if method=="initializeBoss()V" else "events"
            for idx,op in enumerate(ops):
                if "INVOKEVIRTUAL java.util.ArrayList.add(" not in op:
                    continue
                direct=re.fullmatch(r"(\d+): LDC(?:_W)? (.+)",ops[idx-1])
                if not direct:
                    assert family=="boss_encounters" and ".get(I)" in ops[idx-1], (cls,method,op)
                    continue
                key=direct[2]
                if family=="events":
                    assert key in catalog[family]
                out[family][key].append([cls,method,int(direct[1])])
    note=classes["dungeons.AbstractDungeon"]["isNoteForYourselfAvailable()Z"]
    assert all(x in note for x in ("22: BIPUSH 15","24: IF_ICMPLT ->40","38: ICONST_0","39: IRETURN"))
    cards=classes["helpers.CardLibrary"]["addGreenCards()V"]
    green=[m[1].removeprefix("com.megacrit.cardcrawl.") for op in cards if (m:=re.search(r"NEW (com\.megacrit\.cardcrawl\.cards\.green\.\w+)$",op))]
    assert len(green)==len(set(green))==sum(".add(" in x for x in cards)
    for cls,methods in dump(tuple(green)).items():
        ids={l.split(" ",2)[-1] for key,v in methods.items() if key=="<init>()V" for l in v if ": LDC" in l and l.split(" ",2)[-1] in catalog["cards"]}
        assert len(ids)==1,(cls,ids)
        out["cards"][ids.pop()].append([cls,"helpers.CardLibrary.addGreenCards()V"])
    metadata=read(R3/"coverage/RESULT.json")
    pristine=Path(read(PROJECT/"native_runtime/compact_native_004/target.json")["files"]["game/desktop-1.0.jar"]["source"])
    base_names=list(DUNGEONS)+["helpers.CardLibrary"]+green
    with ZipFile(JAR) as isolated, ZipFile(pristine) as original:
        hashes={}
        for c in base_names:
            member="com/megacrit/cardcrawl/"+c.replace(".","/")+".class"
            bs=original.read(member)
            assert bs==isolated.read(member)
            hashes[c]=hashlib.sha256(bs).hexdigest()
    return out,hashes,metadata["source_game_sha256"]


def objects(game):
    def emit(family,where,rows):
        for row in rows or []:
            if isinstance(row,dict) and row.get("id") and row["id"]!="Potion Slot":
                yield family,row["id"],where
    for fam,k in (("cards","deck"),("relics","relics"),("potions","potions")):
        yield from emit(fam,k,game.get(k))
    screen=game.get("screen_state") or {}
    if game["screen_type"]=="EVENT" and screen.get("event_id"):
        yield "events",screen["event_id"],"event"
    for family in ("cards","relics","potions"):
        yield from emit(family,game["screen_type"],screen.get(family))
    for row in screen.get("rewards",[]):
        for fam,k in (("cards","card"),("relics","relic"),("potions","potion")):
            yield from emit(fam,"reward_offer",[row.get(k)])
    combat=game.get("combat_state") or {}
    for field in ("hand","draw_pile","discard_pile","exhaust_pile"):
        yield from emit("cards",field,combat.get(field))
    enemies=combat.get("monsters",[])
    yield from emit("monsters","battle",enemies)
    for scope,who in [("player",combat.get("player") or {})]+[("monster",m) for m in enemies]:
        yield from emit("powers",scope,who.get("powers"))
    if enemies and game["room_type"]=="MonsterRoomBoss" and game.get("act_boss"):
        yield "boss_encounters",game["act_boss"],"boss_battle"


def build():
    object_path=R3/"coverage/OBJECT_IDS.csv"
    lookup=defaultdict(set)
    for row in table(object_path):
        lookup[row["原版目录"]].add(row["原版标识"])
    registered,classes,original_sha=read_registrations(lookup)
    lookup["boss_encounters"]=set(registered["boss_encounters"])
    cutoff=datetime.fromisoformat(read(R4/"fresh/RESULT.json")["sealed_at"])
    source_files={}
    observations=defaultdict(dict)
    outside=defaultdict(dict)
    paths=[(PROJECT,p) for p in sorted((PROJECT/"native_runtime").glob("*/bridge/sessions/*/raw.jsonl"))]
    paths+=[(OLDER,p) for p in sorted(OLDER.glob("**/bridge/sessions/*/raw.jsonl"))]
    frame_count=0
    for base,path in paths:
        if "_r5_" in path.as_posix():continue
        prefix="project/" if base==PROJECT else "historical_original/"
        source=prefix+str(path.relative_to(base))
        n=0
        for ln in path.open():
            row=json.loads(ln)
            if datetime.fromisoformat(row["received_utc"])>cutoff:continue
            g=row["raw"].get("game_state") or {}
            if g.get("class")!="THE_SILENT" or g.get("ascension_level")!=20:continue
            n+=1
            for typ,id_,where in objects(g):
                target=observations if id_ in lookup[typ] else outside
                ent=target[(typ,id_)]
                if where not in ent:
                    ent[where]={"source":source,"sequence":row["sequence"],"raw_sha256":row["raw_hash"]}
        if n:
            source_files[source]={"sha256":sha(path),"qualifying_frames":n}
            frame_count+=n
    entries=[]
    for family in FAMILIES+("boss_encounters",):
        for key in sorted(lookup[family]):
            roles=observations.get((family,key),{})
            reg=registered[family].get(key,[])
            entries.append({"family":family,"id":key,"registration":reg,"excluded_a20":family=="events" and key=="NoteForYourself","observations":roles})
    counts={}
    for family in FAMILIES+("boss_encounters",):
        rows=[r for r in entries if r["family"]==family]
        counts[family]={"candidate_ids":len(rows),"observed_ids":sum(bool(r["observations"]) for r in rows),
                        "registrations_checked":sum(bool(r["registration"]) for r in rows),
                        "registered_seen":sum(bool(r["observations"]) and bool(r["registration"]) for r in rows)}
    assert sum(len(lookup[f]) for f in FAMILIES)==967 and len(lookup["boss_encounters"])==10
    heart=read(EXPERIMENTS/"terminal_metrics/RESULT.json")["native_heart_runs"]
    assert len(heart)==2 and all(r["victory"] and r["boss_floor"]==56 for r in heart)
    return {"catalog_sha256":sha(object_path),"retail_jar_sha256":original_sha,"registration_class_sha256":classes,
            "frozen_before":cutoff.isoformat(),"families":counts,"records":entries,"witness_files":source_files,
            "qualifying_raw_frames":frame_count,"raw_sessions":len(source_files),
            "raw_id_outside_catalog":[{"family":typ,"id":id_,"observations":r} for (typ,id_),r in sorted(outside.items())],
            "heart_archive_only":{"scope":"两份已赢心脏的玩家存档另列，只证终局，无逐回合轨迹。","path":"experiments/terminal_metrics/RESULT.json",
                                  "sha256":sha(EXPERIMENTS/"terminal_metrics/RESULT.json"),"records":len(heart)},
            "limits":"收录决策框内或陈列、持有、战斗实际出现的原版ID，每种语境给一个可按序号定位的回执。地图预告不计首领实战。只见ID不能证明效果、合法掩码或行为完整。注册表可能受角色、幕、存档、成就、钥匙等条件限制。未匹配字符串单列。"}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    report=build()
    output=HERE/"CATALOG.json"
    if args.check:assert report==read(output)
    else:output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(report["families"], report["raw_sessions"], report["qualifying_raw_frames"])
