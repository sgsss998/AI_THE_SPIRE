"""Read resources after leaving a full potion shop through the original Escape key."""
from pathlib import Path
import json,subprocess,time
from native_runtime import now,write
from .native import NATIVE,read
HERE=Path(__file__).resolve().parent
def main():
    d=NATIVE/'compact_native_r5_shop_flex_001';out=d/'shop_check'
    s=Path(read(d/'bridge/active_session.json')['session_dir']);pid=read(d/'process.json')['pid']
    assert read(s/'session.json')['parent_pid']==pid and not (d/'process_exit.json').exists()
    assert 'NOT ENOUGH POTION SLOTS' in (d/'launch.log').read_text() and (out/'full_query.json').exists()
    before=read(s/'current.json')
    if before['raw']['game_state']['screen_type']=='SHOP_SCREEN':
        assert not (out/'full_escape.json').exists()
        proc=subprocess.run([str(HERE/'leave'),str(pid)],capture_output=True,text=True)
        write(out/'full_escape.json',dict(at=now(),pid=pid,code=proc.returncode));proc.check_returncode()
    for _ in range(25):
        b=read(s/'current.json')
        if b['sequence']>read(out/'end.json')['sequence']:break
        time.sleep(.25)
    g=b['raw']['game_state']
    assert b['sequence']>read(out/'end.json')['sequence'] and g['gold']==118
    assert [q['id'] for q in g['potions']]==['SteroidPotion','FearPotion']
    write(out/'full_witness.json',dict(game_message='NOT ENOUGH POTION SLOTS',after=b,after_page=g['screen_type']))
if __name__=='__main__':main()
