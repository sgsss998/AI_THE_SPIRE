"""Run retail Pandora's Box onEquip with a non-rendering output screen and native card pools."""
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from experiments.common_relic193.pools import ROOT, JAR
from experiments.neow_transform_two193.random_audit import load_pools
from experiments.sa_calibration_round6.reference import read, sha

HERE = Path(__file__).resolve().parent


def run(seeds):
    native, _ = load_pools()
    java=JAR.parent/"jre/bin/java"
    standard=JAR.parent/"ModTheSpire.jar"
    compiler, = [r for r in read(ROOT/"native_fixture_work/BUILD.json")["inputs"] if "ecj-" in r["path"]]
    assert sha(Path(compiler["path"])) == compiler["sha256"]
    extra=("cards.AbstractCard","cards.CardGroup","cards.green.Strike_Green","helpers.CardLibrary","unlock.UnlockTracker",
           "relics.PandorasBox","screens.select.GridCardSelectScreen","core.Settings")
    with TemporaryDirectory() as folder:
        tmp=Path(folder)
        boot=(ROOT/"experiments/golden_loot193/HeadlessBoot.java").read_text()
        marker='"characters.AbstractPlayer"'
        assert boot.count(marker)==1
        boot=boot.replace(marker,",".join('"'+name+'"' for name in extra)+","+marker)
        (tmp/"HeadlessBoot.java").write_text(boot)
        data=tmp/"pools.tsv"
        data.write_text("".join(f"{kind}\t{name}\n" for kind in ("common","uncommon","rare") for name in native[kind]))
        cp=f"{JAR}:{standard}"
        compile=subprocess.run([java,"-jar",compiler["path"],"-1.8","-nowarn","-proc:none","-cp",cp,"-d",tmp,
                              tmp/"HeadlessBoot.java",HERE/"RetailBox.java"],text=True,capture_output=True)
        if compile.returncode:raise RuntimeError(compile.stdout+compile.stderr)
        assets=tmp/"bootstrap"
        subprocess.run([java,"-cp",f"{tmp}:{cp}","HeadlessBoot",JAR,assets],check=True,capture_output=True)
        process=subprocess.run([java,"-cp",f"{assets}:{tmp}:{cp}","RetailBox",data,*map(str,seeds)],cwd=tmp,capture_output=True,text=True)
        if process.returncode:raise RuntimeError(process.stdout[-1000:]+process.stderr[-1800:])
    output={}
    for line in process.stdout.splitlines():
        if line.startswith("BOX\t"):
            _,s,deck,faces=line.split("\t")
            output[int(s)]=dict(pre_confirm_deck=deck.split(","),confirmation=faces.split(","))
    assert set(output)==set(seeds) and all(len(x["confirmation"])==10 for x in output.values())
    return output


if __name__=="__main__":
    print(run([2895685479221259731]))
