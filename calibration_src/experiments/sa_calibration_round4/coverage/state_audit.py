"""Audit paired real/model decisions in the three R4 repairs, with explicit evidence per action domain."""
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path

from experiments.sa_calibration_round4 import release
from experiments.sa_calibration_round4.events import verify as event
from experiments.sa_calibration_round4.neow import verify as neow
from experiments.sa_calibration_round4.death import live as fungi

HERE=Path(__file__).resolve().parent
R4=HERE.parent
ROOT=R4.parents[1]


def read(path):
    return json.loads(path.read_bytes())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def append(rows,scope,seed,frame,receipt,native_controls,domain,complete,actual,values,source):
    vector=frame.state.vector
    assert len(vector)==3122 and len(frame.supported_actions)==193
    rows.append(dict(scene=scope,seed=str(seed),page=frame.page,native_sequence=receipt,
                     state_sha256=hashlib.sha256(struct.pack('<3122d',*vector)).hexdigest(),
                     model_supported=[i for i,b in enumerate(frame.supported_actions) if b],
                     model_marks_mask_complete=frame.policy_mask is not None,
                     native_controls=native_controls,domain=domain,native_complete=complete,actual_native_input_mapped_to_A=actual,
                     fields=values,source=source))

def neow_rows(rows):
    for seed,seq in ((46,[('0001',110,112),('0002',112,121),('0003',121,115)]),
                     (48,[('offer',110,112),('settled_grid',112,111),('after_0',111,111),('after_1',111,111),('after_2',111,110)])):
        inst='compact_fixture_neow_transform_seed46' if seed==46 else 'compact_native_r4_neow48_001'
        s=neow.make('fast' if seed==46 else 'settled');f=s.reset(seed)
        for label,action,actual in seq:
            f=neow.apply(s,f,action);v=f.state.vector
            path=ROOT/'native_runtime'/inst/'fixture_control/observations'/label
            b,g,n=neow.audit_native(path)
            oracle=n['independent_legal_actions'];full=oracle['status']=='complete'
            if g['screen_type']=='EVENT':
                assert 'obtain a curse transform 2 cards'==g['choice_list'][2]
                assert (v[335],v[336])==(17,5)
                legal=[110+i for i,o in enumerate(g['screen_state']['options']) if not o['disabled']]
                values={'S335_bonus':17,'S336_cost':5,'native_text':g['choice_list'][2]}
                domain='enabled_dialogue_rows'
            else:
                options=g['screen_state']['cards'];selected=g['screen_state']['selected_cards']
                legal=[110+item['choice_index'] for item in oracle['semantic_actions'] if item['type']=='choose']
                assert full and len(legal)==12 and not n['independent_legal_actions']['unknown_domains']
                checked=[i for i in range(12) if v[325+6*i]]
                assert [options[i]['uuid'] for i in checked]==[x['uuid'] for x in selected]
                assert len(g['deck'])==v[22]==v[1763] and v[27]==2 and v[28]==len(checked)
                values={'S22_and_S1763_deck':int(v[22]),'S27_required':2,'S28_selected':len(checked),
                        'S325_plus_6i_selected_rows':checked,'S2684_to_2695_permanent_references':list(v[2684:2696])}
                domain='whole_canonical_action_contract'
            assert f.supported_actions[actual]
            append(rows,'neow',seed,f,b['sequence'],legal,domain,full,actual,values,str(path.relative_to(ROOT)))

