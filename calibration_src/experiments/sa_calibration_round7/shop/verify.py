"""Purchase receipt and full old retail replay with the unique public boss map entry."""
from dataclasses import replace
from pathlib import Path
from silent_env.observation import schema
from experiments.sa_calibration_round3.fresh import replay as view
from experiments.sa_calibration_round4.fresh import invocations
from experiments.sa_calibration_round5.replay import original_inputs
from experiments.sa_calibration_round6.reference import R4, read, sha, write
from ..wall import verify as wall
from ..fungi import verify as fungi
from . import candidate

HERE = Path(__file__).resolve().parent


def boss_entry(frame, engine, snap):
    g = snap["raw"]["game_state"]
    if (g["screen_type"]!="MAP" or g.get("choice_list") != ["boss"]
            or not g["screen_state"]["boss_available"] or g["screen_state"]["next_nodes"]
            or frame.state.vector[6]!=5 or not frame.supported_actions[110]):
        return None
    choices = view.options(frame)
    if len(choices)!=1 or choices[0][1]!=(7,0,schema()["enums"]["Room"]["BOSS"]+1,0,0,1):
        return None
    raw = engine._source._current
    ids = [b.simulator_id for b in raw.bindings if b.policy_id==110 and b.choice_row==0 and b.operation=="choose_map_node"]
    name = engine._source._backend.ENCOUNTER_NAMES[int(frame.state.vector[15])-1]
    if len(ids)==1 and engine._source._env.is_valid(ids[0]) and view.norm(name)==view.norm(g["act_boss"]):
        return name
    return None


def combat_card_offer(frame, engine, snap):
    """Bind a combat potion selection only when every public card, slot and skip match."""
    g = snap["raw"]["game_state"]
    if (g["screen_type"]!="CARD_REWARD" or not g["screen_state"].get("skip_available")
            or frame.state.vector[6:8] != (9,1)):
        return None
    rows = view.options(frame)
    cards = g["screen_state"]["cards"]
    if (not cards or len(rows)!=len(cards)+1
            or rows[-1][1]!=(6,0,0,0,0,1)):
        return None
    raw = engine._source._current
    if raw is None or frame.engine_steps!=raw.engine_steps:
        return None
    for i, ((slot,r),card) in enumerate(zip(rows[:-1],cards,strict=True)):
        if (slot!=i or r[0]!=1 or not r[5] or not frame.supported_actions[110+i]
                or [engine._source._backend.CARD_IDS[int(r[1])-1],int(r[2])] != view.card(card)
                or not any((b.policy_id,b.operation)==(110+i,"select_offered_card") for b in raw.bindings)):
            return None
    if not frame.supported_actions[177] or not any(b.policy_id==177 and b.operation=="skip_offers" for b in raw.bindings):
        return None
    return [view.card(c) for c in cards]


def compare(engine, frame, snap):
    assert frame.state.state_version.endswith(candidate.TAG)
    projected = replace(frame, state=replace(frame.state, state_version=frame.state.state_version.removesuffix(candidate.TAG)))
    diff = fungi.compare(engine, projected, snap)
    if diff.get("next_x")=={"model":[0],"original":[]} and boss_entry(frame,engine,snap):
        del diff["next_x"]
    public_cards = combat_card_offer(frame,engine,snap)
    if public_cards is not None:
        if diff.get("offered_cards")=={"model":None,"original":public_cards}:
            del diff["offered_cards"]
        if diff.get("page")=={"model":9,"original":10}:
            del diff["page"]
    return diff


def map_input(row, frame, engine):
    boss = boss_entry(frame,engine,row["before"])
    if boss and row["aid"]==110:
        return 110,dict(boss=boss,binding="unique public boss entry")
    cards = combat_card_offer(frame,engine,row["before"])
    if cards is not None and (row["aid"]==177 or 110<=row["aid"]<110+len(cards)):
        return row["aid"],dict(public_card_choices=cards,binding="all public offered faces and skip match")
    return view.map_action(row,frame,engine)


def audit():
    journal = original_inputs()
    seed = journal[0]["before"]["raw"]["game_state"]["seed"]%(1<<64)
    replay, frames = wall.retail_replay(journal,invocations.captures(),seed=seed,session_factory=candidate.make_session,
                     compare_frame=compare,map_input=map_input,watch=(245,246,320))
    row = journal[245]
    assert row["index"]==246 and row["command"]=="choose 1"
    a,b = [row[k]["raw"]["game_state"] for k in ("before","after")]
    card = a["screen_state"]["cards"][0]
    assert a["choice_list"][1]==card["name"].lower()
    ids = lambda cards: [c["uuid"] for c in cards]
    assert ids(b["deck"])==ids(a["deck"])+[card["uuid"]]
    assert card["uuid"] not in ids(b["screen_state"]["cards"])
    pre,post=[frames[i].state.vector for i in (245,246)]
    aid=replay["rows"][245]["public_action"]
    slot_offset=322+(aid-110)*6
    displayed=pre[slot_offset:slot_offset+6]
    assert displayed[0]==1 and displayed[2]==card["upgrades"] and displayed[3]==card["price"]
    old_size=2*int(pre[22])
    assert (pre[22],post[22])==(len(a["deck"]),len(b["deck"]))
    assert tuple(post[706:706+old_size])==tuple(pre[706:706+old_size])
    assert post[706+old_size:708+old_size]==displayed[1:3]
    assert pre[2]==a["gold"] and post[2]==b["gold"]==a["gold"]-card["price"]
    assert sha(R4/"fresh/ACTIONS.jsonl")==read(R4/"fresh/TERMINAL.json")["trace_sha256"]
    purchase=dict(index=246,seed=seed,original_before=row["before"]["raw_hash"],original_after=row["after"]["raw_hash"],
                  card=card["id"],upgrades=card["upgrades"],retail_shelf_uuid=card["uuid"],retail_deck_added_uuid=b["deck"][-1]["uuid"],
                  price=card["price"],gold=[a["gold"],b["gold"]],deck_sizes=[int(pre[22]),int(post[22])],
                  entire_old_deck_verified=True,candidate_actions=replay["rows"][245]["offered"],retail_actions=row["legal"],
                  shelf_cards=sorted(c["id"] for c in a["screen_state"]["cards"]))
    return dict(checked_representations={"boss_map_input":252,"combat_potion_offer_input":321,
                "potion_offers":[view.card(c) for c in journal[320]["before"]["raw"]["game_state"]["screen_state"]["cards"]]},
                runtime={p.name:sha(p) for p in (HERE/"candidate.py",HERE/"session.py")},
                journal=sha(R4/"fresh/ACTIONS.jsonl"),purchase=purchase,replay=replay)


if __name__=="__main__":
    evidence = audit()
    write(HERE/"RESULT.json",evidence)
    print(evidence["purchase"],evidence["replay"]["completed_inputs"],evidence["replay"]["first_substantive_difference"],evidence["replay"]["stop"])
