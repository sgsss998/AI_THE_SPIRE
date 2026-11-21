"""Expose the paid, settled two-card Neow picker at its next player decision."""
from dataclasses import replace

from experiments.action193_grid.session import witness
from experiments.neow_transform_two193.kernel import rules
from experiments.neow_transform_two193.session import DECK, ROWS
from silent_env.interface import InterfaceMismatch


class NeowEngineMixin:
    """The curse is an asynchronous obtain effect. Present its settled deck, keeping the original selectable rows."""

    def __init__(self, *args, neow_curse_timing='settled', **kwargs):
        if neow_curse_timing not in ('settled', 'fast'):
            raise ValueError('Expected settled or fast Neow timing')
        self.neow_curse_timing = neow_curse_timing
        super().__init__(*args, **kwargs)

    def _grid_page(self):
        frame = super()._grid_page()
        picker = self._transform
        if picker.get('cost') != 5 or self.neow_curse_timing != 'fast' or picker['grid_inputs'] >= 2:
            return frame
        # Seed 46 accepted its first choice before the curse's obtain effect.
        # Only its original deck and the separately frozen selectable references were visible.
        vector = list(frame.state.vector)
        vector[22] = vector[1763] = 13
        vector[DECK+26:DECK+28] = [0, 0]
        vector[2587+13] = 0
        self._current = replace(frame, state=replace(frame.state, vector=tuple(vector)))
        return self._current

    def _choose(self, slot):
        if self._transform.get('cost') == 5:
            self._transform['grid_inputs'] += 1
        return super()._choose(slot)

    def _available(self, frame):
        frame = super()._available(frame)
        if (frame.page != 'NEOW_OFFERS' or frame.engine_steps != 0
                or frame.state.vector[334:340] != (9, 17, 5, 0, 0, 1)
                or self._raw is not self._source._current or not self._source.verified_opening()
                or not rules().eligible(self._source._env, 5)):
            return frame
        actions = list(frame.supported_actions)
        actions[112] = True
        self._current = replace(frame, supported_actions=tuple(actions),
                                action_gaps=tuple(g for g in frame.action_gaps if g != 'kernel_neow_outcome_unverified_slot_2'))
        return self._current

    def _open(self, before):
        if before.state.vector[336] != 5:
            return super()._open(before)
        source = self._source
        env = source._env
        previous = self._raw
        if (previous is not source._current or self._legacy._current is not self._bound
                or not rules().eligible(env, 5)):
            raise InterfaceMismatch('Stale curse-cost two-card offer')
        self._current = None
        if not rules().open(env, 5):
            raise InterfaceMismatch('Neow did not open the two-card picker')
        raw, base = self._refresh(previous, 83)
        vector, opening = base.state.vector, before.state.vector
        live = witness().describe(env)
        cards = tuple((int(c), int(upgrade), int(position)) for c,upgrade,position in live['rows'])
        if not (vector[:6] == opening[:6] and vector[6:10] == (4,0,10,0)
                and vector[22:24] == (14,1) and vector[26:29] == (1,2,0)
                and vector[DECK:DECK+26] == opening[DECK:DECK+26]
                and vector[DECK+26] > 0 and vector[DECK+27:898] == (0,)*(898-DECK-27)
                and vector[32:112] == opening[32:112]):
            raise InterfaceMismatch('The settled cost must append exactly one card to the original deck')
        if not (live['task']==1 and live['required']==2 and live['selected']==0 and live['steps']==1
                and tuple(position for _,_,position in cards)==tuple(range(1,13))
                and raw.packet_sha256 and raw.packet_sha256==raw.choice_metadata['packet_sha256']):
            raise InterfaceMismatch('The selectable original instances must exclude the acquired curse')
        for index,(card,upgrade,position) in enumerate(cards):
            row=raw.choice_metadata['choices'][index]
            if not (vector[DECK+2*position:DECK+2*position+2] == (card+1,upgrade)
                    and vector[ROWS+6*index:ROWS+6*index+6] == (1,card+1,upgrade,0,0,1)
                    and row['slot']==index and row['sim_action']==81+index and row['legal'] and raw.backend_mask[81+index]):
                raise InterfaceMismatch('The visible choice row does not address its permanent card')
        self._transform = dict(source=raw, base=base, cards=cards, first=None, cost=5, grid_inputs=0)
        return self._grid_page()
