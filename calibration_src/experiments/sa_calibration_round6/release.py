"""R6 uses the existing backend and attaches a typed ordinary combat reward adapter."""
from dataclasses import replace
from hashlib import sha256
import json
from experiments.sa_calibration_round5 import release as parent
from .reference import HERE,R5,read,sha
from .rewards.session import InkRewardSetup

TAG="+silent-a20-round6-v1"
RUNTIME=("release.py","rewards/session.py")

class Round6Engine(parent.Round5Engine):
    setup_class=InkRewardSetup

class VersionedSession(parent.VersionedSession):
    def _publish(self,frame):
        assert frame.state.state_version.endswith(parent.TAG)
        return replace(frame,state=replace(frame.state,state_version=frame.state.state_version+TAG))

def make_engine(*,neow_curse_timing="settled"):
    engine=Round6Engine(neow_curse_timing=neow_curse_timing)
    parent.install_shop(engine)
    return engine

def make_session(engine=None):
    engine=make_engine() if engine is None else engine
    return VersionedSession(parent.make_session(engine))

def source_hashes():
    return {name:sha(HERE/name) for name in RUNTIME}

def interface_signature():
    old=parent.interface_signature()
    old.assert_matches(read(R5/"INTERFACE.json"))
    files=source_hashes()
    def derive(h):
        return sha256(json.dumps([h,files],sort_keys=True).encode()).hexdigest()
    first=make_session().reset(1)
    old.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    return replace(old,state_version=first.state.state_version,state_sha256=derive(old.state_sha256),
                   state_decoder_sha256=derive(old.state_decoder_sha256),action_source_sha256=derive(old.action_source_sha256),
                   action_adapter_version=old.action_adapter_version+TAG)
