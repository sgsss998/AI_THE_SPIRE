"""Compare the reconstructed original registration order against every retained Silent card-pool position."""
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import subprocess

from experiments.common_relic193.pools import ROOT,JAR
from experiments.neow_transform_two193.random_audit import load_pools
from experiments.ordinary_reward_hooks193.audit import dump
from experiments.sa_calibration_round6.reference import read,sha,write

HERE=Path(__file__).resolve().parent


def extract():
    lib="helpers.CardLibrary"
    rules=dump((lib,"dungeons.AbstractDungeon"))
    registered=[re.search(r'\.add(\w+)Cards\(\)V',line).group(1) for line in rules[lib]["initialize()V"] if ".add" in line and "Cards()V" in line]
    assert registered==["Red","Green","Blue","Purple","Colorless","Curse"]
    assert "java.util.HashMap.put" in "\n".join(rules[lib]["add(Lcom/megacrit/cardcrawl/cards/AbstractCard;)V"])
    color="\n".join(rules["dungeons.AbstractDungeon"]["addColorlessCards()V"])
    assert all(t in color for t in ("CardLibrary.cards","java.util.HashMap.entrySet()","CardRarity.BASIC","CardRarity.SPECIAL","CardType.STATUS","CardGroup.addToTop"))
    java=JAR.parent/"jre/bin/java"
    cp=f"{JAR}:{JAR.parent/'ModTheSpire.jar'}"
    compiler,=[x for x in read(ROOT/"native_fixture_work/BUILD.json")["inputs"] if "ecj-" in x["path"]]
    assert sha(Path(compiler["path"]))==compiler["sha256"]
    with TemporaryDirectory() as name:
        d=Path(name)
        subprocess.run([java,"-jar",compiler["path"],"-1.8","-nowarn","-proc:none","-cp",cp,"-d",d,HERE/"RetailCardOrder.java"],check=True)
        res=subprocess.run([java,"-cp",f"{d}:{cp}","RetailCardOrder",JAR],capture_output=True,text=True)
        if res.returncode:
            raise RuntimeError(res.stdout+res.stderr)
    data=defaultdict(list)
    size=0
    for ln in res.stdout.splitlines():
        if ln.startswith("SIZE\t"):
            size=int(ln.split("\t")[1])
        if ln.startswith("CARD\t"):
            _,tier,card=ln.split("\t")
            data[tier].append(card)
    native,_=load_pools()
    for rarity in ("common","uncommon","rare"):
        empirical=native[rarity]
        computed=data["Green_"+rarity.upper()]
        assert computed==(empirical if rarity=="common" else list(reversed(empirical))),(rarity,computed,empirical)
    # Preserve interleaved rarity order in the colorless pool.
    colors=[ln.split("\t")[2] for ln in res.stdout.splitlines() if ln.startswith("CARD\tColorless_")]
    assert size>360 and len(colors)==len(set(colors))==35
    return dict(retail_jar=sha(JAR),registered_cards=size,validated_silent_pool_positions=sum(len(native[k]) for k in ("common","uncommon","rare")),
                source_colorless=list(reversed(colors)))


if __name__=="__main__":
    write(HERE/"CARD_ORDER.json",extract())
