"""Audit R5's rejected reward and R6's actual public transactions from ordinary resets."""
from dataclasses import replace
from hashlib import sha256
from zipfile import ZipFile
import json

from experiments.combat_loot193 import retail
from experiments.reward_ui_adapter.adapter import Unsupported, read_rows
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.sa_calibration_round3.fresh import replay as view
from experiments.sa_calibration_round5 import release as r5
from experiments.sa_calibration_round5 import replay as r5replay
from experiments.sa_calibration_round6 import release
from experiments.sa_calibration_round6.reference import HERE, R4, R5, sha, read, write
from silent_env.runtime import StaleFrameError
from .session import INK, PUZZLE, inventory, loot, victory


def retail_proof():
    from experiments.ordinary_reward_hooks193.audit import dump, JAR, RETAIL
    from native_runtime import GAME
    from experiments.common_relic193.rules import relic_id
    names = {"INK_BOTTLE": "InkBottle", "CENTENNIAL_PUZZLE": "CentennialPuzzle"}
    callbacks = _local_dependencies(retail.callbacks.__wrapped__, CLASSES=names)()
    defs = dump(tuple("relics."+name for name in names.values()))
    original = GAME / "desktop-1.0.jar"
    assert sha(original) == "dd60a613a6178e08f1a57bcb8d5747e33c21fd49e743b88d76e9d74042803b2a"
    with ZipFile(original) as jar:
        for key, name in names.items():
            assert callbacks[key]["class_sha256"] == sha256(jar.read("com/megacrit/cardcrawl/relics/"+name+".class")).hexdigest()
            assert not callbacks[key]["external_id_references"]
    assert set(callbacks["INK_BOTTLE"]["hooks"]) == {"atBattleStart", "onUseCard"}
    assert set(callbacks["CENTENNIAL_PUZZLE"]["hooks"]) == {"atPreBattle", "justEnteredRoom", "wasHPLost", "onVictory"}
    puzzle = defs["relics.CentennialPuzzle"]
    won = puzzle["onVictory()V"]
    assert len(won) == 4 and won[2].endswith(".pulse:Z")
    hurt = puzzle["wasHPLost(I)V"]
    for term in ("RoomPhase.COMBAT", "usedThisCombat", "DrawCardAction", "ICONST_3"):
        assert any(term in line for line in hurt)
    return dict(retail_sha256=sha(original), inspected_archive_sha256=RETAIL, compiled_relic_classes=callbacks,
                observation_ids={name:relic_id(name) for name in names}, puzzle_victory_code=won,
                puzzle_hurt_draw_code=[line for line in hurt if any(w in line for w in ("RoomPhase.COMBAT","usedThisCombat","DrawCardAction","ICONST_3"))])


def step(session, frame, aid):
    assert aid in view.allowed(frame), (frame.page, aid, view.allowed(frame))
    return session.step(aid, frame_id=frame.frame_id, action_version=frame.action_version)


def checkpoint(version, seed, records):
    engine = version.make_engine()
    session = version.make_session(engine)
    frame = session.reset(seed)
    for row in records[:128]:
        previous = frame
        for aid in row["actions_executed"]:
            frame = step(session,frame,aid)
    assert len(frame.state.vector) == 3122 and len(frame.supported_actions) == 193
    return engine, session, previous, frame


def state(frame, engine):
    s = view.model(frame,engine)
    suffix = frame.state.vector[3118:]
    assert len(frame.state.vector)==3122 and len(frame.supported_actions)==193
    assert not frame.state.vector[7] and tuple(suffix)==(0,0,0,0)
    return dict(page=frame.page, full_state_sha256=sha256(json.dumps(frame.state.vector,separators=(",",":")).encode()).hexdigest(),
                extended_fields=list(suffix), visible_rows=int(frame.state.vector[1769]), resources=s["resources"],
                potion_slots=s["potions"], deck_size=len(s["deck"]), relics=s["relics"], rewards=s.get("rewards"),
                offered_cards=s.get("offered_cards"), supported=s["supported"], legal_mask_complete=frame.policy_mask is not None)


def compared(frame,engine,snapshot):
    observed = view.model(frame,engine)
    expected = view.original(snapshot)
    differences = {k:[observed.get(k),v] for k,v in expected.items() if observed.get(k)!=v}
    assert not differences, differences
    native = snapshot["raw"]["game_state"]
    if native["screen_type"] in ("COMBAT_REWARD", "CARD_REWARD"):
        want = len(native.get("choice_list", []))
        assert frame.state.vector[1769] == want
    return sorted(expected)


