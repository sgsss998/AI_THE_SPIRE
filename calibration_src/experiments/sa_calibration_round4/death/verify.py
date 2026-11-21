"""Verify each frozen occurrence, bind journal receipts, and compare original immediate snapshots."""
import argparse
from hashlib import sha256
from pathlib import Path
import json
from . import session
from .live import HERE, ROOT, read, dest, source
from experiments.sa_calibration_round3.death import anchors, cohort
from experiments.sa_calibration_round4 import release

def digest(path):return sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(s) for s in path.read_bytes().splitlines()]

def before_after(seed,entry):
    prefix, _ = source(seed)
    engine=entry.make_engine(); owner=entry.make_session(engine)
    f=owner.reset(seed)
    trace_ids=[]
    for k,aid in enumerate(prefix):
        assert f.supported_actions[aid], (seed,k,aid)
        trace_ids.append(f.frame_id)
        f=owner.step(aid,frame_id=f.frame_id,action_version=f.action_version)
    was=anchors.scalar(f)
    mask=[a for a,x in enumerate(f.supported_actions) if x]
    result=dict(seed=seed,old_prefix=len(prefix),old_prefix_complete=True,advanced=bool(mask),
                available=mask,initial_gaps=list(f.action_gaps),width=len(f.state.vector),version=f.state.state_version)
    if mask:
        assert len(mask)==1
        aid=mask[0]
        for bad_frame,bad_a in [(trace_ids[-1],aid),(f.frame_id,10 if aid==23 else 20)]:
            # Only the actual original bindings should survive the partial mask.
            if bad_frame==f.frame_id and f.supported_actions[bad_a]:
                continue
            ticks=f.engine_steps
            try: owner.step(bad_a,frame_id=bad_frame,action_version=f.action_version)
            except (ValueError,RuntimeError):pass
            else: raise AssertionError((seed,bad_a,'unsafe action allowed'))
            assert engine._source._env.steps==ticks
        g=owner.step(aid,frame_id=f.frame_id,action_version=f.action_version)
        assert g.engine_steps==f.engine_steps+1
        result.update(after=anchors.scalar(g),before=was,next_supported=[i for i,x in enumerate(g.supported_actions) if x],
            next_gaps=list(g.action_gaps),terminal=g.done,lost=bool(engine._source._env.lost),
            strength_after=[int(r[session.STRENGTH]) for r in session.r3.ordinary.rows(g.state.vector) if r[0]])
    return result

def native(r):
    seed=r['seed'];p=dest(seed);ev=p/'r4_death'; cap=read(ev/'RESULT.json');late=read(ev/'SETTLED.json')
    log=rows(ev/'actions.jsonl');actual=cap['real'];s=p/'bridge/sessions'/cap['source_session']
    raw={z['sequence']:z for z in rows(s/'raw.jsonl')}
    attempts=rows(s/'attempts.jsonl')
    for i,step in enumerate(log):
        for side in ('before','after'):
            assert raw[step[side]]['raw_hash']==step[side+'_hash']
        assert any(z.get('request_id')==step['request'] and z.get('command')==step['command'] and z['event']=='dispatch_intent' for z in attempts)
    assert [a['model_action'] for a in log if a['role']=='prefix']==source(seed)[0]
    assert cap['real']['model_action']==r['available'][0] and len(r['available'])==1
    assert r['before']==cap['native_before'] and r['after']==cap['native_after']
    assert read(p/'process_exit.json')['pid']==read(p/'process.json')['pid']
    assert cap['independent']['boundary']['admissible']
    first,last=late['records'];dead=0 if seed==59 else 1
    assert first['CM']==r['after']
    assert r['strength_after']==[sum(q['amount'] for q in m['powers'] if q['id']=='Strength') for m in first['native_monsters']]
    if seed==19:
        assert r['terminal'] and r['lost'] and late['query']['after']['raw']['game_state']['screen_state']['victory'] is False
    else:
        assert first['native_monsters'][dead]['is_dying'] and not first['native_monsters'][dead]['is_dead']
        assert last['native_monsters'][dead]['is_dead'] and not r['terminal'] and not r['next_supported']
    return dict(seed=seed,actual_actions=len(log),prefix_inputs=r['old_prefix'],action=actual,matching_before=cap['native_before'],
            matching_immediate_after=cap['native_after'],native_after_passive_query=last['CM'],immediate_strength=r['strength_after'],
            passive_strength=[sum(q['amount'] for q in m['powers'] if q['id']=='Strength') for m in last['native_monsters']],
            immediate_dead_flag=first['native_monsters'][dead]['is_dead'],passive_dead_flag=last['native_monsters'][dead]['is_dead'],
            physical_bindings=cap['lethal']['identity'],original_partial_actions=cap['legal_before'],reward_conditioned=False,
            real_terminal=r['terminal'],game_over=late['query']['after']['raw']['game_state']['screen_state'],
            archive_hashes={str(v.relative_to(ROOT)):digest(v) for v in [ev/'RESULT.json',ev/'SETTLED.json',ev/'actions.jsonl',
               s/'raw.jsonl',s/'attempts.jsonl',p/'target.json',p/'fixture_receipt.json',p/'process_exit.json']})

def run(frozen):
    interface=release.interface_signature().metadata()
    if frozen:assert interface==read(HERE.parent/'INTERFACE.json')
    previous=read(cohort.HERE/'COHORT.json')['actual_replays']
    measured=[]
    for row in previous:
        r=before_after(row['seed'],release);measured.append(dict(r,cohort=row['cohort'],old_opened=bool(row['new_actions'])))
    fixed=[r for r in measured if r['cohort']=='fixed']
    assert len(fixed)==20 and len(measured)==21
    cases=[native(r) for r in measured if r['seed'] in (59,19)]
    assert all(any(c['seed']==s for c in cases) for s in (59,19))
    by_seed={r['seed']:r for r in measured}
    assert by_seed[9000020]['available']==[10] and not by_seed[17000028]['available']
    old=[anchors.capture(anchors.triple.SEED,anchors.triple.ARCHIVE,335,release),anchors.capture(anchors.probe.SEED,anchors.probe.ARCHIVE,526,release)]
    assert [r['r3']['a'] for r in old]==[170,10]
    assert all(r['r3']['width']==3122 for r in old)
    return dict(interface=interface,final_interface=frozen,source_sha=digest(HERE/'session.py'),cases=cases,
                fixed_original_cases=20,formerly_open=1,fixed_now_open=sum(r['advanced'] for r in fixed),
                fixed_newly_open=sum(r['advanced'] and not r['old_opened'] for r in fixed),
                fixed_successor_terminals=sum(r.get('terminal',False) for r in fixed),rows=measured,
                controls=old,passive_query_limitation="Seed 59's R4 step returns the immediate original state. The later wall-clock animation completion alone does not generate a model decision.",
                training_updates=0)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');args=p.parse_args()
    result=run(args.final);name='RESULT.json' if args.final else 'CANDIDATE.json'
    (HERE/name).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(result['fixed_now_open'],result['fixed_newly_open'],result['fixed_successor_terminals'])
