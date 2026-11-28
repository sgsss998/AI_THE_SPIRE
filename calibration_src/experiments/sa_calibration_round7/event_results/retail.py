"""Re-execute the signed public command journals and compare all inventory at four original boundaries."""
from pathlib import Path
from experiments.common_relic193.pools import core_pools
from experiments.reward_frontier_640.pair import potion
from experiments.event_result_frontiers193.verify import bracket, FIXTURES
from experiments.ordinary_reward_inventory193.verify import deck as native_deck, lines
from experiments.sa_calibration_round6.reference import ROOT,write,sha
from experiments.shining_result_frontiers193.retail import CASES as SHINING
from ..wall.verify import legal,step
from . import candidate,session

HERE=Path(__file__).resolve().parent


def fixture(name,run,seed):
    path=ROOT/'native_runtime'/run
    journal=path/'fish_audit/commands.jsonl'
    records=lines(journal)
    e=candidate.make_engine()
    s=candidate.make_session(e)
    f=s.reset(seed)
    frames={}
    for i,row in enumerate(records):
        assert row['status']=='observed_transition' and row['aid'] in legal(f)
        if i==len(records)-2:
            frames['offer']=f
        if i==len(records)-1:
            frames['settled_leave']=f
            frames['first_leave']=f
        f=step(s,f,row['aid'])
    frames['map']=f
    assert frames['first_leave'].page=='EVENT_RESULT' and 110 in legal(frames['first_leave'])
    assert f.state.vector[6]==5 and f.engine_steps==frames['settled_leave'].engine_steps
    checks=[]
    for key,f in frames.items():
        snap,raw=bracket(path,key)
        original=snap['raw']['game_state']
        v=f.state.vector
        assert tuple(v[:6])==(raw['player']['hp'],raw['player']['max_hp'],raw['gold'],raw['floor'],raw['act'],20)
        assert tuple(v[:6])==tuple(original[n] for n in ('current_hp','max_hp','gold','floor','act','ascension_level'))
        assert native_deck(v,e._source._backend)==[(c['id'],c['times_upgraded']) for c in raw['master_deck']]
        actual=[(c['id'],c['counter']) for c in raw['relics']]
        ids={session.relic_id(k):n for k,n in core_pools()[0].items()}
        assert [(ids[k],n) for k,n in session.relics(v)]==[(k,max(n+1,0)) for k,n in actual]
        pots=[x['id'] for x in raw['potions']]
        assert list(pots)==[x['id'] for x in original['potions']]
        assert [potion(e._source._backend,x) for x in v[17:17+int(v[16])]] == [k.replace(' ','') for k in pots]
        if key in ('first_leave','settled_leave'):
            assert original['choice_list']==['leave']
        checks.append(dict(stage=key,resources=list(v[:3]),deck_size=v[22],relics=actual,
                           original_potions=pots,original_record=snap['raw']['capture_alignment']['native_record_sequence']))
    return dict(event=name,seed=seed,command_count=len(records),journal_sha256=sha(journal),points=checks)


def main():
    cases={**FIXTURES,'Shining Light':(SHINING[-1][0],8000022),
           'Big Fish Box Snecko Skull':('compact_fixture_big_fish_box_seed5000003',5000003),
           'Big Fish Box Omamori':('compact_fixture_big_fish_omamori_seed6000020',6000020)}
    result=[fixture(k,*v) for k,v in cases.items()]
    write(HERE/'RETAIL.json',result)
    print([(r['event'],r['command_count']) for r in result])


if __name__=='__main__':
    main()
