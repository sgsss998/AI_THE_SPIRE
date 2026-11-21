"""Drive an isolated seeded original with archived controls bound to physical card/target identity."""
from pathlib import Path
from hashlib import sha256
import gzip
import json
import sys
import time
import traceback

from native_pilot import append, bind, libraries
from native_runtime import write
from experiments.common_relic193 import native as common
from experiments.sa_calibration_round3 import release
from experiments.sa_calibration_round3.fresh import replay as pair
from experiments.ordinary_reward_live193.hand_gui import actual
from experiments.sa_calibration_round3.death import anchors
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CASES={str(seed):(f'compact_fixture_r4_fungi_{seed}',f'r4_fungi_{seed}',code,seed) for seed,code in [(59,'1P'),(19,'J')]}


def read(path):return json.loads(path.read_bytes())
def dest(seed):return ROOT/'native_runtime'/CASES[str(seed)][0]

def stage():
    from attach_native_hand_input import attach
    # The whole batch is staged once. Each profile has a unique bridge and nonce.
    common.HERE,common.CASES=HERE,CASES
    common.stage()
    for key in CASES:attach(dest(key),'0.2.0')

def source(seed):
    index=ROOT/'experiments/sa_calibration_round2/regression/RESULT.json'
    full=read(index)['public']['full']
    path=index.parent/full['path'];assert sha256(path.read_bytes()).hexdigest()==full['sha256']
    r=next(r for r in read(path)['runs'] if r['seed']==seed)
    cf=next(x for x in read(HERE.parent.parent/'sa_calibration_round3/death/COHORT.json')['actual_replays'] if x['seed']==seed)
    trace=Path(r['trace']['path']);assert sha256(trace.read_bytes()).hexdigest()==cf['trace_sha256']
    return r['episode']['actions'],json.loads(gzip.decompress(trace.read_bytes()))

