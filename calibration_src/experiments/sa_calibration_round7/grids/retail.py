"""Re-open original UUID-bearing samples and compare the current grid and three successive inputs."""
from hashlib import sha256
from pathlib import Path
from experiments.hand_selection_frontiers193 import evidence
from experiments.ordinary_reward_hooks193.audit import dump
from experiments.sa_calibration_round6.reference import read,sha,write
from silent_env.action193 import choice_action
from . import candidate
from .verify import step

HERE=Path(__file__).resolve().parent


def case(seed, prefix, trail, row, *, runtime=candidate):
    e=runtime.make_engine()
    session=runtime.make_session(e)
    f=session.reset(seed)
    for act in prefix:
        f=step(session,f,act)
    states=[]
    for i,r in enumerate(trail):
        g=r['raw']['game_state']
        v=f.state.vector
        expect=[(c['id'],c['upgrades']) for c in g['deck']]
        assert [(e._source._backend.CARD_IDS[int(v[k])-1],int(v[k+1])) for k in range(706,898,2) if v[k]]==expect
        assert (v[0],v[1],v[2],v[3])==(g['current_hp'],g['max_hp'],g['gold'],g['floor'])
        grid=g['screen_type']=='GRID'
        if grid:
            rows=g['screen_state']['cards']
            ids=[c['uuid'] for c in g['deck']]
            for j,c in enumerate(rows):
                assert v[2684+j]-203==ids.index(c['uuid'])
                assert e._source._backend.CARD_IDS[int(v[323+6*j])-1]==c['id']
            if i==1:
                assert g['screen_state']['confirm_up'] and v[28]==1 and v[325+6*row]==1
        # Actions with gameplay effects are directly enumerated from the original UI.
        # Map-route numbering is a separate adapter; audit its state and the actual route above.
        event_actions={}
        if g["screen_type"] in ("EVENT","GRID"):
            buttons=r["raw"]["available_commands"]
            expected_actions={choice_action(j) for j in range(len(g.get("choice_list",[])))} if "choose" in buttons else set()
            expected_actions.update(a for cmd,a in (("confirm",172),("cancel",173)) if cmd in buttons)
            assert not any(p["can_use"] for p in g["potions"])
            expected_actions.update(105+j for j,p in enumerate(g["potions"]) if p["can_discard"] and "potion" in buttons)
            actual={i for i,v in enumerate(f.supported_actions) if v}
            event_actions=dict(missing=sorted(expected_actions-actual),extra=sorted(actual-expected_actions))
            assert not event_actions["extra"]
            if f.policy_mask is not None:
                assert not event_actions["missing"]
        states.append(dict(page=f.page,game=g['screen_type'],retail_hash=r['raw_hash'],deck_size=len(expect),
                           measured_action_gaps=event_actions))
        if i<3:
            act=(110+row,172,110)[i]
            assert f.supported_actions[act]
            f=step(session,f,act)
    return states


def run():
    records=[]
    for path,seq,row,source,nlog in evidence.event_paths():
        truth=evidence.audit(path,seq,row,source,nlog)
        frames={r['sequence']:r for r in evidence.lines(path)}
        prefix=next(r['actions'] for _,r in evidence.cases() if r['seed']==truth['seed'])
        stages=case(truth['seed'],prefix,[frames[j] for j in range(seq,seq+4)],row)
        records.append(dict(source=source,seed=truth['seed'],target=truth['selected_uuid'],
                            replacement=truth['replacement_id'],new_uuid=truth['replacement_uuid'],stages=stages))
    root=evidence.ROOT/'native_runtime/compact_fixture_permanent_upgrade_seed42'
    phases=('grid','preview','result','map')
    trail=[read(root/'fixture_control/observations'/p/'bridge_snapshot.json') for p in phases]
    prefix=[r['action'] for r in evidence.lines(root/'prefix_actions.jsonl')]+[110]
    row=1
    stages=case(42,prefix,trail,row)
    target=trail[0]['raw']['game_state']['screen_state']['cards'][row]['uuid']
    cards=trail[-1]['raw']['game_state']['deck']
    assert [c['upgrades'] for c in cards if c['uuid']==target]==[1]
    records.append(dict(source='Upgrade Shrine',seed=42,target=target,stages=stages))
    methods=dump(('events.exordium.Cleric','events.shrines.PurificationShrine','cards.CardGroup','potions.AbstractPotion','potions.SmokeBomb','potions.FairyPotion'))
    for cl in ('events.exordium.Cleric','events.shrines.PurificationShrine'):
        enter='\n'.join(methods[cl]['buttonEffect(I)V'])
        settle='\n'.join(methods[cl]['update()V'])
        assert 'CardGroup.getPurgeableCards' in enter and 'GridCardSelectScreen.open' in enter and 'openMap()' in enter
        assert 'CardGroup.removeCard' in settle
    assert any('BIPUSH 75' in x for x in methods['events.exordium.Cleric']['<init>()V'])
    assert any('118: INVOKEVIRTUAL com.megacrit.cardcrawl.characters.AbstractPlayer.loseGold' in x for x in methods['events.exordium.Cleric']['buttonEffect(I)V'])
    assert methods['potions.FairyPotion']['canUse()Z']==['0: ICONST_0','1: IRETURN']
    assert any('AbstractPotion.canUse()' in x for x in methods['potions.SmokeBomb']['canUse()Z'][:3])
    obs={'same_seed_original_samples':records,
         'original_methods':{cl:sha256(str(methods[cl]).encode()).hexdigest() for cl in methods},
         'same_seed_new_graphical_games':0}
    write(HERE/'RETAIL.json',obs)
    print([(r['source'],r['seed']) for r in records])


if __name__=='__main__':
    run()
