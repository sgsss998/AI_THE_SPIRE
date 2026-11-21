"""Classify R3's blocked decisions from pinned trajectories and their live physical selection rows."""
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import gzip
import json
from pathlib import Path

from experiments.action193_grid.session import witness
from experiments.grid_frontier_640.audit import TASKS
from experiments.sa_calibration_round3 import release
from silent_env.observation import schema

HERE = Path(__file__).resolve().parent
R3 = HERE.parents[1] / "sa_calibration_round3"
REG = R3 / "regression"
BASE = json.loads((REG / "RESULT.json").read_bytes())["full"]
TABLE = REG / BASE["path"]
ENUMS = schema()["enums"]
def lookup(domain, value):
    return next((name for name, number in ENUMS[domain].items() if number+1 == value), None)

def one(row):
    seed = row["seed"]
    episode = row["episode"]
    data = (TABLE.parent / "traces" / f"{seed}.json.gz").read_bytes()
    assert sha256(data).hexdigest() == row["trace"]["sha256"]
    archived = json.loads(gzip.decompress(data))
    engine = release.make_engine()
    session = release.make_session(engine)
    f = session.reset(seed, ascension=20, final_act=True)
    for action in episode["actions"]:
        prev = f
        f = session.step(action, frame_id=f.frame_id, action_version=f.action_version)
    assert all(list(obj.state.vector)==old["state"] and obj.page==old["page"] for obj,old in zip((prev,f),archived[-2:],strict=True))
    assert not f.done and not any(f.supported_actions)
    raw = engine._raw
    assert raw.engine_steps == f.engine_steps and raw.choice_metadata["packet_sha256"] == raw.packet_sha256
    v, w = prev.state.vector, f.state.vector
    choices = [{"kind":x["kind_name"], "args":list(x["parameters"]), "legal_in_kernel":x["legal"]} for x in raw.choice_metadata["choices"]]
    room = lookup("Room",w[8])
    event = lookup("Event",v[9])
    source = event if event and event!="INVALID" else room
    detail = dict(seed=seed, floor=int(w[3]), before=prev.page, room=room, event=event, action_into_page=action,
                  trace_sha256=row["trace"]["sha256"], packet_sha256=raw.packet_sha256,
                  prefix_inputs=len(episode["actions"]), page=f.page, physical_choices=choices)
    if f.page == "GRID_UNVERIFIED":
        grid = witness().describe(engine._source._env)
        assert grid["active"] and grid["required"] == w[27] and len(choices)==grid["count"]
        task = TASKS[grid["task"]]
        if task=="transform_and_upgrade":
            relic = ENUMS["RelicId"]["ASTROLABE"]+1
            if relic in w[32:112:2] and relic not in v[32:112:2]:
                source = "NEOW_SWAP_ASTROLABE"
        elif task=="bonfire_offering":
            source="BONFIRE_SPIRITS"
        detail.update(task=task, required=grid["required"], candidates=grid["count"], group=f"grid/{source}/{task}/{grid['required']}")
    else:
        assert f.page == "REWARD_UNVERIFIED"
        kinds = sorted({c["kind"] for c in choices})
        if prev.page=="NEOW_OFFERS":
            added=[lookup("RelicId",i) for i in w[32:112:2] if i and i not in v[32:112:2]]
            source="NEOW_SWAP_"+"+".join(added) if added else "NEOW"
        detail.update(group=f"reward/{source}/" + "+".join(kinds), offered_kinds=kinds)
    return detail

def main():
    assert sha256(TABLE.read_bytes()).hexdigest() == BASE["sha256"]
    rows = [x for x in json.loads(TABLE.read_bytes())["runs"] if x["cohort"]=="fixed" and
            x["episode"]["reason"]=="unsupported" and x["episode"]["page"] in ("GRID_UNVERIFIED","REWARD_UNVERIFIED")]
    with ProcessPoolExecutor(3) as pool:
        items = list(pool.map(one, rows, chunksize=2))
    groups = defaultdict(list)
    for item in items:
        groups[item["group"]].append(item["seed"])
    assert Counter(x["page"] for x in items)=={"GRID_UNVERIFIED":76,"REWARD_UNVERIFIED":53}
    result = dict(reference_table_sha256=BASE["sha256"], reference_interface=release.interface_signature().metadata(),
                  original_games=0, groups=dict(sorted(groups.items())), cases=items)
    (HERE/"STOPS.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print({k:len(v) for k,v in sorted(groups.items())},flush=True)
if __name__ == "__main__":
    main()
