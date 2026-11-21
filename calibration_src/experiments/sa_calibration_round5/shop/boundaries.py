"""Collect the full-inventory rejection and the observed 1-gold shop shelf."""
import sys,time
from pathlib import Path
from native_pilot import bind,libraries,append
from native_runtime import now,write
from .native import NATIVE,read,step

def main(label):
    dest=NATIVE/('compact_native_r5_shop_'+label+'_001')
    out=dest/'shop_check'
    T,_,legal,_,*_=libraries(dest)
    if label=='flex':
        s=Path(read(dest/'bridge/active_session.json')['session_dir'])
        assert read(s/'session.json')['parent_pid']==read(dest/'process.json')['pid']
        tr=T(s,allow_experiment_controls=True)
    else:tr,s,oracle,_=bind(dest,T)
    b=tr.read_current()
    if label=='weak':
        assert b.raw['game_state']['gold']==172 and b.raw['game_state']['potions'][0]['id']=='Weak Potion'
        assert b.raw['game_state']['potions'][0]['can_discard']
        b=step(tr,b,105,legal,out,'discard_purchased_weak')
        assert b.raw['game_state']['potions'][0]['id']=='Potion Slot' and b.raw['game_state']['gold']==172
        write(out/'discard.json',b.as_dict())
    elif label=='mirror':
        g=b.raw['game_state']
        if g['gold']==57:
            assert g['screen_type']=='SHOP_SCREEN' and 'flex potion' in g['choice_list'] and 'quick slash' not in g['choice_list']
            b=step(tr,b,110+g['choice_list'].index('flex potion'),legal,out,'57_less_56_leaves_one')
        else:
            assert '57_less_56_leaves_one' in (out/'choices.jsonl').read_text()

        assert b.raw['game_state']['gold']==1 and not b.raw['game_state'].get('choice_list')
        write(out/'one_gold.json',b.as_dict())
    else:
        status=read(s/'status.json')
        pending=status.get('pending')
        if pending:
            assert pending['phase']=='uncertain' and pending['request_id']==read(out/'full_attempt.json')['receipt']['request_id']
            req=tr.recover_pending(pending['request_id'],'Independently observe original after full potion rack refusal. No new purchase.',timeout=15)
        else:req=tr.query_state(timeout=12)
        write(out/'full_query.json',req.as_dict())
        assert req.after is not None,req.as_dict()
        g=req.after.raw['game_state']
        assert g['gold']==118 and [x['id'] for x in g['potions']]==['SteroidPotion','FearPotion'] and 'weak potion' in g['choice_list']
        assert 'NOT ENOUGH POTION SLOTS' in (dest/'launch.log').read_text()
        write(out/'full_witness.json',dict(at=now(),game_message='NOT ENOUGH POTION SLOTS',after=req.after.as_dict(),mask=legal(req.after.raw)))
        # A native observation proves a failed sale. Its re-query may leave the bridge uncertain.
if __name__=='__main__':main(sys.argv[1])
