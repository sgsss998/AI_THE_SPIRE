"""Exercise every old Astrolabe stop; run the actual original opening grid and transformation function."""
from collections import Counter
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from experiments.common_relic193.pools import JAR,ROOT
from experiments.neow_transform_two193.random_audit import load_pools
from experiments.ordinary_reward_hooks193.audit import dump
from experiments.sa_calibration_round6.reference import read,write,sha
from experiments.sa_calibration_round6.rewards.verify import view
from experiments.wing_removal_640.session import current_deck
from silent_env.runtime import StaleFrameError,UnverifiedSemanticsError
from ..grids.verify import step,probe
from . import candidate
from .astrolabe import GRID,LEAVE
from .survey import HERE


def retail(cases):
    classes=dump(("relics.Astrolabe","screens.select.GridCardSelectScreen"))
    a=classes["relics.Astrolabe"]
    select="\n".join(a["update()V"])
    give="\n".join(a["giveCards(Ljava/util/ArrayList;)V"])
    assert "ArrayList.size()I\n20: ICONST_3\n21: IF_ICMPNE" in select and ".giveCards(" in select
    assert all(s in give for s in ("ArrayList.iterator","CardGroup.removeCard","55: ICONST_1","AbstractDungeon.miscRng",
                                   "AbstractDungeon.transformCard","ShowCardAndObtainEffect.<init>","ArrayList.clear"))
    ui="\n".join(classes["screens.select.GridCardSelectScreen"]["update()V"])
    assert all(s in ui for s in ("ArrayList.contains","ArrayList.remove","GridCardSelectScreen.numCards","AbstractDungeon.closeCurrentScreen"))
    pools,_=load_pools()
    java=JAR.parent/"jre/bin/java"
    compiler,=[r for r in read(ROOT/"native_fixture_work/BUILD.json")["inputs"] if "ecj-" in r["path"]]
    assert sha(Path(compiler["path"]))==compiler["sha256"]
    cp=f"{JAR}:{JAR.parent/'ModTheSpire.jar'}"
    extra=("cards.AbstractCard","cards.CardGroup","cards.green.Strike_Green","helpers.CardLibrary","unlock.UnlockTracker",
           "relics.Astrolabe","relics.PandorasBox","screens.select.GridCardSelectScreen","core.Settings","ui.buttons.DynamicBanner","localization.LocalizedStrings")
    boot=(ROOT/"experiments/golden_loot193/HeadlessBoot.java").read_text()
    mark='"characters.AbstractPlayer"'
    assert boot.count(mark)==1
    with TemporaryDirectory() as temp:
        work=Path(temp)
        src=work/"HeadlessBoot.java"
        src.write_text(boot.replace(mark,",".join('"'+s+'"' for s in extra)+","+mark))
        data=work/"pools.tsv"
        data.write_text("".join(f"{kind}\t{name}\n" for kind in ("common","uncommon","rare") for name in pools[kind]))
        rows=work/"cases.tsv"
        rows.write_text("".join("\t".join(map(str,(r["seed"],*r["slots"])))+"\n" for r in cases))
        build=subprocess.run([java,"-jar",compiler["path"],"-1.8","-nowarn","-proc:none","-cp",cp,"-d",work,src,
                              HERE.parent/"neow/RetailBox.java",HERE/"RetailAstrolabe.java"],text=True,capture_output=True)
        if build.returncode:raise RuntimeError(build.stderr+build.stdout)
        subprocess.run([java,"-cp",f"{work}:{cp}","HeadlessBoot",JAR,work/"boot"],check=True,capture_output=True)
        run=subprocess.run([java,"-cp",f"{work/'boot'}:{work}:{cp}","RetailAstrolabe",data,rows],text=True,capture_output=True)
        if run.returncode:raise RuntimeError(run.stderr[-1200:]+run.stdout[-250:])
    ans=[r.split("\t")[1:] for r in run.stdout.splitlines() if r.startswith("CARDS\t")]
    assert len(ans)==len(cases)
    for (seed,cards,s0,s1),case in zip(ans,cases,strict=True):
        assert int(seed)==case["seed"] and cards.split(",")==case["replacements"] and list(map(int,(s0,s1)))==case["rng_after"][1:],case


def check(r,slots):
    seed=r["seed"]
    e=candidate.make_engine();s=candidate.make_session(e);f=s.reset(seed)
    f=step(s,step(s,f,110),113);base=f
    cards=current_deck(e)
    assert f.page==GRID and view.allowed(f)==list(range(110,122)) and s.real_action_mask(frame_id=f.frame_id)==f.supported_actions
    assert list(f.state.vector[2684:2696])==list(range(204,216)) and sum(f.state.vector[2696:2748])==0
    try:step(s,f,172)
    except UnverifiedSemanticsError:pass
    else:raise AssertionError("A separate confirm was accepted")
    pick=[n+110 for n in slots]
    first=step(s,f,pick[0]);second=step(s,first,pick[1])
    assert second.state.vector[28]==2 and second.state.vector[325+6*slots[0]]==second.state.vector[325+6*slots[1]]==1
    first_again=step(s,second,pick[1]);assert first_again.state.vector==first.state.vector
    none=step(s,first_again,pick[0]);assert none.state.vector==base.state.vector
    f=step(s,step(s,none,pick[0]),pick[1])
    assert current_deck(e)==cards and f.engine_steps==1
    leave=step(s,f,pick[2]);now=current_deck(e)
    assert leave.page==LEAVE and view.allowed(leave)==[110] and leave.engine_steps==4
    assert now[:-3]==tuple(c for i,c in enumerate(cards) if i-1 not in slots) and all(c[1]==1 for c in now[-3:])
    try:step(s,f,pick[2])
    except StaleFrameError:pass
    else:raise AssertionError("A stale Astrolabe click repeated")
    rng=probe().audit(e._source._env)["all_rng"][6]
    m=step(s,leave,110)
    assert m.state.vector[6]==5 and view.allowed(m) and m.state.vector[:6]==leave.state.vector[:6]
    assert leave.state.vector[706:898]==m.state.vector[706:898] and current_deck(e)==now
    return dict(seed=seed,group=r["group"],slots=slots,deck_positions=[k+1 for k in slots],
                replacements=[e._source._backend.CARD_IDS[c[0]-1] for c in now[-3:]],rng_after=[rng[0],*(n%(1<<64) for n in rng[1:])])


def main():
    old=[r for r in read(HERE/"SURVEY.json")["cases"] if r["raw_relics"]==["Astrolabe"] and not r["legal"]]
    cases=[check(r,slots) for r in old for slots in ((4,1,10),(11,10,8))]
    retail(cases)
    out=dict(repaired=dict(Counter(r["group"] for r in old)),branch_orders=len(cases),original_cards=3*len(cases),
             source="Retail Astrolabe.onEquip and AbstractDungeon.transformCard, plus Astrolabe.giveCards and grid control bytecode",
             jar=sha(JAR),source_sha=sha(HERE/"astrolabe.py"),cases=cases)
    write(HERE/"ASTROLABE.json",out)
    print(out["repaired"],out["original_cards"])


if __name__=="__main__":main()
