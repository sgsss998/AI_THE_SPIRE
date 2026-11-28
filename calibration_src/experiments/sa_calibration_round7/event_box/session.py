"""Settle an original box's delayed card hooks and its inventory changes in the same public decision."""
from dataclasses import replace
from experiments.sa_calibration_round7.event_results import session as event

relic_id=event.relic_id
NEW={relic_id(k) for k in ('TOXIC_EGG','MOLTEN_EGG','FROZEN_EGG','THE_COURIER','DU_VU_DOLL',
                          'SUNDIAL','POTION_BELT','CERAMIC_FISH','DARKSTONE_PERIAPT')}
# These held relics have no effect on receiving Regret or creating the new relic, except the explicitly handled effects.
HELD={relic_id(k) for k in ('RING_OF_THE_SNAKE','WRIST_BLADE','SNECKO_EYE','OMAMORI','CERAMIC_FISH','DARKSTONE_PERIAPT')}
POTION_BELT=relic_id('POTION_BELT')
DOLL=relic_id('DU_VU_DOLL')
SUNDIAL=relic_id('SUNDIAL')


def settled(v,w):
    if (v[4:10]!=(1,20,1,0,3,event.IDS['Big Fish']+1) or v[2968:2970]!=(2,0)
            or v[334:340]!=(8,2,0,0,0,1) or w[3:6]!=v[3:6] or w[6:10]!=(5,0,3,0)
            or not 1<=v[22]<=96 or not 1<=w[22]<=96
            or not 1<=v[23]<40 or w[23]!=v[23]+1
            or w[1762:1764]!=(w[23],w[22]) or v[1762:1764]!=(v[23],v[22])):
        return None
    old=event.relics(v)
    new=event.relics(w)
    found,charge=new[-1]
    held=dict(old)
    if not set(held)<=HELD or found not in NEW or found in held:
        return None
    # Omamori's check runs while the card effect is constructed. Card pickup callbacks
    # run later and iterate the player's then-current relic list, including the new item.
    blocked=held.get(event.OMAMORI,0)>1
    if (new[:-1]!=tuple((k,n-int(k==event.OMAMORI and blocked)) for k,n in old)
            or event.deck(w)!=event.deck(v)+(() if blocked else ((event.REGRET,0),))):
        return None
    expected_charge=0
    if found==DOLL:
        expected_charge=1+sum(event.TYPES[str(k-1)]=='CURSE' for k,_ in event.deck(w))
    elif found==SUNDIAL:
        expected_charge=1
    if charge!=expected_charge:
        return None
    both=set(held)|{found}
    gain_hp=6*int(event.DARKSTONE in both and not blocked)
    gain_gold=9*int(event.CERAMIC in both and not blocked)
    if w[:3]!=(v[0]+gain_hp,v[1]+gain_hp,v[2]+gain_gold):
        return None
    if (w[16]!=v[16]+2*int(found==POTION_BELT) or w[16]>5 or v[17:22]!=w[17:22]
            or v[1771]!=v[16] or w[1771]!=w[16]):
        return None
    stable=((10,16),(24,26),(112,322),(898,1761),(1764,1769),(1770,1771),(1772,2586),(2587,2683),
            (2748,2770),(2775,2968),(3114,len(v)))
    if any(v[a:b]!=w[a:b] for a,b in stable):
        return None
    if any(w[706+2*int(w[22]):898]) or any(w[32+2*int(w[23]):112]):
        return None
    out=list(v)
    for a,b in ((0,3),(16,24),(32,112),(706,898),(1762,1764)):
        out[a:b]=w[a:b]
    out[1771]=w[1771]
    if w[2770]==2:
        out[2770:2775]=w[2770:2775]
    out[322:706]=[8,0,0,0,0,1]+[0]*378
    out[1769]=1
    out[2683:2748]=[2]+[0]*64
    out[2968:3114]=[2,1]+[0]*144
    return tuple(out)


class DelayedBoxResult:
    def _capture(self,source):
        transition=self._transition
        out=super()._capture(source)
        if not transition or not self._event_pending or out.done or out.page!='EVENT_RESULT_UNVERIFIED':
            return out
        before,action,offer=transition
        if offer is None or (offer.name,offer.physical,action)!=('Big Fish',2,83):
            return out
        if not getattr(self._delegate._session,'ordered_fish_bound',False):
            return out
        event.require(source is self._delegate._current and source.frame_id==self._source_id
                      and source.engine_steps==out.engine_steps==before.engine_steps+1,
                      'Missing original current box transaction')
        vector=settled(offer.vector,source.state.vector)
        if vector is None:
            return out
        gap=event.EMPTY_RESULT if vector[16:22]==(2,0,0,0,0,0) else 'event_result_full_mask_unverified'
        self._current=replace(out,state=replace(out.state,vector=vector),page='EVENT_RESULT',
                              policy_mask=None,supported_actions=event.LEAVE,action_gaps=(gap,))
        return self._current
