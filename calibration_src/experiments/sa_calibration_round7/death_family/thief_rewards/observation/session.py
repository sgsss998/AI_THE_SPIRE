"""Five per-monster stolen-gold counters appended to a frozen S3122 owner."""
from dataclasses import replace
from hashlib import sha256
from threading import RLock

from silent_env.interface import InterfaceMismatch
from silent_env.runtime import StaleFrameError
from ...session import MONSTERS
from .build import HERE, observer

TAG = "+privileged-thief-purses-v1"
WIRE = frozenset((MONSTERS["LOOTER"] + 1, MONSTERS["MUGGER"] + 1))
OFFSETS = range(993, 1253, 52)


class Session:
    def __init__(self, owner, engine):
        self.delegate = owner
        self.engine = engine
        self._lock = RLock()

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def _publish(self, f):
        v = f.state.vector
        source = self.engine._source
        if len(v) != 3122 or len(f.supported_actions) != 193:
            raise InterfaceMismatch("Expected S3122/A193")
        raw = source._current
        if (
            raw is None
            or raw.engine_steps != f.engine_steps
            or source._env.steps != f.engine_steps
        ):
            raise StaleFrameError("Underlying observation changed")
        suffix = (0,) * 5
        if v[7] and any(v[i] in WIRE for i in OFFSETS):
            if any(raw.raw_base[i] != v[i] for i in OFFSETS):
                raise InterfaceMismatch("Public and kernel monster rows disagree")
            suffix = tuple(
                observer().values(
                    source._env, f.engine_steps, tuple(int(v[i]) for i in OFFSETS)
                )
            )
            if len(suffix) != 5 or any(
                x < 0 or (x and v[i] not in WIRE) for x, i in zip(suffix, OFFSETS)
            ):
                raise InterfaceMismatch("Unexpected purse slot")
        return replace(
            f,
            state=replace(
                f.state, vector=v + suffix, state_version=f.state.state_version + TAG
            ),
        )

    def reset(self, *args, **kw):
        with self._lock:
            return self._publish(self.delegate.reset(*args, **kw))

    def reset_fixture(self, *args, **kw):
        with self._lock:
            return self._publish(self.delegate.reset_fixture(*args, **kw))

    def step(self, *args, **kw):
        with self._lock:
            return self._publish(self.delegate.step(*args, **kw))


def signature(parent):
    if parent.observation_dimension != 3122 or parent.actions != 193:
        raise InterfaceMismatch("Expected original S3122/A193")

    def derive(old, names):
        digest = sha256(old.encode())
        for name in names:
            digest.update(sha256((HERE / name).read_bytes()).digest())
        return digest.hexdigest()

    return replace(
        parent,
        observation_dimension=3127,
        state_version=parent.state_version + TAG,
        state_sha256=derive(parent.state_sha256, ["schema.json"]),
        state_decoder_sha256=derive(
            parent.state_decoder_sha256,
            ["schema.json", "purses.cpp", "session.py", "build.py"],
        ),
    )
