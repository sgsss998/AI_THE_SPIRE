"""Check blocked and extra independently drawn boss swaps against the original game's Pandora."""
import argparse
from hashlib import sha256
from importlib import import_module
from pathlib import Path

from experiments.common_relic193 import pools
from experiments.neow_transform_two193.fixture import CASES
from experiments.ordinary_reward_hooks193.audit import dump
from experiments.sa_calibration_round6.reference import sha, write
from experiments.sa_calibration_round6.rewards.verify import step, view
from experiments.sa_calibration_round7.oracles.step_checks import audit_frame
from experiments.sa_calibration_round7.triage import rows, RUNS
from silent_env.runtime import StaleFrameError, UnverifiedSemanticsError
from . import box_candidate
from .pandora import GRID
from .retail_box import run as run_box

HERE = Path(__file__).resolve().parent
CM = pools.ARCHIVE / "oracle_work/evidence/communication_terminal.bytecode.txt"


def retail_classes():
    rules = {
        ("dungeons.AbstractDungeon","initializeCardPools"): ("517: GETSTATIC com.megacrit.cardcrawl.dungeons.AbstractDungeon.commonCardPool", "550: GETSTATIC com.megacrit.cardcrawl.dungeons.AbstractDungeon.srcCommonCardPool","555: INVOKEVIRTUAL com.megacrit.cardcrawl.cards.CardGroup.addToBottom"),
        ("cards.CardGroup","addToBottom"): ("4: ICONST_0","java.util.ArrayList.add(ILjava/lang/Object;)V"),
        ("dungeons.AbstractDungeon","returnTrulyRandomCard"): ("srcCommonCardPool","srcUncommonCardPool","srcRareCardPool","cardRandomRng"),
        ("relics.PandorasBox","onEquip"): ("STARTER_STRIKE","STARTER_DEFEND","returnTrulyRandomCard","openConfirmationGrid"),
        ("screens.select.GridCardSelectScreen","openConfirmationGrid"): ("isJustForConfirming","CancelButton.hideInstantly","GridSelectConfirmButton.show","isDisabled","canCancel"),
        ("screens.select.GridCardSelectScreen","update"): ("247: GETFIELD com.megacrit.cardcrawl.screens.select.GridCardSelectScreen.targetGroup","253: INVOKEVIRTUAL java.util.ArrayList.iterator","292: INVOKESPECIAL com.megacrit.cardcrawl.vfx.FastCardObtainEffect","302: INVOKESTATIC com.megacrit.cardcrawl.dungeons.AbstractDungeon.closeCurrentScreen"),
        ("vfx.FastCardObtainEffect","update"): ("AbstractRelic.onObtainCard","SoulGroup.obtain","onMasterDeckChange"),
        ("cards.Soul","obtain"): ("masterDeck","CardGroup.addToTop"),
        ("cards.CardGroup","addToTop"): ("java.util.ArrayList.add(Ljava/lang/Object;)Z",),
    }
    klass = dump(tuple(sorted(set(name for name,_ in rules))))
    hashes = {}
    for (name,method), markers in rules.items():
        body = "\n".join(line for desc,code in klass[name].items() if desc.startswith(method+"(") for line in code)
        assert all(word in body for word in markers), (name,method,markers)
        hashes[name+"."+method] = sha256(body.encode()).hexdigest()
    com = CM.read_text()
    for method, clauses in (("getGridScreenChoices",("isJustForConfirming","23: IFEQ ->28","27: ARETURN")),
                            ("isGridScreenConfirmAvailable",("isJustForConfirming","18: ICONST_1","19: IRETURN")),
                            ("isGridScreenCancelAvailable",("canCancel","confirmScreenUp"))):
        body = com.split("METHOD "+method+"(",1)[1].split("METHOD ",1)[0]
        assert all(x in body for x in clauses)
    return hashes


