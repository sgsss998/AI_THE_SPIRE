"""Verify the actual Neow relic, curse, wallet, HP, potion slots and War Paint's exact deck positions."""
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from experiments.common_relic193 import pools
from experiments.neow_transform_two193.random_audit import load_pools,java_rng
from experiments.ordinary_reward_hooks193.audit import dump
from experiments.remaining_neow193.rules import trace_reference
from experiments.sa_calibration_round6.reference import read,sha,write
from experiments.sa_calibration_round6.rewards.verify import view
from ..grids.verify import step
from . import candidate
from .direct import COMMON,RARE,MAW,LIZARD,DOLL,BELT,PAINT,relic_id
from .survey import HERE


def verify_classes():
    sub=dump(tuple('relics.'+cls for cls in (*COMMON.values(),*RARE.values())))
    original={}
    for enum,cls in {**COMMON,**RARE}.items():
        info=sub["relics."+cls]
        poses=info["<init>()V"]
        ident,=[l[7:] for l in poses if l.startswith("1: LDC ")]
        tier="RARE" if enum in RARE else "COMMON"
        assert any(f"RelicTier.{tier}:" in l for l in poses)
        equip="\n".join(info.get("onEquip()V",[]))
        if enum=="MANGO" or enum=="STRAWBERRY":
            assert "AbstractPlayer.increaseMaxHp(IZ)V" in equip and ("BIPUSH 14" if enum=="MANGO" else "BIPUSH 7") in equip
        elif enum=="POTION_BELT":
            assert ".potionSlots:I" in equip and "ICONST_2" in equip and equip.count("PotionSlot.<init>")==2
        elif enum=="WAR_PAINT":
            assert all(m in equip for m in ("CardType.SKILL","AbstractCard.canUpgrade","miscRng","Random.randomLong","Collections.shuffle","AbstractCard.upgrade"))
        elif enum=="DU_VU_DOLL":
            assert all(m in equip for m in ("CardType.CURSE","counter:I","IADD"))
        elif enum=="INCENSE_BURNER":
            assert "ICONST_0" in equip and "counter:I" in equip
        else:
            assert not equip,(enum,equip)
        original[relic_id(enum)]=ident
    return original


def draws(seeds):
    saved=[pools.read_save(x) for x in pools.SAVES]
    roll=pools.permutations(sorted(set(seeds)|{s for s,_,_ in saved}))
    orders={}
    for tier,index in ((8,0),(14,2)):
        maps=[[v for _,v in sorted(zip(roll[s][index],inv[index],strict=True))] for s,inv,_ in saved]
        assert all(ls==maps[0] for ls in maps)
        orders[tier]={s:maps[0][roll[s][index][0]] for s in seeds}
    return orders,[ref for _,_,ref in saved]


def paint(seeds):
    java=pools.JAR.parent/"jre/bin/java"
    compiler,=[x for x in read(pools.ROOT/"native_fixture_work/BUILD.json")["inputs"] if "ecj-" in x["path"]]
    assert sha(Path(compiler["path"]))==compiler["sha256"]
    if not seeds:return {}
    with TemporaryDirectory() as tmp:
        subprocess.run([java,"-jar",compiler["path"],"-1.8","-nowarn","-proc:none","-cp",pools.JAR,"-d",tmp,HERE/"ShuffleSkills.java"],check=True)
        text=subprocess.check_output([java,"-cp",f"{tmp}:{pools.JAR}","ShuffleSkills",*map(str,seeds)],text=True)
    return {int(a):sorted([int(x),int(y)]) for a,x,y in (l.split("\t") for l in text.splitlines())}


def run():
    surveys=read(HERE/"SURVEY.json")["cases"]
    old=[r for r in surveys if not r["legal"] and r["gift"] in (8,14)]
    expected,saves=draws([r['seed'] for r in old])
    native_ids=verify_classes()
    upgraded=paint([r["seed"] for r in old if r["raw_relics"][-1]=="War Paint"])
    native,_=load_pools()
    rng=java_rng()
    cases=[]
    for r in old:
        seed=r['seed'];e=candidate.make_engine();s=candidate.make_session(e);f=s.reset(seed)
        f=step(s,f,110);f=step(s,f,r["aid"])
        assert f.page=="NEOW_RESULT" and view.allowed(f)==[110],r
        v=f.state.vector;rid=int(v[34]);assert native_ids[rid]==expected[r["gift"]][seed]
        oo=dict(seed=seed,group=r["group"],native_id=native_ids[rid],cost=r["cost"],resources=list(v[:3]),counter=int(v[35])-1)
        if rid==PAINT:
            actual=[i for i in range(13) if v[707+2*i]]
            assert actual==upgraded[seed],(seed,actual,upgraded[seed])
            oo["matched_original_skill_indices"]=actual
        if r["cost"]==5:
            idx=int(subprocess.check_output([*rng,str(seed),"5","0","71","10"],text=True).strip().split(",")[-1])
            assert e._source._backend.CARD_IDS[int(v[732])-1]==native["curse"][idx]
            oo["matched_original_curse"]=native["curse"][idx]
        if rid==DOLL:
            assert v[35]==2+int(r["cost"]==5)
        if rid in (MAW,LIZARD):
            assert v[2770:2775]==(2,0,int(rid==MAW),0,0)
        if rid==BELT:assert v[16:22]==(4,0,0,0,0,0)
        mapped=step(s,f,110);w=mapped.state.vector
        assert mapped.state.vector[6]==5 and w[:3]==v[:3] and w[16:24]==v[16:24] and w[32:112]==v[32:112] and w[706:898]==v[706:898]
        assert w[2770:2775]==v[2770:2775]
        cases.append(oo)
    result=dict(repaired=dict(Counter(r["group"] for r in cases)),original_classes=native_ids,recovered_original_pools=saves,
                original_leave_receipts=trace_reference(),cases=cases,sha=sha(HERE/"direct.py"),original_jar=sha(pools.JAR))
    write(HERE/"DIRECT.json",result)
    print(result["repaired"])


if __name__=="__main__":
    run()
