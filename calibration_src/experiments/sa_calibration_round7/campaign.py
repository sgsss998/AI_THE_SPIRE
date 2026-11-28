"""Run a pinned seed cohort with per-episode resume and portable 100-game shards."""
import argparse
import concurrent.futures as futures
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import fcntl
import gzip
import importlib
import json
import random
import resource
import secrets
import sqlite3
import time
from pathlib import Path

from experiments.sa_calibration_round5.reference import read, sha, write

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
R6 = HERE.parent / "sa_calibration_round6"
EDITION = "experiments.sa_calibration_round6.release"
PUBLIC_COMMIT = "4c2708709a58febd64072a7159309a193d89dbd8"
TERMINAL = {"loss", "act3_win", "heart_win"}

def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

def environment(edition):
    module = importlib.import_module(edition)
    signature = module.interface_signature().metadata()
    if edition == EDITION:
        assert signature == read(R6/"INTERFACE.json")
    sources = [Path(__file__), HERE/"episode.py", HERE/"oracles/step_checks.py"]
    return {"entry": edition, "interface": signature, "parent": PUBLIC_COMMIT,
            "runner_sources": {str(p.relative_to(HERE)): sha(p) for p in sources if p.is_file()}}

def new_manifest(folder, count, cap, env):
    prior = set(read(R6/"fresh/SEEDS_BEFORE.json")["seeds_u64"])
    prior.add(int(read(R6/"fresh/SEED.json")["unsigned"]))
    for path in RUNS.glob("*/manifest.json"):
        prior.update(row["seed"] for row in read(path)["jobs"])
    salt = secrets.token_hex(16)
    rng = random.Random(salt)
    names = ["fixed"]*(count*4//10) + ["survival"]*(count*4//10)
    names += ["explore"]*(count-len(names))
    rng.shuffle(names)
    jobs = []
    for index, name in enumerate(names):
        seed = rng.getrandbits(63)
        while seed in prior:
            seed = rng.getrandbits(63)
        prior.add(seed)
        jobs.append(dict(index=index, seed=seed, strategy=name))
    data = dict(created=datetime.now(timezone.utc).isoformat(),salt=salt, cap=cap,
                environment=env,jobs=jobs,verification="same seed, same actions, deterministic trace")
    write(folder/"manifest.json",data)
    return data

def worker(job, edition, cap):
    from .episode import trial
    begin = time.monotonic()
    result = trial(job["seed"],job["strategy"],cap=cap,runtime=importlib.import_module(edition),verify_repeat=True)
    assert result["seed"]==job["seed"] and result["strategy"]==job["strategy"]
    result["worker_seconds"]=round(time.monotonic()-begin,4)
    result["worker_maxrss_bytes"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return job["index"],encode(result)

def shard(db, folder, block, expected):
    rows = list(db.execute("select idx,data from episodes where idx>=? and idx<? order by idx",(100*block,100*block+100)))
    if len(rows)!=expected:return
    path=folder/f"shard-{block:04d}.jsonl.gz"
    payload="".join(s+"\n" for _,s in rows).encode()
    if path.exists():
        assert gzip.decompress(path.read_bytes())==payload
        return
    tmp=path.with_suffix(".tmp")
    tmp.write_bytes(gzip.compress(payload,compresslevel=3,mtime=0))
    tmp.replace(path)

def summary(db, folder, total):
    reasons, pages, strategies, floors, issues = (Counter() for _ in range(5))
    peak=0
    actions=0
    for (data,) in db.execute("select data from episodes order by idx"):
        row=json.loads(data)
        reasons[row["reason"]]+=1
        strategies[row["strategy"]]+=1
        floors[row["engine_floor"]]+=1
        if row["reason"] not in TERMINAL:pages[row["page"]]+=1
        if row.get("first_issue"):
            issue=row["first_issue"]
            issues[str(issue.get("kind","flagged") if isinstance(issue,dict) else issue)]+=1
        actions+=len(row["actions"])
        peak=max(peak,row["worker_maxrss_bytes"])
    completed=sum(reasons.values())
    return dict(requested=total,completed=completed,outcomes=dict(reasons),strategies=dict(strategies),
                stop_pages=dict(pages),first_issues=dict(issues),max_floor=max(floors,default=0),
                actions=actions,max_worker_rss_bytes=peak,
                shard_bytes=sum(f.stat().st_size for f in folder.glob("shard-*.gz")),
                elapsed_active_seconds=round(db.execute("select coalesce(sum(active),0) from timing").fetchone()[0],2))

def execute(args):
    folder=RUNS/args.name
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/"lock").open("a") as lock, closing(sqlite3.connect(folder/"progress.sqlite3")) as db:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        env=environment(args.edition)
        manifest=read(folder/"manifest.json") if (folder/"manifest.json").exists() else new_manifest(folder,args.count,args.cap,env)
        jobs=manifest["jobs"]
        assert len(jobs)==args.count and env==manifest["environment"] and manifest["cap"]==args.cap
        db.execute("create table if not exists episodes(idx integer primary key,data text not null)")
        db.execute("create table if not exists timing(active real not null)")
        done={i for (i,) in db.execute("select idx from episodes")}
        assert done<=set(range(args.count))
        block_counts=Counter(i//100 for i in done)
        todo=iter(j for j in jobs if j["index"] not in done)
        workers=args.workers
        marked=time.monotonic()
        with futures.ProcessPoolExecutor(workers) as pool:
            pending={}
            def fill():
                for j in todo:
                    pending[pool.submit(worker,j,args.edition,args.cap)]=j
                    if len(pending)>=workers*2:break
            fill()
            while pending:
                finished,_=futures.wait(pending,return_when=futures.FIRST_COMPLETED)
                ready_blocks = []
                for future in finished:
                    job=pending.pop(future)
                    try:
                        index,result=future.result()
                    except Exception as err:
                        write(folder/"failure.json",dict(job=job,exception=repr(err)))
                        raise
                    assert index==job["index"]
                    db.execute("insert into episodes values(?,?)",(index,result))
                    done.add(index)
                    block_counts[index//100]+=1
                    block = index // 100
                    if block_counts[block] == min(100, args.count-100*block):
                        ready_blocks.append(block)
                now=time.monotonic()
                db.execute("insert into timing values(?)",(now-marked,))
                db.commit()
                marked=now
                for block in ready_blocks:
                    shard(db, folder, block, block_counts[block])
                fill()
        for block in range((args.count+99)//100):
            shard(db,folder,block,min(100,args.count-100*block))
        result=summary(db,folder,args.count)
        assert result["completed"]==args.count
        assert env==environment(args.edition)
        result.update(manifest_sha256=sha(folder/"manifest.json"),workers=workers,
                      shards={p.name:sha(p) for p in sorted(folder.glob("shard-*.gz"))})
        write(folder/"RESULT.json",result)
        print(encode({k:v for k,v in result.items() if k!="shards"}),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--count",type=int,required=True)
    parser.add_argument("--workers",type=int,choices=range(1,17),default=4)
    parser.add_argument("--cap",type=int,default=2000)
    parser.add_argument("--edition",default=EDITION)
    args=parser.parse_args()
    if not args.name.replace("-","").isalnum() or args.count<=0 or args.cap<=0:parser.error("invalid batch")
    execute(args)
