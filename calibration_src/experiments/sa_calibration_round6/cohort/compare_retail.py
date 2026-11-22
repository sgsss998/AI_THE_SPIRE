"""Join the seeded retail control to exact captures and replay its physical selections on R6."""
from pathlib import Path
import re

from native_pilot import libraries
from experiments.sa_calibration_round3.fresh import replay as view
from experiments.sa_calibration_round6 import replay
from experiments.sa_calibration_round6.reference import HERE, ROOT, read, sha, write
from .retail import DEST, OUT, SEED


def play():
    libraries(DEST)
    from silent_env.native_compare import verify_capture_record, json_hash
    source=[OUT/f for f in ('START_INPUT.json','START_OUTPUT.json','ACTIONS.jsonl','END.json')]
    session=Path(read(DEST/'bridge/active_session.json')['session_dir'])
    oracle,=list((DEST/'native_oracle').glob('*/*.jsonl'))
    raw=session/'raw.jsonl';attempts=session/'attempts.jsonl'
    source.extend([oracle,raw,attempts,DEST/'target.json',DEST/'process.json',DEST/'launch.log'])
    original=view.rows(OUT/'ACTIONS.jsonl')
    alignment={r['data']['capture_id']:r for r in view.rows(oracle) if r['kind']=='native_capture'}
    raw_by_seq={r['sequence']:r for r in view.rows(raw)}
    sent={r['request_id']:r for r in view.rows(attempts) if r['event']=='dispatched'}
    assert [r['index'] for r in original]==list(range(1,len(original)+1))
    assert read(OUT/'START_OUTPUT.json')['after']['raw']['game_state']['seed']==SEED
    assert read(OUT/'END.json')['raw']['game_state']['screen_type']=='MAP'
    view.NATIVE.clear()
    for row in original:
        assert sent[row['request_id']]['command']==row['command']
        for label in ('before','after'):
            snap=row[label];key=snap['session'],snap['sequence']
            if key not in view.NATIVE:
                tag=snap['raw']['capture_alignment']
                cap=verify_capture_record(alignment[tag['capture_id']],bridge_row=raw_by_seq[snap['sequence']],scope=dict(
                    native_session=tag['native_session'],bridge_session=key[0],bridge_sequence=key[1],
                    native_after_sequence=0,native_through_sequence=tag['native_record_sequence']))
                assert cap.evidence['exact_capture_binding'] and cap.evidence['bracket_verified'] and cap.evidence['bridge_raw_sha256']==snap['raw_hash']==json_hash(snap['raw'])
                view.NATIVE[key]=cap.payload
    calls=[(r['seq'],r['data']) for r in view.rows(oracle) if r['kind']=='native_card_invoked']
    result=replay.run(original,calls,SEED)
    assert result['signature']==read(HERE/'INTERFACE.json')
    version,=re.findall(r'desktop\.DesktopLauncher> version: (\S+)',(DEST/'launch.log').read_text())
    physical=[]
    for row in original:
        before,after=row['before'],row['after']
        if before['raw']['game_state']['screen_type'] in ('COMBAT_REWARD','CARD_REWARD') or after['raw']['game_state']['screen_type']=='COMBAT_REWARD':
            physical.append(dict(index=row['index'],choice=row['reason'],command=row['command'],reported_controls=row['legal'],
                                 before=view.original(before),after=view.original(after),before_sha256=before['raw_hash'],after_sha256=after['raw_hash']))
    rewards=[x for x in result['records'] if original[x['index']-1]['before']['raw']['game_state']['screen_type'] in ('COMBAT_REWARD','CARD_REWARD')]
    result['reported_reward_menus']={
        'compared':len(rewards),'equal':sum(x['actual_reported']==x['offered'] for x in rewards),
        'indices':[x['index'] for x in rewards],
        'meaning':'Controls recorded by retail transport and offered by public R6 on the five visited reward decisions.'
    }
    result.update(seed=SEED,display='5ZWYT',seed_source='preselected R5 reward-stop cohort',original_reward_inputs=physical,
            genuine_original=True,independent_seed_from_development=True,unseen_random_holdout=False,game_version=version,
            verified_unique_captures=len(view.NATIVE),source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in source})
    write(HERE/'cohort/INDEPENDENT.json',result)
    print(result['completed_inputs'],result['stop'],result['first_content'],flush=True)


if __name__=='__main__':play()
