"""Replay archived retail evidence and late diagnostic starts without launching the game."""
from collections import Counter
from hashlib import sha256
import importlib
import importlib.util
import json
from pathlib import Path
from random import Random
import subprocess
from tempfile import TemporaryDirectory

from experiments.retail_map_layout193.later import evidence, public_heart_layout, route_fixture, HEART
from experiments.retail_map_layout193.model import PINNED_BUILD, PINNED_SHA
from experiments.retail_map_layout193.verify import from_rows, from_observation, differences
from experiments.sa_calibration_round3.fresh.replay import PAGES, allowed, card, model, norm
from experiments.sa_calibration_round7.episode import select, snapshot
from silent_env.observation import schema
from .entry import prepared

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARCHIVE = ROOT.parent / 'AI_THE_SPIRE_实机验证'
ACT2 = ARCHIVE / '20261114/captures/20261114_234424_41550'
RUNS = ARCHIVE / '20261115_SA验收/baseline/game_profile/runs'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def histories():
    counts = Counter()
    heart = []
    for path in sorted(RUNS.glob('*THE_SILENT/[0-9]*.run')):
        r = json.loads(path.read_bytes())
        if r['character_chosen'] != 'THE_SILENT' or r['ascension_level'] != 20 or any(r[k] for k in ('is_endless','is_daily','is_trial')):
            continue
        counts['runs'] += 1
        damage = r.get('damage_taken', [])
        for key, lo, hi in [('act2_combat',18,34), ('act3_combat',35,51), ('act4_combat',52,56)]:
            counts[key] += int(any(lo <= item['floor'] <= hi for item in damage))
        if damage and damage[-1]['enemies'] == 'The Heart':
            counts['heart_fights'] += 1
            if r['victory']:
                heart.append(dict(file=path.relative_to(RUNS).as_posix(), sha256=digest(path), combat=damage[-1], summary_floor=r['floor_reached']))
    return dict(counts=counts, winning_summaries=heart)


