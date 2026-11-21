"""Reapply two actual original serpent branches. Never starts or dispatches to the game."""
import argparse
from dataclasses import asdict, replace
from hashlib import sha256
from importlib import import_module
import json
from pathlib import Path
from zipfile import ZipFile

from experiments.ordinary_reward_hooks193.audit import dump, JAR, RETAIL
from experiments.sa_calibration_round1.fidelity.supplement.compare import OLDER
from experiments.sa_calibration_round2.events import verify as old
from experiments.sa_calibration_round3 import release as r3
from experiments.sa_calibration_round3.fresh import replay
from experiments.sa_calibration_round3.fresh.instance import DEST
from native_pilot import libraries
from silent_env.native_compare import json_hash
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError
from .serpent import CONTINUE, LEAVE, decode_offer, event_frame, wrap

HERE = Path(__file__).resolve().parent
R3 = HERE.parents[1] / 'sa_calibration_round3'


def read(p):
    return json.loads(p.read_bytes())


def digest(p):
    return sha256(p.read_bytes()).hexdigest()


def make_session(module, seed):
    engine = module.make_engine()
    session = module.make_session(engine)
    if module is r3:
        session = wrap(engine, session)
    return engine, session, session.reset(seed)


def step(s, f, aid):
    return s.step(aid, frame_id=f.frame_id, action_version=f.action_version)


def check_frame(frame, snapshot, engine):
    g = snapshot['raw']['game_state']
    assert json_hash(snapshot['raw']) == snapshot['raw_hash']
    v = frame.state.vector
    deck = [(engine._source._backend.CARD_IDS[int(v[i]) - 1], int(v[i+1]))
            for i in range(706,898,2) if v[i]]
    assert deck == [(c['id'], c['upgrades']) for c in g['deck']]
    assert len(deck) == v[22]
    assert list(v[:6]) == [g[k] for k in ('current_hp','max_hp','gold','floor','act','ascension_level')]
    assert v[6] == {'MAP':5, 'EVENT':1}[g['screen_type']]
    if v[6] == 1:
        options = g['screen_state']['options']
        assert len(options) == v[1769]
        assert [i for i in range(110,170) if frame.supported_actions[i]] == [110 + o['choice_index'] for o in options if not o['disabled']]
        assert [v[i+5] for i in range(322,322+6*len(options),6)] == [int(not o['disabled']) for o in options]
    return dict(hp=int(v[0]),gold=int(v[2]),deck_count=len(deck),end_card=list(deck[-1]),page=frame.page,
                event_phase=int(v[2969]),engine_steps=frame.engine_steps,original_sha256=snapshot['raw_hash'])


def rejected(s, frame, aid, error):
    try:
        step(s, frame, aid)
    except error:
        return
    raise AssertionError(f'Accepted {aid} with an illegal or previously used frame')


def accepted(module):
    base = R3 / 'fresh'
    baseline = read(base / 'RESULT.json')
    trace = read(base / baseline['replay']['path'])
    seq = replay.rows(base/'ACTIONS.jsonl')
    assert len(seq) == len(trace['trace']) == 93
    engine, session, frame = make_session(module, trace['seed_unsigned'])
    settled = []
    replayed = []
    for record, previous in zip(seq, trace['trace'], strict=True):
        i = record['index']
        assert i == previous['index'] and record['before']['raw_hash'] == json_hash(record['before']['raw'])
        action = previous['mapped_aid']
        if i == 50:
            assert action is None and record['before']['raw']['game_state']['choice_list'] == ['leave']
            check_frame(frame, record['after'], engine)
            continue
        if i in (53,54):
            action = 110
        before = frame
        if i == 52:
            offer = decode_offer(before.state.vector)
            import numpy as np
            assert offer == decode_offer(list(before.state.vector)) == decode_offer(np.asarray(before.state.vector))
            assert decode_offer([]) is None
            held = list(before.state.vector)
            held[17] = 1
            stub = replace(before, state=replace(before.state, vector=tuple(held)))
            for phase in (CONTINUE, LEAVE):
                partial = event_frame(stub, stub, phase)
                assert partial.policy_mask is None and partial.action_gaps == ('serpent_optional_potions_unverified',)
            text = record['before']['raw']['game_state']['screen_state']['options'][0]['text']
            assert offer.gold == 150 and offer.curse == 'Doubt' and str(offer.gold) in text and offer.curse in text
        if i in (53,54):
            assert replay.allowed(frame) == [110]
            rejected(session, frame, 111, UnverifiedSemanticsError)
        frame = step(session, before, action)
        replayed.append(i)
        if i in (51,52,53,54):
            result = check_frame(frame, record['after'], engine)
            if i in (52,53):
                assert replay.allowed(frame) == [110]
            settled.append(dict(index=i, **result))
            rejected(session, before, action, StaleFrameError)
    assert [s['gold'] for s in settled] == [2,2,152,152]
    assert [s['deck_count'] for s in settled] == [15,15,16,16]
    assert [s['page'] for s in settled[1:3]] == [CONTINUE,LEAVE]
    assert settled[2]['end_card'] == ['Doubt',0]
    assert [s['engine_steps']-settled[0]['engine_steps'] for s in settled] == [0,0,1,1]
    assert frame.done and engine._source._env.lost
    endpoint = replay.model(frame, engine)
    assert endpoint['resources'] == trace['original_endpoint']['resources'] == [0,66,152,7,1,20]
    assert endpoint['deck'] == trace['original_endpoint']['deck'] and endpoint['enemies'] == trace['original_endpoint']['enemies']
    final = dict(resources=endpoint['resources'], enemies=endpoint['enemies'], lost=endpoint['lost'], engine_steps=endpoint['engine_steps'])
    return dict(seed='35LAE5197HT9L', original_inputs=len(seq), real_model_actions=len(replayed),
                original_only=[50], quote=asdict(offer), stages=settled, endpoint=final,
                receipt_sha256=digest(base/'ACTIONS.jsonl'))


