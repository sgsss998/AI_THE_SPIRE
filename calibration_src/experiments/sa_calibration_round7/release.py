"""R7 composes the Living Wall removal adapter with the frozen R6 runtime."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from experiments.sa_calibration_round6 import release as parent
from experiments.sa_calibration_round6.reference import read, sha
from .wall.session import WallRemovalMixin

HERE = Path(__file__).resolve().parent
R6 = Path(parent.__file__).resolve().parent
TAG = "+silent-a20-round7-v1"
RUNTIME = ("release.py", "wall/session.py")


class Round7Engine(WallRemovalMixin, parent.Round6Engine):
    pass


class VersionedSession(parent.VersionedSession):
    def _publish(self, frame):
        assert frame.state.state_version.endswith(parent.TAG)
        return replace(frame, state=replace(frame.state, state_version=frame.state.state_version + TAG))


def make_engine(*, neow_curse_timing="settled"):
    engine = Round7Engine(neow_curse_timing=neow_curse_timing)
    parent.parent.install_shop(engine)
    return engine


def make_session(engine=None):
    return VersionedSession(parent.make_session(make_engine() if engine is None else engine))


def source_hashes():
    return {name: sha(HERE/name) for name in RUNTIME}


def interface_signature():
    old = parent.interface_signature()
    old.assert_matches(read(R6/"INTERFACE.json"))
    hashes = source_hashes()
    def derive(inherited):
        return sha256(json.dumps([inherited, hashes], sort_keys=True).encode()).hexdigest()
    first = make_session().reset(1)
    old.assert_model_dimensions(len(first.state.vector), len(first.supported_actions))
    return replace(old, state_version=first.state.state_version, state_sha256=derive(old.state_sha256),
                   state_decoder_sha256=derive(old.state_decoder_sha256), action_source_sha256=derive(old.action_source_sha256),
                   action_adapter_version=old.action_adapter_version+TAG)
