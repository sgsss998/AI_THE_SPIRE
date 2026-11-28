"""Add original colorless transformations to the independently versioned single-card picker."""
from pathlib import Path

from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.sa_calibration_round6.reference import read
from . import session

COLORLESS=frozenset(read(Path(__file__).with_name("CARD_ORDER.json"))["source_colorless"])


class ColorlessGridMixin(session.SingleGridMixin):
    step=_local_dependencies(session.SingleGridMixin.step, GREEN=session.GREEN | COLORLESS)
