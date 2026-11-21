"""Silent A20 R3 model entry. Observation extensions and action adapters share a single game."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json

from experiments.sa_calibration_round1.privileged.session import PrivilegedSession
from experiments.sa_calibration_round2.events.quotes import QuoteSession
from experiments.sa_calibration_round2.tea_state import session as tea
from .death.session import attach
from .death.split import split_markers
from .grid.session import GridEngine, make_base_session

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEPENDENCIES = (
    "experiments/sa_calibration_round3/release.py",
    "experiments/sa_calibration_round3/death/session.py",
    "experiments/sa_calibration_round3/grid/session.py",
    "experiments/hand_selection_frontiers193/session.py",
    "experiments/wing_removal_640/session.py",
)


class CalibratedSession(tea.TeaSession):
    def __init__(self, engine):
        self.engine = engine
        actions = attach(make_base_session(engine))
        public = QuoteSession(engine, actions)
        self.delegate = PrivilegedSession(engine, public)
        self._lock = public._lock


def make_engine():
    return GridEngine()


def make_session(engine=None):
    return CalibratedSession(make_engine() if engine is None else engine)


def interface_signature():
    parent = tea.interface_signature()
    parent.assert_matches(json.loads((HERE.parent / "sa_calibration_round2/tea_state/RESULT.json").read_bytes())["interface"])
    pieces = [(name, sha256((ROOT / name).read_bytes()).hexdigest()) for name in DEPENDENCIES]
    def signed(value):
        return sha256(json.dumps([value, pieces], sort_keys=True).encode()).hexdigest()
    first = make_session().reset(1)
    parent.assert_model_dimensions(len(first.state.vector), len(first.supported_actions))
    decoder = sha256((signed(parent.state_decoder_sha256) + sha256((HERE / "death/split.py").read_bytes()).hexdigest()).encode()).hexdigest()
    return replace(parent, state_version=first.state.state_version, state_sha256=signed(parent.state_sha256),
                   state_decoder_sha256=decoder,
                   action_source_sha256=signed(parent.action_source_sha256),
                   action_adapter_version=parent.action_adapter_version + "+round3-calibration-v1")