def drive(seed):
    import os
    profile=dest(seed); ev=profile/'r4_death';ev.mkdir(exist_ok=True)
    cutoff=time.monotonic()+105
    while time.monotonic()<cutoff:
        active=profile/'bridge/active_session.json'
        if active.is_file():
            current=Path(read(active)['session_dir'])/'current.json'
            if current.is_file() and read(current)['raw'].get('ready_for_command'):break
        if (profile/'process_exit.json').exists():raise RuntimeError('Original stopped before opening')
        time.sleep(.2)
    T,_,legal,load,*_=libraries(profile);t,s,log,_=bind(profile,T)
    if not (profile/'fixture_control/start_result.json').exists():
        sys.path.insert(0,str(common.base.PARENT))
        from experiments.neow_direct_frontier193 import control
        common.fixture.CASES=CASES
        control.case=common.fixture.case
        control.start(str(seed),True,profile,t,s,log,load)
    actions,trace=source(seed);e=release.make_engine(); owner=release.make_session(e)
    f=owner.reset(seed)
    journal=ev/'actions.jsonl'
    records=[json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
    completed=[rec for rec in records if rec['role']=='prefix']
    if (ev/'RESULT.json').exists():return
    for rec in completed:
        j=rec['model_index'];assert j<len(actions) and actions[j]==rec['model_action']
        f=owner.step(actions[j],frame_id=f.frame_id,action_version=f.action_version)
    start=len(completed)
    def snap():
        b=t.read_current();g=b.raw['game_state'];assert g['seed']==seed and g['ascension_level']==20
        native=actual(profile,t,s,log,b)
        pair.NATIVE[(b.session,b.sequence)]=native
        return b,g,native
    def send(b,a,j,m,role,detail):
        res=t.step(a,expected_snapshot=b,timeout=25)
        if not res.after or res.status!='observed_transition':
            write(ev/f'FAILED_{j}_{b.sequence}.json',res.as_dict());raise RuntimeError((j,a,res.status,res.reason))
        rec=dict(role=role,model_index=j,model_action=m,real_action=a,command=res.command,request=res.request_id,
                 before=b.sequence,after=res.after.sequence,before_hash=b.raw_hash,after_hash=res.after.raw_hash,identity=detail)
        append(journal,rec);return rec
    def refresh():
        time.sleep(.55);q=t.query_state(timeout=10);assert q.status=='query_observation'
    for i in range(start,len(actions)+1):
        m=actions[i] if i<len(actions) else None
        assert list(f.state.vector[:3118])==trace[i]['state']
        for retry in range(6):
            b,g,n=snap();sc=g['screen_type'];c=g.get('combat_state');v=f.state.vector;mod=pair.model(f,e)
            raw=pair.original(b.as_dict())
            if pair.PAGES.get(sc)!=int(v[6]):
                avail=legal(b.raw)
                choices=g.get('choice_list',[])
                if sc=='EVENT' and choices in (['leave'],['continue']) and avail.count(110)==1:
                    send(b,110,i,None,'native_ack',choices);continue
                if retry<3:refresh();continue
                raise RuntimeError(('page divergence',i,sc,v[6],choices))
            differences={k:(mod.get(k),raw[k]) for k in ('resources','deck','enemies','turn_energy_block') if k in raw and mod.get(k)!=raw[k]}
            if differences:
                if retry<3:refresh();continue
                raise RuntimeError(('content divergence',i,differences))
            break
        else:raise RuntimeError(('no stable frame',i))
        if m is None:
            if not c or [x['id'] for x in c['monsters']]!=['FungiBeast','FungiBeast']:
                raise RuntimeError(('unexpected monsters',i,[x['id'] for x in c['monsters']]))
            ids=legal(b.raw);dead=next(j for j,row in enumerate(c['monsters']) if row['current_hp']==0)
            target=1-dead
            aid=170 if seed==19 else next(a for a in ids if 10*(target+1)<=a<10*(target+2) and c['hand'][a%10]['id']=='Strike_G')
            mappable=pair.map_action({'aid':aid,'before':b.as_dict()},f,e)
            rec=send(b,aid,i,mappable[0],'follow',mappable[1])
            end,after,na=snap()
            write(ev/'RESULT.json',dict(seed=seed,steps=i,lethal=completed[-1] if start==i else json.loads(journal.read_text().splitlines()[-2]),native_before=anchors.oracle(g),native_after=anchors.oracle(after),
                         native_monster_flags_before=[{k:r.get(k) for k in ('id','is_dying','is_dead','is_gone','powers')} for r in c['monsters']],
                         native_monster_flags_after=[{k:r.get(k) for k in ('id','is_dying','is_dead','is_gone','powers')} for r in after['combat_state']['monsters']],
                         legal_before=ids, independent=n['independent_legal_actions'], next_legal=legal(end.raw),
                         real=rec,model_stopped=list(f.action_gaps),source_session=s.name))
            return
        if sc=='HAND_SELECT':
            mask=t.hand_executable_mask(expected_snapshot=b,action_version='silent-canonical-row-a193-v1')
            ids=[i for i,flag in enumerate(mask) if flag]
        else: ids=legal(b.raw)
        pairs=[]
        for aid in ids:
            try:
                mapped,why=pair.map_action({'aid':aid,'before':b.as_dict()},f,e)
            except (IndexError,KeyError,TypeError):
                continue
            if mapped==m:pairs.append((aid,why))
        if len(pairs)!=1:raise RuntimeError(('binding',i,m,sc,ids,pairs,g.get('choice_list'),g.get('screen_state'),pair.options(f)))
        aid,why=pairs[0];send(b,aid,i,m,'prefix',why);f=owner.step(m,frame_id=f.frame_id,action_version=f.action_version)
    raise AssertionError

if __name__=='__main__':
    op=sys.argv[1]
    if op=='stage':stage()
    else:
        seed=int(sys.argv[2])
        if op=='launch':
            from native_runtime import launch
            raise SystemExit(launch(dest(seed).name))
        if op=='drive':
            try:drive(seed)
            except Exception as exc:
                path=dest(seed)/'r4_death';path.mkdir(exist_ok=True)
                append(path/'stops.jsonl',dict(error=repr(exc),trace=traceback.format_exc()));raise
