"""Replay four purchases from isolated original game runs, with per-step receipts."""
import argparse, json, os, shutil, signal, subprocess, time
from pathlib import Path
from native_runtime import write, sha, now, verify
from native_pilot import bind,libraries,append
from experiments.sa_calibration_round3.fresh import instance
from experiments.sa_calibration_round2.live import instance as restore

ROOT=Path(__file__).resolve().parents[3]
NATIVE=ROOT/'native_runtime'
R4=ROOT/'experiments/sa_calibration_round4/fresh'
SEED=-8683615973261774583
def ledger(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]

ITEMS={'mirror':"dolly's mirror",'flex':'flex potion','fear':'fear potion','weak':'weak potion'}
def read(p):return json.loads(p.read_bytes())
def step(tr,b,a,legal,out,reason):
    choices=legal(b.raw)
    assert a in choices,(reason,a,choices)
    receipt=tr.step(a,expected_snapshot=b,timeout=25)
    assert receipt.status=='observed_transition',receipt.as_dict()
    append(out/'choices.jsonl',dict(note=reason,aid=a,legal=choices,before=b.as_dict(),after=receipt.after.as_dict(),
                                    request_id=receipt.request_id,command=receipt.command))
    return receipt.after
def resume(dest):
    T,_,legal,_,*_=libraries(dest);tr,s,oracle,_=bind(dest,T);out=dest/'shop_check'
    b=tr.read_current()
    if not b.raw.get('in_game'):
        pid=read(dest/'process.json')['pid']
        assert read(s/'session.json')['parent_pid']==pid
        cmd=dest.parents[1]/'experiments/sa_calibration_round2/live/continue_menu'
        sent=subprocess.run([str(cmd),str(pid)],text=True,capture_output=True)
        append(out/'CONTINUE.jsonl',dict(at=now(),pid=pid,code=sent.returncode,output=sent.stdout))
        sent.check_returncode()
        for _ in range(34):
            time.sleep(.45);b=tr.read_current()
            if b.raw.get('in_game'):break
        assert b.raw.get('in_game'), 'The game did not resume'

def purchase(dest,label):
    T,_,legal,_,*_=libraries(dest);tr,s,oracle,_=bind(dest,T);out=dest/'shop_check';out.mkdir(exist_ok=True)
    b=tr.read_current()
    if not b.raw.get('in_game'):
        resume(dest);b=tr.read_current()
    if b.raw['game_state']['screen_type']=='SHOP_ROOM':
        assert b.raw['game_state']['choice_list']==['shop']
        b=step(tr,b,110,legal,out,'open')
    g=b.raw['game_state']
    assert g['seed']==SEED and g['floor']==5 and g['gold']==229 and g['current_hp']==66 and g['screen_type']=='SHOP_SCREEN'
    assert g['choice_list'][-4:]==list(ITEMS.values())
    ref=ledger(R4/'ACTIONS.jsonl')[50]['before']['raw']['game_state']
    for key in ('relics','potions','cards'):
        assert [(x['id'],x['price']) for x in g['screen_state'][key]]==[(x['id'],x['price']) for x in ref['screen_state'][key]]
    write(out/'shelf.json',b.as_dict())
    aid=110+g['choice_list'].index(ITEMS[label])
    b=step(tr,b,aid,legal,out,'buy_'+label);fresh=b.raw['game_state']
    if label=='mirror':
        if fresh['screen_type']!='GRID':
            time.sleep(.75); q=tr.query_state(timeout=10);b=q.after;fresh=b.raw['game_state']
        assert fresh['screen_type']=='GRID',(fresh['screen_type'],fresh['choice_list'])
        strikes=[c for c in g['deck'] if c['id']=='Strike_G']
        wanted=strikes[1]['uuid']
        grid=fresh['screen_state']['cards'];row=next(i for i,c in enumerate(grid) if c['uuid']==wanted)
        b=step(tr,b,110+row,legal,out,'copy_second_strike')
        if b.raw['game_state']['screen_type']=='GRID' and 172 in legal(b.raw):b=step(tr,b,172,legal,out,'confirm_copy')
        if b.raw['game_state']['screen_type']!='SHOP_SCREEN':
            time.sleep(1.1);b=tr.query_state(timeout=10).after
    if label=='flex':
        g2=b.raw['game_state']; idx=g2['choice_list'].index('fear potion')
        b=step(tr,b,110+idx,legal,out,'fill_second_slot')
        g3=b.raw['game_state']
        if 'weak potion' in g3['choice_list']:
            action=110+g3['choice_list'].index('weak potion');assert action in legal(b.raw)
            attempt=tr.step(action,expected_snapshot=b,timeout=10)
            write(out/'full_attempt.json',dict(before=b.as_dict(),receipt=attempt.as_dict()))
            if attempt.after: b=attempt.after
            else: b=tr.read_current()
    write(out/'end.json',b.as_dict())
    print(label,b.raw['game_state']['screen_type'],b.raw['game_state']['gold'],flush=True)
if __name__=='__main__':
    cmd=argparse.ArgumentParser();cmd.add_argument('op');cmd.add_argument('branch',choices=ITEMS)
    opt=cmd.parse_args();name='compact_native_r5_shop_'+opt.branch+'_001';dest=NATIVE/name
    if opt.op=='stage':
        instance.ID=name;instance.DEST=dest;instance.stage()
    elif opt.op=='restore':
        cfg=verify(dest)
        src=NATIVE/'compact_native_r5_chest_key_001/chest_check/shop.autosave'
        proof=read(src.with_name('shop_save.json'))
        assert sha(src)==proof['sha256'] and (proof['seed'],proof['floor'],proof['gold'])==(SEED,5,229)
        assert not cfg['fixture_mod_enabled'] and not (dest/'process.json').exists()
        out=dest/'shop_check';out.mkdir(exist_ok=True)
        dst=dest/'game/saves/THE_SILENT.autosave';assert not dst.exists()
        shutil.copyfile(src,dst);assert sha(src)==sha(dst)
        write(out/'RESTORE_INPUT.json',dict(target_sha256=sha(dest/'target.json'),source=str(src.relative_to(dest.parents[1])),
                saves={dst.name:dict(sha256=sha(dst))},stage_utc=now()))
    elif opt.op=='launch':
        restore.HERE=dest/'shop_check';restore.DEST=dest;restore.launch()

    elif opt.op=='resume':resume(dest)
    elif opt.op=='purchase':purchase(dest,opt.branch)
    elif opt.op=='close':
        out=dest/'shop_check';assert (out/'end.json').exists()
        pid=read(dest/'process.json')['pid'];session=Path(read(dest/'bridge/active_session.json')['session_dir'])
        assert read(session/'session.json')['parent_pid']==pid
        os.kill(pid,signal.SIGTERM)
