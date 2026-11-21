"""Read the same decision again after animations settle; retain both captures."""
from .live import *
from native_runtime import now

def check(seed):
    p=dest(seed);ev=p/'r4_death';d=read(ev/'RESULT.json')
    T,*_=libraries(p);t,session,oracle,_=bind(p,T);first=t.read_current()
    assert first.sequence==d['real']['after']
    q=t.query_state(timeout=15)
    assert q.status=='query_observation'
    final=q.after;records=[]
    for snap in (first,final):
        capture=actual(p,t,session,oracle,snap); gs=snap.raw['game_state']
        records.append(dict(sequence=snap.sequence,raw_hash=snap.raw_hash,oracle_capture=snap.raw['capture_alignment'],
            CM=anchors.oracle(gs), CM_monsters=gs['combat_state']['monsters'],
            native_monsters=capture.get('monsters'), keys_in_capture=sorted(capture),
            independent=capture['independent_legal_actions'], raw_legal_buttons=gs.get('choice_list',[])))
    write(ev/'SETTLED.json',dict(query=q.as_dict(),records=records,at=now()))
    import os, signal
    proc=read(p/'process.json');assert proc['pid']==read(session/'session.json')['parent_pid'] and proc['cwd']==str(p/'game')
    assert read(session/'status.json')['pending'] is None
    os.kill(proc['pid'],signal.SIGTERM)

if __name__=='__main__':check(int(sys.argv[1]))
