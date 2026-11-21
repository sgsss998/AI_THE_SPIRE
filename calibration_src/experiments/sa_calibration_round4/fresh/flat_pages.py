"""Original-only shop overlays that the private core flattens into one shop."""


def shop(record, engine, frame):
    native=record['before']['raw']['game_state'];after=record['after']['raw']['game_state']
    screens=(native['screen_type'],after['screen_type']);command=record['command']
    if frame.state.vector[6]!=8 or 'SHOP_ROOM' not in screens:return None
    raw=engine._source._current;choices=[x for x in raw.choice_metadata['choices'] if x['described']]
    assert raw.packet_sha256==raw.choice_metadata['packet_sha256']
    if screens==('SHOP_ROOM','SHOP_SCREEN') and command=='choose 0' and native['choice_list']==['shop']:
        old,store=native,after
    elif screens==('SHOP_SCREEN','SHOP_ROOM') and command=='leave':
        old,store=after,native
    elif screens==('SHOP_ROOM','MAP') and command=='proceed':
        ids=[c['sim_action'] for c in choices if c['kind_name']=='SKIP' and c['legal'] and engine._source._env.is_valid(c['sim_action'])]
        assert len(ids)==1,[(c['kind_name'],c['sim_action']) for c in choices]
        return dict(physical_id=ids[0],scope='exit core shop into original map')
    else:return None
    native_cards=sorted((c['id'],c['upgrades'],c['price']) for c in store['screen_state']['cards'])
    physical_cards=sorted((c['card_identity']['native_id'],int(c['parameters'][1]),int(c['parameters'][2]))
                          for c in choices if c.get('card_identity'))
    assert native_cards==physical_cards and old['gold']==store['gold'] and old['deck']==store['deck'],(native_cards,physical_cards)
    return dict(physical_id=None,scope='original shop open or close, core already at the same stock',cards=native_cards)
