"""Run the installed retail hand picker offline with its gameplay bytecode unchanged."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from experiments.common_relic193.pools import ROOT,JAR
from experiments.sa_calibration_round6.reference import read,sha

HERE=Path(__file__).resolve().parent


def run():
    java = JAR.parent/"jre/bin/java"
    compiler, = [r for r in read(ROOT/"native_fixture_work/BUILD.json")["inputs"] if "ecj-" in r["path"]]
    assert sha(Path(compiler["path"])) == compiler["sha256"]
    extra = ("audio.SoundMaster","cards.AbstractCard","cards.CardGroup","cards.green.Strike_Green",
             "core.CardCrawlGame","core.Settings","helpers.input.InputHelper",
             "screens.select.HandCardSelectScreen","ui.buttons.CardSelectConfirmButton")
    with TemporaryDirectory() as temp:
        root = Path(temp)
        existing = (ROOT/"experiments/golden_loot193/HeadlessBoot.java").read_text()
        marker='"characters.AbstractPlayer"'
        assert existing.count(marker)==1
        source=root/"HeadlessBoot.java"
        source.write_text(existing.replace(marker,",".join('"'+n+'"' for n in extra)+","+marker))
        cp=f"{JAR}:{JAR.parent/'ModTheSpire.jar'}"
        subprocess.run([java,"-jar",compiler["path"],"-1.8","-nowarn","-proc:none","-cp",cp,"-d",root,
                        source,HERE/"RetailSwap.java"],check=True)
        assets=root/"bootstrap"
        subprocess.run([java,"-cp",f"{root}:{cp}","HeadlessBoot",JAR,assets],check=True)
        result=subprocess.run([java,"-Djava.awt.headless=true","-cp",f"{assets}:{root}:{cp}","RetailSwap"],cwd=root,
                              text=True,capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr[-2400:])
        assert "RETAIL_SWAP 45" in result.stdout.splitlines()
    return dict(retail_jar_sha256=sha(JAR),probe_sha256=sha(HERE/"RetailSwap.java"),physical_occurrence_tests=45)

if __name__=="__main__":
    print(run())
