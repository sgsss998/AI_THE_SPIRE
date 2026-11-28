"""Build the isolated curse draw correction against the existing frozen simulation ABI."""
from pathlib import Path
import subprocess
from experiments.policy_backend_hand_order.candidate import PINNED_BUILD,PINNED_SHA,ROOT
from experiments.sa_calibration_round6.reference import read,sha,write

HERE=Path(__file__).resolve().parent


def build():
    assert sha(PINNED_BUILD)==PINNED_SHA
    prior=read(PINNED_BUILD)
    for path,digest in prior["sources"].items():
        assert sha(ROOT/path)==digest
    stage=HERE/"build"
    stage.mkdir(exist_ok=True)
    setup=prior["modules"]["_fixture_setup"]
    target=stage/setup["file"].replace("_fixture_setup","_r7_curse_draw")
    args=list(setup["args"])
    args[args.index(str(PINNED_BUILD.parent/"sources/_fixture_setup.cpp"))]=str(HERE/"correction.cpp")
    args[-1]=str(target)
    subprocess.run(args,check=True)
    write(stage/"BUILD.json",dict(name="_r7_curse_draw",file=target.name,sha256=sha(target),parent_sha256=PINNED_SHA,
                                   sources={p.relative_to(ROOT).as_posix():sha(p) for p in (HERE/"correction.cpp",Path(__file__))}))
    print(sha(stage/"BUILD.json"))


if __name__=="__main__":
    build()
