from experiments.common_relic193.pools import core_pools
from experiments.ordinary_reward_inventory193.verify import deck,lines
from experiments.reward_frontier_640.pair import potion
from experiments.sa_calibration_round6.reference import ROOT,write,sha
from ..wall.verify import step,legal
from . import gifts, verify, gift_candidate

NAMES={gifts.event.relic_id(k):v for k,v in core_pools()[0].items()}


def match(engine,frame,observation):
    g=observation['raw']['game_state'];v=frame.state.vector
    ids=engine._source._backend
    assert tuple(v[:6])==tuple(g[k] for k in ('current_hp','max_hp','gold','floor','act','ascension_level'))
    assert deck(v,ids)==[(x['id'],x['upgrades']) for x in g['deck']]
    assert [(NAMES[k],n) for k,n in gifts.event.relics(v)]==[(x['id'],max(0,x['counter']+1)) for x in g['relics']]
    assert [potion(ids,n) for n in v[17:17+int(v[16])]]==[x['id'].replace(' ','') for x in g['potions']]
    assert g['screen_type']=={1:'EVENT',2:'COMBAT_REWARD',4:'GRID',5:'MAP',10:'CARD_REWARD'}[v[6]]
    if g['screen_type']=='COMBAT_REWARD':
        rows=[v[i:i+6] for i in range(322,706,6) if v[i] and not v[i+4]]
        view=[(x['reward_type'], x['gold'] if x['reward_type']=='GOLD' else x['potion']['id'].replace(' ','') if x['reward_type']=='POTION'
               else x['relic']['id'] if x['reward_type']=='RELIC' else None) for x in g['screen_state']['rewards']]
        assert [(('GOLD',r[1]) if r[0]==4 else ('POTION',potion(ids,r[1])) if r[0]==3 else ('RELIC',NAMES[r[1]]) if r[0]==2
                 else ('CARD',None) if r[0]==15 else (None,None)) for r in rows]==view
    if g['screen_type']=='CARD_REWARD':
        cards=g['screen_state']['cards']
        assert [(ids.CARD_IDS[int(v[i+1])-1],v[i+2]) for i in range(322,706,6) if v[i]==1]==[(x['id'],x['upgrades']) for x in cards]
    if g['screen_type']=='GRID':
        cards=g['screen_state']['cards']
        assert [(ids.CARD_IDS[int(v[323])-1],v[324])]==[(x['id'],x['upgrades']) for x in cards]
        assert legal(frame)==[172] and g['screen_state']['confirm_up']
    return dict(page=g['screen_type'],floor=int(v[3]),wallet=int(v[2]),hp=int(v[0]),maximum_hp=int(v[1]),
                deck_size=int(v[22]),menu=g.get('choice_list'),legal=legal(frame),capture_sha256=observation['raw_hash'])


def journal(seed,folder):
    path=ROOT/'native_runtime'/folder/'gift_audit/commands.jsonl'
    records=lines(path)
    e=gift_candidate.make_engine();s=gift_candidate.make_session(e);f=s.reset(seed)
    checkpoints=[]
    for row in records:
        checkpoints.append(match(e,f,row['before']))
        aid=row['aid']
        assert row['status']=='observed_transition' and aid in legal(f)
        f=step(s,f,aid)
        match(e,f,row['after'])
    checkpoints.append(match(e,f,records[-1]['after']))
    assert f.state.vector[6]==5
    return dict(seed=seed,fixture=folder,journal_sha256=sha(path),inputs=len(records),checkpoints=checkpoints)


def main():
    facts=[journal(31,'compact_fixture_neow_bell_seed31'),journal(1000036,'compact_fixture_neow_tinyhouse_seed1000036')]
    write(verify.HERE/'RETAIL.json',facts)
    print([(r['inputs'],len(r['checkpoints'])) for r in facts])


if __name__=='__main__':
    main()
