"""Replay all exact event stop prefixes in the first 32 discovery shards and check original Java draws."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
from subprocess import check_output,run
from tempfile import TemporaryDirectory
from experiments.ordinary_reward_hooks193.audit import JAR,RETAIL
from experiments.sa_calibration_round6.reference import ROOT,read,write,sha
from ..wall.verify import legal,step
from . import candidate,session

HERE=Path(__file__).resolve().parent
REG=HERE.parent/"runs/discovery-r6"
NAMES={v+1:k for k,v in session.schema()["enums"]["RelicId"].items()}


def records():
    rows=[]
    hashes={}
    for i in range(32):
        path=REG/f"shard-{i:04}.jsonl.gz"
        hashes[path.name]=sha(path)
        with gzip.open(path,"rt") as file:
            rows.extend(r for r in map(json.loads,file) if r["page"]=="EVENT_RESULT_UNVERIFIED")
    return rows,hashes


def evidence(row):
    seed=row["seed"]
    engine=candidate.make_engine()
    s=candidate.make_session(engine)
    f=s.reset(seed)
    for idx,a in enumerate(row["actions"]):
        if a not in legal(f):
            return dict(seed=seed,original_inputs=len(row["actions"]),passed=False,missing_prefix_action=idx+1,page=f.page)
        prev=f
        f=step(s,f,a)
    v,w=prev.state.vector,engine._inner.delegate._delegate._current.state.vector
    name=next(k for k,n in session.IDS.items() if n+1==v[9])
    out=dict(seed=seed,branch=name+"/"+str(row["actions"][-1]-110),floor=int(v[3]),old_inputs=len(row["actions"]),
             page=f.page,passed=f.page=="EVENT_RESULT",before_resources=list(v[:3]),sim_resources=list(w[:3]),
             before_deck=list(session.deck(v)),after_deck=list(session.deck(w)),
             before_relics=[(NAMES[k],n) for k,n in session.relics(v)],after_relics=[(NAMES[k],n) for k,n in session.relics(w)])
    if name=="Shining Light":
        eligible=[i for i,(face,n) in enumerate(session.deck(v)) if not n and session.TYPES[str(face-1)] in ("SKILL","ATTACK","POWER")]
        actual=[i for i,(old,new) in enumerate(zip(session.deck(v),session.deck(w))) if old[1]!=new[1]]
        out.update(eligible=eligible,actual_upgraded=actual)
    if out["passed"]:
        assert legal(f)==[110] and f.state.vector[:3]==w[:3] and session.deck(f.state.vector)==session.deck(w)
        assert session.relics(f.state.vector)==session.relics(w)
        following=step(s,f,110)
        assert following.state.vector[6]==5 and f.engine_steps==following.engine_steps
    return out


def original_upgrades(rows):
    rows=[r for r in rows if "eligible" in r and r["eligible"]]
    arguments=[]
    for r in rows:
        s=r["seed"]%(1<<64)
        if s>=1<<63:s-=1<<64
        arguments.append(f'{s}:{r["floor"]}:'+','.join(map(str,r["eligible"])))
    compiler,=[r for r in read(ROOT/"native_fixture_work/BUILD.json")["inputs"] if "ecj-" in r["path"]]
    assert sha(Path(compiler["path"]))==compiler["sha256"] and sha(JAR)==RETAIL
    java=JAR.parent/"jre/bin/java";source=ROOT/"experiments/shining_light193/RetailUpgrade.java"
    with TemporaryDirectory() as tmp:
        run([java,"-jar",compiler["path"],"-1.8","-cp",JAR,"-d",tmp,source],check=True,capture_output=True)
        text=check_output([java,"-cp",tmp+":"+str(JAR),"RetailUpgrade",*arguments],text=True)
    original={k:sorted(json.loads(vals)) for k,vals in (line.split("=") for line in text.splitlines())}
    for row,key in zip(rows,arguments,strict=True):
        chosen=original[key]
        row["original_java_upgraded"]=chosen
        assert list(session.upgraded_positions(row["seed"],row["floor"],row["eligible"]))==chosen
        if row["passed"]:
            assert row["actual_upgraded"]==chosen


def main():
    rows,shards=records()
    with ProcessPoolExecutor(max_workers=2) as pool:
        facts=list(pool.map(evidence,rows,chunksize=4))
    original_upgrades(facts)
    counts=Counter((r.get("branch","prefix"),r["passed"]) for r in facts)
    retail_files=["event_result_frontiers193/RETAIL_BIG_FISH.json","event_result_frontiers193/RETAIL_THE_CLERIC.json",
                  "event_result_frontiers193/RETAIL_WORLD_OF_GOOP.json","shining_result_frontiers193/RETAIL.json",
                  "box_omamori193/RETAIL.json"]
    totals={k:{str(ok):counts[k,ok] for ok in (False,True)} for k in sorted({k for k,_ in counts})}
    result=dict(shards=shards,baseline_stops=len(rows),resolved=sum(r["passed"] for r in facts),breakdown=totals,
                jar_sha256=RETAIL,original_receipts={n:sha(HERE.parent.parent/n) for n in retail_files},
                runtime={n:sha(HERE/n) for n in ("PASSIVE.json","shuffle.py","session.py","candidate.py")},cases=facts)
    write(HERE/"RESULT.json",result)
    print(result["resolved"],result["baseline_stops"],totals)


if __name__=="__main__":
    main()
