"""Build a content-addressed index from a completed frozen R3 run; no game execution."""
from pathlib import Path
from hashlib import sha256
from collections import Counter
from datetime import datetime,timezone
import argparse,gzip,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def digest(p):return sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def load_trace(ref):
    p=Path(ref['path']);assert digest(p)==ref['sha256'];return json.loads(gzip.decompress(p.read_bytes()))
def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();run=a.run.resolve();top=read(run/'RESULT.json');full=read(run/'full/RESULT.json');targets=read(HERE/'FOCUSED_53.json')
    assert top['valid'] and top['signature_unchanged'] and top['current_interface']==read(HERE.parent/'INTERFACE.json')
    assert full['fixed']['seeds']==640 and full['additional']['seeds']==64
    assert not full['fixed']['errors'] and not full['additional']['errors']
    cases=[];by_seed={r['seed']:r for r in full['runs']};dimensions=Counter();mask_changes=0;all_changes=[]
    for row in full['runs']:
        trace=load_trace(row['trace']);force=row['forced'];chosen=load_trace(force['trace']) if 'trace' in force else trace[:force['archived_action_count']+1]
        rp=Path(top['reference_run'])/'full/traces'/f"{row['seed']}.json.gz";assert digest(rp)==row['reference_trace_sha256'];old=json.loads(gzip.decompress(rp.read_bytes()))
        changed=[]
        for i,(u,v) in enumerate(zip(old,chosen)):
            delta=[j for j,(x,y) in enumerate(zip(u['state']+[0],v['state'])) if x!=y];dimensions.update(delta)
            masks={k:{'old':u[k],'new':v[k]} for k in ('page','done','engine_steps','supported','legal','gaps') if u[k]!=v[k]}
            if any(k in masks for k in ('supported','legal','gaps')):mask_changes+=1
            if delta or masks:changed.append(dict(observation=i,indices=delta,fields=masks))
        if changed:all_changes.append(dict(seed=row['seed'],cohort=row['cohort'],first=changed[0],changed_observations=len(changed)))
    for old in targets['cases']:
        r=by_seed[old['seed']];f=r['forced'];trace=load_trace(r['trace']);n=f['archived_action_count'];same=f['mode']=='reused_identical_resampled_prefix';stop=trace[n] if same else load_trace(f['trace'])[-1]
        actual_after=trace[n+1:] if same else []
        cases.append(dict(seed=r['seed'],category=old['category'],old_public_stop_action_count=n,old_prefix_complete=f['prefix_complete'],
          public_actions_at_old_stop=stop['supported'],remaining_gaps_at_old_stop=stop['gaps'],old_stop_opened=bool(stop['supported']),
          public_actions_after_old_stop=len(actual_after),kernel_steps_after_old_stop=actual_after[-1]['engine_steps']-stop['engine_steps'] if actual_after else 0,
          first_new_action=r['episode']['actions'][n] if actual_after else None,first_new_observation=actual_after[0] if actual_after else None,
          first_semantic_difference=f['first_semantic_difference'],free_endpoint={k:v for k,v in r['episode'].items() if k!='actions'},free_actions_share_entire_old_prefix=same))
    groups={}
    for category in {x['category'] for x in cases}:
        rows=[x for x in cases if x['category']==category];groups[category]=dict(seeds=len(rows),old_prefix_complete=sum(x['old_prefix_complete'] for x in rows),old_stop_opened=sum(x['old_stop_opened'] for x in rows),actual_public_followup=sum(x['public_actions_after_old_stop']>0 for x in rows),outcomes=dict(Counter(x['free_endpoint']['reason'] for x in rows)))
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f');out=HERE/'analyses'/stamp;out.mkdir(parents=True,exist_ok=False)
    analysis=dict(checked_at=datetime.now(timezone.utc).isoformat(),run=str(run.relative_to(ROOT)),groups=groups,target_cases=cases,changed_dimensions=dict(dimensions),action_mask_or_gap_changed_observations=mask_changes,all_seed_first_differences=all_changes)
    ap=out/'RESULT.json';ap.write_text(json.dumps(analysis,ensure_ascii=False,indent=2)+'\n')
    rel=lambda p:dict(path=str(p.relative_to(HERE)),sha256=digest(p))
    result=dict(created_at=datetime.now(timezone.utc).isoformat(),interface=top['current_interface'],run=rel(run/'RESULT.json'),full=rel(run/'full/RESULT.json'),focused=rel(run/'focused/RESULT.json'),analysis=rel(ap),targets=rel(HERE/'FOCUSED_53.json'),summary={k:full[k] for k in ('fixed','additional')},focused_groups=groups,training_steps=0,interpretation='Legacy-prefix compatibility, first-stop opening and complete free-policy endpoints are separate. Only the official R3 session is used; no diagnostic kernel bypass.')
    path=HERE/'RESULT.json';assert not path.exists();path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(path=str(path),sha256=digest(path),groups=groups),ensure_ascii=False))
if __name__=='__main__':main()
