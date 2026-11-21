"""Public entry for the separately versioned Silent A20 round-five adapters."""
from dataclasses import replace
from hashlib import sha256
import json

from experiments.sa_calibration_round4 import release as parent
from .chest.session import InkBottleSetup
from .shop.session import install as install_shop
from .wheel.session import wrap as wrap_wheel
from .reference import HERE, R4, read, sha

TAG = "+silent-a20-round5-v1"
RUNTIME = ("release.py","chest/session.py","shop/session.py","wheel/session.py","wheel/offer.cpp","wheel/build.py","wheel/build/BUILD.json")


class Round5Engine(parent.Round4Engine):
    setup_class = InkBottleSetup


class VersionedSession:
    def __init__(self, delegate):
        self.delegate = delegate

    def __getattr__(self, name):
        return getattr(self.delegate, name)

    def _publish(self, frame):
        version = frame.state.state_version
        assert version.endswith(parent.TAG)
        return replace(frame,state=replace(frame.state,state_version=version+TAG))

    def reset(self, *args, **kwargs):
        return self._publish(self.delegate.reset(*args, **kwargs))

    def reset_fixture(self, request):
        return self._publish(self.delegate.reset_fixture(request))

    def step(self, action, *, frame_id, action_version):
        return self._publish(self.delegate.step(action,frame_id=frame_id,action_version=action_version))


def make_engine(*, neow_curse_timing="settled"):
    engine = Round5Engine(neow_curse_timing=neow_curse_timing)
    install_shop(engine)
    return engine


def make_session(engine=None):
    engine = make_engine() if engine is None else engine
    return VersionedSession(wrap_wheel(engine,parent.make_session(engine)))


def source_hashes():
    return {name:sha(HERE/name) for name in RUNTIME}


def interface_signature():
    previous = parent.interface_signature()
    previous.assert_matches(read(R4/"INTERFACE.json"))
    files = source_hashes()
    def derive(old):
        return sha256(json.dumps([old,files],sort_keys=True).encode()).hexdigest()
    first = make_session().reset(1)
    previous.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    return replace(previous,state_version=first.state.state_version,state_sha256=derive(previous.state_sha256),
                   state_decoder_sha256=derive(previous.state_decoder_sha256),action_source_sha256=derive(previous.action_source_sha256),
                   action_adapter_version=previous.action_adapter_version+TAG)
