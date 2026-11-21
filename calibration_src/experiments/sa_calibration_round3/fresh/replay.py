"""Offline replay of sealed/append-only original inputs; never controls the original game."""
from datetime import datetime, timezone
from dataclasses import replace
from hashlib import sha256
import argparse
import json
from pathlib import Path
import re
from types import SimpleNamespace

from experiments.sa_calibration_round3 import release
from silent_env.observation import schema

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=HERE/'NO_PRIOR_ACTIONS.jsonl'
NEW=HERE/'ACTIONS.jsonl'
PAGES={'EVENT':1,'COMBAT_REWARD':2,'BOSS_REWARD':3,'GRID':4,'MAP':5,'CHEST':6,'REST':7,'SHOP_SCREEN':8,'SHOP_ROOM':8,'SHOP':8,'NONE':9,'HAND_SELECT':9,'CARD_REWARD':10}
NATIVE={}

def norm(x):return re.sub('[^a-z0-9]','',str(x).lower())
def digest(p):return sha256(p.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def rows(p):return [json.loads(x) for x in p.read_bytes().splitlines()] if p.exists() else []

def repeated_reward_cycles(journal):
    """Exclude only repeated open/skip cycles exposing the exact same offers and holdings."""
    cycles=[];last=None
    def holdings(g):return {k:g[k] for k in ('current_hp','max_hp','gold','deck','relics','potions','floor','act')}
    for left,right in zip(journal,journal[1:]):
        a,b,c=left['before']['raw']['game_state'],left['after']['raw']['game_state'],right['after']['raw']['game_state']
        if (a['screen_type'],b['screen_type'],right['before']['raw']['game_state']['screen_type'],c['screen_type'])!=('COMBAT_REWARD','CARD_REWARD','CARD_REWARD','COMBAT_REWARD'):continue
        if right['aid']!=177 or holdings(a)!=holdings(c):continue
        key=json.dumps([holdings(a),a['screen_state']['rewards'],b['screen_state']['cards'],c['screen_state']['rewards']],sort_keys=True)
        repeat=last is not None and last['key']==key and left['index']==last['end']+1
        cycles.append(dict(start=left['index'],end=right['index'],repeated_without_new_content=repeat,
          offered_cards=[card(x) for x in b['screen_state']['cards']],holdings_unchanged=True))
        last=dict(key=key,end=right['index'])
    return cycles
def options(f):return [(i//6,tuple(map(int,f.state.vector[322+i:328+i]))) for i in range(0,384,6) if f.state.vector[322+i]]
def card(c):return [c['id'],int(c.get('upgrades',0))]
def hand(f,e):return [[e._source._backend.CARD_IDS[int(f.state.vector[i])-1],int(f.state.vector[i+1])] for i in range(1253,1313,6) if f.state.vector[i]]
def allowed(f):return [i for i,b in enumerate(f.supported_actions) if b]
def model(f,e):
    from verify.lightspeed_adapter import monster_id
    v=f.state.vector;b=e._source._backend
    out=dict(resources=list(map(int,v[:6])),page=int(v[6]),map_xy=list(map(int,v[10:12])),keys=list(map(bool,v[12:15])),
      deck=[[b.CARD_IDS[int(v[i])-1],int(v[i+1])] for i in range(706,898,2) if v[i]],
      relics=[[norm(b.RELIC_NAMES[int(v[i])-1]),int(v[i+1])-1] for i in range(32,112,2) if v[i]],
      potions=[norm(b.POTION_NAMES[int(n)-1]) if n else None for n in v[17:17+int(v[16])]],
      done=bool(f.done),won=bool(e._source._env.won),lost=bool(e._source._env.lost),engine_steps=f.engine_steps,supported=allowed(f),gaps=list(f.action_gaps),facade_page=f.page)
    if v[7]:
        out.update(turn_energy_block=[int(v[902])+1,int(v[901]),int(v[900])],
          hand=[[b.CARD_IDS[int(v[i])-1],int(v[i+1])] for i in range(1253,1313,6) if v[i] and not v[i+5]],
          selected_hand=[[b.CARD_IDS[int(v[i])-1],int(v[i+1])] for i in range(1253,1313,6) if v[i] and v[i+5]],
          hand_cost_playable_target=[[int(v[i+2]),int(v[i+3]),int(v[i+4])] for i in range(1253,1313,6) if v[i] and not v[i+5]],
          pile_counts=list(map(int,v[1765:1768])),
          enemies=[[norm(monster_id(b.MONSTER_NAMES[int(v[i])-1])),*map(int,v[i+1:i+4])] for i in range(993,1253,52) if v[i]],
          enemy_intents=[[norm(monster_id(b.MONSTER_NAMES[int(v[i])-1])),int(v[i+7])] for i in range(993,1253,52) if v[i] and v[i+1]>0 and not v[i+4]])
    if v[6]==5:out['next_x']=sorted(r[1] for _,r in options(f) if r[0]==7 and r[5])
    if v[6]==10:out['offered_cards']=[[b.CARD_IDS[r[1]-1],r[2]] for _,r in options(f) if r[0]==1 and r[5]]
    if v[6]==2:
        rewards=[]
        for _,r in options(f):
            if not r[5] or r[0]==1:continue
            if r[0]==4:rewards.append(['STOLEN_GOLD' if r[2] else 'GOLD',r[1]])
            elif r[0]==2:rewards.append(['RELIC',norm(b.RELIC_NAMES[r[1]-1])])
            elif r[0]==3:rewards.append(['POTION',norm(b.POTION_NAMES[r[1]-1])])
            elif r[0]==5:rewards.append(['SAPPHIRE_KEY',norm(b.RELIC_NAMES[r[2]-1])])
            elif r[0]==15:rewards.append(['CARD',None])
            else:rewards.append(['UNKNOWN',list(r)])
        out['rewards']=rewards
    return out

def original(snap):
    g=snap['raw']['game_state'];screen=g['screen_type'];ss=g.get('screen_state',{});keys=NATIVE[(snap['session'],snap['sequence'])]['public_run_keys']
    out=dict(resources=[g[k] for k in ('current_hp','max_hp','gold','floor','act','ascension_level')],
      page=PAGES.get(screen,0),keys=[keys[k] for k in ('ruby','emerald','sapphire')],deck=[card(c) for c in g['deck']],
      relics=[[norm(r['name']),r['counter']] for r in g['relics']],potions=[norm(p['name']) if p['id']!='Potion Slot' else None for p in g['potions']])
    if screen in ('NONE','HAND_SELECT','GAME_OVER') and g.get('combat_state'):
        c=g['combat_state'];enum=schema()['enums']['Intent']
        out.update(turn_energy_block=[c['turn'],c['player']['energy'],c['player']['block']],hand=[card(x) for x in c['hand']],
          selected_hand=[card(x) for x in ss.get('selected',[])] if screen=='HAND_SELECT' else [],
          hand_cost_playable_target=[[x['cost'],int(x['is_playable']),int(x['has_target'])] for x in c['hand']],
          pile_counts=[len(c[k]) for k in ('draw_pile','discard_pile','exhaust_pile')],
          enemies=[[norm(m['id']),m['current_hp'],m['max_hp'],m['block']] for m in c['monsters']],
          enemy_intents=[[norm(m['id']),enum[m['intent']]+1] for m in c['monsters'] if m['current_hp']>0 and not m['is_gone']])
    if screen=='MAP':
        out['next_x']=[n['x'] for n in ss['next_nodes']]
        n=ss.get('current_node')
        if n:out['map_xy']=[n['x'],n['y']]
    if screen=='CARD_REWARD':out['offered_cards']=[card(x) for x in ss['cards']]
    if screen=='COMBAT_REWARD':
        out['rewards']=[]
        for r in ss['rewards']:
            k=r['reward_type'];field={'RELIC':'relic','SAPPHIRE_KEY':'link','POTION':'potion'}.get(k)
            out['rewards'].append([k,r['gold'] if k in ('GOLD','STOLEN_GOLD') else norm(r[field]['name']) if field else None])
    return out

def compare(f,e,snap):
    m=model(f,e);n=original(snap)
    formal={}
    game=snap['raw']['game_state']
    m['terminal']=bool(f.done);n['terminal']=game['screen_type']=='GAME_OVER'
    m['won']=bool(e._source._env.won);n['won']=bool(game.get('screen_state',{}).get('victory',False)) if n['terminal'] else False
    if n['terminal'] and m['terminal']:
        formal['terminal_screen_encoding']=dict(model=m['page'],model_done=f.done,original=game['screen_type'],original_victory=n['won'])
        m['page']=n['page']='TERMINAL'
    if n.get('map_xy',[0,0])[1]==-1 and m['map_xy'][1]==-1 and n['map_xy']!=m['map_xy']:
        formal['pre_first_node_x_sentinel']=dict(model=m['map_xy'],original=n['map_xy']);n.pop('map_xy')
    if 'hand_cost_playable_target' in n and f.page!='KERNEL_DIAGNOSTIC':
        from experiments.public_hand_fees.session import displayed_cost,native_icon_cost
        cap=NATIVE[(snap['session'],snap['sequence'])];capture=snap['raw']['capture_alignment']['capture_id']
        projected=replace(f.state,vector=f.state.vector[:3118],state_version=f.state.state_version.removesuffix('+tea-pending-v1').removesuffix('+privileged-draw-top-v1'))
        for i,item in enumerate(m['hand_cost_playable_target']):item[0]=displayed_cost(projected,i)
        for i,item in enumerate(n['hand_cost_playable_target']):item[0]=native_icon_cost(cap['hand'][i],capture,i).displayed_cost
    # Native HAND_SELECT rows move selected cards out of the hand. Published costs are a separate view.
    if snap['raw']['game_state']['screen_type']=='HAND_SELECT':n.pop('hand_cost_playable_target',None)
    diffs={k:dict(model=m.get(k),original=v) for k,v in n.items() if m.get(k)!=v}
    return dict(model=m,original=n,differences=diffs,representation_differences=formal)

def select_face(faces,wanted,ordinal=0):
    matches=[i for i,x in enumerate(faces) if x==wanted]
    return matches[ordinal] if len(matches)>ordinal else None

def map_action(r,f,e):
    """Bind the original physical card/target/choice to the current model view."""
    aid=r['aid'];g=r['before']['raw']['game_state'];v=f.state.vector;ss=g.get('screen_state',{});screen=g['screen_type']
    if f.done:return None,dict(reason='model terminal')
    if PAGES.get(screen)!=int(v[6]):return None,dict(reason='different page',native=screen,model=int(v[6]))
    if aid<70:
        cards=g['combat_state']['hand'];i=aid%10
        if i>=len(cards):return None,dict(reason='native card index absent')
        wanted=card(cards[i]);occ=sum(card(x)==wanted for x in cards[:i]);mi=select_face(hand(f,e),wanted,occ)
        if mi is None:return None,dict(reason='native card face occurrence absent in model',face=wanted,occurrence=occ)
        detail=dict(card=wanted,native_slot=i,model_slot=mi,occurrence=occ)
        if aid>=10:
            from verify.lightspeed_adapter import monster_id
            j=aid//10-1;mons=g['combat_state']['monsters'];target=norm(mons[j]['id']);occ=sum(norm(x['id'])==target for x in mons[:j])
            available=[norm(monster_id(e._source._backend.MONSTER_NAMES[int(v[k])-1])) for k in range(993,1253,52) if v[k]]
            mj=select_face(available,target,occ)
            if mj is None:return None,dict(reason='native target identity absent in model',target=target,occurrence=occ)
            detail.update(target=target,native_target=j,model_target=mj)
            return 10*(mj+1)+mi,detail
        return mi,detail
    if 110<=aid<170:
        i=aid-110
        if screen=='MAP':
            wanted=ss['next_nodes'][i]['x'];xs=sorted(r[1] for _,r in options(f) if r[0]==7 and r[5])
            return (110+xs.index(wanted) if wanted in xs else None),dict(map_x=wanted,model_choices=xs)
        if screen in ('CARD_REWARD','HAND_SELECT','GRID'):
            native=ss.get('cards',ss.get('hand',[]));want=card(native[i]);occ=sum(card(x)==want for x in native[:i]);opts=[(j,[e._source._backend.CARD_IDS[row[1]-1],row[2]]) for j,row in options(f) if row[0]==1 and row[5]]
            matches=[j for j,face in opts if face==want]
            return (110+matches[occ] if len(matches)>occ else None),dict(face=want,occurrence=occ,choices=opts)
        if screen=='SHOP_SCREEN':
            label=(g.get('choice_list') or [])[i]
            native=[c for c in ss.get('cards',[]) if norm(c['name'])==norm(label)]
            if len(native)!=1:return None,dict(reason='shop selection lacks unique physical card',native_choice=label)
            want=native[0];raw=e._source._current;choices=raw.choice_metadata['choices'];candidates=[]
            for ch in choices:
                ident=ch.get('card_identity')
                if ident and ident.get('native_id')==want['id'] and ch['described'] and ch['legal']:
                    candidates.append(dict(slot=ch['slot'],kind=ch['kind_name'],parameters=list(ch['parameters']),eid=ch['sim_action'],identity=dict(ident)))
            if len(candidates)!=1:return None,dict(reason='shop exact card cannot bind uniquely',wanted=want,candidates=candidates)
            ch=candidates[0]
            if (int(ch['parameters'][1]),int(ch['parameters'][2]))!=(int(want['upgrades']),int(want['price'])):return None,dict(reason='shop price mismatch',wanted=want,candidate=ch)
            bindings=[b for b in raw.bindings if b.simulator_id==ch['eid']]
            if len(bindings)!=1:return None,dict(reason='shop card has no unique canonical binding',candidate=ch)
            visible=[j for j,r in options(f) if r[0]==1 and r[1]==ch['identity']['observation_id'] and r[2]==want['upgrades'] and r[3]==want['price'] and r[5]]
            if len(visible)!=1:return None,dict(reason='no unique matching published shop row',wanted=want,candidate=ch,visible=visible)
            return 110+visible[0],dict(shop_card=dict(id=want['id'],upgrades=want['upgrades'],price=want['price'],uuid=want['uuid']),candidate=ch,source_canonical_action=bindings[0].policy_id,published_choice_row=visible[0])
        if screen=='COMBAT_REWARD':
            want=original(r['before'])['rewards'][i];ms=model(f,e)['rewards'];matches=[j for j,item in enumerate(ms) if item==want]
            # Amount discrepancies are kept as state differences; reward kind+identity can still bind.
            if not matches and want[0] in ('GOLD','STOLEN_GOLD'):matches=[j for j,item in enumerate(ms) if item[0]==want[0]]
            return (110+matches[0] if len(matches)==1 else None),dict(reward=want,candidates=matches)
        return aid,dict(binding='same displayed slot on matching page',native_choice=g.get('choice_list',[])[i:i+1])
    return aid,dict(binding='same explicit control/potion slot',control=aid)

def raw_frame(e):
    raw=e._source._current
    return SimpleNamespace(frame_id=raw.frame_id,state=raw.state,done=raw.done,engine_steps=raw.engine_steps,
      supported_actions=tuple(any(b.policy_id==i for b in raw.bindings) for i in range(193)),action_gaps=raw.gaps,
      page='KERNEL_DIAGNOSTIC',action_version='kernel-diagnostic')

def run(limit=None,release_module='experiments.sa_calibration_round1.release'):
    from importlib import import_module
    version=import_module(release_module)
    started=now();signature=version.interface_signature().metadata()
    assert (HERE/'TERMINAL.json').exists(), 'The independent original game must finish before model replay'
    (HERE/'FIRST_SIMULATOR_START.json').write_text(json.dumps(dict(at=started,release=release_module,terminal_sha256=digest(HERE/'TERMINAL.json')))) if not (HERE/'FIRST_SIMULATOR_START.json').exists() else None
    old=rows(OLD);new=rows(NEW);journal=(old+new)[:limit]
    assert [r['index'] for r in journal]==list(range(1,len(journal)+1))
    assert all(r['status']=='observed_transition' and r['after'] is not None for r in journal)
    # Import only the captured transport's read-only parser/identity dictionaries.
    from native_pilot import libraries
    from .instance import DEST
    libraries(DEST)
    from silent_env.native_compare import verify_capture_record,json_hash,_jsonl
    evidence_files=set();dispatches={};archive_cache={};archive_sources={}
    def indexed(path,native):
        if path not in archive_cache:
            records,source=_jsonl(path);index={}
            for line,item in records:
                cid=item.get('data',{}).get('capture_id') if native and item.get('kind')=='native_capture' else item.get('raw',{}).get('capture_alignment',{}).get('capture_id') if not native else None
                if cid is None:continue
                assert cid not in index,('Duplicate capture ID',path,cid)
                index[cid]=(line,item)
            archive_cache[path]=index;archive_sources[path]=source
        return archive_cache[path]
    for r in journal:
        for sn in (r['before'],r['after']):
            key=(sn['session'],sn['sequence'])
            if key in NATIVE:continue
            dest=DEST
            stream=dest/'bridge/sessions'/sn['session']/'raw.jsonl';tag=sn['raw']['capture_alignment']
            oracle=dest/'native_oracle'/tag['native_session']/'native_oracle.jsonl'
            native_record=indexed(oracle,True)[tag['capture_id']][1];bridge_record=indexed(stream,False)[tag['capture_id']][1]
            cap=verify_capture_record(native_record,bridge_row=bridge_record,scope=dict(native_session=tag['native_session'],
              bridge_session=sn['session'],bridge_sequence=sn['sequence'],native_after_sequence=0,native_through_sequence=tag['native_record_sequence']))
            assert cap.evidence['exact_capture_binding'] and cap.evidence['bracket_verified'] and cap.evidence['bridge_raw_sha256']==sn['raw_hash']==json_hash(sn['raw'])
            NATIVE[key]=cap.payload;evidence_files.update((stream,oracle,stream.parent/'attempts.jsonl'))
            if sn['session'] not in dispatches:dispatches[sn['session']]=rows(stream.parent/'attempts.jsonl')
        if r.get('wire_type')=='physical_hand_key':
            physical=HERE/'PHYSICAL.jsonl';evidence_files.add(physical)
            receipts=[a for a in rows(physical) if a.get('request_id')==r['request_id']]
            sent=[a for a in receipts if a['event']=='physical_dispatch_intent'];done=[a for a in receipts if a['event']=='physical_os_return']
            assert len(sent)==len(done)==1 and done[0]['code']==0 and sent[0]['index']==r['index'] and sent[0]['aid']==r['aid']
            if sent[0].get('uuid'):
                assert r['before']['raw']['game_state']['screen_state']['hand'][r['aid']-110]['uuid']==sent[0]['uuid']
        else:
            sent=[a for a in dispatches[r['before']['session']] if a.get('request_id')==r['request_id'] and a['event']=='dispatch_intent']
            assert len(sent)==1 and sent[0]['command']==r['command']
    seed=journal[0]['before']['raw']['game_state']['seed']%(1<<64)
    assert all(r['before']['raw']['game_state']['seed']%(1<<64)==seed for r in journal)
    e=version.make_engine();s=version.make_session(e);f=s.reset(seed)
    trace=[];first_state=None;first_missing=None;first_mask=None;kernel=False;stop=None;state_paired=True
    for r in journal:
        before=compare(f,e,r['before']);aid,identity=map_action(r,f,e)
        row=dict(index=r['index'],original_aid=r['aid'],command=r['command'],request_id=r['request_id'],
          native_session=r['before']['session'],before_sequence=r['before']['sequence'],after_sequence=r['after']['sequence'],
          before=before,mapped_aid=aid,physical_binding=identity,model_layer='kernel_diagnostic' if kernel else release_module)
        retail_mask=set(r.get('legal',[]));model_mask=set(allowed(f))
        nav_only={176} if r['before']['raw']['game_state']['screen_type']=='MAP' else set()
        row['action_set_comparison']=dict(model=sorted(model_mask),original=sorted(retail_mask),
          navigation_only_difference=sorted((model_mask^retail_mask)&nav_only),
          missing_in_model=sorted((retail_mask-model_mask)-nav_only),extra_in_model=sorted((model_mask-retail_mask)-nav_only),
          evidence_status='inventory_only_not_executed_semantics' if r['before']['raw']['game_state']['screen_type']=='HAND_SELECT' else 'reported_masks_not_all_actions_exercised')
        if first_mask is None and (row['action_set_comparison']['missing_in_model'] or row['action_set_comparison']['extra_in_model']):
            first_mask=dict(index=r['index'],**row['action_set_comparison'])
        if before['differences'] and first_state is None:first_state=dict(index=r['index'],phase='before',differences=before['differences'])
        if aid is None:
            # Native-only acknowledgement is admissible only if the next exact public state realigns.
            aft=compare(f,e,r['after']);choices=r['before']['raw']['game_state'].get('choice_list',[])
            unique=(r['command'] in ('proceed','leave','confirm') or (r['command']=='choose 0' and len(choices)==1))
            if unique and not aft['differences']:
                row.update(status='native_only_acknowledgement',after=aft,aligned_fields=list(aft['original']))
                trace.append(row);continue
            if unique and set(aft['differences'])=={'page'} and r['index']<len(journal):
                following=journal[r['index']];fg=following['before']['raw']['game_state'];fl=fg.get('choice_list',[])
                next_unique=following['command'] in ('proceed','leave','confirm') or following['command']=='choose 0' and len(fl)==1
                future=compare(f,e,following['after'])
                if next_unique and following['before']['raw_hash']==r['after']['raw_hash'] and not future['differences']:
                    row.update(status='native_only_acknowledgement',after=aft,pending_unique_confirmation=dict(index=following['index'],command=following['command'],aligned_fields=list(future['original']),alignment=future,kernel_steps_consumed=0))
                    trace.append(row);continue
            row.update(status='unmapped_physical_action',after_if_no_model_step=aft);trace.append(row);stop=row['index'];break
        if aid not in allowed(f):
            row['missing_public_action']=dict(requested=aid,supported=allowed(f),gaps=list(f.action_gaps))
            if first_missing is None:first_missing=dict(index=r['index'],**row['missing_public_action'])
            raw=e._source._current
            binding=next((b for b in raw.bindings if b.policy_id==aid),None)
            if not binding or not e._source._env.is_valid(binding.simulator_id):
                row.update(status='blocked_no_executable_kernel_binding');trace.append(row);stop=row['index'];break
            kernel=True;row['kernel_fallback']=dict(simulator_id=binding.simulator_id,operation=binding.operation)
        prior_steps=e._source._env.steps
        try:
            if kernel:
                source=e._source;raw=source._current
                binding=next((b for b in raw.bindings if b.policy_id==aid),None)
                if binding is None:raise ValueError('No same-frame candidate binding')
                source.step(aid,frame_id=raw.frame_id);f=raw_frame(e)
            else:f=s.step(aid,frame_id=f.frame_id,action_version=f.action_version)
        except Exception as ex:
            row['execution_error']=repr(ex)
            # A postcondition checker may reject after a real kernel action. Never send it twice.
            if e._source._env.steps==prior_steps+1:
                try:
                    e._source._capture();f=raw_frame(e);kernel=True
                    row['recovery']='Consumed once; capture current kernel and continue diagnostic only'
                except Exception as capture_error:
                    row.update(status='execution_error',capture_error=repr(capture_error));trace.append(row);stop=row['index'];break
            else:
                row.update(status='execution_error',kernel_steps_before=prior_steps,kernel_steps_after=e._source._env.steps)
                trace.append(row);stop=row['index'];break
        after=compare(f,e,r['after'])
        if after['differences'] and first_state is None:first_state=dict(index=r['index'],phase='after',differences=after['differences'])
        state_paired=state_paired and not after['differences'] and not before['differences']
        row.update(status='physical_action_replayed',after=after,strict_public_fields_equal=not before['differences'] and not after['differences'],
          cumulative_equal=state_paired,model_layer='kernel_diagnostic' if kernel else release_module)
        trace.append(row)
    finished=now();sources={str(p.relative_to(ROOT)):archive_sources[p]['sha256'] if p in archive_sources else digest(p) for p in (OLD,NEW,Path(__file__),HERE/'TERMINAL.json',*sorted(evidence_files)) if p.exists()}
    cycles=repeated_reward_cycles(journal);excluded=[i for c in cycles if c['repeated_without_new_content'] for i in (c['start'],c['end'])]
    frames={};meaningful={}
    for t in trace:
        for phase in ('before','after'):
            if phase not in t:continue
            key=t['native_session']+':'+str(t[phase+'_sequence']);frames[key]=t[phase]
            if t['index'] not in excluded:meaningful[key]=t[phase]
    def stats(fr):
        return dict(frames=len(fr),equal_frames=sum(not v['differences'] for v in fr.values()),
          field_groups=sum(len(v['original']) for v in fr.values()),equal_field_groups=sum(len(v['original'])-len(v['differences']) for v in fr.values()))
    return dict(started=started,finished=finished,release_module=release_module,seed_unsigned=seed,signature=signature,
      signature_unchanged=signature==version.interface_signature().metadata(),
      original_actions_available=len(old)+len(new),input_actions=len(journal),replayed=sum(r['status']=='physical_action_replayed' for r in trace),
      repeated_reward_cycles=cycles,repeated_no_content_action_indices=excluded,actions_without_repeated_no_content_cycles=len(journal)-len(excluded),
      frame_statistics=dict(all_actual_frames=stats(frames),frames_for_nonrepetitive_inputs=stats(meaningful)),
      native_only_acknowledgements=sum(r['status']=='native_only_acknowledgement' for r in trace),
      first_state_difference=first_state,first_action_set_difference=first_mask,first_missing_public_action=first_missing,stopped_at=stop,
      model_endpoint=model(f,e),original_endpoint=original(journal[-1]['after']),trace=trace,source_sha256=sources,
      input_record_sha256={r['index']:sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest() for r in journal},
      boundary='Compared public fields only. Direct kernel diagnostics are recorded separately from policy actions. No training or original game dispatch.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int);p.add_argument('--release-module',default='experiments.sa_calibration_round3.release');p.add_argument('--label',default='R3');args=p.parse_args()
    assert args.label.replace('_','').isalnum()
    result=run(args.limit,args.release_module)
    dest=HERE/'runs'/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+args.label);dest.mkdir(parents=True,exist_ok=False)
    (dest/'RUNNER_SNAPSHOT.py').write_bytes(Path(__file__).read_bytes())
    (dest/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(path=str(dest),actions=result['input_actions'],replayed=result['replayed'],first_state=result['first_state_difference'],first_missing=result['first_missing_public_action'],stop=result['stopped_at'],endpoint=result['model_endpoint']),ensure_ascii=False))
if __name__=='__main__':main()
