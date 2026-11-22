"""An isolated retail process, separate from the known-seed development branches."""
import subprocess
import sys
from pathlib import Path
from experiments.sa_calibration_round4.fresh import instance as installer
from ..reference import ROOT,HERE as R6,R4,R5,read,write,sha

HERE=R6/"fresh"
ID="compact_native_sa_round6_unseeded_001"
DEST=ROOT/"native_runtime"/ID

def stage():
    installer.ID,installer.DEST=ID,DEST
    installer.stage()
    subprocess.run(["swiftc",str(HERE/"keys.swift"),"-o",str(HERE/"keys")],check=True)
    prior=read(R4/"fresh/SEEDS_BEFORE.json")
    seeds=set(prior["seeds_u64"])
    seeds.add(int(read(R4/"fresh/SEED.json")["unsigned"]))
    seeds.update(r["seed"] for r in read(R5/"regression/RESULT.json")["records"])
    write(HERE/"SEEDS_BEFORE.json",dict(seeds_u64=sorted(seeds),source="R4 previous inventory, R4 holdout and R5 704 fixed games"))

if __name__=="__main__":
    if sys.argv[1:]==["launch"]:
        from native_runtime import launch
        raise SystemExit(launch(ID))
    stage()