def snake(rows):
    record=read(event.R3/'fresh/RESULT.json')
    replay=read(event.R3/'fresh'/record['replay']['path'])
    journal=event.replay.rows(event.R3/'fresh/ACTIONS.jsonl')
    seed=replay['seed_unsigned']
    e,s,f=event.make_session(release,seed)
    def add(f,b,actual):
        v=f.state.vector;g=b['raw']['game_state']
        event.check_frame(f,b,e)
        legal=[110+i for i,o in enumerate(g['screen_state']['options']) if not o['disabled']]
        values={'S2_gold':int(v[2]),'S22_deck':int(v[22]),'S2969_phase':int(v[2969]),'S1769_option_count':int(v[1769])}
        offer=release.decode_offer(v)
        if offer:
            text=g['screen_state']['options'][0]['text']
            assert offer.gold==150==v[2973] and offer.curse=='Doubt'
            assert '150' in text and ('Doubt' in text or '疑虑' in text)
            values.update(S9_event=int(v[9]),S2970_quote_bits=int(v[2970]),S2973_gold=150,decoded_curse='Doubt',original_text=text)
        append(rows,'snake',seed,f,b['sequence'],legal,'enabled_dialogue_rows',False,actual,values,b['raw_hash'])
    for rec,m in zip(journal,replay['trace']):
        i=rec['index']
        if i>54:break
        if i>=52:add(f,rec['before'],110)
        if i!=50:f=event.step(s,f,110 if i in (53,54) else m['mapped_aid'])
    seed=54072726;e,s,f=event.make_session(release,seed)
    route=read(event.old.R1/'fidelity/supplement/RESULT.json')['multi']['prefix']
    packets={r['sequence']:r for r in event.replay.rows(event.OLDER/'raw.jsonl') if r.get('raw',{}).get('game_state',{}).get('seed')==seed}
    for item in route:
        if item['original_input']==262:add(f,packets[262],item['action'])
        f=event.step(s,f,item['action'])
    add(f,packets[263],110)

def fungi_rows(rows):
    for seed in (19,59):
        original=read(fungi.dest(seed)/'r4_death/RESULT.json')
        e=release.make_engine();s=release.make_session(e);f=s.reset(seed)
        for a in fungi.source(seed)[0]:
            f=neow.apply(s,f,a)
        v=f.state.vector;source=original['native_before'];flags=original['native_monster_flags_before']
        monsters=[]
        for slot,m in enumerate(flags):
            start=993+52*slot
            targetable=not m['is_gone'] and source['enemies'][slot][0]>0
            powers={q['id']:q['amount'] for q in m['powers']}
            assert v[start+6]==int(targetable) and v[start+4]==int(m['is_gone'])
            assert (v[start+1],v[start+2],v[start+21],v[start+37])==(source['enemies'][slot][0],source['enemies'][slot][1],powers.get('Strength',0),powers['Spore Cloud'])
            monsters.append(dict(slot=slot,start=start,hp=int(v[start+1]),targetable=targetable,strength=int(v[start+21]),spore=int(v[start+37])))
        assert v[911]==source['vulnerable']==2 and v[901]==source['energy']
        a=original['real']['model_action']
        assert f.supported_actions[a] and f.policy_mask is None
        independent=original['independent']
        calibrated=[170] if seed==19 else [105,170]
        assert {t['type'] for t in independent['semantic_actions']}==({'end'} if seed==19 else {'end','potion_discard'})
        vals={'S911_player_vulnerable':2,'S901_energy':int(v[901]),'monsters':monsters,
              'bridge_candidate_actions':original['legal_before'],'oracle_known_domains':independent['known_domains']}
        append(rows,'fungi',seed,f,original['real']['before'],calibrated,'whole_canonical_action_contract' if seed==19 else 'independent_partial',
               independent['status']=='complete',a,vals,original['real']['before_hash'])

def main():
    interface=release.interface_signature().metadata()
    assert interface==read(R4/'INTERFACE.json')
    rows=[]
    neow_rows(rows);snake(rows);fungi_rows(rows)
    by_state=defaultdict(list)
    for i,row in enumerate(rows):by_state[row['state_sha256']].append(i)
    repeats=[];conflicts=[]
    for h,ids in by_state.items():
        if len(ids)<2:continue
        repeats.append(ids)
        for j,i in enumerate(ids):
            for other in ids[j+1:]:
                a,b=rows[i],rows[other]
                if a['domain']==b['domain'] and a['native_controls']!=b['native_controls']:conflicts.append([i,other])
    result=dict(interface_sha256=digest(R4/'INTERFACE.json'),input_hashes={p:digest(R4/p) for p in ('neow/RESULT.json','neow/TEMPO.json','events/RESULT.json','death/RESULT.json')},
                width=3122,actions=193,paired_decisions=len(rows),distinct_vectors=len(by_state),repeated_rows=repeats,
                identical_state_different_known_controls=conflicts,rows=rows,
                scope='Compared native controls only within the same known domain. Missing or unexercised controls cannot establish equality. No global sufficiency or redundancy claim.')
    (HERE/'STATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(len(rows),len(by_state),repeats,conflicts)
if __name__=='__main__':main()
