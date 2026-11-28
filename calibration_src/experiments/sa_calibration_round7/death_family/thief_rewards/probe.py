from tempfile import TemporaryDirectory
from pathlib import Path
from experiments.sa_calibration_round7.deep import replay as deep
from experiments.sa_calibration_round7.death_family import candidate, verify

SEED = 13655749040571095217


def opening(runtime, directory, *, fixture=None, at_48=None):
    prefix = verify.read(verify.HERE.parent / "deep/REWARD_CANDIDATE.json")
    r = prefix.get("act2_parasite") or next(
        x for x in prefix.values() if isinstance(x, dict) and "simulated_commands" in x
    )
    previous = verify.read(verify.HERE / "RESULT.json")["act2_simulated_thieves"]
    route = [row["action"] for row in r["simulated_commands"]] + previous["actions"]
    fixture = fixture or deep.compile_parasite(directory)
    save = deep.RUNS.parent / "saves/THE_SILENT.autosave.backUp"
    engine, session, frame = deep.prepared(
        runtime, SEED, lambda src: fixture.enter(src, str(save))
    )
    states = []
    if at_48:
        source = engine._source
        original = source._capture
        changed = []

        def captured():
            if source._env.steps == 48 and not changed:
                at_48(source._env)
                changed.append(True)
            return original()

        source._capture = captured
    for a in route:
        v = frame.state.vector
        if v[3] == 19:
            row = {
                "step": frame.engine_steps,
                "gold": v[2],
                "action": a,
                "turn": v[902],
                "enemies": [v[i : i + 10] for i in (993, 1045)],
                "potions": list(v[17:19]),
                "s": list(v),
                "mask": list(frame.supported_actions),
            }
            states.append(row)
        frame = verify.step(session, frame, a)
    if at_48:
        assert changed == [True]
        del source._capture
    return engine, session, frame, states


if __name__ == "__main__":
    with TemporaryDirectory() as d:
        e, s, f, states = opening(candidate, d)
    print(
        [
            (
                r["step"],
                r["gold"],
                r["action"],
                r["turn"],
                r["enemies"][0][1],
                r["enemies"][1][1],
            )
            for r in states
        ]
    )
    raw = e._source._current
    from experiments.sa_calibration_round7.death_family.session import r3

    print("final_witness", r3.ordinary.observer().inspect(e._source._env))
    print(
        "end",
        f.page,
        f.state.vector[:35],
        f.state.vector[17:19],
        [(i, raw.raw_base[i : i + 6]) for i in range(322, 706, 6) if raw.raw_base[i]],
    )