def replay():
    receipts = r5replay.original_inputs()
    seed = receipts[0]["before"]["raw"]["game_state"]["seed"]%(1<<64)
    old = read(R5/"replay/RESULT.json")["records"]
    e5,_,prior5,f5 = checkpoint(r5,seed,old)
    e,s,prior,f = checkpoint(release,seed,old)
    assert f5.page=="REWARD_UNVERIFIED" and not view.allowed(f5)
    packet = e5._inner.delegate._provider.peek()
    raw5 = e5._source._current
    raw6 = e._source._current
    assert raw5.raw_base == raw6.raw_base and raw5.packet_sha256==raw6.packet_sha256
    assert not loot.ordinary(prior5,f5)
    assert not loot.inventory(raw5.raw_base) and inventory(raw5.raw_base)
    try:
        read_rows(packet)
    except Unsupported as err:
        rejection = str(err)
        assert "unreviewed reward-modifying relic" in rejection
    else:
        raise AssertionError("The R5 ordinary reader accepted this exact inventory")
    physical = [dict(kind=r["kind_name"], backing=r["sim_action"], parameters=r["parameters"],
                     card=(r.get("card_identity") or {}).get("native_id"),legal=r["legal"])
                for r in raw5.choice_metadata["choices"]]
    assert [r["kind"] for r in physical]==["GOLD","CARD","CARD","CARD","POTION","SKIP"]
    assert [r["card"] for r in physical if r["kind"]=="CARD"]==["Riddle With Holes","Flying Knee","Backflip"]
    reject = dict(r5_page=f5.page, r5_supported=view.allowed(f5), r5_read_rows=rejection,
                  r5_victory=False, actual_last_attack_relics=[list(prior5.state.vector[32:36]),list(f5.state.vector[32:36])],
                  native_rows=physical, identical_backing_packet_sha256=raw5.packet_sha256)
    # Verify the ordinary gate against raw physical sources. Projected public reward rows differ.
    prefix = old[:127]
    detached = release.make_engine()
    test = release.make_session(detached)
    test_frame = test.reset(seed)
    for row in prefix:
        for a in row["actions_executed"]:
            test_frame = step(test,test_frame,a)
    previous = detached._source._current
    for a in old[127]["actions_executed"]:
        test_frame = step(test,test_frame,a)
    current = detached._source._current
    assert victory(previous,current)
    def altered(packet, changes):
        values=list(packet.state.base)
        for i,x in changes.items():
            values[i]=x
        return replace(packet,state=replace(packet.state,base=tuple(values)))
    unsafe = dict(unknown_relic={34:0}, ink_counter_out_of_range={35:11}, impossible_counter_jump={35:7},
                  puzzle_cannot_gain_counter={34:PUZZLE,35:1}, extra_relic={23:3,36:PUZZLE}, elite={8:2}, event={9:1})
    for changes in unsafe.values():
        assert not victory(previous,altered(current,changes))
    assert not victory(previous,replace(current,engine_steps=current.engine_steps+1))
    cases = []
    for row in receipts[128:133]:
        before = state(f,e)
        fields = compared(f,e,row["before"])
        assert before["supported"]==row["legal"]
        aid, bound=view.map_action(row,f,e)
        original_before=f
        f=step(s,f,aid)
        try:
            s.step(aid,frame_id=original_before.frame_id,action_version=original_before.action_version)
        except StaleFrameError:
            pass
        else:
            raise AssertionError("The previous frame was accepted twice")
        after=state(f,e)
        compared(f,e,row["after"])
        cases.append(dict(index=row["index"],aid=aid,binding=bound,source_hashes=[row["before"]["raw_hash"],row["after"]["raw_hash"]],
                          checked_native_fields=fields, before=before, after=after, rejected_duplicate_request=True))
    assert cases[0]["after"]["resources"][2]-cases[0]["before"]["resources"][2]==20
    assert cases[1]["after"]["potion_slots"]==["regenpotion",None]
    assert cases[2]["after"]["offered_cards"]==[["Riddle With Holes",0],["Flying Knee",0],["Backflip",0]]
    assert cases[3]["after"]["deck_size"]==cases[3]["before"]["deck_size"]+1 and "next_x" in view.model(f,e)
    return dict(seed=str(seed), from_public_reset=True, reused_original=True, r5_root_cause=reject,
                gate_negatives=[*unsafe,"nonconsecutive_physical_transition"], steps=cases)


if __name__=="__main__":
    frozen=read(HERE/"FREEZE.json")
    assert release.source_hashes()==frozen["runtime"]
    data = dict(interface=sha(HERE/"INTERFACE.json"),runtime=frozen["runtime"], parent_replay=sha(R5/"replay/RESULT.json"),
                original_journal=sha(R4/"fresh/ACTIONS.jsonl"), retail=retail_proof(), primary=replay())
    write(HERE/"rewards/RESULT.json",data)
    print([r["index"] for r in data["primary"]["steps"]])
