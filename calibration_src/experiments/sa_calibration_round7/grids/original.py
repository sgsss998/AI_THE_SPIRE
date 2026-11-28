"""Use the original Java transformation routine, with two retained original card pools."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from experiments.common_relic193.pools import JAR,ROOT
from experiments.neow_transform_two193.random_audit import load_pools
from experiments.sa_calibration_round6.reference import read,sha

HERE=Path(__file__).resolve().parent


def transformations(cases):
    if not cases:
        return []
    values,_=load_pools()
    values["colorless"]=read(HERE/"CARD_ORDER.json")["source_colorless"]
    java=JAR.parent/"jre/bin/java"
    compiler,=[x for x in read(ROOT/"native_fixture_work/BUILD.json")["inputs"] if "ecj-" in x["path"]]
    assert sha(Path(compiler["path"]))==compiler["sha256"]
    cp=f"{JAR}:{JAR.parent/'ModTheSpire.jar'}"
    boot=(ROOT/"experiments/golden_loot193/HeadlessBoot.java").read_text()
    extra=("cards.AbstractCard","cards.CardGroup","cards.green.Strike_Green","helpers.CardLibrary","unlock.UnlockTracker",
           "relics.PandorasBox","screens.select.GridCardSelectScreen","core.Settings")
    mark='"characters.AbstractPlayer"'
    assert boot.count(mark)==1
    with TemporaryDirectory() as folder:
        root=Path(folder)
        stage=root/"HeadlessBoot.java"
        stage.write_text(boot.replace(mark,",".join('"'+n+'"' for n in extra)+","+mark))
        pool=root/"pools"
        pool.write_text("".join(f"{k}\t{c}\n" for k in ("common","uncommon","rare","colorless","curse") for c in values[k]))
        table=root/"input"
        table.write_text("".join("\t".join(map(str,(r["seed"],r["floor"],*r["rng"],r["chosen"],r.get("color","green"))))+"\n" for r in cases))
        cmd=[java,"-jar",compiler["path"],"-1.8","-nowarn","-proc:none","-cp",cp,"-d",root,stage,HERE.parent/"neow/RetailBox.java",HERE/"RetailTransform.java"]
        compile=subprocess.run(cmd,capture_output=True,text=True)
        if compile.returncode:
            raise RuntimeError(compile.stdout+compile.stderr)
        subprocess.run([java,"-cp",f"{root}:{cp}","HeadlessBoot",JAR,root/"boot"],check=True,capture_output=True)
        run=subprocess.run([java,"-cp",f"{root/'boot'}:{root}:{cp}","RetailTransform",pool,table],capture_output=True,text=True)
        if run.returncode:
            raise RuntimeError(run.stderr[-1500:]+run.stdout[-500:])
    results=[line.split("\t")[1:] for line in run.stdout.splitlines() if line.startswith("CARD\t")]
    assert [int(s) for s,_ in results]==[r["seed"] for r in cases]
    return [card for _,card in results]
