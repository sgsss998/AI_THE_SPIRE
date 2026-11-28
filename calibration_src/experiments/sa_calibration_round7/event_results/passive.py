"""Build runtime identities from the installed original's equip and permanent-card callbacks."""
from pathlib import Path
from zipfile import ZipFile
import json
from experiments.common_relic193.pools import core_pools
from experiments.common_relic193.rules import relic_id
from experiments.ordinary_reward_hooks193.audit import dump,JAR,RETAIL
from experiments.sa_calibration_round6.reference import sha,write

HERE=Path(__file__).resolve().parent


def extract():
    assert sha(JAR)==RETAIL
    with ZipFile(JAR) as jar:
        lookup={Path(p).stem.lower():Path(p).stem for p in jar.namelist() if p.startswith("com/megacrit/cardcrawl/relics/")
                and "$" not in p and p.endswith(".class")}
    ids,_=core_pools()
    names={}
    for key,native in ids.items():
        cls=lookup.get(("SneckoSkull" if key=="SNECKO_SKULL" else native.replace(" ","")).lower())
        if cls:
            names[key]="relics."+cls
    methods=dump(tuple(names.values())+("relics.AbstractRelic",))
    base=methods["relics.AbstractRelic"]
    assert base["onEquip()V"]==["0: RETURN"]
    rows={}
    for key,cls in names.items():
        defs=methods[cls]
        ctor=defs.get("<init>()V",[])
        if (not ctor or not any("relics.AbstractRelic.<init>" in line for line in ctor)
                or any(k.startswith(("onEquip(","onObtainCard(","obtain(","instantObtain(")) for k in defs)
                or any("PUTFIELD" in line and ".counter:I" in line for line in ctor)):
            continue
        rows[key]=relic_id(key)
    return dict(original_sha256=RETAIL,passive=rows)


if __name__=="__main__":
    result=extract()
    write(HERE/"PASSIVE.json",result)
    print(len(result["passive"]))
