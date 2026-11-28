"""Recheck the installed retail class bytes and the archived real-game receipts."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from experiments.boss_loot_retail193 import verify as wrist
from experiments.combat_loot193 import retail
from experiments.ordinary_reward_hooks193.audit import dump
from experiments.sa_calibration_round1.fidelity.boss.check import map_alignment
from experiments.sa_calibration_round2.boss.verify_opening import CASES, read_case, receipt
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.sa_calibration_round6.reference import sha
from experiments.sa_calibration_round6.rewards.verify import step, view
from .session import CLASSES


def retail_rules():
    from native_runtime import GAME
    live = GAME / "desktop-1.0.jar"
    assert sha(live) == "dd60a613a6178e08f1a57bcb8d5747e33c21fd49e743b88d76e9d74042803b2a"
    definitions = _local_dependencies(retail.callbacks.__wrapped__, CLASSES=CLASSES)()
    forbidden = {"onGainGold", "onLoseGold", "onObtainCard", "onMasterDeckChange", "changeNumberOfCardsInReward",
                 "onPreviewObtainCard", "onObtainPotion", "onRewardClaim"}
    references = {"BLUE_CANDLE": {"cards/AbstractCard", "unlock/relics/ironclad/BlueCandleUnlock", "unlock/UnlockTracker"},
                  "CULTIST_HEADPIECE": {"events/shrines/FaceTrader"}, "CURSED_KEY": {"characters/AbstractPlayer"},
                  "DREAM_CATCHER": {"vfx/campfire/CampfireSleepEffect"}, "NLOTHS_HUNGRY_FACE": {"events/shrines/FaceTrader"},
                  "RUNIC_PYRAMID": {"powers/RetainCardPower","actions/common/DiscardAtEndOfTurnAction"},
                  "PRESERVED_INSECT": {"core/AbstractCreature"}, "RING_OF_THE_SNAKE": {"relics/RingOfTheSerpent", "characters/TheSilent"}}
    with ZipFile(live) as archive:
        for key, item in definitions.items():
            assert not forbidden.intersection(item["hooks"])
            assert set(item["external_id_references"]) == references.get(key, set())
            path = "com/megacrit/cardcrawl/relics/" + CLASSES[key] + ".class"
            assert sha256(archive.read(path)).hexdigest() == item["class_sha256"]
    method = dump(("relics.Orichalcum",))["relics.Orichalcum"]["onVictory()V"]
    assert len(method) == 3 and method[1].endswith("Orichalcum.stopPulse()V")
    kunai = dump(("relics.Kunai",))["relics.Kunai"]["onVictory()V"]
    assert len(kunai) == 4 and kunai[1].endswith("ICONST_M1") and kunai[2].endswith(".counter:I")
    return dict(retail_game_sha256=sha(live), classes=definitions, orichalcum_victory=method,kunai_victory=kunai)


def norm(name):
    return view.norm(name) if name != "Potion Slot" else None


def wrist_receipts(runtime, kind):
    # Reuse the retail auditor, which binds every CM result to an independent original observation.
    verified = wrist.run(kind)
    original = verified["frames"]
    dest = wrist.ROOT / "native_runtime" / verified["instance"]
    commands = view.rows(dest/"boss_audit/commands.jsonl")
    prefix = verified["matched_input_prefix"]
    game = runtime.make_engine()
    session = runtime.make_session(game)
    frame = session.reset(verified["seed"])
    for row in commands[:prefix]:
        frame = step(session, frame, row["aid"])
    evidence = []
    for j, record in enumerate(original):
        snap = commands[prefix+j]["before"] if j+1 < len(original) else commands[-1]["after"]
        assert snap["raw_hash"] == record["sha256"]
        g = snap["raw"]["game_state"]
        observed = view.model(frame, game)
        assert list(frame.state.vector[:6]) == [g[k] for k in ("current_hp","max_hp","gold","floor","act","ascension_level")]
        assert observed["deck"] == [view.card(c) for c in g["deck"]]
        assert observed["potions"] == [norm(p["id"]) for p in g["potions"]]
        assert observed["relics"] == [[norm(r["id"]),r["counter"]] for r in g["relics"]]
        if "rows" in record:
            wanted = [[k, norm(v) if k == "POTION" else v] for k,v in record["rows"]]
            assert observed["rewards"] == wanted
        if "offered" in record:
            assert observed["offered_cards"] == [list(r[:2]) for r in record["offered"]]
        if "available_a193" in record:
            assert record["available_a193"] == view.allowed(frame)
            assert frame.policy_mask == frame.supported_actions, (kind, j, frame.action_gaps)
        else:
            assert g["screen_type"] == "MAP" and frame.state.vector[6] == 5
            assert observed["next_x"] == [n["x"] for n in g["screen_state"]["next_nodes"]]
        evidence.append(dict(original_sequence=snap["sequence"], original_sha256=snap["raw_hash"],
                             available=record.get("available_a193"), gold=g["gold"], deck_size=len(g["deck"]),
                             potions=[p["id"] for p in g["potions"]], original_action=record.get("a193")))
        if j+1 < len(original):
            frame = step(session, frame, record["a193"])
    return dict(seed=verified["seed"], archive=verified["instance"], original_inputs=len(commands),
                matched_public_reward_and_map_frames=len(evidence), states=evidence)


def stone_archive():
    directory = CASES[0][0]
    seed = 54072729
    raw, commands = read_case(directory, seed)
    result = []
    for begin, end, gain in ((1068, 1073, 11), (1098, 1102, 19)):
        sequence = []
        for seq in range(begin, end+1):
            command = commands[seq]
            if command["kind"] == "query":
                source = directory/"results"/(command["request_id"]+".json")
                from experiments.sa_calibration_round6.reference import read
                packet = read(source)
                assert (packet["status"] == "query_observation" and packet["request_id"] == raw[seq+1]["pending_request_id_at_receipt"]
                        and packet["before"]["raw_hash"] == raw[seq]["raw_hash"] and packet["after"]["raw_hash"] == raw[seq+1]["raw_hash"])
                r = {"command":"state", "receipt_sha256":sha(source)}
            else:
                r = receipt(directory, raw, command, seq)
            g = raw[seq]["raw"]["game_state"]
            assert g["room_type"] == "MonsterRoom" and [x["id"] for x in g["relics"]] == ["Ring of the Snake", "Oddly Smooth Stone"]
            sequence.append(dict(sequence=seq, screen=g["screen_type"], command=r["command"],
                                 wallet=g["gold"], potions=[p["id"] for p in g["potions"]],
                                 deck=len(g["deck"]), receipt_sha256=r["receipt_sha256"]))
        def game(i):
            return raw[i]["raw"]["game_state"]
        assert game(begin+1)["gold"] - game(begin)["gold"] == gain
        assert game(end+1)["screen_type"] == "MAP"
        assert len(game(end)["deck"]) == len(game(begin)["deck"])+1
        result.append(sequence)
    return dict(seed=seed, source_sha256=sha(directory/"raw.jsonl"), evidence="recorded original transactions",
                ordinary_room_steps=result)


def smooth_replay(runtime):
    directory = CASES[0][0]
    raw, commands = read_case(directory, 54072729)
    engine = runtime.make_engine()
    s = runtime.make_session(engine)
    f = s.reset(54072729)
    emitted, bridges, checked = [], [], []
    stop = None

    def comparable(r, frame):
        g = r["raw"]["game_state"]
        model = view.model(frame,engine)
        want = [g[k] for k in ("current_hp","max_hp","gold","floor","act","ascension_level")]
        return (model["resources"] == want and model["deck"] == [view.card(c) for c in g["deck"]]
                and model["potions"] == [norm(p["id"]) for p in g["potions"]]
                and model["relics"] == [[norm(v["id"]),v["counter"]] for v in g["relics"]])

    for i, cmd in sorted(commands.items()):
        if i > 1102:
            break
        g = raw[i]["raw"]["game_state"]
        a = cmd["action_id"]
        if cmd["kind"] == "query":
            continue
        after = raw.get(i+1)
        if g["screen_type"] == "EVENT" and g.get("choice_list") == ["离开"] and f.state.vector[6] == 5 and after and after["raw"]["game_state"]["screen_type"] == "MAP":
            alignment = map_alignment(after["raw"],f,engine,s)
            diff = alignment["differences"]
            # The archive uses x=0 and no first node before floor one; that x is a sentinel.
            if set(diff) <= {"map_xy"} and comparable(after,f):
                if diff and not (g["floor"] == 0 and f.state.vector[11] == -1):
                    break
                proof = receipt(directory,raw,cmd,i)
                bridges.append(dict(sequence=i, command=cmd["command"], receipt=proof["receipt_sha256"]))
                continue
        if not comparable(raw[i],f):
            stop = dict(sequence=i, action=a, reason="resources_deck_relic_or_potion_disagrees", model_page=f.page)
            break
        if g["screen_type"] == "COMBAT_REWARD":
            tag = (raw[i]["session"], i)
            view.NATIVE[tag] = {"public_run_keys":g["public_run_keys"]}
        mapped, _ = view.map_action(dict(aid=a,before=raw[i]),f,engine)
        if mapped is None or mapped not in view.allowed(f):
            stop = dict(sequence=i, action=a, reason="unavailable_input", model_page=f.page, offered=view.allowed(f))
            break
        if g["floor"] in (11,12) and g["screen_type"] in ("COMBAT_REWARD","CARD_REWARD"):
            checked.append(i)
        r = receipt(directory,raw,cmd,i)
        f = step(s,f,mapped)
        emitted.append([i,mapped,r["receipt_sha256"]])
    return dict(seed=54072729, public_inputs=len(emitted), selected_reward_frames_reached=checked, stop=stop,
                representation_bridges=bridges)
