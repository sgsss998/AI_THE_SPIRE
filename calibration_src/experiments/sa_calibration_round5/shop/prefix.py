"""Replay the reconciled development input prefix, including verified extra card plays."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R4 = HERE.parents[1] / 'sa_calibration_round4'
def journal():
    return json.loads((R4/'fresh/PUBLIC_TRACE.json').read_bytes())
def advance(session, frame, action):
    return session.step(action,frame_id=frame.frame_id,action_version=frame.action_version)
def prefix(version, stop):
    j=journal()
    engine=version.make_engine()
    session=version.make_session(engine)
    frame=session.reset(int(j['original_seed'])%(1<<64))
    for row in j['inputs'][:stop]:
        r=row['comparisons']['official_semantic']
        if r['status']=='native_only_acknowledgement':
            if frame.page.startswith('WHEEL_'):
                frame=advance(session,frame,110)
            continue
        frame=advance(session,frame,r['mapped_aid'])
        for extra in r.get('native_effects',[]):
            frame=advance(session,frame,extra['model_action'])
    return engine,session,frame
