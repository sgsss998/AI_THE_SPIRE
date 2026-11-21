"""Measure observed mechanics in the held-out game and link them to actually executed replay actions."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def read(p):return json.loads(p.read_bytes())
def digest(p):return sha256(p.read_bytes()).hexdigest()
def gid(row,phase):return row[phase]['raw']['game_state']
def faces(cards):return [[c['id'],c['upgrades']] for c in cards]
def positions(combat,pile):return {c['uuid']:c for c in combat[pile]}
def hp(combat):return [m['current_hp'] for m in combat['monsters']]
def powers(unit):return {p['id']:p['amount'] for p in unit['powers']}
def ink(g):return next((r['counter'] for r in g['relics'] if r['id']=='InkBottle'),None)

def registry(public,diagnostic):
    official=read(public)
    assert not official['diagnostic_allowed'] and not official['used_kernel'] and official['signature_unchanged']
    result={}
    for kind,data in [('formal',official)]+([('diagnostic',read(diagnostic))] if diagnostic else []):
        assert data['signature']==read(HERE.parent/'INTERFACE.json')
        for r in data['trace']:
            if r['index'] in result or r['status']!='physical_action_replayed' or 'after' not in r:continue
            result[r['index']] = (kind,r)
    return result

def spore_vectors(selected, registry, ledger):
    """Re-execute only the selected diagnostic prefix and inspect the vectors at its original receipt IDs."""
    from types import FunctionType
    from experiments.sa_calibration_round4.fresh import replay
    fixed=read(selected)
    if 143 not in registry:return None
    origins={phase['sequence']:phase for i in (142,143) for phase in (ledger[i-1]['before'],ledger[i-1]['after'])}
    observed={}
    def examine(frame,engine,snapshot):
        checked=replay.compare(frame,engine,snapshot)
        if snapshot['sequence'] in origins and snapshot['raw_hash']==origins[snapshot['sequence']]['raw_hash']:
            v=frame.state.vector
            native=snapshot['raw']['game_state']['combat_state']
            real=dict(vulnerable=powers(native['player']).get('Vulnerable',0),slots=[[m['current_hp'],powers(m).get('Spore Cloud',0),powers(m).get('Strength',0)] for m in native['monsters']])
            simulated=dict(vulnerable=int(v[911]),slots=[[int(v[i+1]),int(v[i+37]),int(v[i+21])] for i in (993,1045)])
            observed[snapshot['sequence']]=dict(raw_hash=snapshot['raw_hash'],status=frame.page,true=real,model=simulated,equal=(real==simulated))
        return checked
    execute=FunctionType(replay.run.__code__,dict(replay.run.__globals__,compare=examine),argdefs=replay.run.__defaults__)
    rerun=execute(limit=143,diagnostic=fixed['diagnostic_allowed'],native_effects=fixed['reconciled_native_physical_effects'])
    assert rerun['signature']==fixed['signature']
    assert len(rerun['trace'])==143
    assert [(r['index'],r['status'],r.get('mapped_aid'),r.get('model_layer')) for r in rerun['trace']]==[(r['index'],r['status'],r.get('mapped_aid'),r.get('model_layer')) for r in fixed['trace'][:143]]
    assert set(observed)==set(origins)
    return observed

def run(public,diagnostic=None):
    paired=registry(public,diagnostic)
    original=HERE/'ACTIONS.jsonl';log=[json.loads(line) for line in original.read_bytes().splitlines()]
    assert [r['index'] for r in log]==list(range(1,340))
    def evidence(r,fields):
        data=dict(index=r['index'],original_command=r['command'],floor=gid(r,'after')['floor'],
            original_before_hash=r['before']['raw_hash'],original_after_hash=r['after']['raw_hash'])
        if r['index'] not in paired:return dict(data,scope='original_only')
        scope,row=paired[r['index']]
        assert row['request_id']==r['request_id'] and row['before_sequence']==r['before']['sequence'] and row['after_sequence']==r['after']['sequence']
        checks={}
        for phase in ('before','after'):
            a=row[phase]
            checks[phase]={key:bool(a['model'].get(key)==a['original'][key]) for key in fields if key in a['original']}
        return dict(data,scope=scope,mapped_action=row['mapped_aid'],paired_field_groups=checks)
    shuffles=[];opens=[];targets=[];aoe=[];ink_acquire=[];ink_fires=[];fungus=[];snake=[];boss=[]
    multi_ids=set()
    oracle,=(HERE.parents[2]/'native_runtime/compact_native_sa_round4_unseeded_001/native_oracle').glob('*/native_oracle.jsonl')
    calls=[(x['seq'],x['data']) for line in oracle.open() if '"kind":"native_card_invoked"' in line and (x:=json.loads(line))]
    incidental=[]; attack_calls=Counter(); global_target_cards=[]
    for r in log:
        a,b=gid(r,'before'),gid(r,'after');c=a.get('combat_state');z=b.get('combat_state')
        if not c and z and z['turn']==1 and any(x['id']=='Ring of the Snake' for x in b['relics']):
            opens.append(dict(evidence(r,('relics','hand','pile_counts')),opening_hand_size=len(z['hand']),hand=faces(z['hand'])))
        lo,hi=[r[side]['raw']['capture_alignment']['native_record_sequence'] for side in ('before','after')]
        for seq,call in calls:
            if not lo<seq<=hi:continue
            assert call['source']=='AbstractPlayer.useCard'
            face=call['card']
            if face['type']=='ATTACK':attack_calls[face['target_type']]+=1
            elif face['target_type']=='ALL_ENEMY':
                global_target_cards.append(dict(index=r['index'],source=seq,card=face['id'],type=face['type'],
                          living=[v['id'] for v in c['monsters'] if v['current_hp']>0 and not v['is_gone']]))
            if (c and sum(v['current_hp']>0 and not v['is_gone'] for v in c['monsters'])>=2
                    and call['target']['kind']=='monster' and not r['command'].startswith('play ')):
                incidental.append(dict(evidence(r,('hand','enemies','turn_energy_block')),source_sequence=seq,uuid=face['uuid'],card=face['id'],
                         target=call['target']['id'],slot=call['target']['monster_position']['index'],before=hp(c),after=hp(z)))
        if ink(a) is None and ink(b) is not None:
            ink_acquire.append(dict(evidence(r,('relics','rewards')),counter=ink(b)))
        if a.get('screen_state',{}).get('event_id')=='Liars Game':
            assert a['floor']==2
            snake.append(dict(evidence(r,('resources','deck','page')),option=a.get('choice_list'),gold=[a['gold'],b['gold']],
                  deck_sizes=[len(a['deck']),len(b['deck'])],new_cards=[x['id'] for x in b['deck'] if x['uuid'] not in {q['uuid'] for q in a['deck']}]))
        if not (c and z and a['floor']==b['floor']):continue
        command=r['command'].split()
        played=c['hand'][int(command[1])-1] if command[0]=='play' else None
        old_discard=positions(c,'discard_pile')
        new_draw=positions(z,'draw_pile');new_hand=positions(z,'hand')
        returned=set(old_discard)&set(new_draw);dealt=set(old_discard)&set(new_hand)
        if returned:
            shuffles.append(dict(evidence(r,('hand','pile_counts')),turn=[c['turn'],z['turn']],pile_counts_before=[len(c[k]) for k in ('draw_pile','discard_pile','hand')],
                                pile_counts_after=[len(z[k]) for k in ('draw_pile','discard_pile','hand')],
                                previous_discard_to_draw=sorted(returned),previous_discard_to_hand=sorted(dealt),hand_after=faces(z['hand'])))
        if sum(m['current_hp']>0 and not m['is_gone'] for m in c['monsters'])>=2:
            if command[0]=='play' and len(command)==3:
                j=int(command[2]);targets.append(dict(evidence(r,('enemies','hand','turn_energy_block')),slot=j,target=c['monsters'][j]['id'],card=played['id'],
                                 before=hp(c),after=hp(z)))
                multi_ids.add(played['id'])
            hit=[j for j,(x,y) in enumerate(zip(c['monsters'],z['monsters'])) if x['current_hp']>y['current_hp']]
            if len(hit)>1:aoe.append(dict(evidence(r,('enemies',)),slots=hit,card=played and played['id']))
        if ink(a) is not None and ink(b) is not None and ink(b)<ink(a):
            new_dealt=set(positions(c,'draw_pile'))&set(new_hand)
            new_dealt |= dealt
            ink_fires.append(dict(evidence(r,('relics','hand','pile_counts')),counter=[ink(a),ink(b)],
                       played=played and played['id'],actual_new_drawn_faces=[new_hand[u]['id'] for u in sorted(new_dealt)],
                       actual_new_drawn_uuids=sorted(new_dealt)))
        if c['monsters'][0]['id']=='FungiBeast' and (r['index'] in (142,143)):
            fungus.append(dict(evidence(r,('enemies','resources','turn_energy_block')),before=hp(c),after=hp(z),
                               native_powers_before=[powers(m) for m in c['monsters']],native_powers_after=[powers(m) for m in z['monsters']],
                               vulnerable=[powers(t['player']).get('Vulnerable',0) for t in (c,z)]))
        if a['room_type']=='MonsterRoomBoss':
            boss.append(dict(evidence(r,('resources','turn_energy_block','enemies','terminal')),enemy=c['monsters'][0]['id'],
                             turn=[c['turn'],z['turn']],player_hp=[a['current_hp'],b['current_hp']],enemy_hp=[hp(c),hp(z)]))
    assert len(shuffles)==15 and len(ink_fires)==14 and len(fungus)==2 and len(boss)==87 and {r['index'] for r in snake}=={38,39,40}
    assert len(ink_acquire)==1 and all(row['counter']==[9,0] for row in ink_fires)
    assert not aoe and all(r['floor']==16 and r['enemy']=='Hexaghost' for r in boss)
    counts=lambda data:dict(Counter(row['scope'] for row in data))
    floors=defaultdict(set)
    for r in targets:floors[r['floor']].add(r['slot'])
    assert len(targets)+len(incidental)==14 and [x['index'] for x in incidental]==[10,66]
    return dict(oracle_sha256=digest(oracle),seed=read(HERE/'SEED.json'),original_sha256=digest(original),script_sha256=digest(Path(__file__)),
         public=dict(path=public.relative_to(HERE).as_posix(),sha256=digest(public)),
         diagnostic=dict(path=diagnostic.relative_to(HERE).as_posix(),sha256=digest(diagnostic)) if diagnostic else None,
         scope='formal and diagnostic mark the executed model step against the bracketed original input; per-field comparisons are recorded separately. Original UUIDs do not imply native UUIDs are present on the model side.',
         actual_shuffle=dict(count=len(shuffles),by_scope=counts(shuffles),records=shuffles,definition='original old discard UUID appears in later draw pile within same combat; public comparison tests resulting hand and pile counts, not native hidden order'),
         separate_targeted_attacks=dict(count=len(targets)+len(incidental),explicit_play_inputs=len(targets),incidental_actions=len(incidental),by_scope=counts(targets+incidental),explicit_slots_per_floor={k:sorted(s) for k,s in floors.items()},records=targets,confirmed_incidental_actions=incidental),
         simultaneous_multi_enemy_damage=dict(native_attack_invocations_by_target_type=dict(attack_calls),all_enemy_nonattack_invocations=global_target_cards,recorded_multi_hp_drops=aoe,observed_single_target_cards=sorted(multi_ids),denominator='Comparisons of bridged combat HP before/after in multi-live-enemy rooms; separate attacks do not establish AoE.'),
         ink_bottle=dict(acquired=ink_acquire,counter_wraps=ink_fires,by_scope=counts(ink_fires),count=len(ink_fires),definition='9-to-0 InkBottle transitions with newly drawn card UUIDs checked against previous draw/discard. Some card plays have other draws; no unique attribution is inferred for those copies.'),
         snake_ring=dict(first_hands=opens,by_scope=counts(opens),limits='Original has Ring of the Snake at room entry and displays first hands. This does not isolate a causal counterfactual without the relic.'),
         serpent=snake,spores=fungus,spore_vector_checks=spore_vectors(diagnostic or public,paired,log),boss=dict(actions=len(boss),by_scope=counts(boss),range=[boss[0]['index'],boss[-1]['index']],first=boss[0],last=boss[-1],
                first_damage_to_boss=next(r for r in boss if r['enemy_hp'][0]!=r['enemy_hp'][1]),last_paired_boss_input=next((r for r in reversed(boss) if r['scope']!='original_only'),None)))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('public',nargs='?',type=Path);parser.add_argument('--diagnostic',type=Path);args=parser.parse_args()
    if args.public is None:
        if args.diagnostic is not None:
            parser.error('Use both explicit paths or omit both to verify the sealed editions.')
        sealed=read(HERE/'RESULT.json')
        for kind in ('reconciled_official','diagnostic'):
            ref=sealed[kind]
            assert ref and digest(HERE/ref['path'])==ref['sha256']
        public=HERE/sealed['reconciled_official']['path']
        diagnostic=HERE/sealed['diagnostic']['path']
    else:
        public=args.public.resolve()
        diagnostic=args.diagnostic.resolve() if args.diagnostic else None
    data=run(public,diagnostic)
    (HERE/'MECHANISMS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(data['actual_shuffle']['by_scope'],data['ink_bottle']['by_scope'],data['boss']['by_scope'])
