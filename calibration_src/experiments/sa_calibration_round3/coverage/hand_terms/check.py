"""Two natural-prefix upgrade cases and the historical same-hand Skill Potion fee fixture."""
from pathlib import Path
from hashlib import sha256
import json
from experiments.sa_calibration_round3 import release
from experiments.sa_calibration_round1.privileged.session import enrich
from experiments.sa_calibration_round2.frontiers.verify import ARCHIVE,run
from silent_env.native_compare import load_native_capture,json_hash
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def read(p):return json.loads(p.read_bytes())
def sha(p):return sha256(p.read_bytes()).hexdigest()
def step(s,f,a):return s.step(a,frame_id=f.frame_id,action_version=f.action_version)
def records(p):return {r['sequence']:r for r in map(json.loads,p.open())}
def receipt(p,a,b):
    rpath=p.parent/'results'/f"{b['pending_request_id_at_receipt']}.json"
    r=read(rpath)
    assert r['status']=='observed_transition'
    assert r['before']['raw_hash']==json_hash(a['raw'])==a['raw_hash'] and r['after']['raw_hash']==json_hash(b['raw'])==b['raw_hash']
    return r,rpath
def witness(p,point):
    src=point['raw'].get('capture_alignment')
    if not src:return None
    folder=p.parents[3];n=folder/'native_oracle'/src['native_session']/'native_oracle.jsonl'
    scope=dict(native_session=src['native_session'],bridge_session=p.parent.name,bridge_sequence=point['sequence'],native_after_sequence=0,native_through_sequence=src['native_record_sequence'])
    paired=load_native_capture(n,src['capture_id'],bridge_log=p,scope=scope)
    assert paired.evidence['exact_capture_binding'] and paired.evidence['bracket_verified']
    assert paired.evidence['bridge_raw_sha256']==point['raw_hash']
    return paired.payload

def view(point,f,e,focus):
    game=point['raw']['game_state'];cs=game['combat_state'];v=f.state.vector
    assert len(v)==3122 and len(f.supported_actions)==193
    ids=e._source._backend.CARD_IDS;hand=cs['hand']
    model_hand=[[ids[int(v[k])-1],int(v[k+1])] for k in range(1253,1313,6) if v[k]]
    assert model_hand==[[c['id'],c['upgrades']] for c in hand]
    pairs={}
    for name,native,model in [('energy',cs['player']['energy'],v[901]),('block',cs['player']['block'],v[900]),('player_hp',game['current_hp'],v[0]),
        ('monster_hp',[m['current_hp'] for m in cs['monsters']],[int(v[k+1]) for k in range(993,1253,52) if v[k]]),
        ('piles',[len(cs[k]) for k in ('draw_pile','discard_pile','exhaust_pile')],list(map(int,v[1765:1768])))]:
        assert native==model,(name,native,model);pairs[name]=native
    rows=[]
    for i,c in enumerate(hand):
        if c['id']!=focus:continue
        k=1253+6*i;ka=1775+4*i
        assert c['is_playable']==bool(v[k+3]) and c['has_target']==bool(v[k+4])
        if c['has_target']:
            actions=[10*(t+1)+i for t,m in enumerate(cs['monsters']) if m['current_hp']>0 and not m['is_gone'] and c['is_playable']]
        else:actions=[i] if c['is_playable'] else []
        flags=[a for a in range(i,60,10) if f.supported_actions[a]]
        assert actions==flags
        rows.append(dict(slot=i,id=c['id'],uuid=c['uuid'],upgrades=c['upgrades'],cm_cost=c.get('cost'),cm_turn_cost=c.get('cost_for_turn'),playable=c['is_playable'],target=c['has_target'],
                    raw_hand_start=k,dynamic_start=ka,model_hand_fields=list(v[k:k+6]),attributes=list(v[ka:ka+4]),actions=flags))
    return dict(seq=point['sequence'],sha=point['raw_hash'],rows=rows,hand=model_hand,player_enemy_piles=pairs)

