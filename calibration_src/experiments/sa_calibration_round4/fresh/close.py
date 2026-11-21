"""Close only this isolated process after independently recorded GAME_OVER."""
import json,os,signal
from .instance import DEST,HERE
from native_runtime import write,now,sha
p=json.loads((DEST/'process.json').read_bytes());terminal=json.loads((HERE/'TERMINAL.json').read_bytes())
assert terminal['snapshot']['raw']['game_state']['screen_type']=='GAME_OVER'
assert p['cwd']==str(DEST/'game') and not (DEST/'process_exit.json').exists()
active=json.loads((DEST/'bridge/active_session.json').read_bytes());session=__import__('pathlib').Path(active['session_dir'])
current=json.loads((session/'current.json').read_bytes());assert current['raw']['game_state']['screen_type']=='GAME_OVER'
assert current['raw']['game_state']['seed']==terminal['summary']['seed']
write(HERE/'CLOSE.json',dict(at=now(),pid=p['pid'],instance=DEST.name,terminal_sha256=sha(HERE/'TERMINAL.json'),reason='Natural terminal already captured; close only isolated validation game'))
os.kill(p['pid'],signal.SIGTERM)
