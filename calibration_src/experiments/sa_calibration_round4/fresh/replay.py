"""Replay this round's completed independent original, with explicit public/diagnostic modes."""
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import argparse
import json
from experiments.sa_calibration_round3.fresh.replay import (
    NATIVE, allowed, compare as compare_r3, digest, map_action, model, now, original, raw_frame,
    repeated_reward_cycles, rows,
)
from .instance import HERE,ROOT

OLD=HERE/'NO_PRIOR_ACTIONS.jsonl'
NEW=HERE/'ACTIONS.jsonl'

def compare(frame, engine, snapshot):
    # The R3 renderer already strips its own two optional observation suffixes
    # before reading hand costs. Remove only the *checked* R4 release tag for
    # that read-only path; all current vector values and actual actions persist.
    if frame.page != 'KERNEL_DIAGNOSTIC':
        from experiments.sa_calibration_round4.release import TAG
        assert frame.state.state_version.endswith(TAG)
        frame = replace(frame,state=replace(frame.state,state_version=frame.state.state_version.removesuffix(TAG)))
    out=compare_r3(frame,engine,snapshot)
    g=snapshot['raw']['game_state']
    if (frame.page=='KERNEL_DIAGNOSTIC' and g['screen_type']=='MAP' and g.get('choice_list')==['boss']
        and g['screen_state']['boss_available'] and out['differences'].get('next_x')=={'model':[0],'original':[]}):
        from experiments.sa_calibration_round3.fresh.replay import norm
        raw=engine._source._current
        bindings=[b for b in raw.bindings if b.policy_id==110 and b.operation=='choose_map_node']
        name=engine._source._backend.ENCOUNTER_NAMES[int(raw.state.vector[15])-1]
        if len(bindings)==1 and norm(name)==norm(g['act_boss']) and engine._source._env.is_valid(bindings[0].simulator_id):
            out['representation_differences']['sole_boss_map_entry']=dict(public_name=name,**out['differences'].pop('next_x'))
    return out


