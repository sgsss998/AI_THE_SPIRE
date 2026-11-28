"""Independent retail receipts, Act II branches, and the controlled observation collision."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from experiments.sa_calibration_round6.reference import read, write, sha
from experiments.sa_calibration_round7 import battle
from experiments.ordinary_reward_hooks193.audit import JAR, RETAIL, dump
from experiments.stolen_gold_live193 import verify as native
from . import candidate, probe
from .observation.build import HERE as ODIR, build
from .observation.session import Session, signature
from .observation import release
from ..verify import deep, step
from ..session import r3

HERE = Path(__file__).resolve().parent
VERSIONED = SimpleNamespace(
    make_engine=candidate.make_engine,
    make_session=lambda e: Session(candidate.make_session(e), e),
)


def options(f):
    return [
        tuple(map(int, f.state.vector[i : i + 6]))
        for i in range(322, 706, 6)
        if f.state.vector[i]
    ]


def digest(s):
    return sha256(json.dumps(s, separators=(",", ":")).encode()).hexdigest()


def retail_sources():
    raw = native.verify()
    fees = dump(
        (
            "monsters.city.Mugger",
            "monsters.exordium.Looter",
            "rooms.AbstractRoom#addStolenGoldToRewards",
        )
    )
    rules = {}
    for e in ("monsters.city.Mugger", "monsters.exordium.Looter"):
        body = fees[e]["die()V"]
        reads = [
            x.strip()
            for x in body
            if "GETFIELD" in x and ("gold" in x.lower() or "stol" in x.lower())
        ]
        assert reads and any("addStolenGoldToRewards" in x for x in body)
        rules[e] = dict(native_field=reads, death_sha256=digest(body))
    assert sha(JAR) == RETAIL
    return dict(
        sha256=RETAIL,
        fixture_sha256=sha(native.HERE / "RESULT.json"),
        seed=15,
        wallet_and_options=raw["actual_original"],
        credit_rule=rules,
    )


def real_balances():
    session = release.make_session()
    frame = session.reset(15)
    records = []
    starting_wallet = None
    for row in native.read_lines(native.A / "commands.jsonl"):
        r = row["before"]
        g = r["raw"]["game_state"]
        combat = g.get("combat_state")
        if (
            g["floor"] == 4
            and combat
            and [a["id"] for a in combat["monsters"]] == ["Looter"]
        ):
            if starting_wallet is None:
                starting_wallet = g["gold"]
            suffix = tuple(frame.state.vector[-5:])
            assert g["gold"] == frame.state.vector[2] and suffix == (
                starting_wallet - g["gold"],
                0,
                0,
                0,
                0,
            )
            records.append(
                dict(
                    sequence=r["sequence"],
                    sha256=r["raw_hash"],
                    wallet=g["gold"],
                    model_purse=suffix[0],
                )
            )
        frame = step(session, frame, row["aid"])
    assert len(records) == 21 and {r["model_purse"] for r in records} == {0, 20, 40, 60}
    return dict(
        records=records,
        seed=15,
        floor=4,
        starting_wallet=starting_wallet,
        method="Wallet change with a single original-game thief; no other observed transfers.",
    )


def branches(d):
    fixture = deep.compile_parasite(d)
    mut = build(d, ODIR / "diagnostic.cpp", "_r7_swap_purses")
    outputs = []
    twins = []
    for kind, sequence in [
        ("native-order", [111, 110, 110, 177, 171]),
        ("stolen-first", [110, 110, 110, 111, 171]),
        ("exit", [171]),
    ]:
        e, s, f, states = probe.opening(VERSIONED, d, fixture=fixture)
        assert (
            f.page == "COMBAT_REWARD"
            and f.state.vector[2] == 199
            and deep.allowed(f) == [110, 111, 112, 171]
        )
        assert options(f)[:2] == [(4, 60, 1, 0, 0, 1), (4, 15, 0, 0, 0, 1)]
        assert f.policy_mask == f.supported_actions and f.state.vector[-5:] == (
            0,
            0,
            0,
            0,
            0,
        )
        initial = deep.snapshot(f)
        steps = []
        deck = f.state.vector[22]
        held = f.state.vector[32:112]
        for aid in sequence:
            before = f
            f = step(s, f, aid)
            assert f.state.vector[4] == 2 and f.state.vector[32:112] == held
            assert f.state.vector[-5:] == (0, 0, 0, 0, 0)
            if f.page in ("COMBAT_REWARD", "CARD_REWARD"):
                assert f.policy_mask == f.supported_actions
            steps.append(
                dict(
                    aid=aid,
                    previous_steps=before.engine_steps,
                    after=deep.snapshot(f),
                    rows=options(f),
                )
            )
        assert f.state.vector[6] == 5 and f.state.vector[2] == (
            199 if kind == "exit" else 274
        )
        assert f.state.vector[22] == deck + int(kind == "stolen-first")
        outputs.append(dict(branch=kind, initial=initial, steps=steps))
        if not twins:
            twins = [states]
    _, _, alt, other = probe.opening(
        VERSIONED, d, fixture=fixture, at_48=mut.swap_directed
    )
    baseline = next(r for r in twins[0] if r["step"] == 48)
    alt0 = next(r for r in other if r["step"] == 48)
    assert baseline["s"][:-5] == alt0["s"][:-5] and baseline["mask"] == alt0["mask"]
    assert baseline["s"][-5:] == [60, 40, 0, 0, 0] and alt0["s"][-5:] == [
        40,
        60,
        0,
        0,
        0,
    ]
    assert (
        [r["action"] for r in twins[0] if r["step"] >= 48]
        == [r["action"] for r in other if r["step"] >= 48]
        == [10, 170]
    )
    assert options(alt)[:2] == [(4, 40, 1, 0, 0, 1), (4, 15, 0, 0, 0, 1)]
    return outputs, dict(
        seed=probe.SEED,
        floor=19,
        wallet=199,
        step=48,
        stored_gold=baseline["s"][-5:],
        counterfactual=alt0["s"][-5:],
        original_and_counterfactual_S3122_sha256=digest(baseline["s"][:-5]),
        original_and_counterfactual_A193_sha256=digest(baseline["mask"]),
        actions=[10, 170],
        original_rewards=[60, 15],
        swapped_rewards=[40, 15],
        native_act2_turns=False,
        natural_purse_readings=[
            dict(step=r["step"], pooled_wallet=r["gold"], purses=r["s"][-5:])
            for r in twins[0]
        ],
    )


def verify():
    with TemporaryDirectory() as d:
        branches_run, collision = branches(d)
    state = signature(battle.interface_signature())
    return dict(
        original_game=retail_sources(),
        single_thief_original_game=real_balances(),
        directed_branches=branches_run,
        same_state_collision=collision,
        schema=read(ODIR / "schema.json"),
        sample_interface=state.as_dict() if hasattr(state, "as_dict") else vars(state),
        sources={
            p.relative_to(HERE).as_posix(): sha(p)
            for p in sorted(
                [
                    *HERE.glob("*.py"),
                    *ODIR.glob("*.py"),
                    *ODIR.glob("*.cpp"),
                    ODIR / "schema.json",
                ]
            )
        },
    )


if __name__ == "__main__":
    result = verify()
    write(HERE / "RESULT.json", result)
    print(
        result["same_state_collision"]["original_rewards"],
        result["same_state_collision"]["swapped_rewards"],
    )
