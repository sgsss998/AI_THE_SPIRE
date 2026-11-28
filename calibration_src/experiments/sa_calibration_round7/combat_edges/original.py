"""Original actions before and after an identity-confirmed attack on the right slime."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from experiments.ordinary_reward_hooks193.audit import dump, JAR, RETAIL
from experiments.sa_calibration_round6.reference import sha
from silent_env.native_compare import verify_capture_record

ROOT = Path(__file__).resolve().parents[3]
ARCH = (
    ROOT.parent
    / "AI_THE_SPIRE_实机验证/20261115_SA验收/next_iteration/live_v6/audits_final/accept-v6-01/frozen_inputs"
)


def clip():
    seqs = (355, 359, 367)
    bridge_path = ARCH / "raw.jsonl"
    journal = ARCH / "native_oracle.jsonl"
    calls = ARCH / "attempts.jsonl"
    numbers = set(seqs) | {i + 1 for i in seqs}
    bridges = {}
    requests = {}
    for line in bridge_path.open():
        row = json.loads(line)
        if row["sequence"] in numbers:
            bridges[row["sequence"]] = row
    for line in calls.open():
        r = json.loads(line)
        if (
            r["event"] == "attempt_result"
            and r["status"] == "observed_transition"
            and r["before"]["sequence"] in seqs
        ):
            k = r["before"]["sequence"]
            assert all(
                r[side][field] == bridges[n][field]
                for side, n in [("before", k), ("after", k + 1)]
                for field in ("raw_hash", "raw", "session", "sequence")
            )
            requests[k] = r

    def serial(n):
        return bridges[n]["raw"]["capture_alignment"]["native_record_sequence"]

    windows = {i: [serial(i), serial(i + 1)] for i in seqs}
    captures = {}
    invoked = {}
    callback = {}
    for line in journal.open():
        r = json.loads(line)
        seq = r["seq"]
        if seq > max(serial(i) for i in numbers):
            break
        for i, (a, b) in windows.items():
            if seq in (a, b):
                j = i if seq == a else i + 1
                bridge = bridges[j]
                tag = bridge["raw"]["capture_alignment"]
                cap = verify_capture_record(
                    r,
                    bridge_row=bridge,
                    scope=dict(
                        native_session=tag["native_session"],
                        native_after_sequence=0,
                        native_through_sequence=seq,
                        bridge_session=bridge["session"],
                        bridge_sequence=j,
                    ),
                )
                assert cap.evidence["exact_capture_binding"]
                captures[j] = cap
            if not a < seq <= b:
                continue
            if r["kind"] == "native_card_invoked":
                assert i not in invoked
                invoked[i] = r["data"]
            if r["kind"] == "native_card_use_callback":
                assert i not in callback
                callback[i] = r["data"]
    evidence = []
    for i in seqs:
        cmd = requests[i]
        parts = cmd["command"].split()
        assert parts[0] == "play" and int(parts[-1]) == 2
        native = captures[i].payload
        before = native["monsters"]
        after = captures[i + 1].payload["monsters"]
        assert [m["id"] for m in before] == [
            "AcidSlime_M",
            "AcidSlime_L",
            "AcidSlime_M",
        ]
        assert [m["hp"] > 0 for m in before] == [False, False, True]
        assert [m["hp"] for m in after[:2]] == [0, 0] and 0 < after[2]["hp"] < before[
            2
        ]["hp"]
        physical = int(parts[1]) - 1
        item = native["hand"][physical]
        iv = invoked[i]
        assert iv["target"]["monster_position"] == {
            "index": 2,
            "index_base": 0,
            "status": "matched_by_object_identity",
        }
        assert item["uuid"] == iv["card"]["uuid"] == callback[i]["card"]["uuid"]
        evidence.append(
            dict(
                sequence=i,
                seed=bridges[i]["raw"]["game_state"]["seed"],
                native_action=cmd["action_id"],
                compact_target_action=cmd["action_id"] - 10,
                command=cmd["command"],
                request=cmd["request_id"],
                card=item["id"],
                uuid=item["uuid"],
                native_target=iv["target"],
                before_hp=[m["hp"] for m in before],
                after_hp=[m["hp"] for m in after],
                before_capture=captures[i].evidence["post_native_sha256"],
                after_capture=captures[i + 1].evidence["post_native_sha256"],
            )
        )
    return dict(
        hashes={p.name: sha(p) for p in (bridge_path, journal, calls)},
        paired_inputs=evidence,
    )


def rules():
    assert sha(JAR) == RETAIL
    cases = ("AcidSlime", "SpikeSlime")
    methods = dump(
        tuple(f"monsters.exordium.{c}_L#takeTurn" for c in cases)
        + ("actions.common.SpawnMonsterAction#update", "monsters.MonsterGroup")
    )
    out = {}
    for name in cases:
        key = f"monsters.exordium.{name}_L"
        code = next(iter(methods[key].values()))
        assert (
            sum(f"{name}_M.<init>" in x for x in code) == 2
            and sum("SpawnMonsterAction.<init>" in x for x in code) == 2
        )
        out[key] = sha256("\n".join(code).encode()).hexdigest()
    group = methods["monsters.MonsterGroup"][
        "addSpawnedMonster(Lcom/megacrit/cardcrawl/monsters/AbstractMonster;)V"
    ]
    assert any("ArrayList.add(ILjava/lang/Object;)" in x for x in group)
    return dict(
        game_sha256=RETAIL,
        split_methods=out,
        original_group_insertion=sha256("\n".join(group).encode()).hexdigest(),
    )
