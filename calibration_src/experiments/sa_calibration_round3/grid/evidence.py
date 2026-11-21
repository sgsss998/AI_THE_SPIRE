"""Pair immutable original receipts with newly executed formal R3 branches."""
import json
from .cohort import HERE, ROOT, COHORT, digest, prefix, step, deck
from silent_env.runtime import UnverifiedSemanticsError
from .live import CASES, WING_PREFIX
from experiments.sa_calibration_round3 import release


def read(path):return json.loads(path.read_bytes())

def check(case):
    name, _, _, seed=CASES[case]
    dst=ROOT/'native_runtime'/name
    native=read(dst/'grid_evidence/RESULT.json')
    bridge=dst/'bridge/sessions'/native['source_session']
    lines=[json.loads(z) for z in (dst/'grid_evidence/COMMANDS.jsonl').read_text().splitlines()]
    receipts=[]
    for row in lines:
        path=bridge/'results'/f"{row['req']}.json";r=read(path)
        assert row['status']==r['status']=='observed_transition'
        assert row['before_sha']==r['before']['raw_hash'] and row['after_sha']==r['after']['raw_hash']
        assert r['action_id']==row['action']
        receipts.append(dict(label=row['label'],aid=row['action'],id=row['req'],sha256=digest(path),
                             raw=[r['before']['sequence'],r['after']['sequence']]))
    snapshots={}
    def capture(label):
        p=dst/'fixture_control/observations'/label
        source=read(p/'bridge_snapshot.json');oracle=read(p/'native_payload.json')
        snapshots[label]=dict(raw=source['sequence'],sha256=source['raw_hash'],
                              native_payload_sha256=digest(p/'native_payload.json'),
                              witness_sha256=digest(p/'evidence.json'))
        return source['raw']['game_state'],oracle
    e,s,f=prefix(seed,(110,110) if case=='neow' else WING_PREFIX,release)
    def checked_resources(g,frame):
        v=frame.state.vector;b=e._source._backend
        assert list(v[:6])==[g[k] for k in ('current_hp','max_hp','gold','floor','act','ascension_level')]
        assert [(b.CARD_IDS[z-1],u) for z,u in deck(frame)]==[(c['id'],c['upgrades']) for c in g['deck']]
        normalize=lambda v:''.join(c for c in v.lower() if c.isalnum())
        assert [(normalize(b.RELIC_NAMES[int(v[i])-1]),int(v[i+1])-1) for i in range(32,112,2) if v[i]]==[(normalize({'NeowsBlessing':'Neows Lament'}.get(r['id'],r['id'])),r['counter']) for r in g['relics']]
        assert [normalize(b.POTION_NAMES[int(k)-1]) if k else 'potionslot' for k in v[17:17+int(v[16])]]==[normalize(r['id']) for r in g['potions']]
    g,n=capture('list');checked_resources(g,f)
    action_rows=[a for a in n['independent_legal_actions']['semantic_actions'] if a['type']=='choose']
    choices=[];candidates=g['screen_state']['cards'];v=f.state.vector
    assert [a['choice_index'] for a in action_rows]==list(range(len(candidates)))
    assert [i for i,flag in enumerate(f.supported_actions) if flag]==list(range(110,110+len(candidates)))
    for i,(card,action) in enumerate(zip(candidates,action_rows,strict=True)):
        pos=int(v[2684+i])-203
        observed=g['deck'][pos]
        assert (action['object_uuid'],action['object_id'])==(observed['uuid'],observed['id'])==(card['uuid'],card['id'])
        assert (e._source._backend.CARD_IDS[int(v[323+i*6])-1],int(v[324+i*6]))==(card['id'],card['upgrades'])
        choices.append(dict(row=i,permanent_slot=pos,id=card['id'],upgrades=card['upgrades'],uuid=card['uuid']))
    before=f.engine_steps
    preview=step(s,f,111);g,n=capture('preview');checked_resources(g,preview)
    assert g['screen_state']['confirm_up'] and preview.engine_steps==before and preview.state.vector[28]==1
    assert [i for i in range(len(candidates)) if preview.state.vector[325+6*i]]==[1]
    assert set(i for i,ok in enumerate(preview.supported_actions) if ok)=={172,173}
    final=step(s,preview,172)
    assert final.engine_steps==before+1 and final.state.vector[6]==5
    post,_=capture('after_confirm')
    # Resource settlement and the following actual map were independently captured.
    checked_resources(post,final)
    g,n=capture('settled_map');checked_resources(g,final)
    assert g['screen_type']=='MAP' and final.state.vector[1769]==len(g['screen_state']['next_nodes'])
    exits=sorted(int(final.state.vector[i+1]) for i in range(322,706,6) if final.state.vector[i]==7)
    assert exits==sorted(node['x'] for node in g['screen_state']['next_nodes'])
    target=read(dst/'target.json');assert target['fixture_mode'] and read(dst/'fixture_receipt.json')['initializations']==1
    close=read(dst/'close_before.json')['bridge_status']
    assert close['pending'] is None and not close['quarantine'] and not close['policy_blocked']
    info=dict(seed=seed,public_dimension=len(final.state.vector),execution='original targeted start, pinned read-only 99 gold assertion',
              source=dst.relative_to(ROOT).as_posix(),source_session=native['source_session'],requests=receipts,snapshots=snapshots,
              engine_steps_select_preview_confirm=[before,preview.engine_steps,final.engine_steps],candidates=choices,
              selected=native['selected'],new_card=native['final'][-1] if case=='neow' else None,
              confirmed_deck=len(native['immediate']),map_deck=len(native['final']),hp=g['current_hp'],gold=g['gold'],map_exits=exits,
              original_cancel_performed=False,native_buttons_on_preview=['confirm','cancel'],
              receipts_sha=digest(bridge/'raw.jsonl'),native_log_sha=digest(next((dst/'native_oracle').glob('*/*.jsonl'))),
              original_model_eligible=False)
    if case=='wing':
        q,_=capture('quote');c,_=capture('continue')
        assert q['current_hp']==59 and c['current_hp']==52 and q['deck']==c['deck'] and q['gold']==c['gold']==99
        info['prayer']={'hp':[59,52],'deck_count':len(q['deck']),'gold':99}
    return info