def seeds():
    blocked = [r["seed"] for _,r in rows(RUNS/"pilot-r6") if r["page"]=="NEOW_RESULT_UNVERIFIED" and r["actions"][-1]==113]
    assert len(blocked)==3
    saved = [pools.read_save(k) for k in pools.SAVES]
    rolls = pools.permutations(sorted(set(blocked) | set(range(512)) | {s for s,_,_ in saved}))
    ordered = [[v for _,v in sorted(zip(rolls[s][-1],relics[-1],strict=True))] for s,relics,_ in saved]
    assert all(ordered[0]==ls for ls in ordered)
    def is_box(s):
        return ordered[0][rolls[s][-1][0]] == "Pandora's Box"
    extra = [s for s in range(512) if is_box(s)]
    assert all(is_box(s) for s in blocked) and len(extra)>10
    return blocked, extra, [proof for _,_,proof in saved]


def case(runtime, seed, reference):
    engine = runtime.make_engine()
    session = runtime.make_session(engine)
    f = session.reset(seed)
    initial = step(session,f,110)
    grid = step(session,initial,113)
    assert grid.page == GRID and view.allowed(grid)==[172] and not audit_frame(grid)
    assert session.real_action_mask(frame_id=grid.frame_id)==grid.supported_actions
    v = grid.state.vector
    faces = engine._source._backend.CARD_IDS
    names = [faces[int(v[323+6*j])-1] for j in range(10)]
    shown = view.model(grid,engine)
    assert shown["deck"] == [[n,0] for n in reference["pre_confirm_deck"]]
    assert names == reference["confirmation"], (seed,names,reference)
    assert v[1769]==0 and all(v[322+6*j:328+6*j]==(1,v[323+6*j],0,0,0,0) for j in range(10))
    assert v[382:706] == (0,)*324
    for illegal in (110,173):
        try:
            session.step(illegal,frame_id=grid.frame_id,action_version=grid.action_version)
        except UnverifiedSemanticsError:
            pass
        else:
            raise AssertionError(("Must reject individual card and cancel",seed,illegal))
    leave = step(session,grid,172)
    assert leave.page=="NEOW_RESULT" and view.allowed(leave)==[110] and not audit_frame(leave)
    try:
        step(session,grid,172)
    except StaleFrameError:
        pass
    else:
        raise AssertionError(("Expired Pandora frame accepted twice",seed))
    mapped = step(session,leave,110)
    assert mapped.state.vector[6]==5 and view.allowed(mapped) and mapped.engine_steps==leave.engine_steps==grid.engine_steps==1
    expected = shown["deck"] + [[n,0] for n in names]
    for frame in (leave,mapped):
        observed=view.model(frame,engine)
        assert observed["deck"]==expected and observed["resources"]==shown["resources"]
        assert observed["potions"]==shown["potions"] and observed["relics"]==shown["relics"]
    return dict(seed=seed, surviving_cards=reference["pre_confirm_deck"], replacement_order=names,
                controls={"grid":[172],"settlement":[110],"map":view.allowed(mapped)},
                rejected_individual_choice_cancel_and_duplicate=True, final_cards=len(expected))


def main():
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument("--runtime",default=box_candidate.__name__)
    args.add_argument("--output",type=Path,default=HERE/"PANDORA.json")
    options=args.parse_args()
    blocked,extra,receipts=seeds()
    classes=retail_classes()
    expected=run_box(blocked+extra)
    runtime=import_module(options.runtime)
    results=[case(runtime,s,expected[s]) for s in blocked+extra]
    data=dict(runtime=options.runtime, historical_blocked=len(blocked), extra_boss_swaps=len(extra), discovery_range=[0,511],
              matched_ordered_positions=10*len(results), same_seed_graphical_runs=0,
              validation="retail onEquip, RNG, deck removals and ordered UI content run on original Java; confirmation and engine continuation checked against original method logic",
              inputs={p.name:sha(p) for p in (HERE/"pandora.py",HERE/"box_candidate.py",HERE/"RetailBox.java",HERE/"retail_box.py",
                                                Path(__file__), pools.JAR, pools.ROOT/"experiments/golden_loot193/HeadlessBoot.java",CM)},
              card_pool_capture_with_mixed_live_common_and_original_uncommon_rare={k:sha(pools.ROOT/"native_runtime"/v[0]/"offline_pool_evidence.json") for k,v in CASES.items()},
              retail_code=classes, boss_pool_sources=receipts, cases=results)
    write(options.output,data)
    print(len(blocked),len(extra),data["matched_ordered_positions"])


if __name__ == "__main__":
    main()
