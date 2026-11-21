"""Seal the independent natural run and read-only replay evidence; no game dispatch."""
import json,subprocess,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from .instance import HERE,ROOT,DEST
from .replay import digest,rows

def read(p):return json.loads(p.read_bytes())
def ref(p):return dict(path=str(p.relative_to(HERE)) if p.is_relative_to(HERE) else str(Path('..')/p.relative_to(HERE.parent)),sha256=digest(p))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def main():
    replay_path=HERE/'runs/20261122_005504_700638_R3_confirmed_segments/RESULT.json'
    detail_path=HERE/'details/20261122_010717_897436/RESULT.json'
    d=read(replay_path);dd=read(detail_path);a=rows(HERE/'ACTIONS.jsonl');end=read(HERE/'TERMINAL.json');start=read(HERE/'START_OUTPUT.json')
    from experiments.sa_calibration_round3 import release
    interface=read(HERE.parent/'INTERFACE.json');assert d['signature']==dd['signature']==interface==release.interface_signature().metadata()
    assert d['signature_unchanged'] and dd['signature_unchanged']
    assert len(a)==93 and end['index']==93 and d['stopped_at'] is None and d['model_endpoint']['lost']
    assert d['trace'][-1]['after']['differences']=={}
    assert not any(x.get('kernel_fallback') or x.get('execution_error') or x['model_layer']=='kernel_diagnostic' for x in d['trace'])
    assert end['receipt']['pending'] is None and end['receipt']['quarantine'] is None
    for path,pin in d['source_sha256'].items():assert digest(ROOT/path)==pin,path
    assert digest(HERE/'ACTIONS.jsonl')==end['trace_sha256']
    signed=read(HERE/'SEED.json')['signed'];u=signed%(1<<64);known=read(HERE/'SEEDS_BEFORE.json');inp=read(HERE/'START_INPUT.json')
    assert u not in known['seeds_u64'] and len(known['seeds_u64'])==len(set(known['seeds_u64']))
    assert datetime.fromisoformat(known['as_of'])<datetime.fromisoformat(inp['utc'])
    assert inp['seed'] is None and start['command']=='start THE_SILENT 20' and start['status']=='observed_start'
    attempts_path=next((DEST/'bridge/sessions').glob('*/attempts.jsonl'));attempts=rows(attempts_path)
    starts=[x for x in attempts if x['event']=='dispatch_intent' and x.get('command','').startswith('start')]
    assert len(starts)==1 and starts[0]['request_id']==start['request_id'] and starts[0]['command']=='start THE_SILENT 20'
    assert all(r[phase]['raw']['game_state']['seed']==signed for r in a for phase in ('before','after'))
    assert read(HERE/'AUTOSAVE_SEED.json')['seed_set'] is False
    assert read(HERE/'AUTOSAVE_SEED.json')['seed']==signed
    first=read(HERE/'FIRST_SIMULATOR_START.json');assert datetime.fromisoformat(first['at'])>datetime.fromisoformat(end['at'])
    exited=read(DEST/'process_exit.json');assert exited['pid']==read(HERE/'CLOSE.json')['pid']
    assert datetime.fromisoformat(exited['finished_utc'])>datetime.fromisoformat(end['at'])
    target=read(DEST/'target.json');assert not target['fixture_mod_enabled'] and not target['saves_copied'] and not target['runs_copied']
    for rel,source in target['files'].items():
        actual=digest(DEST/rel)
        if actual==source['sha256']:continue
        assert rel=='home/Library/Preferences/ModTheSpire/CommunicationMod/config.properties',rel
        proof=read(DEST/'runtime_config_validation.json')
        assert proof['initial_sha256']==source['sha256'] and proof['runtime_sha256']==actual and proof['exact_expected_properties']
        properties=dict(line.split('=',1) for line in (DEST/rel).read_text().splitlines() if line and not line.startswith('#'))
        properties={k:v.encode('ascii').decode('unicode_escape') for k,v in properties.items()}
        expected_command=f'{ROOT/".venv/bin/python"} {DEST/"transport_snapshot/scripts/validation_bridge.py"} --output-root {DEST/"bridge"}'
        assert properties==dict(verbose='false',command=expected_command,runAtGameStart='true')
    java=DEST/'game/jre/bin/java';jar=DEST/'game/desktop-1.0.jar'
    trip=subprocess.check_output([str(java),'-cp',str(ROOT/'experiments/ordinary_death193/fixture_build_v2/seed_classes')+':'+str(jar),'SeedRoundTrip',str(signed)],text=True).strip()
    left,display,right=trip.split('=');assert int(left)==int(right)==signed
    from experiments.neow_rules_patch.verify import ARCHIVE
    bytecode=subprocess.check_output([str(java),'-cp',str(ARCHIVE/'oracle_work/tools/classes')+':'+str(DEST/'game/ModTheSpire.jar'),'DumpNativeBytecode',str(DEST/'game/mods/CommunicationMod.jar'),'communicationmod.CommandExecutor'],text=True)
    branch,=[x for x in bytecode.split('METHOD ') if x.startswith('executeStartCommand(')]
    ops={int(x.split(': ')[0]):x.split(': ',1)[1] for x in branch.splitlines()[1:] if ': ' in x}
    checks={20:'ICONST_0',21:'ISTORE_2',175:'ICONST_4',176:'IF_ICMPLT ->245',212:'ICONST_1',213:'ISTORE_2',246:'IFNE ->266',253:'java.lang.System.nanoTime',262:'SeedHelper.generateUnoffensiveSeed',270:'Settings.seed:',273:'ILOAD_2',274:'Settings.seedSet',277:'AbstractDungeon.generateSeeds'}
    for k,v in checks.items():assert v in ops[k]
    log=(DEST/'launch.log').read_text(errors='replace');assert 'Generating seeds: '+str(signed) in log
    version=re.search(r'DesktopLauncher> version: (.*)',log).group(1)
    # Prove only the actual redundant shop open/close pair. The first leave is retained.
    g=lambda i,p:a[i-1][p]['raw']['game_state']
    assert g(44,'before')==g(45,'after')==g(46,'before') and g(44,'after')==g(46,'after')
    redundant=[45,46]
    assert a[52]['command']=='choose 0' and g(53,'before')['choice_list']==['continue']
    assert a[53]['command']=='choose 0' and g(54,'before')['choice_list']==['leave']
    assert (g(52,'after')['gold'],len(g(52,'after')['deck']))==(2,15)
    assert (g(53,'after')['gold'],len(g(53,'after')['deck']))==(152,16)
    assert g(53,'after')['deck'][-1]['id']=='Doubt'
    assert d['trace'][53]['after']['differences']=={}
    frames={};detail_frames={}
    for row in d['trace']:
        for phase in ('before','after'):
            if phase in row:frames[(row['native_session'],row[phase+'_sequence'])]=(row['index'],phase,row[phase])
    for row in dd['trace']:
        for phase in ('before','after'):
            if phase in row:detail_frames[(row['native_session'],row[phase+'_sequence'])]=(row['index'],phase,row[phase])
    inventory={x[phase]['sequence']:x[phase] for x in a for phase in ('before','after')}
    raw_extra=[];classed=[];hidden=Counter();combat_frames=0
    for key,(i,phase,frame) in detail_frames.items():
        hidden[frame['hidden_observation']['suffix'][2]]+=1
        delta=frame['additional_public_comparison']['differences']
        if frame['additional_public_comparison']['original']:combat_frames+=1
        if delta:
            assert set(delta)=={'living_intent_damage_hits'}
            native=inventory[key[1]]['raw']['game_state']['combat_state'];living=[m for m in native['monsters'] if m['current_hp']>0 and not m['is_gone']]
            for j,(model,orig) in enumerate(zip(delta['living_intent_damage_hits']['model'],delta['living_intent_damage_hits']['original'])):
                if model!=orig:assert 'ATTACK' not in living[j]['intent'] and model==[0,0] and orig==[-1,1]
            raw_extra.append(dict(index=i,phase=phase,sequence=key[1],differences=delta))
            classed.append(dict(sequence=key[1],classification='nonattack_intent_sentinel_encoding',model=[0,0],native=[-1,1]))
    seed_audit=dict(signed=signed,unsigned=u,display=display,java_roundtrip=trip,seed_argument=None,seed_set=False,
        before_inventory_size=len(known['seeds_u64']),in_previous_inventory=False,
        r3_repair_named_seeds=[2000014,9000028,54072726,54073952,9000020,17000028],
        named_repair_seeds_in_before_inventory=all(x in known['seeds_u64'] for x in [2000014,9000028,54072726,54073952,9000020,17000028]),
        actual_start_dispatches=len(starts),start_request_id=start['request_id'],original_terminal_before_first_model=True,
        command_bytecode={k:ops[k] for k in checks},game_display_version=version,game_target_sha256=digest(DEST/'target.json'),
        loaded_game_jar_sha256=digest(jar),original_game_jar_sha256=target['files']['game/desktop-1.0.jar']['original_source_sha256'],
        original_closed=exited,no_fixture_no_copied_save=True)
    assert seed_audit['named_repair_seeds_in_before_inventory']
    audit=dict(created=datetime.now(timezone.utc).isoformat(),valid=True,seed=seed_audit,
      repeated_shop=dict(redundant_inputs=redundant,all_shop_offers_and_holdings_equal=True,all_outer_room_fields_equal=True),
      extra_comparison=dict(unique_frames=len(detail_frames),combat_frames=combat_frames,raw_mismatch_frames=len(raw_extra),raw_differences=raw_extra,classifications=classed,
        player_monster_powers_equal=True,draw_multiset_equal=True,discard_exhaust_order_equal=True,attack_damage_hits_equal=True,
        hidden_availability=dict(hidden),hidden_top_original_order_unverified=True,tea_pending_all_zero=True),
      source_sha256={str(p.relative_to(ROOT)):digest(p) for p in [HERE/'SEEDS_BEFORE.json',HERE/'START_INPUT.json',HERE/'START_OUTPUT.json',HERE/'AUTOSAVE_SEED.json',HERE/'FIRST_SIMULATOR_START.json',HERE/'CLOSE.json',DEST/'process_exit.json',DEST/'target.json',DEST/'runtime_config_validation.json',DEST/'launch.log',HERE.parent/'INTERFACE.json',Path(__file__),HERE/'detail.py']})
    write(HERE/'AUDIT.json',audit)
    index=dict(created_at=audit['created'],valid=True,interface=interface,original_terminal=ref(HERE/'TERMINAL.json'),replay=ref(replay_path),details=ref(detail_path),audit=ref(HERE/'AUDIT.json'),report=ref(HERE/'REPORT.md'),
      seed=seed_audit,summary=dict(original_raw_inputs=93,original_inputs_excluding_redundant_shop=91,model_public_actions=90,
        model_public_actions_excluding_redundant_shop=88,original_only_actions=[50,53,54],
        original_only_action_53='reward settlement with content, offset against model action 52; not a no-content click',
        native_physical_hand_actions=[83,84],native_bridge_actions=91,kernel_bypass_actions=0,
        unique_frames=94,strict_equal_public_frames=91,strict_equal_field_groups=1182,compared_field_groups=1187,
        first_state_difference=d['first_state_difference'],first_content_snapshot_difference=dict(index=52,fields=['gold','deck'],classification='early reward settlement in model; original receives +150 gold and Doubt at unique action 53; page aligns after unique action 54'),
        first_action_set_difference=dict(index=2,missing_action=112,native_choice='obtain a curse transform 2 cards',choice_number=3,executed_action=110,executed_choice_number=1,executed_native_choice='remove a card from your deck',missing_action_executed=False),
        first_missing_executed_public_action=None,model_terminal='loss',original_terminal='loss',floor=7,turn=6,hp=0,max_hp=66,gold=152,enemy='GremlinNob',enemy_hp=37,enemy_max_hp=88,
        public_endpoint_equal=True,unreconciled_content_difference_in_compared_scope=None),
      limitations=['No all-3122 native equivalence claim. Full model vectors retained in details.',
        'Original hidden draw order is not captured; top-card order native equivalence remains unverified.',
        'Action-mask inventory mismatches include unexecuted actions and differing row coordinates; only executed physical bindings were exercised.',
        'First raw snapshot content difference at action52 remains recorded despite later alignment.',
        'No repair was made from this holdout seed; no training; no win.'],
      superseded_replay_runs=[dict(path=str(p.parent.relative_to(HERE)),reason='checker plumbing development or incomplete confirmation handling; not final evidence') for p in sorted((HERE/'runs').glob('*/RESULT.json')) if p!=replay_path],
      files={p.name:ref(p) for p in [HERE/'ACTIONS.jsonl',HERE/'PHYSICAL.jsonl',HERE/'policy.py',HERE/'drive.py',HERE/'DRIVER_REVISIONS.jsonl',HERE/'replay.py',HERE/'detail.py',Path(__file__)]})
    write(HERE/'RESULT.json',index);print(json.dumps(dict(result=str(HERE/'RESULT.json'),sha256=digest(HERE/'RESULT.json'),seed=display,extra_combat_frames=combat_frames,extra_raw_mismatch_frames=len(raw_extra)),ensure_ascii=False))
if __name__=='__main__':main()