def declined(module):
    seed = 54072726
    route = read(old.R1/'fidelity/supplement/RESULT.json')['multi']['prefix']
    packets = {r['sequence']:r for r in replay.rows(OLDER/'raw.jsonl') if r.get('raw',{}).get('game_state',{}).get('seed')==seed}
    engine, session, frame = make_session(module, seed)
    receipt = []
    for pt in route:
        input_seq, output = pt['original_input'], pt['output']
        raw = packets[output]
        assert digest(OLDER/'results'/(raw['pending_request_id_at_receipt']+'.json')) == pt['receipt_sha256']
        if input_seq == 262:
            offer = decode_offer(frame.state.vector)
            assert offer.gold == 150 and offer.curse == 'Doubt'
            g = packets[input_seq]['raw']['game_state']
            assert '150' in g['screen_state']['options'][0]['text'] and '疑虑' in g['screen_state']['options'][0]['text']
            receipt.append(check_frame(frame, packets[262], engine))
        frame = step(session, frame, pt['action'])
    assert frame.page == LEAVE and frame.state.vector[2969] == 2
    receipt.append(check_frame(frame, packets[263], engine))
    prior = frame
    frame = step(session, prior, 110)
    rejected(session, prior, 110, StaleFrameError)
    receipt.append(check_frame(frame, packets[264], engine))
    assert [r['gold'] for r in receipt] == [128]*3 and [r['deck_count'] for r in receipt] == [16]*3
    return dict(seed=seed, actual_choice='decline', stages=receipt)


def original_rule():
    cls = 'events.exordium.Sssserpent'
    methods = dump((cls,))[cls]
    assert any('NEW com.megacrit.cardcrawl.cards.curses.Doubt' in ins for ins in methods['<init>()V'])
    assert any('AbstractPlayer.gainGold(I)V' in ins for ins in methods['buttonEffect(I)V'])
    with ZipFile(JAR) as archive:
        data = archive.read('com/megacrit/cardcrawl/'+cls.replace('.','/')+'.class')
    return dict(class_sha256=sha256(data).hexdigest(), jar_sha256=RETAIL, class_name=cls,
                fields={'S9':'event ID', 'S2969':'event phase', 'S2973':'quoted gold'},
                decoded_offer='Doubt is the unique curse named on this event offer. Relic effects at receipt time are separate.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--module', default=r3.__name__)
    parser.add_argument('--output',default='CANDIDATE.json')
    args = parser.parse_args()
    libraries(DEST)
    module = import_module(args.module)
    pin = digest(HERE/'serpent.py')
    result = dict(entry=args.module, wrapped_on_r3=module is r3, module_sha256=pin,
                  original_rule=original_rule(), accepted=accepted(module), declined=declined(module))
    if module is not r3:
        result['signature'] = module.interface_signature().metadata()
    assert pin == digest(HERE/'serpent.py')
    (HERE/args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(result['accepted']['endpoint'], result['declined']['stages'][-1]['gold'])


if __name__ == '__main__':
    main()
