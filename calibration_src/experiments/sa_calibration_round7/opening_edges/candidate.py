from .. import events_and_grids as v6
from .astrolabe import AstrolabeMixin
from .direct import OpeningRelicsMixin


class Engine(AstrolabeMixin,OpeningRelicsMixin,v6.Engine):
    pass


def make_engine(*,neow_curse_timing="settled"):
    e=Engine(neow_curse_timing=neow_curse_timing)
    battle=v6.parent.battle
    battle.install_shop(e)
    battle.bind_box(e)
    battle.parent.install_card_shelf(e)
    battle.install_merchandise(e)
    v6.install_door(e)
    return v6.parent.install_opening(e)


def make_session(engine=None):
    return v6.make_session(make_engine() if engine is None else engine)
