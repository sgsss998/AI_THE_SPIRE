"""Resolve the published address spaces and test coordinate conversion without claiming native equivalence."""
from pathlib import Path
from hashlib import sha256
import json
from silent_env import action193,policy_actions
from experiments.sa_calibration_round3 import release
from experiments.sa_calibration_round2.tea_state import session as tea
from .verify import ROOT,HERE,digest

def load(path):return json.loads((ROOT/path).read_text())

def address(lo,hi,label,status='context_bound'):
    return dict(start=lo,end=hi,size=hi-lo+1,meaning=label,classification=status)

def main():
    schema_file='contracts/state_schema.json'; a_native='contracts/actions.json';policy_file='contracts/policy_actions.json';a193_file='contracts/policy_actions_193.json'
    extra='experiments/sa_calibration_round1/privileged/schema.json'
    spec=load(schema_file);old=load(a_native)['a189'];new=load(a193_file);target=load(policy_file);draw=load(extra)
    assert digest(ROOT/policy_file)==new['inherits']['source_sha256'] and digest(ROOT/a_native)==new['inherits']['native_source_sha256']
    blocks=[]
    for family in ('base_blocks','extra_blocks'):
        for b in spec[family]:
            k=b.get('availability_width',0);size=b['rows']*b['width']+k
            assert size==b.get('size',size) and len(b['fields'])==b['width']
            assert b['offset']==sum(p['size'] for p in blocks)
            blocks.append(dict(source=schema_file,family=family,start=b['offset'],end=b['offset']+size-1,size=size,
                       name=b['name'],rows=b['rows'],row_width=b['width'],availability_prefix=k,
                       first_row_start=b['offset']+k,layout_template=b['fields']))
    assert sum(p['size'] for p in blocks)==3118
    for i,name in zip(draw['offsets'],draw['fields'],strict=True):
        blocks.append(dict(source=extra,start=i,end=i,size=1,name=name))
    blocks.append(dict(source='experiments/sa_calibration_round2/tea_state/session.py',start=3121,end=3121,size=1,name='tea_set_pending'))
    new_sig=release.interface_signature().metadata()
    assert [j for b in blocks for j in range(b['start'],b['end']+1)]==list(range(new_sig['observation_dimension']))
    assert new_sig['action_version']==action193.POLICY_VERSION and new_sig['actions']==new['size']==193
    assert target['canonical_rows']==5 and target['sixth_policy_target_block']=='reserved_and_rejected'
    assert old['ranges']==dict(play=[0,69],potion_use_no_target=[70,74],potion_use_targeted=[75,104],potion_discard=[105,109],choose=[110,169],unchoose_selected_slot=[179,188])
    assert old['reserved']==[174,175]
    segs=[address(0,9,'无目标出手牌 h'),address(10,59,'出手牌 h，目标为行 t；10*(t+1)+h'),
          address(60,69,'指向第六目标行的手牌动作','reserved'),address(70,74,'使用槽 s 的无目标药水'),
          address(75,99,'使用槽 s 的药水指向行 t；75+5*t+s'),address(100,104,'指向第六目标行的药水动作','reserved'),
          address(105,109,'丢弃药水槽 s'),address(110,169,'当前界面显示的第0至59个选项')]
    segs.extend(address(a,a,k,'reserved' if a in old['reserved'] else 'context_bound') for k,a in old['controls'].items())
    segs.extend([address(179,188,'取消已选手牌槽0至9'),address(189,192,'当前界面显示的第60至63个选项')])
    assert [i for r in segs for i in range(r['start'],r['end']+1)]==list(range(193))
    reserved={i for r in segs if r['classification']=='reserved' for i in range(r['start'],r['end']+1)}
    frame_key='coordinate-only';binding=policy_actions.TargetBinding(frame_key,frame_key,frame_key,5,tuple(range(5)),(True,)*5,(True,)*5,(True,)*5)
    rejected=[]
    for a in range(193):
        try:n=action193.policy_to_native(a,binding,frame_id=frame_key,source_version=action193.POLICY_VERSION)
        except policy_actions.TargetBindingError:rejected.append(a);continue
        assert n==a
    assert set(rejected)==reserved and len(rejected)==17
    assert all(action193.choice_slot(action193.choice_action(i))==i for i in range(64))
    try:action193.choice_action(64)
    except ValueError:pass
    else:raise AssertionError('65th choice accepted')
    sources=[schema_file,a_native,policy_file,a193_file,extra,'src/silent_env/action193.py','src/silent_env/policy_actions.py',
             'experiments/public_hand_fees/session.py','experiments/public_card_attributes_v3/attributes.py','experiments/sa_calibration_round2/events/quotes.py',
             'experiments/sa_calibration_round2/tea_state/session.py','experiments/sa_calibration_round2/tea_state/pending.cpp',
             'experiments/sa_calibration_round3/release.py','experiments/sa_calibration_round3/death/session.py','experiments/sa_calibration_round3/death/split.py','experiments/sa_calibration_round3/INTERFACE.json']
    summary=dict(coordinates='Zero-based inclusive; i-th row begins at first_row_start + i*row_width. The candidate schema defines slot geometry; current producers and ABI define value interpretation.',
                 width=3122,action_count=193,signature=new_sig,source_hashes={n:digest(ROOT/n) for n in sources},observation=blocks,
                 supplemental_group_availability=spec['availability'],draw_top_semantics=draw,tea_semantics='1 only before combat with charged Ancient Tea Set; 0 during combat after its benefit is applied and at terminal.',
                 runtime_annotations=[
                     dict(blocks=['hand','hand_dynamics'],rule='Current public hand uses shown cost icon; dynamic four-slot hand encoding uses combat cost, displayed cost, special data, flags for which are known/free. See current codec; bare zero can be unknown.',source=sources[7:9]),
                     dict(blocks=['counts','event_values'],rule='Reviewed Scrap Ooze / Serpent choices expose two options and only current available quote bits.',source=sources[9]),
                     dict(blocks=['monsters'],rule='Spore Cloud is row-relative +37. The two specific historical follow-ups clear only the receipted dead slot. Split is a derived live-slot marker and uses no extra field.',source=sources[13:15])],
                 historical_representation_sources=new['state']['representation_sources'],actions=segs,reserved_coordinates=rejected,
                 action_verification=dict(identity_binding_only=176,reserved_rejected=17,choices_roundtrip=64,choice_65_rejected=True),
                 limits='Location and coordinate-conversion verification only. No per-field native-fidelity certificate; empty slots, unknown observations and unsupported page-specific actions remain separately identified in actual paired cases.')
    (HERE/'LAYOUT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print([(k,len(spec[k])) for k in ('base_blocks','extra_blocks')],len(rejected),len(blocks))
if __name__=='__main__':main()
