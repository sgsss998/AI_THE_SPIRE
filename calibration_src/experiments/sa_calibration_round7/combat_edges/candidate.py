"""Add proven post-split targets to the fifth R7 candidate."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from experiments.sa_calibration_round7 import decisions
from .session import attach

TAG = "+split-slime-child-target-v1"
make_engine = decisions.make_engine


class Session:
    def __init__(self, owner):
        self.delegate = owner

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def _publish(self, f):
        return replace(
            f, state=replace(f.state, state_version=f.state.state_version + TAG)
        )

    def reset(self, *args, **kw):
        return self._publish(self.delegate.reset(*args, **kw))

    def reset_fixture(self, *args, **kw):
        return self._publish(self.delegate.reset_fixture(*args, **kw))

    def step(self, *args, **kw):
        return self._publish(self.delegate.step(*args, **kw))


def make_session(engine=None):
    return Session(
        attach(decisions.make_session(engine if engine is not None else make_engine()))
    )


def interface_signature():
    old = decisions.interface_signature()
    rule = Path(__file__).with_name("session.py").read_bytes()

    def derive(x):
        return sha256(x.encode() + rule).hexdigest()

    return replace(
        old,
        state_version=old.state_version + TAG,
        state_sha256=derive(old.state_sha256),
        state_decoder_sha256=derive(old.state_decoder_sha256),
        action_source_sha256=derive(old.action_source_sha256),
        action_adapter_version=old.action_adapter_version + TAG,
    )
