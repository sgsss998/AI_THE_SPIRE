"""Pair original purchases and boundary cases with actual public R5 sessions."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from experiments.sa_calibration_round5 import release
from experiments.public_shop.session import row_at
from silent_env.runtime import StaleFrameError,UnverifiedSemanticsError
from .prefix import HERE,prefix,advance
from .native import ITEMS,NATIVE,read,ledger

def sha(p):return sha256(p.read_bytes()).hexdigest()
def norm(x):return ''.join(c for c in x.lower() if c.isalnum())
def controls(f):return [i for i,x in enumerate(f.supported_actions) if x]
def compare(e,f,snap):
    g=snap['raw']['game_state'];v=f.state.vector;b=e._source._backend
    assert tuple(v[:6])==(g['current_hp'],g['max_hp'],g['gold'],g['floor'],g['act'],g['ascension_level'])
    deck=[[b.CARD_IDS[int(v[i])-1],int(v[i+1])] for i in range(706,898,2) if v[i]]
    assert deck==[[c['id'],c['upgrades']] for c in g['deck']]
    belt=[norm(b.POTION_NAMES[int(a)-1]) if a else None for a in v[17:17+int(v[16])]]
    assert belt==[None if x['id']=='Potion Slot' else norm(x['name']) for x in g['potions']]
    relics=[norm(b.RELIC_NAMES[int(v[i])-1]) for i in range(32,112,2) if v[i]]
    assert relics==[norm(x['name']) for x in g['relics']]
    state=dict(gold=g['gold'],hp=g['current_hp'],deck_count=len(deck),relics=relics,potions=belt,page=f.page,
               original_page=g['screen_type'],original_raw_sha256=snap['raw_hash'],S_sha256=sha256(json.dumps(v,separators=(',',':')).encode()).hexdigest(),actions=controls(f))
    if g['screen_type']=='SHOP_SCREEN':
        rows=[row_at(v,i) for i in range(64) if row_at(v,i)[0]]
        expected=[]
        store=g['screen_state']
        for typ in ('cards','relics','potions'):
            opts=store[typ]
            expected.extend((norm(x['id'] if typ=='cards' else x['name']),x['price']) for x in opts)
        actual=[]
        for k,ident,lvl,price,_,affordable in rows:
            if k==11:continue
            names={1:b.CARD_IDS,2:b.RELIC_NAMES,3:b.POTION_NAMES}[k]
            actual.append((norm(names[int(ident)-1]),int(price)))
            assert affordable==int(g['gold']>=price)
        assert Counter(expected)==Counter(actual),(expected,actual)
        native_count=len(g.get('choice_list',[]))
        assert int(v[1769])==sum(int(x[-1]) for x in rows)==native_count,(g['gold'],v[1769],native_count)
        state.update(shop_rows_match=True,original_affordable=native_count,model_affordable=int(v[1769]),
                     model_supported_shop_choices=sum(bool(f.supported_actions[i]) for i in range(110,110+native_count)))
    if g['screen_type']=='GRID':
        cards=g['screen_state']['cards']
        assert [(b.CARD_IDS[int(row_at(v,i)[1])-1],int(row_at(v,i)[2])) for i in range(len(cards))]==[(c['id'],c['upgrades']) for c in cards]
        assert v[2684:2684+len(cards)]==tuple(203+i for i in range(len(cards)))
        state['mirror_grid_size']=len(cards)
    return state

def measure():
    results={}
    costs=dict(mirror=172,flex=56,fear=55,weak=57)
    for label in ITEMS:
        e,s,f=prefix(release,50);out=NATIVE/('compact_native_r5_shop_'+label+'_001')/'shop_check'
        records=ledger(out/'choices.jsonl');steps=[]
        for r in records:
            if r['note']=='open':continue
            start=compare(e,f,r['before'])
            previous=f;f=advance(s,f,r['aid'])
            try:advance(s,previous,r['aid'])
            except StaleFrameError:pass
            else:raise AssertionError('Double submission of the old frame succeeded')
            end=compare(e,f,r['after'])
            steps.append(dict(action=r['aid'],command=r['command'],label=r['note'],before=start,after=end,stale_rejected=True,
                             model_missing_listed_actions=sorted(set(r['legal'])-set(start['actions'])),model_extra_actions=sorted(set(start['actions'])-set(r['legal']))))
        assert steps[0]['before']['gold']==229 and steps[0]['after']['gold']==229-costs[label]
        assert steps[0]['before']['actions']==[i for i in range(110,122)]+[178]
        record=dict(items=steps,initial_offer=ITEMS[label],initial_cost=costs[label],same_original_save=read(out/'RESTORE_INPUT.json')['saves']['THE_SILENT.autosave']['sha256'])
        if label=='mirror':
            proof=next(q for q in records if q['note']=='copy_second_strike')
            old=proof['before']['raw']['game_state'];new=proof['after']['raw']['game_state']
            c=old['screen_state']['cards'][proof['aid']-110];strikes=[x for x in old['deck'] if x['id']=='Strike_G']
            assert strikes[1]['uuid']==c['uuid'] and new['deck'][:-1]==old['deck'] and new['deck'][-1]['id']==c['id']
            assert new['deck'][-1]['uuid'] not in {x['uuid'] for x in old['deck']} and new['deck'][-1]['upgrades']==c['upgrades']
            record['copied']=dict(original_uuid=c['uuid'],new_uuid=new['deck'][-1]['uuid'],originals_preserved=15,aid=proof['aid'])
            assert read(out/'one_gold.json')['raw']['game_state']['gold']==1
        if label=='flex':
            full=read(out/'full_witness.json');frozen=read(out/'full_attempt.json');prev=frozen['before']['raw']['game_state']
            assert prev['gold']==118 and 'weak potion' in prev['choice_list']
            after=full['after']['raw']['game_state']
            assert (after['screen_type'],after['gold'])==('SHOP_ROOM',118) and after['potions']==prev['potions']
            flag=110+prev['choice_list'].index('weak potion')
            assert not f.supported_actions[flag]
            try:advance(s,f,flag)
            except UnverifiedSemanticsError:pass
            else:raise AssertionError('Full inventory sale accepted')
            record['full_slots']=dict(native_control=flag,model_sale_supported=False,original_game_message=full['game_message'],
                                      after_original_gold=118,after_original_potions=[x['id'] for x in after['potions']],original_before_sha256=frozen['before']['raw_hash'],original_later_sha256=full['after']['raw_hash'])
        record['raw']={q.name:sha(q) for q in sorted(out.iterdir()) if q.is_file() and q.suffix in ('.json','.jsonl')}
        results[label]=record
    return dict(parent='R4 c165cd0',formal_interface=release.interface_signature().metadata(),real_seed='2W47ZBJ8TBFMD',
                raw_root_pattern='native_runtime/compact_native_r5_shop_{branch}_001/shop_check',branches=results)
if __name__=='__main__':
    obj=measure(); (HERE/'RESULT.json').write_text(json.dumps(obj,indent=2)+'\n');print('4 original shop branches matched')
