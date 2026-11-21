"""Actual R2/R3 API inheritance checks. Only writes the new compatibility ledger."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from struct import pack
from silent_env.native_compare import json_hash
from experiments.sa_calibration_round2 import draw_check,verify_release as frozen
from experiments.sa_calibration_round2.tea_state import session as r2tea
from experiments.sa_calibration_round2.boss.verify_prefix import TeaSetup,TeaEngine,build_tea
from experiments.sa_calibration_round2.boss.verify_opening import read_case,receipt
from experiments.sa_calibration_round2.replay.run import rows,OLD,NEW,repeated_reward_cycles
from experiments.sa_calibration_round3 import release

HERE=Path(__file__).resolve().parent
R2=HERE.parent.parent/'sa_calibration_round2'
ROOT=HERE.parents[2]

def digest(p):return sha256(p.read_bytes()).hexdigest()
def vhash(v):return sha256(pack(f'<{len(v)}d',*v)).hexdigest()
def advance(s,f,a):return s.step(a,frame_id=f.frame_id,action_version=f.action_version)
def face(c):return [c['id'],int(c['upgrades'])]

def same(a,b):
    assert (len(a.state.vector),len(b.state.vector),len(a.supported_actions),len(b.supported_actions))==(3122,3122,193,193)
    assert a.state.vector==b.state.vector and a.supported_actions==b.supported_actions and a.policy_mask==b.policy_mask
    assert a.action_gaps==b.action_gaps and a.page==b.page and a.done==b.done and a.engine_steps==b.engine_steps

def draw():
    archive=json.loads((R2/'replay/RESULT.json').read_bytes()); prior=json.loads((R2/'DRAW_CHECK.json').read_bytes())
    journal=rows(OLD)+rows(NEW); hashes={str(p.relative_to(ROOT)):digest(p) for p in (OLD,NEW)}
    assert all(archive['source_sha256'][k]==v for k,v in hashes.items())
    versions=[r2tea.make_session(),release.make_session()]
    frames=[s.reset(archive['seed_unsigned']) for s in versions]; same(*frames)
    view_digest=sha256();availability=Counter();events=[];tea=[]
    def record(f):
        view_digest.update(pack('<3122d',*f.state.vector));availability[int(f.state.vector[3120])]+=1;tea.append(f.state.vector[3121])
    record(frames[1])
    for entry in journal:
        before,after=entry['before'],entry['after']
        for x in (before,after):assert x['raw_hash']==json_hash(x['raw'])
        old=before['raw']['game_state'].get('combat_state') or {}; new=after['raw']['game_state'].get('combat_state') or {}
        top=frames[1].state.vector[3118:3121]
        frames=[advance(s,f,entry['aid']) for s,f in zip(versions,frames,strict=True)]
        same(*frames);record(frames[1])
        if entry['aid']!=170 or not old.get('draw_pile') or not new.get('hand'):continue
        assert old['turn']+1==new['turn']
        names=versions[1].engine._source._backend.CARD_IDS
        prediction=[names[int(top[0])-1],int(top[1])]
        hand=new['hand']
        assert top[2]==2 and prediction==face(hand[0]) and hand[0]['uuid'] in {c['uuid'] for c in old['draw_pile']}
        v=frames[1].state.vector
        recomputed=[[names[int(v[j])-1],int(v[j+1])] for j in range(1253,1313,6) if v[j]]
        assert recomputed==[face(c) for c in hand]
        discarded={c['uuid'] for c in old['discard_pile']}
        events.append(dict(action=entry['index'],floor=before['raw']['game_state']['floor'],turn=old['turn'],prediction=prediction,
             original_uuid=hand[0]['uuid'],draw_count_before=len(old['draw_pile']),whole_hand=recomputed,
             original_cards_returned_from_discard=[c['uuid'] for c in hand if c['uuid'] in discarded],
             native_capture_ids=[x['raw']['capture_alignment']['capture_id'] for x in (before,after)]))
    assert prior['observations']==events and frames[1].done and not any(tea)
    cycle_inputs=set()
    for cycle in repeated_reward_cycles(journal):
        if cycle['repeated_without_new_content']:
            cycle_inputs.update(range(cycle['start'],cycle['end']+1))
    assert len(cycle_inputs)==248 and all(s.engine._source._env.lost for s in versions)
    res=dict(seed=archive['seed_unsigned'],nonrepeating_inputs=len(journal)-len(cycle_inputs),repeating_inputs=len(cycle_inputs),
             terminal_hp=frames[1].state.vector[0],terminal_gold=frames[1].state.vector[2],actual_inputs=len(journal),equal_observations=len(tea),source_sha256=hashes,
             ordered_float64_stream_sha256=view_digest.hexdigest(),available_counts=dict(availability),terminal_both=frames[1].done,
             tea_zero_frames=len(tea),eligible=len(events),actual_reshuffle_action_indices=[x['action'] for x in events if x['original_cards_returned_from_discard']],
             historical_per_draw_receipt_agreement=len(events),draws=events)
    return res

class DiagnosticGridEngine(release.GridEngine):
    setup_class=TeaSetup

def historical(probe):
    case=json.loads((R2/'boss/PREFIX.json').read_text())['cases'][0]; seed=case['seed'];path=Path(case['source'])
    original,attempts=read_case(path,seed)
    hashes={n:digest(path/n) for n in case['archival_hashes']};assert hashes==case['archival_hashes']
    plans=case['diagnostic_tea_and_kunai']['actions']
    controls=[r2tea.make_session(),release.make_session(),release.make_session()]
    frames=[s.reset(seed) for s in controls]
    standard=[]; fork=None; stop=None; ticks=0;draws=[]
    for record in plans:
        k=record['sequence'];act=record['action']
        assert record==receipt(path,original,attempts[k],k)
        same(frames[0],frames[1])
        if 746<=k<=756:
            game=original[k]['raw']['game_state']
            relic=next(z for z in game['relics'] if z['id']=='Ancient Tea Set')
            if not game.get('combat_state'):
                assert frames[1].state.vector[3121]==int(relic['counter']==-2)
            standard.append(dict(sequence=k,pending=frames[1].state.vector[3121],original_counter=relic['counter'],actions=[i for i,b in enumerate(frames[1].supported_actions) if b]))
        if not frames[1].supported_actions[act]:
            stop=dict(sequence=k,floor=original[k]['raw']['game_state']['floor'],action=act,gaps=frames[1].action_gaps)
            break
        before=original[k]['raw']['game_state'].get('combat_state') or {}
        after=original[k+1]['raw']['game_state'].get('combat_state') or {}
        if act==170 and before.get('draw_pile') and after.get('hand') and after['turn']==before['turn']+1:
            actual=after['hand'][0]
            if actual['uuid'] in {x['uuid'] for x in before['draw_pile']}:
                val=frames[1].state.vector[3118:3121];names=controls[1].engine._source._backend.CARD_IDS
                assert val[2]==2 and [names[int(val[0])-1],int(val[1])]==face(actual)
                draws.append(dict(sequence=k,card=face(actual),uuid=actual['uuid'],receipt_sha256=record['receipt_sha256']))
        if k==750:
            assert frames[2].state.vector==frames[1].state.vector and frames[2].state.vector[3121]==1
            probe.clear_test_charge(controls[2].engine._source._env)
        frames=[advance(s,f,act) for s,f in zip(controls,frames,strict=True)];ticks+=1
        if k==750:
            a,b=frames[1:]; v,w=a.state.vector,b.state.vector
            assert a.supported_actions==b.supported_actions and a.policy_mask==b.policy_mask and v[:-1]==w[:-1] and v[-1]==1 and w[-1]==0
            fork=dict(sequence=751,preceding_receipt=record,shared_S3121_sha256=vhash(v[:-1]),R3_S3122_normal_sha256=vhash(v),
                      R3_S3122_control_sha256=vhash(w),differing_indices=[3121],shared_A193_sha256=sha256(bytes(a.supported_actions)).hexdigest())
    assert stop['sequence']==752 and fork and ticks==184
    reset=controls[2].reset(1);assert reset.state.vector[3121]==0
    try: r2tea.observer().pending(controls[1].engine._source._env,frames[1].engine_steps+1)
    except ValueError: stale=True
    else:raise AssertionError('Accepted wrong engine step')
    diag=[r2tea.make_session(TeaEngine()),release.make_session(DiagnosticGridEngine())]
    frames=[s.reset(seed) for s in diag];observed=[];n=0
    for record in plans:
        k=record['sequence'];same(*frames); assert record==receipt(path,original,attempts[k],k)
        if 746<=k<=756:
            g=original[k]['raw']['game_state'];c=g.get('combat_state');relic=next(x for x in g['relics'] if x['id']=='Ancient Tea Set')
            expected=int(not c and relic['counter']==-2)
            assert frames[1].state.vector[3121]==expected
            energy=int(frames[1].state.vector[901]) if c else None
            if c:assert energy==c['player']['energy']
            observed.append(dict(sequence=k,original_tea=relic['counter'],pending=expected,energy_both=energy))
        if k==756:break
        frames=[advance(s,f,record['action']) for s,f in zip(diag,frames,strict=True)];n+=1
    assert {x['sequence']:x['energy_both'] for x in observed if x['energy_both'] is not None}=={755:5,756:4}
    return dict(seed=seed,source_hashes=hashes,actual_public_inputs=ticks,public_stop=stop,public_points=standard,controlled_comparison=fork,
                additional_tea_history_draws=draws,reset_cleared=True,stale_rejected=stale,diagnostic_rule='Only the already audited Ring + Tea / Kunai chest branch is enabled by the diagnostic backing.',
                diagnostic_inputs=n,diagnostic_points=observed)

def main():
    manifest=frozen.build();assert manifest==frozen.read(R2/'RELEASE.json')
    iface=release.interface_signature().metadata()
    assert iface==json.loads((HERE.parent/'INTERFACE.json').read_text())
    trip=draw()
    with TemporaryDirectory() as td:tea=historical(build_tea(td))
    out=dict(R3_interface_sha256=digest(HERE.parent/'INTERFACE.json'),R2_manifest_sha256=digest(R2/'RELEASE.json'),
             R2_verified_files=len(manifest['files']),checker_sha256=digest(Path(__file__)),draw=trip,tea=tea)
    assert digest(R2/'RELEASE.json')==out['R2_manifest_sha256']
    (HERE/'RESULT.json').write_text(json.dumps(out,indent=2)+'\n')
    print(trip['eligible'],trip['actual_reshuffle_action_indices'],tea['public_stop'],out['R2_verified_files'])
if __name__=='__main__':main()
