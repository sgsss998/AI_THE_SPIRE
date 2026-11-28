"""Initialize one historical position before capture, with production map/reward rules active."""
from experiments.sa_calibration_round1.privileged.session import PrivilegedSession


def prepared(runtime, seed, setup, *, outer_fixture=False):
    engine = runtime.make_engine()
    session = runtime.make_session(engine)
    source = engine._source
    capture = source._capture
    applied = []
    def initial_capture():
        if not applied:
            applied.append(setup(source._env))
        return capture()
    source._capture = initial_capture
    if outer_fixture:
        # Negative control: historical fixture-mode reset turns off normal map and loot rules.
        layer = session
        while not isinstance(layer, PrivilegedSession):
            layer = vars(layer)['delegate']
        entry = layer.base
        source.reset_fixture = lambda req: source.reset(seed, ascension=20, final_act=True)
        entry.reset = lambda *args, **kwargs: entry.reset_fixture({'op':'r7_archived_position'})
    else:
        # Skip only the new-game Neow greeting. Every actual decision, including
        # subsequent menus, uses the full standard adapter and the normal run flag.
        entry = engine._legacy
        entry.reset = lambda *args, **kwargs: engine._publish_inner(engine._inner.reset(*args, **kwargs))
    try:
        frame = session.reset(seed, ascension=20, final_act=True)
    finally:
        del source._capture, entry.reset
        if outer_fixture:
            del source.reset_fixture
    assert len(applied) == 1 and frame.engine_steps == 0
    assert engine._inner.delegate._ordinary_run == (not outer_fixture)
    return engine, session, frame
