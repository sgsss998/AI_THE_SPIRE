"""Verify the independent retail session, public replay and any separately labelled diagnostics."""
import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from native_runtime import now
from .instance import HERE,ROOT,DEST
from .replay import digest,rows


def read(p):
    return json.loads(p.read_bytes())


def ref(path):
    return {'path':str(path.relative_to(HERE)), 'sha256':digest(path)}


def source_id(path):
    return str(path.relative_to(ROOT))


def first_content(d):
    for t in d['trace']:
        for stage in ('before','after'):
            if stage not in t: continue
            diff = {k:v for k,v in t[stage]['differences'].items() if k != 'page'}
            if diff:
                return dict(index=t['index'],stage=stage,fields=diff)
    return None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('public',type=Path)
    parser.add_argument('--reconciled',type=Path,required=True)
    parser.add_argument('--diagnostic',type=Path)
    args=parser.parse_args()
    public_path=HERE/args.public
    d=read(public_path); iface=read(HERE.parent/'INTERFACE.json')
    assert d['signature']==iface and d['signature_unchanged']
    assert not d['diagnostic_allowed'] and not d['used_kernel'] and not d['reconciled_native_physical_effects']
    semantic_path=HERE/args.reconciled;sem=read(semantic_path)
    assert sem['reconciled_native_physical_effects'] and not sem['used_kernel'] and not sem['diagnostic_allowed']
    assert sem['signature_unchanged'] and sem['signature']==iface
    for name,h in sem['source_sha256'].items(): assert digest(ROOT/name)==h,name
    ledger=rows(HERE/'ACTIONS.jsonl')
    end=read(HERE/'TERMINAL.json'); inp=read(HERE/'START_INPUT.json')
    start=read(HERE/'START_OUTPUT.json')
    first=read(HERE/'FIRST_SIMULATOR_START.json');known=read(HERE/'SEEDS_BEFORE.json')
    assert inp['seed'] is None and start['command']=='start THE_SILENT 20'
    assert inp['interface_sha256']==digest(HERE.parent/'INTERFACE.json')
    assert start['status']=='observed_start'
    assert datetime.fromisoformat(known['as_of']) < datetime.fromisoformat(inp['utc']) < datetime.fromisoformat(end['at']) < datetime.fromisoformat(first['at'])
    signed=start['after']['raw']['game_state']['seed']
    seed=signed%(1<<64)
    assert seed not in known['seeds_u64'] and seed==d['seed_unsigned']
    assert [x['index'] for x in ledger]==list(range(1,end['index']+1))
    assert end['trace_sha256']==digest(HERE/'ACTIONS.jsonl')
    assert ledger[-1]['after']['raw']['game_state']['screen_type']=='GAME_OVER' or end['snapshot']['raw']['game_state']['screen_type']=='GAME_OVER'
    assert end['receipt']['pending'] is None and end['receipt']['quarantine'] is None
    assert all(s[phase]['raw']['game_state']['seed']==signed for s in ledger for phase in ('before','after'))
    assert not read(HERE/'AUTOSAVE_SEED.json')['seed_set']
    assert len(known['seeds_u64'])==len(set(known['seeds_u64']))
    for name,h in d['source_sha256'].items():
        assert digest(ROOT/name)==h, name
    sessions = [p for p in (DEST/'bridge/sessions').iterdir() if (p/'attempts.jsonl').exists()]
    starts=[r for s in sessions for r in rows(s/'attempts.jsonl') if r.get('event')=='dispatch_intent' and r.get('command','').startswith('start')]
    assert len(starts)==1 and starts[0]['request_id']==start['request_id']
    target=read(DEST/'target.json')
    assert not target['fixture_mod_enabled'] and not target['saves_copied'] and not target['runs_copied']
    jar=DEST/'game/desktop-1.0.jar'
    assert digest(jar)==target['files']['game/desktop-1.0.jar']['sha256']
    seed_code=subprocess.check_output([str(DEST/'game/jre/bin/java'),'-cp',str(ROOT/'experiments/ordinary_death193/fixture_build_v2/seed_classes')+':'+str(jar),'SeedRoundTrip',str(signed)],text=True).strip()
    left,display,right=seed_code.split('=')
    assert int(left)==int(right)==signed
    log=(DEST/'launch.log').read_text(errors='replace')
    assert 'Generating seeds: '+str(signed) in log
    model=d['model_endpoint'];native=d['original_endpoint']; g=end['snapshot']['raw']['game_state']
    diag=None
    if args.diagnostic:
        dip=HERE/args.diagnostic;dr=read(dip)
        assert dr['diagnostic_allowed'] and dr['signature']==iface and dr['signature_unchanged'] and dr['seed_unsigned']==seed
        for name,h in dr['source_sha256'].items(): assert digest(ROOT/name)==h,name
        diag=dict(**ref(dip),used_kernel=dr['used_kernel'],stop=dr['stopped_at'],replayed=dr['replayed'],endpoint=dr['model_endpoint'],
                  quality=dr['frame_statistics']['all_actual_frames'],typed_chest=dr['diagnostic_typed_chest'],
                  extra_effects=sum(len(t.get('native_effects',[])) for t in dr['trace']),map_or_event_only=dr['native_only_acknowledgements'])
        assert dr['stopped_at'] is None and dr['model_endpoint']['lost'] and dr['original_endpoint']['resources']==dr['model_endpoint']['resources']
        assert dr['model_endpoint']['enemies']==dr['original_endpoint']['enemies'] and dr['model_endpoint']['relics']==dr['original_endpoint']['relics']
    mask_diffs=[]
    for row in d['trace']:
        ms=row['action_set_comparison']
        if ms['missing_in_model'] or ms['extra_in_model']:
            mask_diffs.append(dict(index=row['index'],missing=ms['missing_in_model'],extra=ms['extra_in_model'],scope=ms['evidence_status']))
    refs={p.name:ref(p) for p in (HERE/'ACTIONS.jsonl',HERE/'TERMINAL.json',HERE/'START_INPUT.json',HERE/'START_OUTPUT.json',HERE/'SEEDS_BEFORE.json',HERE/'FIRST_SIMULATOR_START.json',HERE/'AUTOSAVE_SEED.json') }
    for p in (HERE/'PHYSICAL.jsonl', HERE/'CLOSE.json'):
        if p.is_file():refs[p.name]=ref(p)
    scene_counts=Counter(x['before']['raw']['game_state']['screen_type'] for x in ledger)
    floor_counts=Counter(x['before']['raw']['game_state']['floor'] for x in ledger)
    endpoint_equal={k:(v==model.get(k)) for k,v in native.items() if k!='page'}
    idx=dict(valid=True,sealed_at=now(),display=display,seed_unsigned=str(seed),seed_signed=str(signed),original_version=re.search(r'DesktopLauncher> version: (.*)',log).group(1),
             original_game_sha256=target['files']['game/desktop-1.0.jar']['original_source_sha256'],isolated_game_sha256=digest(jar),
             started_blank=True,start_dispatches=len(starts),known_before=len(known['seeds_u64']),in_original_inventory=False,original_completed_before_model=True,
             model_interface=iface,official_replay=ref(public_path),first_public_state_difference=d['first_state_difference'],
             first_public_content_difference=first_content(d),first_reported_action_set_difference=d['first_action_set_difference'],
             first_missing_chosen_action=d['first_missing_public_action'],first_unmapped_or_failed_input=d['stopped_at'],masks_with_differences=mask_diffs,
             reconciled_official=dict(**ref(semantic_path),replayed_receipts=sem['replayed'],extra_card_actions=[dict(input=t['index'],actions=t['native_effects']) for t in sem['trace'] if t.get('native_effects')],
                                      first_unavailable=sem['first_missing_public_action'],stopped_at=sem['stopped_at'],endpoint=sem['model_endpoint'],quality=sem['frame_statistics']['all_actual_frames'],
                                      first_content_difference=first_content(sem),original_only=sem['native_only_acknowledgements']),
             initial_action_semantic_review=dict(first_ui_only=5,first_choice_discrepancy_in_partial_original_inventory=10,
                    first_independent_shop_object_gap=51,first_missing_chosen_object=98,chosen_object='InkBottle',first_unexecuted_relic_row=97),
             original_inputs=len(ledger),model_actions=d['replayed'],original_only_inputs=[x['index'] for x in d['trace'] if x['status']=='native_only_acknowledgement'],
             quality=d['frame_statistics']['all_actual_frames'],repeated_reward_cycles=d['repeated_reward_cycles'],original_screens=scene_counts,
             original_floor_input_counts=floor_counts,original_final=dict(hp=g['current_hp'],max_hp=g['max_hp'],gold=g['gold'],floor=g['floor'],loss=not end['terminal']['victory'],native_score=end['terminal'].get('score')),
             official_model_endpoint=dict(resources=model['resources'],end_page=model['facade_page'],lost=model['lost'],won=model['won'],done=model['done'],
                                          monsters=model.get('enemies'),engine_steps=model['engine_steps']),
             final_compared_fields_equal=endpoint_equal if d['stopped_at'] is None else None,diagnostic=diag,source_files=refs,training_steps=0)
    for src in [HERE/'drive.py',HERE/'physical.py',HERE/'keys.swift',HERE/'policy.py',HERE/'inventory.py',HERE/'invocations.py',HERE/'chest_diag.py',HERE/'flat_pages.py',HERE/'seal.py',HERE/'replay.py',HERE.parent/'FREEZE.json',HERE.parent/'INTERFACE.json']:
        idx.setdefault('source_sha256',{})[source_id(src)]=digest(src)
    raw_strokes=rows(HERE/'PHYSICAL.jsonl')
    idx['original_physical_keys_sent']=sum(v['event']=='physical_dispatch_intent' for v in raw_strokes)
    idx['original_physical_keys_with_decision_change']=sum(v.get('wire_type')=='physical_hand_key' for v in ledger)
    idx['original_physical_keys_without_observed_decision_change']=idx['original_physical_keys_sent']-idx['original_physical_keys_with_decision_change']
    (HERE/'RESULT.json').write_text(json.dumps(idx,ensure_ascii=False,indent=2)+'\n')
    print(display,idx['original_final'],idx['official_model_endpoint'],idx['first_unmapped_or_failed_input'])


if __name__=='__main__':main()