def run(limit=None,release_module='experiments.sa_calibration_round4.release',diagnostic=False,native_effects=False):
    from importlib import import_module
    version=import_module(release_module)
    started=now();signature=version.interface_signature().metadata()
    assert (HERE/'TERMINAL.json').exists(), 'The independent original game must finish before model replay'
    (HERE/'FIRST_SIMULATOR_START.json').write_text(json.dumps(dict(at=started,release=release_module,terminal_sha256=digest(HERE/'TERMINAL.json')))) if not (HERE/'FIRST_SIMULATOR_START.json').exists() else None
    assert json.loads((HERE.parent/'INTERFACE.json').read_bytes())==signature
    old=rows(OLD);new=rows(NEW);journal=(old+new)[:limit]
    assert [r['index'] for r in journal]==list(range(1,len(journal)+1))
    assert all(r['status']=='observed_transition' and r['after'] is not None for r in journal)
    # Import only the captured transport's read-only parser/identity dictionaries.
    from native_pilot import libraries
    from .instance import DEST
    libraries(DEST)
    from silent_env.native_compare import verify_capture_record,json_hash,_jsonl
    evidence_files=set();dispatches={};archive_cache={};archive_sources={}
    def indexed(path,native):
        if path not in archive_cache:
            records,source=_jsonl(path);index={}
            for line,item in records:
                cid=item.get('data',{}).get('capture_id') if native and item.get('kind')=='native_capture' else item.get('raw',{}).get('capture_alignment',{}).get('capture_id') if not native else None
                if cid is None:continue
                assert cid not in index,('Duplicate capture ID',path,cid)
                index[cid]=(line,item)
            archive_cache[path]=index;archive_sources[path]=source
        return archive_cache[path]
    NATIVE.clear()
    def verify_snapshot(sn):
        key=(sn['session'],sn['sequence'])
        if key in NATIVE:return
        dest=DEST
        stream=dest/'bridge/sessions'/sn['session']/'raw.jsonl';tag=sn['raw']['capture_alignment']
        oracle=dest/'native_oracle'/tag['native_session']/'native_oracle.jsonl'
        native_record=indexed(oracle,True)[tag['capture_id']][1];bridge_record=indexed(stream,False)[tag['capture_id']][1]
        cap=verify_capture_record(native_record,bridge_row=bridge_record,scope=dict(native_session=tag['native_session'],
          bridge_session=sn['session'],bridge_sequence=sn['sequence'],native_after_sequence=0,native_through_sequence=tag['native_record_sequence']))
        assert cap.evidence['exact_capture_binding'] and cap.evidence['bracket_verified'] and cap.evidence['bridge_raw_sha256']==sn['raw_hash']==json_hash(sn['raw'])
        NATIVE[key]=cap.payload;evidence_files.update((stream,oracle,stream.parent/'attempts.jsonl'))
        if sn['session'] not in dispatches:dispatches[sn['session']]=rows(stream.parent/'attempts.jsonl')
    full_terminal=json.loads((HERE/'TERMINAL.json').read_bytes())['snapshot']
    verify_snapshot(full_terminal)
    for r in journal:
        for sn in (r['before'],r['after']):
            verify_snapshot(sn)
        if r.get('wire_type')=='physical_hand_key':
            physical=HERE/'PHYSICAL.jsonl';evidence_files.add(physical)
            receipts=[a for a in rows(physical) if a.get('request_id')==r['request_id']]
            sent=[a for a in receipts if a['event']=='physical_dispatch_intent'];done=[a for a in receipts if a['event']=='physical_os_return']
            assert len(sent)==len(done)==1 and done[0]['code']==0 and sent[0]['index']==r['index'] and sent[0]['aid']==r['aid']
            if sent[0].get('uuid'):
                assert r['before']['raw']['game_state']['screen_state']['hand'][r['aid']-110]['uuid']==sent[0]['uuid']
        else:
            sent=[a for a in dispatches[r['before']['session']] if a.get('request_id')==r['request_id'] and a['event']=='dispatch_intent']
            assert len(sent)==1 and sent[0]['command']==r['command']
    seed=journal[0]['before']['raw']['game_state']['seed']%(1<<64)
    assert all(r['before']['raw']['game_state']['seed']%(1<<64)==seed for r in journal)
    from .invocations import captures,received,binding as bind_invoked
    invoked=captures() if native_effects else []
    if diagnostic:
        from .chest_diag import InspectEngine,receipt as diagnostic_receipt
        e=InspectEngine()
    else:
        e=version.make_engine()
    diagnosis_override=False
    s=version.make_session(e);f=s.reset(seed)
    trace=[];first_state=None;first_missing=None;first_mask=None;kernel=False;stop=None;state_paired=True
    from experiments.sa_calibration_round2.frontiers import diagnostic as shared
    for r in journal:
        before=compare(f,e,r['before'])
        native=r['before']['raw']['game_state']
        if kernel and native['screen_type']=='MAP' and native.get('choice_list')==['boss'] and not native['screen_state'].get('next_nodes'):
            raw=e._source._current; candidate=[b for b in raw.bindings if b.policy_id==110 and b.operation=='choose_map_node']
            from experiments.sa_calibration_round3.fresh.replay import norm
            name=e._source._backend.ENCOUNTER_NAMES[int(raw.state.vector[15])-1]
            assert len(candidate)==1 and norm(native['act_boss'])==norm(name)
            aid,identity=110,dict(boss=name,source='bound unique physical boss map action')
        else:
            aid,identity=map_action(r,f,e)
        row=dict(index=r['index'],original_aid=r['aid'],command=r['command'],request_id=r['request_id'],
          native_session=r['before']['session'],before_sequence=r['before']['sequence'],after_sequence=r['after']['sequence'],
          before=before,mapped_aid=aid,physical_binding=identity,model_layer='kernel_diagnostic' if kernel else 'typed_chest_diagnostic' if diagnosis_override else release_module)
        if diagnostic:
            ink=diagnostic_receipt(e._source,r,f)
            if ink is not None:
                row['diagnostic_typed_chest']=ink
                diagnosis_override=True
        retail_mask=set(r.get('legal',[]));model_mask=set(allowed(f))
        nav_only={176} if r['before']['raw']['game_state']['screen_type']=='MAP' else set()
        row['action_set_comparison']=dict(model=sorted(model_mask),original=sorted(retail_mask),
          navigation_only_difference=sorted((model_mask^retail_mask)&nav_only),
          missing_in_model=sorted((retail_mask-model_mask)-nav_only),extra_in_model=sorted((model_mask-retail_mask)-nav_only),
          evidence_status='inventory_only_not_executed_semantics' if r['before']['raw']['game_state']['screen_type']=='HAND_SELECT' else 'reported_masks_not_all_actions_exercised')
        if first_mask is None and (row['action_set_comparison']['missing_in_model'] or row['action_set_comparison']['extra_in_model']):
            first_mask=dict(index=r['index'],**row['action_set_comparison'])
        if before['differences'] and first_state is None:first_state=dict(index=r['index'],phase='before',differences=before['differences'])
        direct=None
        g=r['before']['raw']['game_state'];raw=e._source._current
        if kernel and g['screen_type']=='CARD_REWARD' and raw.state.vector[6]==9 and raw.state.vector[7] and r['command']=='skip':
            offers=[(x['card_identity']['native_id'],int(x['parameters'][1])) for x in raw.choice_metadata['choices']
                    if x['legal'] and x['described'] and x.get('card_identity')]
            orig=[(c['id'],c['upgrades']) for c in g['screen_state']['cards']]
            matches=[b for b in raw.bindings if b.policy_id==177 and raw.backend_mask[b.simulator_id] and e._source._env.is_valid(b.simulator_id)]
            assert offers==orig and len(matches)==1 and g['screen_state']['skip_available'],(offers,orig,matches)
            direct=dict(physical_id=matches[0].simulator_id,original_offers=orig,physical_offers=offers,operation=matches[0].operation)
            aid=177;row['diagnostic_discovery_skip']=direct
        if kernel and raw.state.vector[6]==8:
            from .flat_pages import shop
            direct=shop(r,e,f)
            if direct is not None:
                aid=r['aid'];row['diagnostic_shop']=direct
        if diagnostic and g['screen_type'] in ('COMBAT_REWARD','CARD_REWARD') and raw.state.vector[6]==2 and (aid is None or aid not in allowed(f) or kernel):
            binding,error=shared.reward_binding(r['before'],r['after'],r['aid'],r['command'].split(),raw,e,{})
            row['physical_reward_diagnostic']=binding
            if not error and 'physical_id' in binding:
                direct=binding
                aid=r['aid'];kernel=True
        if aid is None:
            # Native-only acknowledgement is admissible only if the next exact public state realigns.
            aft=compare(f,e,r['after']);choices=r['before']['raw']['game_state'].get('choice_list',[])
            unique=(r['command'] in ('proceed','leave','confirm') or (r['command']=='choose 0' and len(choices)==1))
            if unique and not aft['differences']:
                row.update(status='native_only_acknowledgement',after=aft,aligned_fields=list(aft['original']))
                trace.append(row);continue
            if unique and set(aft['differences'])=={'page'} and r['index']<len(journal):
                following=journal[r['index']];fg=following['before']['raw']['game_state'];fl=fg.get('choice_list',[])
                next_unique=following['command'] in ('proceed','leave','confirm') or following['command']=='choose 0' and len(fl)==1
                future=compare(f,e,following['after'])
                if next_unique and following['before']['raw_hash']==r['after']['raw_hash'] and not future['differences']:
                    row.update(status='native_only_acknowledgement',after=aft,pending_unique_confirmation=dict(index=following['index'],command=following['command'],aligned_fields=list(future['original']),alignment=future,kernel_steps_consumed=0))
                    trace.append(row);continue
            row.update(status='unmapped_physical_action',after_if_no_model_step=aft);trace.append(row);stop=row['index'];break
        if aid not in allowed(f) and direct is None:
            row['missing_public_action']=dict(requested=aid,supported=allowed(f),gaps=list(f.action_gaps))
            if first_missing is None:first_missing=dict(index=r['index'],**row['missing_public_action'])
            if not diagnostic:
                row.update(status='stopped_at_missing_public_action');trace.append(row);stop=row['index'];break
            raw=e._source._current
            binding=next((b for b in raw.bindings if b.policy_id==aid),None)
            if not binding or not e._source._env.is_valid(binding.simulator_id):
                row.update(status='blocked_no_executable_kernel_binding',available_physical_choices=[dict(kind=x['kind_name'],legal=x['legal'],params=list(x['parameters']),physical=x['sim_action']) for x in raw.choice_metadata['choices'] if x['described']],canonical_bindings=[(b.policy_id,b.simulator_id) for b in raw.bindings]);trace.append(row);stop=row['index'];break
            kernel=True;row['kernel_fallback']=dict(simulator_id=binding.simulator_id,operation=binding.operation)
        prior_steps=e._source._env.steps
        try:
            if direct is not None:
                source=e._source;physical=direct['physical_id']
                if physical is not None:
                    assert source._env.is_valid(physical) and source._env.step(physical)
                    source._capture()
                assert source._env.steps == prior_steps + int(physical is not None)
                f=raw_frame(e)
            elif kernel:
                source=e._source;raw=source._current
                binding=next((b for b in raw.bindings if b.policy_id==aid),None)
                if binding is None:raise ValueError('No same-frame candidate binding')
                source.step(aid,frame_id=raw.frame_id);f=raw_frame(e)
            else:f=s.step(aid,frame_id=f.frame_id,action_version=f.action_version)
        except Exception as ex:
            row['execution_error']=repr(ex)
            # A postcondition checker may reject after a real kernel action. Never send it twice.
            if diagnostic and e._source._env.steps==prior_steps+1:
                try:
                    e._source._capture();f=raw_frame(e);kernel=True
                    row['recovery']='Consumed once; capture current kernel and continue diagnostic only'
                except Exception as capture_error:
                    row.update(status='execution_error',capture_error=repr(capture_error));trace.append(row);stop=row['index'];break
            else:
                row.update(status='execution_error',kernel_steps_before=prior_steps,kernel_steps_after=e._source._env.steps)
                trace.append(row);stop=row['index'];break
        extras=[]
        for seq,record in received(r,invoked):
            follow,physical=bind_invoked(r,record,f,e)
            if follow not in allowed(f):
                if not diagnostic:
                    raise RuntimeError(('Incidental original action missing from model',r['index'],follow))
                source=e._source; raw=source._current
                if not any(b.policy_id==follow and source._env.is_valid(b.simulator_id) for b in raw.bindings):
                    raise RuntimeError(('Incidental original action missing from kernel',r['index'],follow))
                kernel=True
            if kernel:
                source=e._source;source.step(follow,frame_id=source._current.frame_id);f=raw_frame(e)
            else:
                f=s.step(follow,frame_id=f.frame_id,action_version=f.action_version)
            extras.append(dict(native_record_sequence=seq, model_action=follow,binding=physical,layer='kernel_diagnostic' if kernel else 'public'))
        if extras:row['native_effects']=extras
        after=compare(f,e,r['after'])
        if after['differences'] and first_state is None:first_state=dict(index=r['index'],phase='after',differences=after['differences'])
        state_paired=state_paired and not after['differences'] and not before['differences']
        row.update(status='physical_action_replayed',after=after,strict_public_fields_equal=not before['differences'] and not after['differences'],
          cumulative_equal=state_paired,model_layer='kernel_diagnostic' if kernel else 'typed_chest_diagnostic' if diagnosis_override else release_module)
        trace.append(row)
    finished=now();sources={str(p.relative_to(ROOT)):archive_sources[p]['sha256'] if p in archive_sources else digest(p) for p in (OLD,NEW,Path(__file__),HERE.parents[1]/'sa_calibration_round3/fresh/replay.py',HERE/'TERMINAL.json',*sorted(evidence_files)) if p.exists()}
    cycles=repeated_reward_cycles(journal);excluded=[i for c in cycles if c['repeated_without_new_content'] for i in (c['start'],c['end'])]
    frames={};meaningful={}
    for t in trace:
        for phase in ('before','after'):
            if phase not in t:continue
            key=t['native_session']+':'+str(t[phase+'_sequence']);frames[key]=t[phase]
            if t['index'] not in excluded:meaningful[key]=t[phase]
    def stats(fr):
        return dict(frames=len(fr),equal_frames=sum(not v['differences'] for v in fr.values()),
          field_groups=sum(len(v['original']) for v in fr.values()),equal_field_groups=sum(len(v['original'])-len(v['differences']) for v in fr.values()))
    return dict(started=started,finished=finished,release_module=release_module, diagnostic_allowed=diagnostic, reconciled_native_physical_effects=native_effects, diagnostic_typed_chest=diagnosis_override, used_kernel=kernel or diagnosis_override,seed_unsigned=seed,signature=signature,
      signature_unchanged=signature==version.interface_signature().metadata(),
      original_actions_available=len(old)+len(new),input_actions=len(journal),replayed=sum(r['status']=='physical_action_replayed' for r in trace),
      repeated_reward_cycles=cycles,repeated_no_content_action_indices=excluded,actions_without_repeated_no_content_cycles=len(journal)-len(excluded),
      frame_statistics=dict(all_actual_frames=stats(frames),frames_for_nonrepetitive_inputs=stats(meaningful)),
      native_only_acknowledgements=sum(r['status']=='native_only_acknowledgement' for r in trace),
      first_state_difference=first_state,first_action_set_difference=first_mask,first_missing_public_action=first_missing,stopped_at=stop,
      model_endpoint=model(f,e),original_endpoint=original(full_terminal),terminal_capture_sequence=full_terminal['sequence'],trace=trace,source_sha256=sources,
      input_record_sha256={r['index']:sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest() for r in journal},
      boundary='Compared public fields only. Direct kernel diagnostics are recorded separately from policy actions. No training or original game dispatch.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int);p.add_argument('--release-module',default='experiments.sa_calibration_round4.release');p.add_argument('--label',default='public');p.add_argument('--diagnostic',action='store_true');p.add_argument('--native-effects',action='store_true');args=p.parse_args()
    assert args.label.replace('_','').isalnum()
    result=run(args.limit,args.release_module,diagnostic=args.diagnostic,native_effects=args.native_effects)
    dest=HERE/'runs'/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+args.label);dest.mkdir(parents=True,exist_ok=False)
    (dest/'RUNNER_SNAPSHOT.py').write_bytes(Path(__file__).read_bytes())
    (dest/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(path=str(dest),actions=result['input_actions'],replayed=result['replayed'],first_state=result['first_state_difference'],first_missing=result['first_missing_public_action'],stop=result['stopped_at'],endpoint=result['model_endpoint']),ensure_ascii=False))
if __name__=='__main__':main()
