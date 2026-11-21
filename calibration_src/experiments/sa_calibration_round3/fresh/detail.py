"""Read captured evidence and repeat the frozen replay with extra public checks.
This never dispatches to the original game or changes the release.
"""
from datetime import datetime
from pathlib import Path
import json
from . import replay as r

FIELDS={b['name']:{f['name']:b['offset']+i for i,f in enumerate(b['fields'])} for b in r.schema()['base_blocks']}
POWER={'Dexterity':'dexterity','Draw Card':'draw_card_next_turn','Vulnerable':'vulnerable','Weakened':'weak','Anger':'enrage','Strength':'strength'}
BASE_COMPARE=r.compare

def detailed(f,e,snap):
    out=BASE_COMPARE(f,e,snap);v=f.state.vector;g=snap['raw']['game_state'];c=g.get('combat_state');b=e._source._backend
    out['state_vector_3122']=list(map(int,v));assert len(v)==3122
    extra={};other={};boundary=[]
    if c and int(v[7]):
        def powers(items):
            assert all(p['id'] in POWER for p in items),items
            return {POWER[p['id']]:int(p['amount']) for p in items if p['amount']}
        extra['player_powers']={k.removeprefix('status_'):int(v[i]) for k,i in FIELDS['player'].items() if k.startswith('status_') and int(v[i])}
        other['player_powers']=powers(c['player']['powers'])
        extra['monster_powers']=[];other['monster_powers']=[]
        for j,m in enumerate(c['monsters']):
            extra['monster_powers'].append({k.removeprefix('status_'):int(v[i+j*52]) for k,i in FIELDS['monsters'].items() if k.startswith('status_') and int(v[i+j*52])})
            other['monster_powers'].append(powers(m['powers']))
        for name,offset,key in [('draw_multiset',1313,'draw_pile'),('discard_order',1441,'discard_pile'),('exhaust_order',1569,'exhaust_pile')]:
            mm=[[b.CARD_IDS[int(v[i])-1],int(v[i+1])] for i in range(offset,offset+128,2) if v[i]]
            nn=[r.card(x) for x in c[key]]
            if key=='draw_pile':mm=sorted(mm);nn=sorted(nn)
            extra[name]=mm;other[name]=nn
        extra['living_intent_damage_hits']=[];other['living_intent_damage_hits']=[]
        for j,m in enumerate(c['monsters']):
            if m['current_hp']<=0 or m['is_gone']:continue
            extra['living_intent_damage_hits'].append([int(v[993+j*52+8]),int(v[993+j*52+9])])
            # Only attack intents expose a positive hit count; native uses 0 on nonattacks.
            other['living_intent_damage_hits'].append([int(m['move_adjusted_damage']),int(m['move_hits'])])
    # Simulator-only hidden observation; original oracle deliberately stores an unordered draw multiset.
    suffix=list(map(int,v[3118:3122]));assert suffix[2] in (0,1,2) and suffix[3] in (0,1)
    if suffix[2]==2:
        assert suffix[0]>0 and int(v[7]) and not f.done
        assert [b.CARD_IDS[suffix[0]-1],suffix[1]] in extra.get('draw_multiset',[])
    elif suffix[2]==1:assert int(v[7]) and not f.done and not extra.get('draw_multiset',[])
    else:assert not int(v[7]) or f.done
    assert suffix[3]==0 # This untouched natural route owns no tea relic.
    out['additional_public_comparison']=dict(model=extra,original=other,differences={k:dict(model=extra[k],original=x) for k,x in other.items() if extra[k]!=x})
    out['hidden_observation']=dict(suffix=suffix,draw_top_original_equivalence='unverified: original capture is unordered',tea_expected_zero_no_tea_relic=True)
    return out

def main():
    r.compare=detailed
    result=r.run(release_module='experiments.sa_calibration_round3.release')
    result['detail_scope']='All represented nonzero player/monster powers; public draw multiset, discard/exhaust order and living intent damage/hits. Full 3122 model vector is retained, not asserted equivalent to native.'
    dest=r.HERE/'details'/(datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    dest.mkdir(parents=True,exist_ok=False)
    (dest/'RUNNER_SNAPSHOT.py').write_bytes(Path(__file__).read_bytes())
    (dest/'REPLAY_SNAPSHOT.py').write_bytes(Path(r.__file__).read_bytes())
    (dest/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    diff=[];frames={}
    for row in result['trace']:
        for side in ('before','after'):
            if side not in row:continue
            key=(row['native_session'],row[side+'_sequence']);frames[key]=row[side]
            d=row[side]['additional_public_comparison']['differences']
            if d:diff.append(dict(index=row['index'],phase=side,differences=d))
    print(json.dumps(dict(path=str(dest),unique_frames=len(frames),extra_mismatch_frames=sum(bool(x['additional_public_comparison']['differences']) for x in frames.values()),differences=diff),ensure_ascii=False))
if __name__=='__main__':main()
