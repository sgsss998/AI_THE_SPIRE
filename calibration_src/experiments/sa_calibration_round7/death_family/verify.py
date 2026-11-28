"""Verify the actual retail death methods and commands alongside seeded simulator regressions."""
from collections import Counter
from hashlib import sha256
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from experiments.ordinary_death193.fixture import dest
from experiments.ordinary_reward_hooks193.audit import RETAIL, JAR, dump
from experiments.sa_calibration_round6.reference import read, write, sha
from experiments.sa_calibration_round7.deep import replay as deep
from experiments.sa_calibration_round7 import combined
from . import candidate
from .session import VICTIMS, MONSTERS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CLASSES = dict(
    ACID_SLIME_S="exordium.AcidSlime_S",
    ACID_SLIME_M="exordium.AcidSlime_M",
    SPIKE_SLIME_S="exordium.SpikeSlime_S",
    SPIKE_SLIME_M="exordium.SpikeSlime_M",
    GREEN_LOUSE="exordium.LouseDefensive",
    RED_LOUSE="exordium.LouseNormal",
    RED_SLAVER="exordium.SlaverRed",
    BLUE_SLAVER="exordium.SlaverBlue",
    SENTRY="exordium.Sentry",
    FAT_GREMLIN="exordium.GremlinFat",
    MAD_GREMLIN="exordium.GremlinWarrior",
    SNEAKY_GREMLIN="exordium.GremlinThief",
    SHIELD_GREMLIN="exordium.GremlinTsundere",
    GREMLIN_WIZARD="exordium.GremlinWizard",
    JAW_WORM="exordium.JawWorm",
    CULTIST="exordium.Cultist",
    REPULSOR="beyond.Repulsor",
    SPIKER="beyond.Spiker",
    LOOTER="exordium.Looter",
    MUGGER="city.Mugger",
)


def rules():
    assert set(CLASSES) == VICTIMS and sha(JAR) == RETAIL
    methods = dump(
        tuple("monsters." + c for c in CLASSES.values()) + ("monsters.AbstractMonster",)
    )
    data = {}
    master = methods["monsters.AbstractMonster"]
    assert any("ArrayList.clear" in line for line in master["updateDeathAnimation()V"])
    with ZipFile(JAR) as z:
        for name, c in CLASSES.items():
            member = methods["monsters." + c]
            body = member.get("die()V", [])
            if body:
                assert any("AbstractMonster.die()V" in line for line in body)
            if name in ("LOOTER", "MUGGER"):
                assert any("addStolenGoldToRewards" in line for line in body)
            if name in ("ACID_SLIME_M", "SPIKE_SLIME_M"):
                assert any("areMonstersBasicallyDead" in line for line in body)
            data[name] = dict(
                source=c,
                bytecode=sha256(
                    z.read(
                        "com/megacrit/cardcrawl/monsters/"
                        + c.replace(".", "/")
                        + ".class"
                    )
                ).hexdigest(),
                die_method_sha256=sha256("\n".join(body).encode()).hexdigest()
                if body
                else None,
            )
    return dict(original_jar_sha256=RETAIL, classes=data)


def step(session, f, action):
    assert f.supported_actions[action], (f.page, action, f.action_gaps)
    return session.step(action, frame_id=f.frame_id, action_version=f.action_version)


def to(runtime, seed, actions):
    e = runtime.make_engine()
    s = runtime.make_session(e)
    f = s.reset(seed)
    for a in actions:
        f = step(s, f, a)
    return e, s, f


