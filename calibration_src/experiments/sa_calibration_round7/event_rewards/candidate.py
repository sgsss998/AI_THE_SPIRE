from dataclasses import replace
from .. import events_and_grids as parent
from .session import EventRewardMixin


class Setup(EventRewardMixin,parent.Setup):
    pass


class Engine(parent.Engine):
    setup_class=Setup


def make_engine(**kwargs):
    engine=Engine(**kwargs)
    battle=parent.parent.battle
    battle.install_shop(engine)
    battle.bind_box(engine)
    battle.parent.install_card_shelf(engine)
    battle.install_merchandise(engine)
    parent.install_door(engine)
    return parent.parent.install_opening(engine)


class Session(parent.Session):
    def _publish(self,frame):
        out=super()._publish(frame)
        self._latest=replace(out,state=replace(out.state,state_version=out.state.state_version+'+event-item-rows-v1'))
        return self._latest


def make_session(engine=None):
    engine=make_engine() if engine is None else engine
    return Session(parent.parent.make_session(engine),engine)
