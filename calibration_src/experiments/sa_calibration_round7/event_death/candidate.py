"""Independent reproduction of event defeat handling against the first R7 runtime."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from experiments.sa_calibration_round7 import release as parent
from .session import Session, TAG

make_engine = parent.make_engine


def make_session(engine=None):
    engine = make_engine() if engine is None else engine
    return Session(parent.make_session(engine), engine)


def interface_signature():
    old = parent.interface_signature()
    rule = Path(__file__).with_name("session.py").read_bytes()

    def digest(x):
        return sha256(x.encode() + rule).hexdigest()

    return replace(
        old,
        state_version=old.state_version + TAG,
        state_sha256=digest(old.state_sha256),
        state_decoder_sha256=digest(old.state_decoder_sha256),
        action_source_sha256=digest(old.action_source_sha256),
        action_adapter_version=old.action_adapter_version + TAG,
    )
