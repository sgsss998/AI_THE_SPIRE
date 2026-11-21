import json
from hashlib import sha256
from pathlib import Path
from experiments.sa_calibration_round5 import release as r5
from experiments.sa_calibration_round4 import release as parent
from experiments.sa_calibration_round5.shop.prefix import prefix,advance,R4
from silent_env.runtime import StaleFrameError
from .session import wrap,observer

def measure(version=None):
    version=version or r5
    retail=[json.loads(x) for x in (R4/'fresh/ACTIONS.jsonl').read_bytes().splitlines()]
    engine,session,frame=prefix(version,44); seen=[]
    for index in range(45,49):
        entry=retail[index-1]; before=frame
        assert before.state.vector[0]==entry['before']['raw']['game_state']['current_hp']
        frame=advance(session,frame,110);v=frame.state.vector;g=entry['after']['raw']['game_state']
        assert tuple(v[:3])==(g['current_hp'],g['max_hp'],g['gold'])
        assert len(g['deck'])==v[22] and len(g['relics'])==v[23]
        try:advance(session,before,110)
        except StaleFrameError:pass
        else:raise AssertionError('Consumed wheel token accepted')
        seen.append(dict(input=index,original_command=entry['command'],label=entry['before']['raw']['game_state']['choice_list'],
                         before_hp=int(before.state.vector[0]),after_hp=int(v[0]),gold=int(v[2]),page=frame.page,
                         core_steps=frame.engine_steps,original_before=entry['before']['raw_hash'],original_after=entry['after']['raw_hash']))
    assert [x['core_steps'] for x in seen]==[seen[0]['core_steps']+i for i in (0,0,1,1)]
    assert [x['after_hp'] for x in seen]==[65,65,66,66] and frame.state.vector[6]==5
    return dict(interface=version.interface_signature().metadata(),source='R4 real development game 2W47ZBJ8TBFMD',original_sha256=sha256((R4/'fresh/ACTIONS.jsonl').read_bytes()).hexdigest(),
                verified_outcome='heal',other_outcomes_verified=0,receipts=seen)
if __name__=='__main__':
    out=measure();(Path(__file__).resolve().parent/'RESULT.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
