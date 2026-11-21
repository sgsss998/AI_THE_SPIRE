"""Compose fourth-round decisions on the same game instance and pin their sources."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from experiments.sa_calibration_round1.privileged.session import PrivilegedSession
from experiments.sa_calibration_round2.events.quotes import QuoteSession
from experiments.sa_calibration_round2.tea_state import session as tea
from experiments.sa_calibration_round3 import release as parent
from experiments.sa_calibration_round3.grid.session import GridEngine, make_base_session
from experiments.sa_calibration_round3.death.split import split_markers
from .death.session import attach
from .events.serpent import decode_offer, wrap
from .neow.session import NeowEngineMixin

HERE = Path(__file__).resolve().parent
R3 = HERE.parent / "sa_calibration_round3"
SOURCES = ("release.py", "neow/session.py", "death/session.py", "events/serpent.py")
TAG = "+silent-a20-round4-v1"

class Round4Engine(NeowEngineMixin, GridEngine):
    """One native environment, with the original grid timing selected at construction."""

class Observations(tea.TeaSession):
    def __init__(self, engine):
        self.engine = engine
        decisions = attach(make_base_session(engine))
        quoted = QuoteSession(engine, decisions)
        self.delegate = PrivilegedSession(engine, quoted)
        self._lock = quoted._lock

    def _publish(self, frame):
        enriched = super()._publish(frame)
        return replace(enriched, state=replace(enriched.state, state_version=enriched.state.state_version + TAG))

def make_engine(*, neow_curse_timing="settled"):
    return Round4Engine(neow_curse_timing=neow_curse_timing)

def make_session(engine=None):
    engine = make_engine() if engine is None else engine
    return wrap(engine, Observations(engine))

def source_hashes():
    return {name:sha256((HERE/name).read_bytes()).hexdigest() for name in SOURCES}

def interface_signature():
    previous = parent.interface_signature()
    previous.assert_matches(json.loads((R3 / "INTERFACE.json").read_bytes()))
    sources = source_hashes()
    def sign(inherited):
        data = json.dumps([inherited, sources], sort_keys=True).encode()
        return sha256(data).hexdigest()
    first = make_session().reset(1)
    previous.assert_model_dimensions(len(first.state.vector),len(first.supported_actions))
    return replace(previous, state_version=first.state.state_version, state_sha256=sign(previous.state_sha256),
                   state_decoder_sha256=sign(previous.state_decoder_sha256), action_source_sha256=sign(previous.action_source_sha256),
                   action_adapter_version=previous.action_adapter_version+TAG)
