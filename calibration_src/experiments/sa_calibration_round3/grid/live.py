"""Capture two targeted original-game paths in separate, empty profiles."""
import json
import sys
import time
from pathlib import Path
from native_pilot import append, bind, libraries
from native_runtime import now, write
from experiments.common_relic193 import native as common
from experiments.runtime_death_boundary import live as runner

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEEDS = {'neow': (2000014, '1BMN9'), 'wing': (9000028, '5ZWYN')}
CASES = {k:('compact_fixture_r3_grid_'+k,'grid_'+k,code,seed) for k,(seed,code) in SEEDS.items()}
WING_PREFIX = (110,111,110,113,20,1,12,111,111,171,110,110)


def cards(rows):
    return [(c['id'], c['upgrades'], c['uuid']) for c in rows]


def drive(case, dest):
    seed, code = SEEDS[case]
    Transport, _, legal, load, *_ = libraries(dest)
    t, session, oracle, _ = bind(dest, Transport)
    from experiments.ordinary_targeting193.native import NativeGate
    from native_fixture_control import capture
    gate = NativeGate(t, oracle)
    evidence = dest/'grid_evidence'
    evidence.mkdir()
    sys.path.insert(0,str(common.base.PARENT))
    from experiments.neow_direct_frontier193 import control
    common.fixture.CASES=CASES
    control.case=common.fixture.case
    control.start(case,True,dest,t,session,oracle,load)
    def current():
        return t.read_current()
    def observe(label):
        b,n,_=capture(dest,t,session,oracle,load,label)
        g=b.raw['game_state']
        assert cards(g['deck'])==[(c['id'],c['times_upgraded'],c['uuid']) for c in n.payload['master_deck']]
        return b,g,n.payload
    def send(a, label):
        b=current()
        assert a in legal(b.raw), (label,a,legal(b.raw),b.raw['game_state']['screen_type'])
        r=t.step(a,expected_snapshot=b,timeout=18)
        append(evidence/'COMMANDS.jsonl',dict(action=a,label=label,req=r.request_id,status=r.status,before=b.sequence,
               before_sha=b.raw_hash,after=r.after.sequence if r.after else None,after_sha=r.after.raw_hash if r.after else None))
        assert r.status=='observed_transition', (label,r.status)
    prefix=(110,110) if case=='neow' else WING_PREFIX
    for i, a in enumerate(prefix):
        g=current().raw['game_state']
        if case=='wing' and i==11:
            _,g,_=observe('quote')
            assert g['screen_state']['event_id']=='Golden Wing' and g['current_hp']==59 and g['gold']==99
        send(a, f'prefix_{i}')
        if case=='wing' and i in (5,6,8):
            time.sleep(.5)
            q=t.query_state(timeout=8);assert q.status=='query_observation'
    if case=='wing':
        _,g,_=observe('continue')
        assert g['choice_list']==['continue'] and g['current_hp']==52
        send(110,'unique_continue')
    _,g,n=observe('list')
    eligible=cards(g['screen_state']['cards']);original=cards(g['deck'])
    assert eligible==original[1:] and len(set(c[2] for c in original))==len(original)
    assert g['screen_state']['for_transform' if case=='neow' else 'for_purge']
    j=next(i for i,c in enumerate(eligible) if c[0]=='Strike_G' and sum(x[0]=='Strike_G' for x in eligible[:i])==1)
    picked=eligible[j]
    real,=[a for a in n['independent_legal_actions']['semantic_actions'] if a['type']=='choose' and a.get('object_uuid')==picked[2]]
    assert real['choice_index']==j
    send(110+j,'choose_second_strike')
    _,g,_=observe('preview')
    assert g['screen_state']['confirm_up'] and cards(g['deck'])==original
    send(172,'confirm')
    _,g,_=observe('after_confirm')
    assert g['choice_list']==['leave']
    immediate=cards(g['deck'])
    send(110,'unique_leave')
    _,g,_=observe('first_map')
    assert g['screen_type']=='MAP'
    first=cards(g['deck'])
    if case=='neow' and len(first)<len(original):
        time.sleep(.8)
        q=t.query_state(timeout=10);assert q.status=='query_observation'
    _,g,_=observe('settled_map')
    final=cards(g['deck']);left=[c for c in original if c!=picked]
    if case=='neow':
        assert final[:-1]==left and final[-1][2] not in {c[2] for c in original} and final[-1][0]!='Strike_G'
    else:assert final==left
    write(evidence/'RESULT.json',dict(seed=seed,seed_text=code,case=case,original=original,
          eligible=eligible,selected=picked,selected_row=j,immediate=immediate,first_map=first,final=final,
          hp=g['current_hp'],gold=g['gold'],floor=g['floor'],source_session=t.session,now=now(),real_game=True))

def main():
    action,case=sys.argv[1:];name=CASES[case][0]
    dest=ROOT/'native_runtime'/name
    if action=='stage':
        common.HERE,common.CASES=HERE,CASES
        common.stage()
    elif action=='run':
        runner.ID,runner.DEST=name,dest
        runner.drive=lambda:drive(case,dest)
        runner.run()
    else:raise ValueError(action)

if __name__=='__main__':main()
