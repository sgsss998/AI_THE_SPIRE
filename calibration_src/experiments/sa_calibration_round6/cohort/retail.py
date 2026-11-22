"""Play a seeded original negative/positive control to the first resolved reward, without focus input."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import time

from native_pilot import append, bind, libraries
from native_runtime import now, sha, write
from experiments.sa_calibration_round3.fresh.replay import rows
from experiments.sa_calibration_round6.reference import ROOT, read

SEED=9000033
DEST=ROOT/'native_runtime/compact_native_r6_control_9000033_002'
OUT=DEST/'cohort_check'


def choose(g,legal):
    screen=g['screen_type']
    choices=g.get('choice_list') or []
    if screen=='EVENT':
        if len(choices)>1:
            return 111, 'second Neow offer'
        return (110 if 110 in legal else 171), 'Neow text confirmation'
    if screen=='MAP':
        nodes=g['screen_state']['next_nodes']
        return 110+next(j for j,n in enumerate(nodes) if n['x']==5),'map x=5'
    if screen=='NONE' and g.get('combat_state'):
        c=g['combat_state']
        targets=[j for j,m in enumerate(c['monsters']) if not m['is_gone'] and m['current_hp']>0]
        for prefer in ('Neutralize','Strike_G','Defend_G'):
            for i,card in enumerate(c['hand']):
                if card['id']==prefer and card['is_playable'] and targets:
                    aid=10*(1+targets[0])+i if card['has_target'] else i
                    if aid in legal:return aid, prefer
        return 170,'end turn'
    if screen=='COMBAT_REWARD':
        for j,row in enumerate(g['screen_state']['rewards']):
            if row['reward_type'] in ('GOLD','POTION','CARD'):
                return 110+j,row['reward_type']
        return 171,'proceed after collection'
    if screen=='CARD_REWARD':return 110,'first physical card'
    raise ValueError((screen,g.get('choice_list'),legal))


def play():
    OUT.mkdir(exist_ok=True)
    Transport,_,legal,*_=libraries(DEST)
    t,s,oracle,_=bind(DEST,Transport)
    frame=t.read_current()
    if not (OUT/'START_INPUT.json').exists():
        assert not frame.raw['in_game']
        cp=os.pathsep.join(map(str,[ROOT/'experiments/ordinary_death193/fixture_build_v2/seed_classes',DEST/'game/desktop-1.0.jar']))
        decoded=subprocess.check_output([str(DEST/'game/jre/bin/java'),'-cp',cp,'SeedRoundTrip',str(SEED)],text=True).strip()
        assert decoded=='9000033=5ZWYT=9000033'
        write(OUT/'START_INPUT.json',dict(seed=SEED,retail_roundtrip=decoded,mode='seeded cross-check',at=now(),start=frame.as_dict()))
        opened=t.start('THE_SILENT',20,seed=decoded.split('=')[1],timeout=45)
        write(OUT/'START_OUTPUT.json',opened.as_dict());assert opened.status=='observed_start',opened.as_dict()
    assert (OUT/'START_OUTPUT.json').exists()
    data=OUT/'ACTIONS.jsonl'
    for idx in range(len(rows(data))+1,100):
        frame=t.read_current();g=frame.raw['game_state']
        assert (g['seed'],g['class'],g['ascension_level'])==(SEED,'THE_SILENT',20)
        if g['floor']==1 and g['screen_type']=='MAP':
            write(OUT/'END.json',frame.as_dict());return
        combat=g.get('combat_state') or {}
        if g['screen_type']=='NONE' and combat and not any(m['current_hp']>0 and not m['is_gone'] for m in combat['monsters']):
            time.sleep(.5);q=t.query_state(timeout=12);assert q.after
            append(OUT/'QUERIES.jsonl',dict(index=idx,reason='wait for reward to settle',after=q.after.as_dict()));continue
        actions=legal(frame.raw);aid,reason=choose(g,actions)
        assert aid in actions,(idx,aid,actions,reason,g.get('choice_list'))
        result=t.step(aid,expected_snapshot=frame,timeout=25)
        assert result.status=='observed_transition',result.as_dict()
        append(data,dict(index=1+len(rows(data)),aid=aid,reason=reason,legal=actions,command=result.command,
                         request_id=result.request_id,before=frame.as_dict(),after=result.after.as_dict()))
        print(idx,g['screen_type'],reason,result.after.raw['game_state']['screen_type'],flush=True)
    raise RuntimeError('No settled first reward within control budget')


def close():
    end=read(OUT/'END.json');proc=read(DEST/'process.json');s=Path(read(DEST/'bridge/active_session.json')['session_dir'])
    assert read(s/'current.json')['raw_hash']==end['raw_hash'] and read(s/'session.json')['parent_pid']==proc['pid']
    assert s.resolve().is_relative_to(DEST.resolve()) and end['raw']['game_state']['screen_type']=='MAP'
    write(OUT/'CLOSE.json',dict(at=now(),pid=proc['pid'],end=sha(OUT/'END.json'),trace=sha(OUT/'ACTIONS.jsonl')))
    os.kill(proc['pid'],signal.SIGTERM)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--close',action='store_true');args=parser.parse_args()
    close() if args.close else play()
