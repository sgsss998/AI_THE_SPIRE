"""Reconcile only an archived unique acknowledgement when next full S3122 is identical."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
import json,gzip
from experiments.sa_calibration_round3 import release
from .run import snap
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REFERENCE=ROOT/'experiments/sa_calibration_round2/regression/runs/20261120_201657_722221_R2_privileged_final/full'
def read(p):return json.loads(p.read_bytes())
def main():
    signature=release.interface_signature().metadata();assert signature==read(HERE.parent/'INTERFACE.json')
    rows={x['seed']:x for x in read(REFERENCE/'RESULT.json')['runs']};cases=[]
    for seed in [25,1000056]:
        row=rows[seed];p=Path(row['trace']['path']);assert sha256(p.read_bytes()).hexdigest()==row['trace']['sha256'];old=json.loads(gzip.decompress(p.read_bytes()))
        e=release.make_engine();s=release.make_session(e);f=s.reset(seed,ascension=20,final_act=True);steps=[];skipped=[];first=None;stop=None
        for i,aid in enumerate(row['episode']['actions']):
            now=snap(f,e,s);v=old[i];nxt=old[i+1]
            if (v['page'] in ('GOLDEN_WING_CONTINUE','REMOVE_LEAVE') and v['supported']==[110] and aid==110
                and v['engine_steps']==nxt['engine_steps']==f.engine_steps and now['state']==nxt['state']+[0]
                and now['supported']==nxt['supported'] and now['done']==nxt['done']):
                skipped.append(dict(old_decision=i+1,old_action=aid,current_page=f.page,all_3122_values_equal_to_old_successor=True,same_kernel_step=True,next_supported_equal=True));continue
            delta=[j for j,(a,b) in enumerate(zip(v['state']+[0],now['state'])) if a!=b]
            if delta and first is None:first=dict(old_decision=i+1,indices=delta)
            if not f.supported_actions[aid]:stop=dict(old_decision=i+1,action=aid,page=f.page,supported=now['supported'],gaps=list(f.action_gaps));break
            f=s.step(aid,frame_id=f.frame_id,action_version=f.action_version);steps.append(aid)
        last=snap(f,e,s);expected=old[-1]
        cases.append(dict(seed=seed,original_actions=len(row['episode']['actions']),executed_actions=len(steps),old_only_unique_confirmations=skipped,stop=stop,first_state_difference=first,
          final_all_3122_equal=last['state']==expected['state']+[0],final_kernel_state_equal=all(last[k]==expected[k] for k in ['engine_steps','kernel_floor','kernel_won','kernel_lost','done']),final=last,reference_trace_sha256=row['trace']['sha256']))
    assert signature==release.interface_signature().metadata()
    out=HERE/'semantic_prefix'/datetime.now().strftime('%Y%m%d_%H%M%S_%f');out.mkdir(parents=True,exist_ok=False)
    result=dict(signature=signature,signature_unchanged=True,cases=cases,scope='The strict unmodified-action counts remain unchanged. Only a no-kernel-step unique old confirmation is consumed on the reference side after all next 3122 state values and supported actions match exactly.')
    (out/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');(out/'RUNNER_SNAPSHOT.py').write_bytes(Path(__file__).read_bytes())
    print(out);print([{k:v for k,v in r.items() if k not in ['final']} for r in cases])
if __name__=='__main__':main()
