"""Expose Pandora's ten displayed replacements, then settle them on the original confirmation."""
from dataclasses import replace
from numbers import Integral
from uuid import uuid4

from experiments.common_relic193.rules import START, relic_id
from experiments.neow_talk_mask193.session import project
from experiments.policy_neow_cards.session import page, require
from experiments.wing_removal_640.session import current_deck
from silent_env.action193 import POLICY_VERSION
from silent_env.interface import InterfaceMismatch
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError

BOX = relic_id("PANDORAS_BOX")
RING = relic_id("RING_OF_THE_SNAKE")
GRID = "NEOW_PANDORA_CONFIRM"


def pages(old, new, cards):
    if (len(old) != 3118 or len(new) != 3118 or len(cards) != 13
            or old[:10] != (59,66,99,0,1,20,1,0,10,6)
            or old[16:24] != (2,0,0,0,0,0,13,1) or old[32:112] != (RING,0)+(0,)*78
            or old[706:732:2] != START or any(old[707:732:2])
            or old[340:346] != (9,19,7,0,0,1) or old[1769] != 4
            or new[6:10] != (5,0,10,0) or new[32:112] != (BOX,0)+(0,)*78):
        return None
    ids = tuple(row[0] for row in cards)
    survivors = (START[0], START[-2], START[-1])
    if (ids[:3] != survivors or set(ids[3:]).intersection(START)
            or any((up, misc, bottled) != (0,0,False) for _,up,misc,bottled in cards)
            or new[706:732:2] != ids or any(new[707:732:2]) or any(new[732:898])
            or new[2586] not in (0,2) or any(new[2587:2683])):
        return None
    for lo,hi in ((0,6),(10,32),(112,322),(898,1769),(1770,2586),(2748,2968),(3114,3118)):
        if old[lo:hi] != new[lo:hi]:
            return None
    leave = list(old)
    leave[32] = BOX
    leave[706:898] = new[706:898]
    leave[2586:2683] = new[2586:2683]
    leave[322:706] = [8,0,0,0,0,1] + [0]*378
    leave[1769] = 1
    leave[2683:2748] = [2]+[0]*64
    leave[2968:3114] = [2,1]+[0]*144
    grid = leave.copy()
    grid[6] = 4
    grid[9] = 0
    grid[22] = grid[1763] = 3
    grid[712:898] = [0]*186
    grid[2586:2683] = [2]+[0]*96
    # These are ten pending cards on the screen. None may be picked individually.
    grid[322:706] = [x for cid in ids[3:] for x in (1,cid,0,0,0,0)] + [0]*324
    grid[1769] = 0
    grid[2968:3114] = [1]+[0]*145
    return grid,leave


class PandoraMixin:
    def step(self, action_id, *, frame_id, action_version):
        with self._lock:
            prior = self._current
            if prior is not None and prior.page == GRID:
                source, raw, leave, cards = self._pandora
                if (frame_id != prior.frame_id or self._raw is not raw or raw is not self._source._current
                        or self._legacy._source is not source or self._inner._current is not source
                        or self._source._env.steps != 1 or current_deck(self) != cards):
                    raise StaleFrameError("Pandora's confirmation has expired")
                if action_version != POLICY_VERSION:
                    raise InterfaceMismatch("Expected A193")
                if isinstance(action_id,bool) or not isinstance(action_id,Integral) or action_id != 172:
                    raise UnverifiedSemanticsError("Only the Pandora confirmation is available")
                result = page(source,"NEOW_RESULT",leave,{110})
                frame = self._sync(self._legacy._cost_projection(self._legacy._version(result)), None)
                self._pandora = None
                self._current = replace(frame,policy_mask=frame.supported_actions,action_gaps=())
                return self._current

            after = super().step(action_id,frame_id=frame_id,action_version=action_version)
            if (prior is None or prior.page != "NEOW_OFFERS" or action_id != 113 or prior.engine_steps
                    or after.page != "NEOW_RESULT_UNVERIFIED"):
                return after
            _,proof = project(prior, "NEOW_OFFERS")
            source, raw = self._legacy._source, self._raw
            if proof is None or not proof.game_legal_mask[113] or source.state.vector[32] != BOX:
                return after
            cards = current_deck(self)
            staged = pages(prior.state.vector, source.state.vector, cards)
            if staged is None:
                return after
            require(source is self._inner._current and raw is self._source._current and raw.state.vector == source.state.vector
                    and self._current is after and self._legacy._current is self._bound and not (source.done or after.done)
                    and source.page == "DELEGATED" and prior.action_version == after.action_version == POLICY_VERSION
                    and raw.engine_steps == source.engine_steps == after.engine_steps == self._source._env.steps == 1
                    and len(raw.packet_sha256) == 64 and raw.packet_sha256 == raw.choice_metadata["packet_sha256"],
                    "Pandora must be bound to the original map settlement")
            grid, leave = staged
            mask = tuple(i == 172 for i in range(len(after.supported_actions)))
            self._pandora = source, raw, leave, cards
            self._current = replace(after,frame_id=str(uuid4()),page=GRID,state=replace(after.state,vector=tuple(grid)),
                                    supported_actions=mask, policy_mask=mask, action_gaps=())
            return self._current
