"""Validate both recorded input timings, their selected retail instances, and all ordered starter pairs."""
import hashlib
from concurrent.futures import ProcessPoolExecutor
from itertools import permutations
import json
from pathlib import Path
from experiments.neow_transform_two193.combinations import AFFECTED
from silent_env.native_compare import json_hash, load_native_capture

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=ROOT/'experiments/neow_transform_two193'


def read(p):
    return json.loads(p.read_bytes())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def make(timing):
    from experiments.sa_calibration_round4 import release
    # Use the published entry points. Only the timing explicitly exercised by the
    # original changes between the two runs.
    if timing=='settled':
        return release.make_session()
    engine=release.make_engine(neow_curse_timing=timing)
    return release.make_session(engine)

def apply(s,frame,action):
    assert frame.supported_actions[action]
    return s.step(action,frame_id=frame.frame_id,action_version=frame.action_version)

def deck(v):
    return [(int(v[i]),int(v[i+1])) for i in range(706,898,2) if v[i]]

def audit_native(path):
    b=read(path/'bridge_snapshot.json')
    g=b['raw']['game_state']
    proof=read(path/'evidence.json')['native']
    n=load_native_capture(path/'native_prefix.jsonl',proof['capture_id'],bridge_log=path/'bridge_prefix.jsonl',scope=proof['source_scope'])
    assert n.evidence['bracket_verified'] and n.evidence['exact_capture_binding']
    assert b['raw_hash']==json_hash(b['raw'])==n.evidence['bridge_raw_sha256']
    native=n.payload
    assert native==read(path/'native_payload.json')
    assert g['seed'] in (46,48) and g['ascension_level']==20
    assert [(c['id'],c['upgrades'],c['uuid']) for c in g['deck']]==[(c['id'],c['times_upgraded'],c['uuid']) for c in native['master_deck']]
    return b,g,native

def paired(seed):
    timing='fast' if seed==46 else 'settled'
    if seed==46:
        instance=ROOT/'native_runtime/compact_fixture_neow_transform_seed46'
        # Sequence 7 is an early receipt to the second click, without a third command.
        sequence=[('0000',None),('0001',110),('0002',112),('0003',121),('0005',115),('0006',110)]
        journal=[json.loads(line) for line in (instance/'fixture_control/actions.jsonl').read_bytes().splitlines()]
        actual=[x['action_id'] for x in journal]
        from experiments.neow_transform_two193.curse_timing import audited_curse
        archived=audited_curse()
        assert archived['early_packet']==7 and archived['actual_post_selection_packet']==8 and not archived['extra_input_needed']
        journal_hash=archived['journal_sha256']
    else:
        instance=ROOT/'native_runtime/compact_native_r4_neow48_001'
        sequence=[('talk',None),('offer',110),('settled_grid',112),('after_0',111),('after_1',111),('after_2',111),('after_3',110),('map',110)]
        journal=[json.loads(line) for line in (instance/'neow_r4/actions.jsonl').read_bytes().splitlines()]
        actual=[x['action'] for x in journal]
        journal_hash=sha(instance/'neow_r4/actions.jsonl')
        bridge=next((instance/'bridge/sessions').glob('*/attempts.jsonl'))
        records=[json.loads(line) for line in bridge.read_bytes().splitlines()]
        assert len({r['req'] for r in journal})==len(journal)
        for row in journal:
            matched=[e for e in records if e.get('request_id')==row['req']]
            for kind in ('dispatch_intent','dispatched','attempt_result'):
                entry,=[e for e in matched if e['event']==kind and (kind!='attempt_result' or e['status']=='observed_transition')]
                assert entry['command']==row['command']
            assert entry['status']=='observed_transition'
        assert read(instance/'process_exit.json')['pid']==read(instance/'process.json')['pid']
        assert not read(instance/'target.json')['fixture_mod_enabled']
    assert actual==[a for _,a in sequence if a is not None]
    obs=instance/'fixture_control/observations'
    extra='0004' if seed==46 else 'first_grid'
    b,g,n=audit_native(obs/extra)
    assert g['screen_type']=='GRID' and len(g['deck'])==(14 if seed==46 else 13)
    assert len(g['screen_state']['selected_cards'])==(1 if seed==46 else 0)
    assert [c['uuid'] for c in g['screen_state']['cards']]==[c['uuid'] for c in g['deck'][1:13]]
    assert n['independent_legal_actions']['status']=='complete'
    assert len(n['independent_legal_actions']['semantic_actions'])==12
    extra_row=dict(sequence=b['sequence'],deck_count=len(g['deck']),selected=len(g['screen_state']['selected_cards']),raw_sha256=b['raw_hash'])
    s=make(timing)
    f=s.reset(seed); faces=s.engine._source._backend.CARD_IDS
    frames=[];original=None
    for label,a in sequence:
        if a is not None:f=apply(s,f,a)
        b,g,n=audit_native(obs/label)
        v=f.state.vector
        current=[(c['id'],c['upgrades'],c['uuid']) for c in g['deck']]
        if original is None:original=current
        assert [tuple(row[:2]) for row in current]==[(faces[wire-1],up) for wire,up in deck(v)]
        assert v[22]==v[1763]==len(current)
        assert v[:6]==(g['current_hp'],g['max_hp'],g['gold'],g['floor'],g['act'],20)
        assert len(v)==3122 and len(f.supported_actions)==193
        if g['screen_type']=='GRID':
            sc=g['screen_state'];order=[c['uuid'] for c in sc['cards']]
            assert order==[row[2] for row in original[1:]] and sc['num_cards']==2 and not sc['confirm_up']
            assert [c['uuid'] for c in sc['selected_cards']]==[order[j] for j in range(12) if v[325+6*j]]
            assert v[28]==len(sc['selected_cards'])
            assert list(v[2684:2696])==list(range(204,216))
            na=n['independent_legal_actions']
            assert na['status']=='complete'
            assert [(q['type'],q['object_uuid']) for q in na['semantic_actions']]==[('choose',uuid) for uuid in order]
            assert [j for j,valid in enumerate(f.supported_actions) if valid]==list(range(110,122))
        elif g['screen_type']=='MAP':
            assert [int(choice[2:]) for choice in g['choice_list']]==[int(v[i+1]) for i in range(322,706,6) if v[i]]
        frames.append(dict(sequence=b['sequence'],sha256=b['raw_hash'],deck=len(current),page=f.page,action=a,
                           source=path_label(obs/label),engine_steps=f.engine_steps))
    gone=(12,6) if seed==46 else (2,1)
    assert [x[2] for x in current[:11]]==[x[2] for i,x in enumerate(original) if i not in gone]
    assert set(x[2] for x in original).isdisjoint(x[2] for x in current[11:])
    return dict(seed=seed,timing=timing,case_kind='archived_targeted_retail' if seed==46 else 'new_targeted_retail',
                selected_permanent_positions=gone,removed_uuid=[original[i][2] for i in gone],suffix=[x[0] for x in current[11:]],
                bound_frames=frames,actual_journal_sha256=journal_hash,original_grid_packet_outside_canonical_sequence=extra_row,actual_inputs=actual)

