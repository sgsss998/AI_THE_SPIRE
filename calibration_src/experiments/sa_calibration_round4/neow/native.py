"""Independent retail capture for the curse-cost two-card transformation."""
import argparse
import json
import os
from pathlib import Path
import signal
import time

from native_pilot import append, bind, libraries
from native_fixture_control import capture
from native_runtime import launch, sha, write
from experiments.sa_calibration_round3.fresh import instance as base

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAME = 'compact_native_r4_neow48_001'
DEST = ROOT/'native_runtime'/NAME

def read(path):
    return json.loads(path.read_bytes())

def drive():
    Transport, _, legal, load, *_ = libraries(DEST)
    tr, session, oracle, _ = bind(DEST, Transport)
    out = DEST/'neow_r4'
    out.mkdir()
    assert not tr.read_current().raw['in_game']
    receipt = tr.start('THE_SILENT',20,seed='1D',timeout=45)
    write(out/'start.json',receipt.as_dict())
    assert receipt.status == 'observed_start'
    def observe(label):
        b,cap,_ = capture(DEST,tr,session,oracle,load,label)
        g = b.raw['game_state']
        assert g['seed']==48 and g['ascension_level']==20 and g['class']=='THE_SILENT'
        assert cap.payload and cap.payload['master_deck'][0]['uuid']==g['deck'][0]['uuid']
        write(out/(label+'.json'),dict(bridge=b.as_dict(),native=cap.payload,evidence=cap.evidence))
        return b,g,cap.payload
    def send(a,b,note):
        assert a in legal(b.raw)
        r=tr.step(a,expected_snapshot=b,timeout=20)
        append(out/'actions.jsonl',dict(action=a,label=note,req=r.request_id,before=b.sequence,
            status=r.status,after=r.after.sequence if r.after else None,command=r.command))
        assert r.status=='observed_transition'
    b,g,_=observe('talk'); send(110,b,'talk')
    b,g,_=observe('offer'); opening=g['deck']; assert 'transform 2 cards' in g['choice_list'][2] and 'curse' in g['choice_list'][2]
    send(112,b,'accept'); b,g,n=observe('first_grid')
    # Observe delayed award by state query before taking the first actual selection.
    time.sleep(0.8)
    q=tr.query_state(timeout=15);assert q.status=='query_observation'
    b,g,n=observe('settled_grid')
    strikes=[c for c in opening if c['id']=='Strike_G']
    for i,card in enumerate((strikes[1],strikes[1],strikes[1],strikes[0])):
        assert g['screen_type']=='GRID' and not g['screen_state']['confirm_up']
        actions=n['independent_legal_actions']
        assert actions['status']=='complete'
        row,=[x for x in actions['semantic_actions'] if x['type']=='choose' and x.get('object_uuid')==card['uuid']]
        send(110+row['choice_index'],b,f'pick_{i}')
        b,g,n=observe(f'after_{i}')
    if g['screen_type']=='GRID':
        time.sleep(.9)
        q=tr.query_state(timeout=15);assert q.status=='query_observation'
        b,g,n=observe('settled_leave')
    assert g['choice_list']==['leave']
    send(110,b,'leave');b,g,n=observe('map')
    assert g['screen_type']=='MAP' and g['current_hp']==59 and g['gold']==99
    assert len(g['deck'])==14
    result=dict(seed=48,retail=True,original=[c['uuid'] for c in opening],
                chosen=[strikes[1]['uuid'],strikes[0]['uuid']],final=g['deck'],map=b.sequence,
                evidence_sha256={f.name:sha(f) for f in out.iterdir() if f.is_file()})
    assert [c['uuid'] for c in g['deck'][:11]]==[c['uuid'] for c in opening if c['uuid'] not in result['chosen']]
    write(out/'RESULT.json',result)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['stage','launch','drive','close'])
    op=parser.parse_args().mode
    if op=='stage':
        base.ID=NAME; base.DEST=DEST; base.stage()
    elif op=='launch':
        raise SystemExit(launch(NAME))
    elif op=='drive':drive()
    else:
        pid=read(DEST/'process.json')['pid']
        session=Path(read(DEST/'bridge/active_session.json')['session_dir'])
        assert read(session/'session.json')['parent_pid']==pid and read(DEST/'neow_r4/RESULT.json')['retail']
        os.kill(pid,signal.SIGTERM)