def real(seed):
    from experiments.ordinary_death193.verify import inspect
    from silent_env.native_compare import verify_capture_record

    root = dest(seed)
    ctl = root / "fixture_control"
    head, out = read(ctl / "header.json"), read(ctl / "outcome.json")
    independent = inspect(seed)
    records = {
        x["sequence"]: x
        for x in deep.jsonl(root / "bridge/sessions" / head["session"] / "raw.jsonl")
    }
    e, s, f = to(candidate, seed, head["route"])
    slot = out["victim_slot"]
    actual = deep.model(f, e)
    seq = out["stable"]["sequence"]
    row = records[seq]
    g = row["raw"]["game_state"]
    c = g["combat_state"]
    native_enemies = [
        [deep.norm(m["id"]), m["current_hp"], m["max_hp"], m["block"]]
        for m in c["monsters"]
    ]
    assert actual["enemies"] == native_enemies and actual["hand"] == [
        deep.card(x) for x in c["hand"]
    ]
    assert actual["turn_energy_block"] == [
        c["turn"],
        c["player"]["energy"],
        c["player"]["block"],
    ]
    assert not any(
        f.supported_actions[k]
        for k in (
            *range(10 + 10 * slot, 20 + 10 * slot),
            *range(75 + 5 * slot, 80 + 5 * slot),
        )
    )
    native_seq = row["raw"]["capture_alignment"]["native_record_sequence"]
    with (
        root / "native_oracle" / head["native"] / "native_oracle.jsonl"
    ).open() as stream:
        native = next(
            x for line in stream if (x := json.loads(line))["seq"] == native_seq
        )
    cap = verify_capture_record(
        native,
        bridge_row=row,
        scope=dict(
            native_session=head["native"],
            native_after_sequence=0,
            native_through_sequence=native_seq,
            bridge_session=head["session"],
            bridge_sequence=seq,
        ),
    )
    legal = cap.payload["independent_legal_actions"]
    assert legal["status"] == "complete" and not legal["unknown_domains"]
    native_ids = []
    for item in legal["semantic_actions"]:
        if item["type"] == "end":
            native_ids.append(170)
        else:
            assert item["type"] == "play"
            pos = item["card_index"]
            target = item["target_slot"]
            assert (
                c["hand"][pos]["uuid"] == item["object_uuid"]
                and c["hand"][pos]["id"] == item["object_id"]
            )
            native_ids.append(pos if target is None else (1 + target) * 10 + pos)
    assert sorted(native_ids) == deep.allowed(f)
    before = dict(
        sequence=seq,
        sha256=row["raw_hash"],
        combatants=native_enemies,
        offered=deep.allowed(f),
        native_actions=sorted(native_ids),
        complete_native_action_set=True,
        native_capture_sha256=cap.evidence["post_native_sha256"],
    )
    after = step(s, f, out["follow_a"])
    j = records[out["follow_bridge"]]
    g = j["raw"]["game_state"]
    m = deep.model(after, e)
    assert (
        m["resources"][0] == g["current_hp"]
        and m["page"] == deep.PAGES[g["screen_type"]]
    )
    if g.get("combat_state"):
        assert m["enemies"] == [
            [deep.norm(x["id"]), x["current_hp"], x["max_hp"], x["block"]]
            for x in g["combat_state"]["monsters"]
        ]
    return dict(
        seed=seed,
        victim=slot,
        action=out["follow_a"],
        command=out["follow_command"],
        before=before,
        after=dict(
            sequence=j["sequence"],
            sha256=j["raw_hash"],
            page=after.page,
            player_hp=m["resources"][0],
        ),
        source_hashes=independent["hashes"],
    )


def discovery():
    root = HERE.parent / "runs/discovery-r6"
    selected = {}
    counts = Counter()
    files = {}
    names = {v + 1: k for k, v in MONSTERS.items()}
    for no in range(4):
        p = root / f"shard-{no:04d}.jsonl.gz"
        files[p.name] = sha(p)
        for line in gzip.open(p):
            r = json.loads(line)
            if r["cause"] != ["death_boundary_unknown"]:
                continue
            v = dict(r["stop"]["after"]["state_nonzero"])
            roster = [
                (names[int(v[i])], int(v.get(i + 1, 0)), bool(v.get(i + 4, 0)))
                for i in range(993, 1253, 52)
                if i in v
            ]
            key = tuple(sorted({name for name, hp, gone in roster if gone}))
            counts["|".join(key)] += 1
            if key and all(name in VICTIMS for name in key) and key not in selected:
                selected[key] = r
    rows = []
    for key, r in selected.items():
        e, s, old = to(combined, r["seed"], r["actions"])
        e, s, now = to(candidate, r["seed"], r["actions"])
        before = deep.snapshot(old)
        after = deep.snapshot(now)
        newly = bool(
            now.supported_actions != old.supported_actions and deep.allowed(now)
        )
        next_frame = None
        if newly:
            a = next(
                (i for i in deep.allowed(now) if 10 <= i < 60), deep.allowed(now)[0]
            )
            post = step(s, now, a)
            next_frame = dict(action=a, after=deep.snapshot(post))
        rows.append(
            dict(
                seed=r["seed"],
                strategy=r["strategy"],
                prefix=r["actions"],
                victims=key,
                before=before,
                after=after,
                restored=newly,
                next_step=next_frame,
            )
        )
    return dict(
        shards=files,
        matching_stops=sum(counts.values()),
        counts=counts,
        representatives=rows,
    )


def run():
    with TemporaryDirectory() as d:
        encounter = deep.parasite(candidate, d)
        _, routes = deep.map_studies(candidate, d)
    assert (
        not encounter["first_difference"] and len(encounter["simulated_commands"]) == 30
    )
    c = encounter["simulator_only_continuation"]
    third = routes[0]
    assert (
        third["terminal"] == "loss"
        and len(third["actions"]) > 25
        and len(c["actions"]) > 20
    )
    return dict(
        rules=rules(),
        retail_inputs=[real(seed) for seed in (10, 18, 19)],
        discovery=discovery(),
        act2_native_combat=dict(
            compared_states=len(encounter["comparisons"]),
            first_difference=encounter["first_difference"],
        ),
        act2_simulated_thieves=c,
        act3_simulated_repulsor=third,
        source_sha256={
            p.name: sha(p)
            for p in (HERE / "candidate.py", HERE / "session.py", Path(__file__))
        },
    )


if __name__ == "__main__":
    out = run()
    write(HERE / "RESULT.json", out)
    print(
        len(out["retail_inputs"]),
        [(r["victims"], r["restored"]) for r in out["discovery"]["representatives"]],
    )
