"""Extract collectible card upgrade and potion/relic hooks from the original game."""
import re
from pathlib import Path
from zipfile import ZipFile

from experiments.common_relic193.pools import JAR, ROOT
from experiments.ordinary_reward_hooks193.audit import dump
from experiments.sa_calibration_round6.reference import sha, write

HERE = Path(__file__).resolve().parent


def classes(zipfile, group):
    prefix = "com/megacrit/cardcrawl/"+group.replace(".","/")+"/"
    return sorted(name[len("com/megacrit/cardcrawl/"):-6].replace("/",".") for name in zipfile.namelist()
                  if name.startswith(prefix) and name.endswith(".class") and not any(ch in name[len(prefix):] for ch in "/$"))


def inspect():
    with ZipFile(JAR) as zipfile:
        groups = {group:classes(zipfile,group) for group in ("cards.green","cards.colorless","cards.curses","relics","potions")}
    out = {k:[] for k in ("single_upgrade","green_transform","never_upgrade","removal_callbacks","smith_callbacks","acquire_callbacks","out_of_combat_potion_exceptions")}
    for group, names in groups.items():
        for name, records in dump(tuple(names)).items():
            methods = {s.split("(")[0] for s in records}
            init = records.get("<init>()V",[])
            if group.startswith("cards"):
                ids = [x[7:] for x in init if x.startswith("1: LDC ")]
                if not ids:
                    continue
                card_id, = ids
                if group=="cards.green":
                    out["green_transform"].append(card_id)
                if "canUpgrade" in methods:
                    continue
                if group=="cards.curses":
                    out["never_upgrade"].append(card_id)
                elif any("upgradeName()V" in x for x in records.get("upgrade()V",())):
                    out["single_upgrade"].append(card_id)
            elif group=="relics":
                for field, hook in (("removal_callbacks","onMasterDeckChange"),("smith_callbacks","onSmith"),
                                   ("acquire_callbacks","onObtainCard")):
                    if hook in methods and not name.endswith("AbstractRelic"):
                        ids = [x[7:] for x in init if x.startswith("1: LDC ")]
                        assert len(ids)==1,(name,hook)
                        out[field].extend(ids)
            elif "canUse" in methods and not name.endswith("AbstractPotion"):
                out["out_of_combat_potion_exceptions"].append(name.rsplit(".",1)[-1])
    assert len(out["single_upgrade"])>85 and "AscendersBane" in out["never_upgrade"]
    assert "Du-Vu Doll" in out["removal_callbacks"] and "CeramicFish" in out["acquire_callbacks"]
    return dict(retail_jar=sha(JAR), **{k:sorted(set(v)) for k,v in out.items()})


if __name__=="__main__":
    write(HERE/"RULES.json",inspect())
