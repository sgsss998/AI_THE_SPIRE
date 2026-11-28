"""Second R7 candidate: independent combat, event and ordinary-reward adapters."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from experiments.box_omamori193 import result as box_result, session as box_session
from experiments.sa_calibration_round5.reference import sha
from silent_env.runtime import StaleFrameError
from . import release as wall
from .fungi.session import attach as attach_fungi
from .reward_family.session import StandardRewardMixin, public_mask

HERE = Path(__file__).resolve().parent
TAG = "+r7-combat-events-rewards-v2"


class Setup(StandardRewardMixin, box_result.BoxResultMixin, wall.Round7Engine.setup_class):
    pass


class Engine(wall.Round7Engine):
    setup_class = Setup


def make_engine(*, neow_curse_timing="settled"):
    engine = Engine(neow_curse_timing=neow_curse_timing)
    wall.parent.parent.install_shop(engine)
    return box_session.bind_box(engine)


class Session(wall.VersionedSession):
    def __init__(self, engine):
        super().__init__(attach_fungi(wall.make_session(engine)))
        self.engine = engine
        self.frame = None

    def _publish(self, frame):
        assert frame.state.state_version.endswith(wall.TAG)
        updated = public_mask(self.engine, frame)
        self.frame = replace(updated, state=replace(updated.state, state_version=updated.state.state_version+TAG))
        return self.frame

    def real_action_mask(self, *, frame_id):
        if self.frame is None or self.frame.frame_id != frame_id:
            raise StaleFrameError("The decision frame has changed")
        return self.frame.policy_mask


def make_session(engine=None):
    return Session(make_engine() if engine is None else engine)


def source_hashes():
    files = [Path(__file__),HERE/"fungi/session.py",HERE/"reward_family/session.py",
             Path(box_result.__file__),Path(box_session.__file__),box_session.BUILD]
    return {p.relative_to(HERE.parent).as_posix():sha(p) for p in files}


def interface_signature():
    parent = wall.interface_signature()
    session = make_session()
    first = session.reset(1)
    parent.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    sources = source_hashes()
    def derive(value):
        return sha256(json.dumps([value, sources],sort_keys=True).encode()).hexdigest()
    return replace(parent,state_version=first.state.state_version,state_sha256=derive(parent.state_sha256),
                   state_decoder_sha256=derive(parent.state_decoder_sha256),action_source_sha256=derive(parent.action_source_sha256),
                   action_adapter_version=parent.action_adapter_version+TAG)