def check_pair(p,b,a,f0,f1,e,focus,provenance):
    before=view(b,f0,e,focus);after=view(a,f1,e,focus)
    r,rpath=receipt(p,b,a);words=r['command'].split();slot=int(words[1])-1;target=int(words[2]) if len(words)==3 else None
    row=next(x for x in before['rows'] if x['slot']==slot)
    assert r['action_id']==(slot if target is None else slot+10*(1+target)) and r['action_id'] in row['actions']
    assert row['uuid'] not in [c['uuid'] for c in a['raw']['game_state']['combat_state']['hand']]
    assert all(c['uuid'] in [c['uuid'] for c in a['raw']['game_state']['combat_state']['hand']] for c in before['rows'] if c['uuid']!=row['uuid'])
    assert row['uuid'] in [c['uuid'] for c in a['raw']['game_state']['combat_state']['discard_pile']]
    native=witness(p,b) if 'capture_alignment' in b['raw'] else None
    if native:
        for rr in before['rows']:
            n=native['hand'][rr['slot']];icon=n['public_cost'];assert icon['available']
            assert n['uuid']==rr['uuid'] and n['times_upgraded']==rr['upgrades']
            assert int(icon['text'])==int(rr['model_hand_fields'][2])==int(rr['attributes'][1]) and int(rr['attributes'][3])&2
            rr['original_icon']=icon['text'];rr['original_internal_turn_cost']=n['cost_for_turn']
        legal=native['independent_legal_actions']
        independent=legal['status']
        if 'play' in legal['known_domains']:
            for rr in before['rows']:
                plays=[z for z in legal['semantic_actions'] if z.get('type')=='play' and z.get('object_uuid')==rr['uuid']]
                observed=sorted(z['card_index']+(0 if z['target_slot'] is None else 10*(1+z['target_slot'])) for z in plays)
                assert observed==rr['actions'];rr['independent_original_actions']=observed
    else:independent='historical CommunicationMod only'
    fee=before['player_enemy_piles']['energy']-after['player_enemy_piles']['energy']
    assert fee==int(row['model_hand_fields'][2])
    return dict(source=str(p.relative_to(ROOT.parent)),source_sha=sha(p),source_kind=provenance,
                raw=[b['sequence'],a['sequence']],request=r['request_id'],request_sha=sha(rpath),command=r['command'],aid=r['action_id'],
                slot=slot,target_slot=target,selected_uuid=row['uuid'],energy_spent=fee,independent_oracle_status=independent,before=before,after=after)

def short_run(name,seq,focus,fixture):
    directory=ROOT/'native_runtime'/name;p=next(directory.glob('bridge/sessions/*/raw.jsonl'));d=records(p)
    e=release.make_engine();s=release.make_session(e)
    if fixture:
        # The public wrapper only exposes normal reset. Initialize its actual owner
        # through the original directed combat config, then apply the published projections.
        owner=s.delegate.base
        base=owner.reset_fixture(dict(op='reset_fixture',seed='1',fixture=read(directory/'fixture_config.json')))
        f=s._publish(enrich(base,e,owner))
        source='archived original controlled combat; internal fixture initialization; formal public step and S3122 projections'
    else:
        f=s.reset(35)
        source='archived original read-only 99-gold assertion; regular formal reset(seed=35), normal gameplay entire prefix'
    for i in range(3,seq):
        r,_=receipt(p,d[i],d[i+1]);f=step(s,f,r['action_id'])
    r,_=receipt(p,d[seq],d[seq+1]);fnext=step(s,f,r['action_id'])
    result=check_pair(p,d[seq],d[seq+1],f,fnext,e,focus,source)
    if fixture:
        follow,fp=receipt(p,d[seq+1],d[seq+2]);assert follow['action_id']==170
        restored=step(s,fnext,170)
        later=view(d[seq+2],restored,e,focus);n=witness(p,d[seq+2])
        row,=[c for c in later['rows'] if c['uuid']==result['selected_uuid']]
        badge=n['hand'][row['slot']]['public_cost']
        assert badge['available'] and badge['text']=='1' and row['model_hand_fields'][2]==row['attributes'][1]==1
        result['same_original_uuid_next_turn']=dict(seq=seq+2,uuid=row['uuid'],slot=row['slot'],original_icon=badge['text'],model_cost=row['model_hand_fields'][2],receipt_sha=sha(fp))
    return result

def normal_other():
    points={};after={}
    def old(k,g,e,s,f):
        if k==286:points['state']=f
    def new(k,g,e,s,f):
        if k==286:after.update(e=e,f=f)
    prefix=run(release,until=287,on_frame=old,on_after=new)
    assert prefix['last_applied_original']==287 and prefix['stop'] is None
    p=ARCHIVE/'raw.jsonl';d=records(p)
    out=check_pair(p,d[286],d[287],points['state'],after['f'],after['e'],'Strike_G','historical natural seed 54072726; regular formal reset, original actions with explicit UI acknowledgements')
    out['normal_actions_through_observed_output']=prefix['actions']
    return out

def main():
    cases=dict(upgraded_play=short_run('compact_fixture_ordinary_reward_seed35',8,'Strike_G',False),
               ordinary_play=normal_other(),temporary_cost=short_run('compact_fixture_skill_001',5,'Backflip',True))
    different=cases['temporary_cost']['before']['rows']
    assert [r['original_icon'] for r in different]==['1','0'] and cases['temporary_cost']['energy_spent']==0
    assert cases['upgraded_play']['before']['rows'][0]['upgrades']==1
    assert cases['upgraded_play']['before']['player_enemy_piles']['monster_hp']==[48] and cases['upgraded_play']['after']['player_enemy_piles']['monster_hp']==[39]
    assert cases['ordinary_play']['before']['player_enemy_piles']['monster_hp']==[10,29] and cases['ordinary_play']['after']['player_enemy_piles']['monster_hp']==[4,29]
    (HERE/'RESULTS.json').write_text(json.dumps(dict(cases=cases,formal_source_sha=sha(ROOT/'experiments/sa_calibration_round3/release.py'),
          search_sha=sha(HERE/'SEARCH.json'),new_games=0,training_updates=0),ensure_ascii=False,indent=2)+'\n')
    print([(k,r['raw'],r['aid'],r['energy_spent']) for k,r in cases.items()])

if __name__=='__main__':main()
