"""Settle ordinary curse transformations using the original order with the chosen ID removed."""
from functools import lru_cache
from pathlib import Path

from experiments.common_relic193.rules import relic_id
from experiments.policy_event_integration.session import load_extension
from experiments.policy_neow_cards.session import require
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from .. import session as base
from ..colorless import COLORLESS,ColorlessGridMixin

BUILD=Path(__file__).resolve().parent/"build/BUILD.json"
PIN="5a528323b117e91ad8943d160e10789ce3600420b7ef0b4c34ec1b6e4041c191"
OMAMORI=relic_id("OMAMORI")
ORDINARY_CURSES=base.CURSE - base.NEVER_REMOVE - {"Pride"}


@lru_cache(maxsize=1)
def kernel():
    return load_extension(BUILD,PIN)


class CurseGridMixin(ColorlessGridMixin):
    step=_local_dependencies(base.SingleGridMixin.step,GREEN=base.GREEN|COLORLESS|ORDINARY_CURSES)

    def _r7_grid_list(self,picker):
        if picker.task==1 and OMAMORI in picker.base.state.vector[32:112:2]:
            names=self._source._backend.CARD_IDS
            picker.selectable=tuple(j for j in picker.selectable if names[picker.cards[picker.positions[j]][0]-1] not in ORDINARY_CURSES)
        return super()._r7_grid_list(picker)

    def _r7_grid_commit(self,picker):
        position=picker.positions[picker.selected]
        face=self._source._backend.CARD_IDS[picker.cards[position][0]-1]
        if picker.task!=1 or face not in ORDINARY_CURSES:
            return super()._r7_grid_commit(picker)
        env=self._source._env
        receipt=kernel().prepare(env,picker.selected,position)
        self._curse_receipt=(picker.raw,81+picker.selected,receipt)
        try:
            return super()._r7_grid_commit(picker)
        finally:
            self._curse_receipt=None

    def _refresh(self,previous,action):
        pending=getattr(self,"_curse_receipt",None)
        if pending is not None:
            raw,eid,receipt=pending
            require(previous is raw and action==eid,"Different transformation reached curse settlement")
            kernel().settle(self._source._env,receipt)
            self._curse_receipt=None
        return super()._refresh(previous,action)
