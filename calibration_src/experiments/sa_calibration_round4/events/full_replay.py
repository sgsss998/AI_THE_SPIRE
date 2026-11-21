"""Reuse the unchanged R3 physical-record comparator against the frozen R4 entry."""
from hashlib import sha256
import json
from .verify import HERE,R3,read
from unittest.mock import patch
from experiments.sa_calibration_round3.fresh import replay as previous
from ..fresh.replay import compare


def main():
    with patch.object(previous, 'compare', compare):
        r=previous.run(release_module='experiments.sa_calibration_round4.release')
    assert r['signature']==read(HERE.parent/'INTERFACE.json') and r['signature_unchanged'] and r['stopped_at'] is None
    assert r['replayed']==92 and r['native_only_acknowledgements']==1 and len(r['trace'])==93
    assert not any(t.get('kernel_fallback') or t.get('execution_error') for t in r['trace'])
    assert r['model_endpoint']['lost'] and r['model_endpoint']['resources']==[0,66,152,7,1,20]
    assert r['model_endpoint']['enemies']==r['original_endpoint']['enemies']
    assert all(not t['after']['differences'] for t in r['trace'][50:54])
    counts=r['frame_statistics']['all_actual_frames']
    diffs=[dict(index=t['index'],phase=p,values=t[p]['differences']) for t in r['trace'] for p in ('before','after') if t[p]['differences']]
    result=dict(module=r['release_module'],interface_sha256=sha256((HERE.parent/'INTERFACE.json').read_bytes()).hexdigest(),
                game_actions=93,public_steps=92,kernel_bypass=0,original_only=[t['index'] for t in r['trace'] if t['status']=='native_only_acknowledgement'],
                scoped_groups=counts,differences=diffs,first_action_set_difference=r['first_action_set_difference'],model_terminal=r['model_endpoint'],
                original_terminal=r['original_endpoint'],old_receipt=r['source_sha256'],trace_sha256=sha256(json.dumps(r['trace'],sort_keys=True).encode()).hexdigest())
    (HERE/'FROZEN_REPLAY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(counts, len(diffs))

if __name__=='__main__':main()
