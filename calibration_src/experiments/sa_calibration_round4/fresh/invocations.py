"""Bind an incidental physical key effect to its original native useCard invocation."""
import json
from experiments.sa_calibration_round3.fresh import replay as base
from .instance import DEST


def captures():
    log, = (DEST/'native_oracle').glob('*/native_oracle.jsonl')
    return [(r['seq'],r['data']) for line in log.open() if (r:=json.loads(line))['kind']=='native_card_invoked']


def received(record, invocations):
    if record.get('wire_type') != 'physical_hand_key':
        return []
    lo = record['before']['raw']['capture_alignment']['native_record_sequence']
    hi = record['after']['raw']['capture_alignment']['native_record_sequence']
    return [(seq,data) for seq,data in invocations if lo < seq <= hi]


def binding(record, data, frame, engine):
    assert record['aid'] == 172 and data['source']=='AbstractPlayer.useCard'
    pos = data['hand_position']
    assert pos['status']=='matched_by_object_identity'
    i=pos['index']; native_card=data['card']
    g=record['before']['raw']['game_state']
    hand=g['screen_state']['hand']
    assert hand[i]['uuid']==native_card['uuid'] and data['turn']==g['combat_state']['turn']
    face=base.card(hand[i]);ordinal=sum(base.card(x)==face for x in hand[:i])
    card_slot=base.select_face(base.hand(frame,engine),face,ordinal)
    target=data['target']
    assert target['kind']=='monster' and target['status']=='matched_by_object_identity'
    t=target['monster_position']['index'];monsters=g['combat_state']['monsters']
    assert monsters[t]['id']==target['id']
    ids=[base.norm(m['id']) for m in monsters]
    index=base.select_face([m[0] for m in base.model(frame,engine)['enemies']],ids[t],ids[:t].count(ids[t]))
    assert index is not None and card_slot is not None
    return 10*(1+index)+card_slot, dict(uuid=native_card['uuid'],card=face,hand_index=i,target=target['id'],target_row=t,
                                         callback_source=data['source'],turn=data['turn'])