def compile_parasite(directory):
    assert digest(PINNED_BUILD) == PINNED_SHA
    record = json.loads(PINNED_BUILD.read_bytes())['modules']['_fixture_setup']
    target = Path(directory) / record['file'].replace('_fixture_setup', '_r7_parasite')
    args = list(record['args'])
    args[args.index(str(PINNED_BUILD.parent / 'sources/_fixture_setup.cpp'))] = str(HERE / 'parasite.cpp')
    args[-1] = str(target)
    subprocess.run(args, check=True)
    spec = importlib.util.spec_from_file_location('_r7_parasite', target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native(g):
    s = dict(resources=[g[k] for k in ('current_hp','max_hp','gold','floor','act','ascension_level')],
             page=PAGES.get(g['screen_type'],0), deck=[card(c) for c in g['deck']],
             relics=[[norm(r['id']),r['counter']] for r in g['relics']],
             potions=[norm(p['id']) if p['id'] != 'Potion Slot' else None for p in g['potions']])
    if g.get('combat_state'):
        c = g['combat_state']
        mons = c['monsters']
        s.update(turn_energy_block=[c['turn'], c['player']['energy'], c['player']['block']],
                 hand=[card(x) for x in c['hand']], selected_hand=[card(x) for x in g['screen_state'].get('selected',[])],
                 pile_counts=[len(c[k]) for k in ('draw_pile','discard_pile','exhaust_pile')],
                 enemies=[[norm(m['id']), m['current_hp'], m['max_hp'], m['block']] for m in mons],
                 enemy_intents=[[norm(m['id']),schema()['enums']['Intent'][m['intent']]+1] for m in mons if m['current_hp']>0])
        for key in ('draw','discard','exhaust'):
            s[key+'_multiset']=sorted(card(x) for x in c[key+'_pile'])
        s['incoming']=[[m['move_adjusted_damage'],m['move_hits']] for m in mons]
        s['enemy_powers']=[[{p['id']:p['amount'] for p in m['powers']}.get(key,0) for key in ('Plated Armor','Poison','Vulnerable','Weakened')] for m in mons]
    if g['screen_type'] == 'CARD_REWARD':
        s['offered_cards'] = [card(c) for c in g['screen_state']['cards']]
    if g['screen_type'] == 'COMBAT_REWARD':
        s['rewards'] = [[r['reward_type'],r.get('gold') if r['reward_type']=='GOLD' else None] for r in g['screen_state']['rewards']]
    return s


def bind(command, g, frame, engine):
    parts = command.split()
    if parts[0] == 'play':
        hand = [card(c) for c in g['combat_state']['hand']]
        i = int(parts[1])-1
        physical = hand[i]
        previous = sum(c == physical for c in hand[:i])
        visible = model(frame, engine).get('hand',[])
        slots = [j for j,c in enumerate(visible) if c == physical]
        if len(slots) <= previous:
            return None
        if len(parts) == 2:
            return slots[previous]
        assert parts[2] == '0' and len(g['combat_state']['monsters']) == 1
        if model(frame,engine).get('enemies',[[]])[0][0] != norm(g['combat_state']['monsters'][0]['id']):
            return None
        return 10 + slots[previous]
    if parts[0] == 'potion':
        assert parts[1] == 'use' and parts[3] == '0'
        slot = int(parts[2]); p = g['potions'][slot]
        if slot >= len(model(frame,engine)['potions']) or model(frame,engine)['potions'][slot] != norm(p['id']):
            return None
        # CommunicationMod accepts a throw target for Explosive Potion; the
        # simulator exposes its all-enemies effect as one target-free control.
        if p['id'] == 'Explosive Potion':
            return 70 + slot
        return 75 + slot if p['requires_target'] else 70 + slot
    if parts[0] == 'choose':
        slot = int(parts[1]); v=frame.state.vector
        if g['screen_type'] == 'HAND_SELECT':
            choices=g['screen_state']['hand']; target=card(choices[slot]); nth=sum(card(c)==target for c in choices[:slot]); rows=[]
            for i in range(64):
                start=322+i*6
                if v[start] == 1 and v[start+5]:
                    face=[engine._source._backend.CARD_IDS[int(v[start+1])-1],int(v[start+2])]
                    if face==target: rows.append(i)
            return 110+rows[nth] if nth<len(rows) else None
        if g['screen_type'] == 'COMBAT_REWARD':
            expected=native(g)['rewards'][slot]; options=model(frame,engine)['rewards']
            hits=[i for i,x in enumerate(options) if x==expected]
            return 110+hits[0] if len(hits)==1 else None
        return None
    return {'confirm':172,'end':170}.get(command)


def extra_reward_choices(runtime, seed, setup, prefix, previous, displayed):
    # Each branch starts from the same real autosave. Only opening the card
    # bundle was clicked in retail. Extra choices test payouts in the simulator.
    evidence=[]
    for name, actions, expected_card in [('gold',[110],None),('return',[111,177],None)]+[
            ('card_'+str(i),[111,110+i],face) for i,face in enumerate(displayed)]:
        engine,session,f=prepared(runtime,seed,setup)
        for action in prefix:
            assert f.supported_actions[action]
            f=session.step(action,frame_id=f.frame_id,action_version=f.action_version)
        assert snapshot(f)['sha256']==previous['simulator']['sha256']
        initial=model(f,engine)
        for a in actions:
            assert f.supported_actions[a],(name,a,allowed(f))
            f=session.step(a,frame_id=f.frame_id,action_version=f.action_version)
        actual=model(f,engine)
        expected_gold=initial['resources'][2]+(previous['original_options'][0][1] if name=='gold' else 0)
        expected_deck=initial['deck']+([expected_card] if expected_card else [])
        assert actual['resources'][2]==expected_gold and actual['deck']==expected_deck
        assert actual['relics']==initial['relics'] and actual['potions']==initial['potions']
        expected_rows=initial['rewards'][1:] if name=='gold' else initial['rewards'] if name=='return' else initial['rewards'][:1]
        assert actual['rewards']==expected_rows
        evidence.append(dict(branch=name,actions=actions,gold=expected_gold,deck_size=len(expected_deck),
                             card_added=expected_card,remaining_rewards=actual['rewards'],verified=True))
    return evidence


def parasite(runtime, directory):
    raw = {r['sequence']: r for r in jsonl(ACT2/'raw.jsonl')}
    archive_actions = jsonl(ACT2/'actions.jsonl')
    sent = {r['request_id'] for r in archive_actions if r['event']=='sent'}
    dispatches = {r['before_sequence']:r for r in archive_actions if r['event']=='dispatch_intent'}
    assert list(sorted(dispatches))==list(range(4,34))
    for k, cmd in dispatches.items():
        assert cmd['expected_state_hash']==cmd['before_state_hash']==raw[k]['state_hash']
        assert cmd['request_id'] in sent and raw[k+1]['recent_action_request_id']==cmd['request_id']
    g = raw[4]['payload']['game_state']; seed=g['seed']%(1<<64)
    fixture = compile_parasite(directory)
    pre_save=RUNS.parent / 'saves/THE_SILENT.autosave.backUp'
    def setup(core):
        return fixture.enter(core,str(pre_save))
    engine, session, frame = prepared(runtime,seed,setup)
    comparisons=[]; accepted=[]; stop=None; k=4
    while k in raw:
        g=raw[k]['payload']['game_state']; expected=native(g); actual=model(frame,engine)
        v=frame.state.vector
        if g.get('combat_state') and v[7]:
            for name,base in [('draw',1313),('discard',1441),('exhaust',1569)]:
                actual[name+'_multiset']=sorted([engine._source._backend.CARD_IDS[int(v[i])-1],int(v[i+1])] for i in range(base,base+128,2) if v[i])
            actual['incoming']=[[int(v[i+8]),int(v[i+9])] for i in range(993,1253,52) if v[i]]
            actual['enemy_powers']=[[int(v[i+j]) for j in (17,18,22,23)] for i in range(993,1253,52) if v[i]]
        diff={key:{'native':value,'model':actual.get(key)} for key,value in expected.items() if actual.get(key)!=value}
        compared={key:actual.get(key) for key in expected}
        encoded=lambda obj:json.dumps(obj,sort_keys=True,separators=(',', ':')).encode()
        comparisons.append(dict(sequence=k,checked=list(expected),diff=diff,native_state_hash=raw[k]['state_hash'],
                                native_fields=expected, native_fields_sha256=sha256(encoded(expected)).hexdigest(),
                                model_fields_sha256=sha256(encoded(compared)).hexdigest(),simulator=snapshot(frame)))
        if g['screen_type'] in ('COMBAT_REWARD','CARD_REWARD'):
            raw_source=engine._source._current
            comparisons[-1]['kernel_choices']=[list(map(int,raw_source.raw_base[i:i+6])) for i in range(322,706,6) if raw_source.raw_base[i]]
            comparisons[-1]['kernel_legal']=[i for i,x in enumerate(raw_source.backend_mask) if x]
            comparisons[-1]['original_options']=expected.get('rewards',expected.get('offered_cards'))
        if k not in dispatches:break
        cmd=dispatches[k]
        if actual['page']!=expected['page']:
            stop=dict(sequence=k,reason='different page',command=cmd['command']);break
        action=bind(cmd['command'],g,frame,engine)
        if action is None or not frame.supported_actions[action]:
            stop=dict(sequence=k,reason='unbound or unsupported physical action',command=cmd['command'], mapped=action,
                      native_request=cmd['request_id'], legal=allowed(frame), gaps=list(frame.action_gaps));break
        frame=session.step(action,frame_id=frame.frame_id,action_version=frame.action_version)
        accepted.append(dict(sequence=k,action=action,command=cmd['command'],native_request=cmd['request_id']));k+=1
    rewards=raw[33]['payload']['game_state']['screen_state']['rewards']
    assert [r['reward_type'] for r in rewards]==['GOLD','CARD']
    native_offers=[card(c) for c in raw[34]['payload']['game_state']['screen_state']['cards']]
    kernel_menu=next((r.get('kernel_choices') for r in comparisons if r['sequence']==33),None)
    reward_independent=None
    if kernel_menu:
        card_ids=engine._source._backend.CARD_IDS
        model_gold=[r[1] for r in kernel_menu if r[0]==4]
        model_offers=[[card_ids[r[1]-1],r[2]] for r in kernel_menu if r[0]==1]
        reward_independent=dict(native_gold=rewards[0]['gold'],model_gold=model_gold,native_cards=native_offers,model_cards=model_offers,
                                matches=(model_gold==[rewards[0]['gold']] and model_offers==native_offers))
    reward_frame=next((r for r in comparisons if r['sequence']==33),None)
    extra=[]
    if reward_frame and {110,111}.issubset(reward_frame['simulator']['legal']):
        prefix=[r['action'] for r in accepted if r['sequence']<33]
        extra=extra_reward_choices(runtime,seed,setup,prefix,reward_frame,native_offers)
    continuation=None
    if stop is None and k==34:
        rng=Random(seed+8384); visits=Counter();more=[]; checkpoints=[snapshot(frame)]
        while not frame.done and allowed(frame) and len(more)<2000:
            a=select(frame,allowed(frame),rng,'survival',visits); prior=frame
            frame=session.step(a,frame_id=frame.frame_id,action_version=frame.action_version);more.append(a)
            if frame.page!=prior.page or frame.state.vector[3:9]!=prior.state.vector[3:9]:
                checkpoints.append(snapshot(frame))
        continuation=dict(from_native_sequence=34,policy='survival',actions=more,checkpoints=checkpoints,
                          end=snapshot(frame),kernel_end_floor=engine._source._env.floor,
                          reason='loss' if engine._source._env.lost else 'win' if engine._source._env.won else 'cap' if len(more)==2000 else 'unsupported')
    return dict(seed=seed,real_commands=30,simulator_only_continuation=continuation,simulator_only_reward_branches=extra,precombat_save_sha256=digest(pre_save),reward_kernel_comparison=reward_independent,real_input_archives={p.name:digest(p) for p in (ACT2/'actions.jsonl',ACT2/'raw.jsonl')},
                simulated_commands=accepted,comparisons=comparisons,first_difference=next((r for r in comparisons if r['diff']),None),stop=stop)


def map_studies(runtime, directory):
    fixture=route_fixture(directory)
    results=[]; diagnostic_runs=[]
    for act in (3,4):
        retail, captured, receipt=evidence(act)
        symbols=captured['public_ui']['fields']['nodes']
        native_layout=from_rows(symbols,native=True,external_leaf=HEART if act==4 else None)
        semantic=public_heart_layout(symbols,captured['public_map_boss']) if act==4 else native_layout
        for y in ([-1] if act==3 else [-1,0,1,2]):
            def start(outer_fixture=False):
                return prepared(runtime,35,lambda core:fixture.enter(core,act,y),outer_fixture=outer_fixture)
            engine,session,f=start()
            v=f.state.vector
            reconstructed=from_observation({'nodes':[v[112+2*i:114+2*i] for i in range(105)],'emerald_observed':v[24:26]})
            mismatch=differences(semantic,reconstructed)
            assert not any(mismatch.values())
            actions=allowed(f)
            _,_,conditional=start(True)
            columns=[int(v[322+6*i+1]) for i in range(7) if v[322+6*i]]
            if y==-1:
                assert columns==[n['x'] for n in retail['screen_state']['next_nodes']]
            assert len(actions)==v[1769]==len(columns)
            row=dict(act=act,previous_y=y,archive_at_same_position=y==-1,native_map_capture=receipt['digest'],
                     native_rendered_rooms=len(native_layout.rooms),published_rooms=len(reconstructed.rooms),
                     normal_edges=len(semantic.roads),boss_edges=len(semantic.boss),raw_diff=differences(native_layout,reconstructed),
                     semantic_diff=mismatch,public_count=int(v[1769]),fixture_mode_count=int(conditional.state.vector[1769]),
                     columns=columns,actions=actions,destinations=[])
            for ordinal,action in enumerate(actions):
                if ordinal:engine,session,f=start()
                out=session.step(action,frame_id=f.frame_id,action_version=f.action_version)
                dest=list(map(int,out.state.vector[10:12]))
                assert dest==[columns[ordinal],y+1] and out.engine_steps==1
                row['destinations'].append(dict(action=action,destination=dest,page=out.page))
            results.append(row)
            if (act,y) in ((3,-1),(4,-1),(4,1),(4,2)):
                engine,session,f=start(); seq=[];states=[snapshot(f)]; visits=Counter();rng=Random(35+8384)
                while not f.done and allowed(f) and len(seq)<300:
                    a=select(f,allowed(f),rng,'survival',visits)
                    previous_view=model(f,engine)
                    f=session.step(a,frame_id=f.frame_id,action_version=f.action_version)
                    seq.append(a);states.append(snapshot(f))
                diagnostic_runs.append(dict(act=act,previous_y=y,actions=seq,states=states,
                    terminal=('loss' if engine._source._env.lost else 'win') if f.done else 'unsupported' if not allowed(f) else 'cap',
                    kernel_end_floor=engine._source._env.floor, before_last_action=previous_view,
                    final_public=model(f,engine), final_kernel_legal=[i for i,x in enumerate(engine._source._current.backend_mask) if x]))
    return results,diagnostic_runs


def boss_branches(runtime):
    from dataclasses import asdict,replace
    from experiments.episode_outcomes193.bosses import BUILD,BUILD_DIGEST
    from experiments.episode_outcomes193.rollout import terminal_or_act_change,endpoint
    from experiments.policy_event_integration.session import load_extension
    fixture=load_extension(BUILD,BUILD_DIGEST); cases={}
    for name,act,keys,loss in [('act3_no_keys',3,False,False),('act3_with_keys',3,True,False),('heart_win',4,True,False),('heart_loss',4,True,True)]:
        engine,session,frame=prepared(runtime,1,lambda core:fixture.prepare_map(core,act,keys)); src=engine._source; core=src._env
        actions=[110,170 if loss else 70]+([71] if act==3 else [])
        rows=[]
        for index,action in enumerate(actions):
            before=src._current; init=[]; original=src._capture
            def capture():
                if not init and index<len(actions)-1 and core.steps>before.engine_steps and core.observe()[7]:
                    fixture.prepare_final_hit(core,loss);init.append(True)
                return original()
            assert frame.supported_actions[action],(name,index,allowed(frame))
            src._capture=capture
            try:after=session.step(action,frame_id=frame.frame_id,action_version=frame.action_version)
            finally:del src._capture
            assert bool(init)==(index<len(actions)-1)
            label=terminal_or_act_change(core,before.raw_base,before.engine_steps,sum(before.backend_mask),src._backend) if index else None
            stripped=replace(after,state=replace(after.state,vector=after.state.vector[:3118]))
            outcome=endpoint(stripped,core,cap_reached=False)
            assert outcome!='terminal' or label.terminated
            rows.append(dict(action=action,prior=snapshot(frame),after=snapshot(after),label=asdict(label) if label else None))
            frame=after
        cases[name]=rows
    assert [(cases[k][-1]['label']['stage'],cases[k][-1]['label']['native_summary_floor']) for k in cases]==[('act3_win',52),('ongoing',None),('heart_win',57),('loss',56)]
    return cases


def run(edition):
    runtime=importlib.import_module(edition)
    with TemporaryDirectory() as tmp:
        encounter=parasite(runtime,tmp)
        maps,trajectories=map_studies(runtime,tmp)
    branches=boss_branches(runtime); originals=histories()
    assert len(originals['winning_summaries'])==2
    assert all(r['combat']['floor']==branches['heart_win'][-1]['label']['engine_floor'] and r['summary_floor']==branches['heart_win'][-1]['label']['native_summary_floor'] for r in originals['winning_summaries'])
    return dict(edition=edition,signature=runtime.interface_signature().metadata() if hasattr(runtime,'interface_signature') else None,
                edition_sources={p.name:digest(p) for p in [Path(runtime.__file__),Path(runtime.__file__).with_name('session.py')] if p.exists()},
                historical_summaries=originals,
                map_studies=maps,directed_runs=trajectories,directed_final_hits=branches,act2_same_fight=encounter,
                deep_natural_end_to_end_paired_runs=0,new_retail_sessions=0,
                source_sha256={p.name:digest(p) for p in [Path(__file__),HERE/'entry.py',HERE/'parasite.cpp']})

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--edition',default='experiments.sa_calibration_round6.release');parser.add_argument('--output',type=Path,default=HERE/'RESULT.json');args=parser.parse_args()
    data=run(args.edition);args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(data['historical_summaries']['counts'], 'Act2 commands',len(data['act2_same_fight']['simulated_commands']), 'late routes',len(data['map_studies']))