def main():
    signed=read(HERE/'COHORT.json')
    assert signed['engine_sha']==digest(HERE/'session.py')
    pairs={k:check(k) for k in CASES}
    selected_points=[]
    for row in signed['cases']:
        e,s,f=prefix(row['seed'],row['prefix'],release)
        start=f.engine_steps;preview=step(s,f,111);returned=step(s,preview,173)
        assert returned.state.vector==f.state.vector
        final=step(s,step(s,returned,111),172)
        assert final.state.vector[6]==5 and final.engine_steps==start+1
        selected_points.append(dict(seed=row['seed'],kind=row['kind'],selection=111,original_slots=row['eligible'],final_hp=final.state.vector[0]))
    negative=[]
    for kind,(_,_,_,seed) in CASES.items():
        e,s,f=prefix(seed,(110,110) if kind=='neow' else WING_PREFIX,release)
        for a in (109,110+int(f.state.vector[1769]),172,173):
            try:s.step(a,frame_id=f.frame_id,action_version=f.action_version)
            except UnverifiedSemanticsError:negative.append(dict(seed=seed,action=a,result='rejected'))
            else:raise AssertionError('Unexpected slot or confirmation before any pick')
    r2=read(COHORT/'RESULT.json')['runs']
    for seed in (1000050,9000015):
        old=next(z['episode'] for z in r2 if z['seed']==seed)
        _,_,f=prefix(seed,old['actions'],release)
        assert f.page=='GRID_UNVERIFIED' and not any(f.supported_actions)
        negative.append(dict(seed=seed,result=f.page,available=0))
    out=dict(verified_targeted_retail_games=2,training_updates=0,frozen_grid_code=digest(HERE/'session.py'),
             negative_checks=negative,formal_release_file=digest(HERE.parent/'release.py'),cohort_receipt=digest(HERE/'COHORT.json'),
             simulated_branches=signed['stats'],formal_representative_checks=len(selected_points),pairs=pairs,formal_seeds=selected_points)
    (HERE/'RESULT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print({k:(z['seed'],z['selected'][2],z['new_card'],z['hp'],z['gold'],z['map_exits']) for k,z in pairs.items()})

if __name__=='__main__':main()
