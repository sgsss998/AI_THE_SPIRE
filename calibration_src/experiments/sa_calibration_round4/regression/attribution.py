"""Read frozen R3 and R4 free trajectories and identify the first policy split for changed outcomes."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
from random import Random
import gzip
import json
from experiments.policy_grid_integration.coverage import choose
from experiments.sa_calibration_round4.events.serpent import CONTINUE, LEAVE

HERE=Path(__file__).resolve().parent
R3=HERE.parent.parent/'sa_calibration_round3/regression'
read=lambda path:json.loads(path.read_bytes())
digest=lambda path:sha256(path.read_bytes()).hexdigest()
UNIQUE=(CONTINUE,LEAVE)

def load(base,record,seed):
    path=base/'traces'/f'{seed}.json.gz'
    assert digest(path)==record['trace']['sha256']
    return json.loads(gzip.decompress(path.read_bytes()))

def next_choice(actions,generator):
    return actions[0] if len(actions)==1 else choose(actions,generator)

def deltas(left,right):
    return [idx for idx,(a,b) in enumerate(zip(left['state'],right['state'])) if a!=b]

def compare(seed,old,new,left,right):
    old_actions,new_actions=old['episode']['actions'],new['episode']['actions']
    gi,gj=Random(seed+8384),Random(seed+8384)
    i=j=0
    inserted=[]
    mask_cause=None
    rng_cause=None
    first_state=None
    while i<len(left) and j<len(right):
        a,b=left[i],right[j]
        if b['page'] in UNIQUE and a['page']!=b['page']:
            assert b['supported']==[110] and new_actions[j]==110
            inserted.append(dict(r4_index=j,old_index=i,page=b['page'],index_deltas=deltas(a,b)))
            j+=1
            continue
        aa,bb=a['supported'],b['supported']
        dif=deltas(a,b)
        if dif and first_state is None:first_state=dict(r3_index=i,r4_index=j,fields=dif)
        if aa!=bb and mask_cause is None:
            mask_cause=dict(r3_index=i,r4_index=j,page=b['page'],r3_supported=aa,r4_supported=bb)
        base=dict(r3_index=i,r4_index=j,old_floor=a['kernel_floor'],new_floor=b['kernel_floor'],old_page=a['page'],new_page=b['page'],
                  old_mask=aa,new_mask=bb,same_s3122=not dif,changed_coordinates=dif,
                  old_ticks=a['engine_steps'],new_ticks=b['engine_steps'])
        if i==len(old_actions) or j==len(new_actions):
            if i==len(old_actions) and j<len(new_actions) and not aa and bb:
                cause='old_unsupported_fungi_now_executable' if 'death_boundary_unknown' in a['gaps'] else 'old_unsupported_now_executable'
            elif j==len(new_actions) and i<len(old_actions) and not bb:
                cause='old_action_unavailable_same_path'
            else:cause='equal_aligned_actions_different_endpoint'
            base.update(cause=cause,old_action=old_actions[i] if i<len(old_actions) else None,new_action=new_actions[j] if j<len(new_actions) else None)
            break
        same_rng=gi.getstate()==gj.getstate()
        oi,ni=old_actions[i],new_actions[j]
        assert next_choice(aa,gi)==oi and next_choice(bb,gj)==ni
        if rng_cause is None and same_rng and gi.getstate()!=gj.getstate():
            rng_cause=dict(old_index=i,r4_index=j,page=b['page'],old_mask=aa,new_mask=bb,old_action=oi,new_action=ni)
        if oi!=ni:
            if b['page']=='NEOW_OFFERS' and 112 not in aa and 112 in bb:
                cause='new_neow_choice_selected' if ni==112 else 'neow_changed_sampling_pool'
            elif not same_rng and aa==bb and rng_cause and rng_cause['page']=='NEOW_OFFERS':
                cause='rng_shift_after_earlier_neow_mask_change'
            elif ni not in aa:cause='newly_supported_choice_selected'
            elif oi not in bb:cause='old_choice_unavailable_same_path'
            else:cause='different_selection_in_common_choices'
            base.update(cause=cause,old_action=oi,new_action=ni,same_policy_rng_before_choice=same_rng)
            break
        i+=1;j+=1
    else:raise AssertionError((seed,len(left),len(right)))
    return dict(first_material_decision=base,first_support_change=mask_cause,first_rng_position_change=rng_cause,
                first_shared_state_value_change=first_state,prior_unique_serpent_steps=inserted)

def main():
    r3_index=read(R3/'RESULT.json'); r3_path=R3/r3_index['full']['path']; assert digest(r3_path)==r3_index['full']['sha256']
    ix=read(HERE/'RESULT.json'); p=HERE/ix['path'];assert digest(p)==ix['sha256']
    old_full=read(r3_path);new_full=read(p)
    old={r['seed']:r for r in old_full['runs']};new={r['seed']:r for r in new_full['runs']}
    assert len(old)==len(new)==704 and old.keys()==new.keys()
    records=[];transition=Counter();groups=Counter();strict_loss_paths={};semantic_loss_paths={};literal_interruptions=[]
    for seed,r in new.items():
        o=old[seed]; endpoints=(o['episode']['reason'],r['episode']['reason'])
        transition[' -> '.join(endpoints)]+=1
        if not r['forced']['prefix_complete']:
            aligned=r.get('aligned') or {}
            literal_interruptions.append(dict(seed=seed,literal_stop=r['forced']['first_unavailable'],aligned_complete=aligned.get('complete'),
                        aligned_stop=None if aligned.get('complete') else {k:aligned.get(k) for k in ('index','action','page')},
                        additional_single_inputs=aligned.get('extra_serpent_inputs'),aligned_endpoint_state_equal=aligned.get('endpoint_state_equal')))
        if endpoints[0]==endpoints[1]:continue
        left,right=load(r3_path.parent,o,seed),load(p.parent,r,seed)
        assert len(left)==len(o['episode']['actions'])+1 and len(right)==len(r['episode']['actions'])+1
        trace=compare(seed,o,r,left,right)
        fo=r['forced'];pair=r['aligned'] or {}
        forcetrace=fo.get('trace')
        if forcetrace:
            # The recorded force-replay may point to its local full path.
            forced_frames=json.loads(gzip.decompress((p.parent/'forced_traces'/f'{seed}.json.gz').read_bytes()))
            assert digest(p.parent/'forced_traces'/f'{seed}.json.gz')==forcetrace['sha256']
            end=forced_frames[-1]
        else:end=right[fo['actions_replayed']]
        if endpoints==('loss','unsupported'):
            strict_loss_paths[seed]=bool(fo['prefix_complete'] and end['kernel_lost'])
            semantic_loss_paths[seed]=strict_loss_paths[seed] or (pair.get('complete') is True and pair.get('endpoint_state_equal') is True and left[-1]['kernel_lost'])
        groups[trace['first_material_decision']['cause']]+=1
        records.append(dict(seed=seed,cohort=r['cohort'],r3_outcome=endpoints[0],r4_outcome=endpoints[1],
            r3_floor=o['episode']['engine_floor'],r4_floor=r['episode']['engine_floor'],r4_final_page=r['episode']['page'],r4_final_gaps=r['episode']['cause'],
            strict_old_prefix_complete=fo['prefix_complete'],strict_old_endpoint_reason=fo['endpoint']['reason'],
            strict_old_endpoint_state_equal=end['state']==left[-1]['state'],strict_first_missing=fo['first_unavailable'],
            aligned_complete=pair.get('complete'),aligned_endpoint_state_equal=pair.get('endpoint_state_equal'),**trace))
    serpent=[r for r in new.values() if (r.get('aligned') or {}).get('extra_serpent_inputs')]
    assert all(r['aligned']['complete'] and r['aligned']['endpoint_state_equal'] for r in serpent)
    decomposition=dict(all_cases=len(serpent),unique_steps=sum(len(r['aligned']['extra_serpent_inputs']) for r in serpent),
                       literal_accepted_but_not_at_old_endpoint=[r['seed'] for r in serpent if r['forced']['prefix_complete'] and r['forced']['endpoint_changes']],
                       equal_aligned_endpoint_states=sum(r['aligned']['endpoint_state_equal'] for r in serpent))
    out=dict(comparison='frozen R3 versus frozen R4; zero-based decision offsets',r3_full_sha256=digest(r3_path),r4_full_sha256=digest(p),
        script_sha256=digest(Path(__file__)),all_seeds=len(old),transitions=dict(transition),outcome_changes=len(records),causes=dict(groups),
        previous_losses_stopped_in_free_policy=len(strict_loss_paths),old_literal_path_still_loses=sum(strict_loss_paths.values()),
        old_path_loses_with_verified_unique_alignment=sum(semantic_loss_paths.values()),serpent_alignment=decomposition,all_literal_interruptions=literal_interruptions,
        old_prefix_still_interrupted_after_alignment=sum(row['aligned_complete'] is not True for row in literal_interruptions),records=records)
    (HERE/'ATTRIBUTION.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(out['transitions'],out['causes'],out['old_literal_path_still_loses'],out['old_path_loses_with_verified_unique_alignment'])

if __name__=='__main__':main()
