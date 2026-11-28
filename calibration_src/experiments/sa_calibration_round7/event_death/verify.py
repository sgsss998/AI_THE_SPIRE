"""Replay frozen seed prefixes, compare retail game methods, and vary a disposable event."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments.episode_outcomes193.rollout import endpoint
from experiments.ordinary_reward_hooks193.audit import RETAIL, JAR, dump
from experiments.sa_calibration_round6.reference import read, write, sha
from experiments.sa_calibration_round7 import episode
from experiments.sa_calibration_round7.death_family.thief_rewards.observation.build import (
    build,
)
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError
from . import candidate

HERE = Path(__file__).resolve().parent
CASES = read(HERE / "CASES.json")


def step(session, frame, action):
    assert frame.supported_actions[action]
    return session.step(
        action, frame_id=frame.frame_id, action_version=frame.action_version
    )


def replay(runtime, row, change=None):
    engine = runtime.make_engine()
    session = runtime.make_session(engine)
    f = session.reset(row["seed"])
    for action in row["route"][:-2]:
        f = step(session, f, action)
    assert row["route"][-1] == 110
    if change:
        source = engine._source
        capture = source._capture
        seen = []

        def apply():
            if not seen:
                change(source._env)
                seen.append(True)
            return capture()

        source._capture = apply
    try:
        f = step(session, f, row["route"][-2])
    finally:
        if change:
            del source._capture
    if change:
        assert seen == [True]
    return engine, session, f


def run_row(row, change=None, action=110):
    engine, owner, prev = replay(candidate, row, change)
    f = step(owner, prev, action)
    core = engine._source._env
    reason = endpoint(
        replace(f, state=replace(f.state, vector=f.state.vector[:3118])),
        core,
        cap_reached=False,
    )
    info = dict(
        seed=row["seed"],
        before=episode.snapshot(prev),
        action=action,
        after=episode.snapshot(f),
        outcome=reason,
        picker=[int(x) for x in f.state.vector[26:29]],
        choice_count=int(f.state.vector[1769]),
        game_reason="loss" if core.lost else "ongoing",
        wallet=f.state.vector[2],
        potions=list(f.state.vector[17:22]),
    )
    if f.done:
        assert reason == "terminal" and f.page == "GAME_OVER" and not f.action_gaps
        assert (
            f.state.vector[6] == 0
            and not any(f.state.vector[26:29])
            and not any(f.state.vector[322:706])
        )
        assert (
            not any(f.state.vector[2684:2748])
            and not any(f.state.vector[2969:3114])
            and f.state.vector[1769] == 0
        )
        assert (
            f.policy_mask
            == f.supported_actions
            == owner.real_action_mask(frame_id=f.frame_id)
        )
        assert not any(f.supported_actions) and f.done and core.lost and not core.won
        try:
            owner.step(110, frame_id=f.frame_id, action_version=f.action_version)
        except UnverifiedSemanticsError:
            pass
        else:
            raise AssertionError("Terminal still accepts a gameplay input")
        try:
            owner.real_action_mask(frame_id=prev.frame_id)
        except StaleFrameError:
            pass
        else:
            raise AssertionError("Stale event mask still usable")
    return info


def originals():
    refs = dump(
        (
            "events.exordium.GoldenWing",
            "events.exordium.ScrapOoze#buttonEffect",
            "characters.AbstractPlayer#damage",
            "screens.DeathScreen",
        )
    )
    wing = refs["events.exordium.GoldenWing"]
    button = wing["buttonEffect(I)V"]
    opening = wing["<init>()V"]
    assert (
        "13: BIPUSH 7" in opening
        and "15: PUTFIELD com.megacrit.cardcrawl.events.exordium.GoldenWing.damage:I"
        in opening
    )
    evidence = {
        "damage": next(x for x in button if ".AbstractPlayer.damage(" in x),
        "purge_stage": next(x for x in button if "CUR_SCREEN.PURGE:" in x),
        "grid": next(x for x in button if "GridCardSelectScreen.open(" in x),
    }
    assert all(
        int(evidence[a].split(":")[0]) < int(evidence[b].split(":")[0])
        for a, b in [("damage", "purge_stage"), ("purge_stage", "grid")]
    )
    assert "166: GOTO ->403" in button and "403: RETURN" in button
    damage = next(iter(refs["characters.AbstractPlayer"].values()))
    for token in (
        "currentHealth:I",
        "FairyPotion",
        "Lizard Tail",
        "isDead:Z",
        "DeathScreen.<init>",
        "AbstractDungeon.deathScreen:",
    ):
        assert any(token in line for line in damage)
    death = next(
        code
        for name, code in refs["screens.DeathScreen"].items()
        if name.startswith("<init>")
    )
    assert any("CurrentScreen.DEATH:" in x for x in death) and any(
        "PUTSTATIC com.megacrit.cardcrawl.dungeons.AbstractDungeon.screen:" in x
        for x in death
    )
    scrap = next(iter(refs["events.exordium.ScrapOoze"].values()))
    assert any(".AbstractPlayer.damage(" in line for line in scrap)
    assert sha(JAR) == RETAIL
    return dict(
        game=RETAIL,
        wing_flow=evidence,
        rule_sha256={
            k: sha256("\n".join(c).encode()).hexdigest()
            for k, c in [
                ("wing", button),
                ("hp", damage),
                ("screen", death),
                ("scrap", scrap),
            ]
        },
    )


def retail_comparison():
    from experiments.wing_removal_640.verify import retail

    data = retail()["states"]
    assert [i["hp"] for i in data[:3]] == [59, 52, 52]
    result = dict(
        seed=9000028, context="Original surviving Golden Wing branch", states=data
    )
    write(HERE / "NATIVE_SURVIVING_WING.json", result)
    return dict(
        seed=9000028, states=len(data), sha256=sha(HERE / "NATIVE_SURVIVING_WING.json")
    )


def verify():
    natural = []
    for row in CASES:
        e, s, f = replay(candidate.parent, row)
        old = step(s, f, row["route"][-1])
        assert (
            f.state.vector[0] == row["expected_hp"]
            and old.done
            and old.policy_mask is None
            and old.page == "GRID_UNVERIFIED"
        )
        fixed = run_row(row)
        assert (
            fixed["before"]["hp"] == row["expected_hp"]
            and fixed["outcome"] == "terminal"
        )
        rollout = episode.trial(
            row["seed"], row["strategy"], runtime=candidate, verify_repeat=True
        )
        assert (
            rollout["reason"] == "loss"
            and rollout["determinism"]["matched"]
            and rollout["actions"] == row["route"]
        )
        rolled = {
            key: rollout[key]
            for key in (
                "reason",
                "engine_floor",
                "engine_steps",
                "summary_floor",
                "determinism",
                "trace_sha256",
            )
        }
        natural.append(
            dict(
                case=row,
                old=episode.snapshot(old),
                corrected=fixed,
                normal_runner=rolled,
            )
        )
    row = next(x for x in CASES if x["expected_hp"] == 2)
    with TemporaryDirectory() as d:
        fixture = build(d, HERE / "directed.cpp", "_r7_event_cost_control")
        directed = {
            name: run_row(row, lambda env: fixture.set(env, hp, fairy, scrap), action)
            for name, hp, fairy, scrap, action in [
                ("exact_7", 7, False, False, 110),
                ("survives_8", 8, False, False, 110),
                ("fairy_saves_2", 2, True, False, 110),
                ("leave_2", 2, False, False, 112),
                ("scrap_ooze_2", 2, False, True, 110),
            ]
        }
    assert (
        directed["exact_7"]["outcome"]
        == directed["scrap_ooze_2"]["outcome"]
        == "terminal"
    )
    assert (
        directed["survives_8"]["after"]["hp"] == 1
        and not directed["survives_8"]["after"]["done"]
    )
    assert (
        directed["fairy_saves_2"]["after"]["hp"] > 0
        and not directed["fairy_saves_2"]["after"]["done"]
    )
    assert (
        directed["leave_2"]["after"]["hp"] == 2
        and not directed["leave_2"]["after"]["done"]
    )
    return dict(
        rules=originals(),
        surviving_retail=retail_comparison(),
        natural=natural,
        directed=directed,
        sources={p.name: sha(p) for p in HERE.iterdir() if p.suffix in (".py", ".cpp")},
    )


if __name__ == "__main__":
    result = verify()
    write(HERE / "RESULT.json", result)
    print(
        [
            (k, x["outcome"], x["after"]["hp"], x["after"]["page"])
            for k, x in result["directed"].items()
        ]
    )
