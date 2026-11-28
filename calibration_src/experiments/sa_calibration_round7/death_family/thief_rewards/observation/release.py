"""Opt-in S3127/A193 against R7 battle v4. The original runtime remains importable."""
from experiments.sa_calibration_round7 import battle
from .session import Session, signature

make_engine = battle.make_engine


def make_session(engine=None):
    engine = engine if engine is not None else make_engine()
    return Session(battle.make_session(engine), engine)


def interface_signature():
    return signature(battle.interface_signature())
