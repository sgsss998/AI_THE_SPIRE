"""Verify all offered input effects at the archived shop and retain each evidence level."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from experiments.ordinary_reward_hooks193.audit import dump,JAR,RETAIL
from experiments.sa_calibration_round6.reference import R4,R5,read,write,sha
from ..wall.verify import step,legal
from ..shop import verify as original
from ..terminal_intent.session import TerminalIntent
from . import candidate, session

HERE=Path(__file__).resolve().parent


def shelf():
    game=read(original.HERE/"RESULT.json")
    engine=candidate.make_engine()
    model=candidate.make_session(engine)
    f=model.reset(game["purchase"]["seed"])
    for row in game["replay"]["rows"][:245]:
        if row["status"]=="executed":
            f=step(model,f,row["public_action"])
            for _,a in row.get("incidental_actions",[]):
                f=step(model,f,a)
    return model,f,engine


def retail_rules():
    assert sha(JAR)==RETAIL
    refs={"shop.StorePotion":["purchasePotion("],"shop.StoreRelic":["purchaseRelic("],
          "shop.ShopScreen":["purchasePurge(","updatePurgeCard("],"relics.BottledLightning":["onEquip(","update("],
          "relics.Omamori":["<init>("],"relics.TwistedFunnel":["atBattleStart("],
          "cards.CardGroup":["getPurgeableCards(","getCardsOfType(","addToBottom("]}
    methods=dump(tuple(refs))
    code={cls:{prefix:next(lines for k,lines in methods[cls].items() if k.startswith(prefix))
               for prefix in prefixes} for cls,prefixes in refs.items()}
    text="\n".join(code["shop.StorePotion"]["purchasePotion("])
    assert text.index("obtainPotion") < text.index("loseGold") and "IFEQ" in text
    assert any("inBottleLightning" in line for line in code["relics.BottledLightning"]["update("])
    assert any("getSkills" in line for line in code["relics.BottledLightning"]["onEquip("])
    assert any("addToBottom" in line for line in code["cards.CardGroup"]["getCardsOfType("])
    assert any("java.util.ArrayList.add(ILjava/lang/Object;)" in line for line in code["cards.CardGroup"]["addToBottom("])
    return dict(jar_sha256=RETAIL,methods={cls:{name:sha256("\n".join(lines).encode()).hexdigest()
                for name,lines in group.items()} for cls,group in code.items()})


def cases():
    raw=original.view.rows(R4/"fresh/ACTIONS.jsonl")[245]
    g=raw["before"]["raw"]["game_state"]
    commands=raw["legal"]
    transitions=[]
    for actions in ([105],[106],[121],[122],[123],[105,121],[105,122],[106,123],
                    [119],[120],[118,111,178],[110,111,172]):
        s,f,e=shelf()
        assert legal(f)==commands
        assert f.policy_mask == f.supported_actions == s.real_action_mask(frame_id=f.frame_id)
        entries=[]
        for aid in actions:
            old=f
            f=step(s,f,aid)
            entries.append(dict(action=aid,page=f.page,old_gold=int(old.state.vector[2]),gold=int(f.state.vector[2]),
                belt=list(f.state.vector[17:19]),deck=int(f.state.vector[22]),engine_steps=f.engine_steps,
                step_delta=f.engine_steps-old.engine_steps,old_refs=list(old.state.vector[3114:3118]),
                refs=list(f.state.vector[3114:3118]),offered=legal(f)))
            if aid in (121,122,123) and 105 not in actions and 106 not in actions:
                assert f.state.vector==old.state.vector and f.engine_steps==old.engine_steps and f.frame_id!=old.frame_id
            elif aid in (105,106):
                slot=aid-105
                assert f.state.vector[17+slot]==0 and old.state.vector[17+slot]>0 and f.state.vector[2]==old.state.vector[2]
            elif aid in (121,122,123):
                retail=g["screen_state"]["potions"][aid-121]
                chosen=1 if 106 in actions else 0
                assert f.state.vector[2]==old.state.vector[2]-retail["price"]
                assert original.view.norm(e._source._backend.POTION_NAMES[int(f.state.vector[17+chosen])-1])==original.view.norm(retail["name"])
            elif aid in (118,119,120):
                retail=g["screen_state"]["relics"][aid-118]
                assert f.state.vector[2]==old.state.vector[2]-retail["price"]
                pos=32+int(old.state.vector[23])*2
                assert f.state.vector[pos+1]-1==retail["counter"]
                assert original.view.norm(e._source._backend.RELIC_NAMES[int(f.state.vector[pos])-1])==original.view.norm(retail["name"])
            elif aid==111 and actions[0]==118:
                assert old.page=="SHOP_BOTTLE_SKILL"
                refs=old.state.vector[2684:2684+len(legal(old))]
                assert list(refs)==sorted(refs,reverse=True)
                assert f.state.vector[3114:3118]==(2,0,refs[1]-202,0)
            elif aid==178 and actions[0]==118:
                assert f.state.vector[3114:3118]==old.state.vector[3114:3118]
            elif aid==172:
                assert f.state.vector[2]==g["gold"]-g["screen_state"]["purge_cost"] and f.state.vector[22]==len(g["deck"])-1
        transitions.append(dict(actions=actions,states=entries))
    return dict(seed=g["seed"],floor=g["floor"],original_hash=raw["before"]["raw_hash"],
                verified_shop_actions=commands,actual_input=raw["command"],model_branches=transitions)


def full_replays():
    from experiments.sa_calibration_round4.fresh import invocations
    from experiments.sa_calibration_round5.replay import original_inputs
    from ..wall import verify as runner
    from ..terminal_intent.verify import original_attack,attack
    def compare(engine,frame,snap):
        assert frame.state.state_version.endswith(candidate.TAG)
        projected=replace(frame,state=replace(frame.state,state_version=frame.state.state_version.removesuffix(candidate.TAG)))
        return original.compare(engine,projected,snap)
    summaries=[]
    for source in ("r6","r4"):
        if source=="r6":
            journal,calls,_=runner.loaded()
        else:
            journal=original_inputs()
            calls=invocations.captures()
        seed=journal[0]["before"]["raw"]["game_state"]["seed"]%(1<<64)
        last=journal[-1]["index"]
        result,frames=runner.retail_replay(journal,calls,seed=seed,map_input=original.map_input,compare_frame=compare,
            session_factory=lambda e:TerminalIntent(candidate.make_session(e)),watch=(last,))
        assert result["completed_inputs"]==last and not result["first_substantive_difference"] and not result["stop"]
        raw=journal[-1]["after"]["raw"]["game_state"]
        assert raw["current_hp"]==0 and frames[last].done and attack(frames[last])==original_attack(raw)
        if source=="r4":
            assert result["rows"][245]["offered"]==journal[245]["legal"]
            assert result["rows"][246]["offered"]==journal[246]["legal"]
        summaries.append(dict(original=source,seed=seed,inputs=last,complete=True,final_floor=raw["floor"],
            terminal_raw_hash=journal[-1]["after"]["raw_hash"],final_attack=attack(frames[last]),
            matching_reported_action_sets=sum(row["offered"]==row["retail_legal"] for row in result["rows"]),
            first_substantive_difference=result["first_substantive_difference"]))
    return summaries


def historical_purge():
    from experiments.public_shop.verify import load_native,CONTROL
    games,actions=load_native()
    listed=games[22]["screen_state"]["cards"][1]
    before=[c["uuid"] for c in games[21]["deck"]]
    after=[c["uuid"] for c in games[24]["deck"]]
    assert listed["id"]=="Strike_G" and len(before)==len(after)+1
    assert after==[uuid for uuid in before if uuid!=listed["uuid"]]
    return dict(input_ledger=sha(CONTROL/"actions.jsonl"),action_count=len(actions),selected_card=listed["id"],
                selected_uuid=listed["uuid"],original_gold=[games[i]["gold"] for i in (21,22,23,24)],
                deck_sizes=[len(before),len(after)])


def main():
    result=cases()
    real=read(R5/"shop/RESULT.json")
    result.update(full_replays=full_replays(),other_original_purge=historical_purge(),runtime={p.name:sha(p) for p in (HERE/"session.py",HERE/"candidate.py")},retail_rules=retail_rules(),
        historical_potion_branches={k:[dict(action=r["command"],before=r["before"]["original_raw_sha256"],
            after=r["after"]["original_raw_sha256"],paid=r["before"]["gold"]-r["after"]["gold"]) for r in row["items"]]
            for k,row in real["branches"].items()},original_full_belt_rejection=real["branches"]["flex"]["full_slots"])
    write(HERE/"RESULT.json",result)
    print("receipted button set",len(result["verified_shop_actions"]),"independent model branches",len(result["model_branches"]))


if __name__=="__main__":
    main()