def path_label(path):
    return str(path.relative_to(ROOT))

def all_pairs(seed):
    historical=next(row for row in read(OLD/'COMBINATIONS.json')['rows'] if row['seed']==seed)
    results=historical['resulting_wire_cards']
    count=0
    timing='fast' if seed==46 else 'settled'
    s=make(timing)
    for i,j in permutations(range(12),2):
        f=apply(s,s.reset(seed),110)
        orig=deck(f.state.vector)
        f=apply(s,f,112)
        assert [k for k,b in enumerate(f.supported_actions) if b]==list(range(110,122))
        f=apply(s,f,110+i)
        assert f.engine_steps==1 and f.state.vector[325+6*i]==1 and f.state.vector[28]==1
        f=apply(s,f,110+j)
        assert f.page=='NEOW_TRANSFORM_LEAVE' and [k for k,b in enumerate(f.supported_actions) if b]==[110]
        f=apply(s,f,110)
        final=deck(f.state.vector)
        assert f.engine_steps==3 and f.state.vector[6]==5
        assert final[:11]==[x for k,x in enumerate(orig) if k not in (i+1,j+1)]
        assert [list(x) for x in final[11:]]==results
        count+=1
    return dict(seed=seed,pairs=count,timing=timing,resulting_wire_cards=results)

def controls():
    from silent_env.interface import InterfaceMismatch
    from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError
    records=[]
    for seed in (46,48,10679156812119886636):
        s=make('settled'); start=s.reset(seed); offer=apply(s,start,110)
        assert [j for j,on in enumerate(offer.supported_actions) if on]==[110,111,112,113]
        assert offer.policy_mask==offer.supported_actions
        frame=apply(s,offer,112)
        for action in (109,122,172,173):
            try:
                s.step(action,frame_id=frame.frame_id,action_version=frame.action_version)
            except UnverifiedSemanticsError:
                pass
            else:
                raise AssertionError('Invalid grid control accepted')
        try:
            s.step(110,frame_id=offer.frame_id,action_version=frame.action_version)
        except StaleFrameError:
            pass
        else:
            raise AssertionError('Prior offer reused')
        try:
            s.step(110,frame_id=frame.frame_id,action_version='wrong-version')
        except InterfaceMismatch:
            pass
        else:
            raise AssertionError('Invalid version accepted')
        before=frame.state.vector
        frame=apply(s,frame,111)
        frame=apply(s,frame,111)
        assert frame.state.vector==before and frame.engine_steps==1
        records.append(dict(seed_u64=str(seed),offer=[110,111,112,113],grid_rows=12,
                            invalid_controls_rejected=[109,122,172,173],stale_rejected=True,
                            wrong_version_rejected=True,repeat_click_undo=True))
    return records

def run():
    from experiments.sa_calibration_round4 import release
    sig=release.interface_signature().metadata()
    assert sig==read(HERE.parent/'INTERFACE.json')
    pairs=[paired(seed) for seed in (46,48)]
    checks=controls()
    with ProcessPoolExecutor(max_workers=3) as workers:
        all_seeds=list(workers.map(all_pairs,AFFECTED))
    assert sig==release.interface_signature().metadata()
    result=dict(interface=sig, frozen_interface_sha256=sha(HERE.parent/'INTERFACE.json'), freeze_sha256=sha(HERE.parent/'FREEZE.json'),formal_release_file=sha(Path(release.__file__)),runtime_sha256=sha(HERE/'session.py'),
                retail_pairs=pairs,scope_checks=checks,affirmed_curse_ordered_pairs=sum(x['pairs'] for x in all_seeds if x['seed'] in (46,48)),
                previous_noncursed_ordered_pairs=sum(x['pairs'] for x in all_seeds if x['seed'] not in (46,48)),
                simulated_cases=all_seeds,retail_rng_reference=sha(OLD/'RESULT.json'),ordered_pairs_reference=sha(OLD/'COMBINATIONS.json'),
                hidden_or_ui_policy="settled replays the actual post-award decision. fast preserves seed 46 first two fast grid decisions; no wall-clock equivalence claim.")
    assert (result['affirmed_curse_ordered_pairs'],result['previous_noncursed_ordered_pairs'])==(264,1452)
    (HERE/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Verified 2 retail branches and 1716 ordered model branches.')

if __name__=='__main__':
    run()
