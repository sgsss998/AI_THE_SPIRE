"""Replay either retail ledger with the same public action mapping, retaining first differences."""
from dataclasses import replace
from experiments.sa_calibration_round3.fresh import replay as view
from experiments.sa_calibration_round4.fresh import invocations, replay as r4view
from experiments.sa_calibration_round5 import replay as r5view
from . import release
from .reference import HERE, R4, read, write, sha

def compare(frame, engine, snap):
    r4version = read(R4 / "INTERFACE.json")["state_version"]
    assert frame.state.state_version == r4version + release.parent.TAG + release.TAG
    projected = replace(frame, state=replace(frame.state, state_version=r4version))
    evidence = r4view.compare(projected,engine,snap)
    game = snap["raw"]["game_state"]
    combat = game.get("combat_state")
    if combat and frame.state.vector[7] and game["screen_type"] in ("NONE","HAND_SELECT") and any(m["id"]=="FungiBeast" for m in combat["monsters"]):
        def power(obj, name):
            return next((x["amount"] for x in obj["powers"] if x["id"]==name),0)
        v = frame.state.vector
        actual = [[m["current_hp"],power(m,"Spore Cloud"),power(m,"Strength")] for m in combat["monsters"]]
        model = [[int(v[o+1]),int(v[o+37]),int(v[o+21])] for i in range(len(actual)) if (o:=993+52*i) < 1253]
        for key,m,n in (("fungus_hp_spores_strength",model,actual),("player_vulnerable",int(v[911]),power(combat["player"],"Vulnerable"))):
            evidence["model"][key], evidence["original"][key] = m,n
            if m != n:
                evidence["differences"][key] = dict(model=m,original=n)
    return evidence

def run(journal,calls,seed):
    engine=release.make_engine()
    session=release.make_session(engine)
    signature=release.interface_signature().metadata()
    frame=session.reset(seed)
    records,checked=[],{}
    stop=first_content=None
    for pos,row in enumerate(journal):
        index=row["index"]
        before=compare(frame,engine,row["before"])
        current=view.allowed(frame)
        try:
            aid, binding=view.map_action(row,frame,engine)
        except (IndexError,KeyError,ValueError) as err:
            aid,binding=None,dict(reason="original object mapping could not be verified",error=repr(err))
        record=dict(index=index,command=row["command"],action=aid,binding=binding,page=frame.page,offered=current,
                    actual_reported=row.get("legal",[]),original_before=row["before"]["raw_hash"],
                    original_after=row["after"]["raw_hash"],before=before,actions_executed=[])
        records.append(record)
        if aid is None:
            after=compare(frame,engine,row["after"])
            matches=r5view.unique_ack(row) and not after["differences"]
            if r5view.unique_ack(row) and set(after["differences"])=={"page"} and pos+1<len(journal):
                following=journal[pos+1]
                matches=(r5view.unique_ack(following) and row["after"]["raw_hash"]==following["before"]["raw_hash"]
                         and not compare(frame,engine,following["after"])["differences"])
            if matches:
                record.update(status="original_only_confirmation",after=after)
            else:
                stop=dict(reason="original_choice_not_mapped",requested=binding)
        elif aid not in current:
            stop=dict(reason="missing_public_action",requested=binding,action=aid)
        else:
            frame=session.step(aid,frame_id=frame.frame_id,action_version=frame.action_version)
            record["actions_executed"].append(aid)
            for seq,event in invocations.received(row,calls):
                try:
                    extra,details=invocations.binding(row,event,frame,engine)
                except (AssertionError,KeyError,IndexError) as err:
                    stop=dict(reason="additional_original_card_use_not_bound",source_event=seq,error=repr(err))
                    break
                if extra not in view.allowed(frame):
                    stop=dict(reason="missing_additional_public_action",source_event=seq,action=extra,requested=details)
                    break
                frame=session.step(extra,frame_id=frame.frame_id,action_version=frame.action_version)
                record["actions_executed"].append(extra)
                record.setdefault("incidental_card",[]).append(dict(record=seq,binding=details))
            if not stop:
                record.update(status="public_action",after=compare(frame,engine,row["after"]))
        for phase in ("before","after"):
            if phase not in record: continue
            ev=record[phase]
            snap=row[phase]
            checked[(snap["session"],snap["sequence"])]=ev
            differences={k:v for k,v in ev["differences"].items() if k!="page"}
            if first_content is None and differences:
                first_content=dict(index=index,phase=phase,floor=ev["original"]["resources"][3],fields=differences)
        if stop:
            stop.update(index=index,floor=before["original"]["resources"][3],page=frame.page,offered=view.allowed(frame),gaps=list(frame.action_gaps))
            record.update(status="stopped",stop=stop)
            break
    assert signature==release.interface_signature().metadata()
    return dict(signature=signature,completed_inputs=sum(r["status"]!="stopped" for r in records),
                official_actions=sum(len(r["actions_executed"]) for r in records),first_content=first_content,stop=stop,
                original_inputs=len(journal),used_kernel_fallback=False,checked_frames=len(checked),
                equal_frames=sum(not x["differences"] for x in checked.values()),
                substance_equal_frames=sum(not(set(x["differences"])-{"page"}) for x in checked.values()),
                final=view.model(frame,engine),records=records)

if __name__=="__main__":
    journal=r5view.original_inputs()
    seed=journal[0]["before"]["raw"]["game_state"]["seed"]%(1<<64)
    result=run(journal,invocations.captures(),seed)
    result.update(original_journal_sha256=sha(R4/"fresh/ACTIONS.jsonl"),seed=read(R4/"fresh/RESULT.json")["display"],independent_holdout=False)
    write(HERE/"replay/RESULT.json",result)
    print({k:result[k] for k in ("completed_inputs","official_actions","first_content","stop")})
