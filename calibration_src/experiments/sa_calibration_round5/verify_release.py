"""Rebuild the local receipt summary and verify the fixed interface and real branches."""
import argparse
import csv
import json

from experiments.sa_calibration_round4 import verify_release as previous_verifier
from . import release
from .coverage import inventory,current
from .reference import HERE,ROOT,R4,PARENT,PARENT_MANIFEST,baseline,read,sha
from .receipts import compact
from .regression import summarize
from .verify_public import validate_batch,validate_chest,validate_replay,validate_shop
from .wheel.verify import measure as wheel_measure


def build():
    assert sha(R4/"RELEASE.json")==PARENT_MANIFEST and previous_verifier.build()==read(R4/"RELEASE.json")
    assert baseline()==read(HERE/"BASELINE.json")
    signature=release.interface_signature().metadata()
    frozen=read(HERE/"FREEZE.json")
    assert frozen["components"]==release.source_hashes() and frozen["supersedes"]==sha(HERE/"editions/rc1/FREEZE.json")
    assert signature==read(HERE/"INTERFACE.json")
    for name in ("control","result"):
        assert compact(HERE/"replay"/(name.upper()+".json")) == read(HERE/"replay"/(name+"-receipts.json"))
    control=read(HERE/"replay/control-receipts.json")
    fixed=read(HERE/"replay/result-receipts.json")
    validate_replay(baseline(),control,fixed)
    batch=read(HERE/"regression/RESULT.json")
    assert batch["signature"]==signature==fixed["signature"] and not batch["smoke"] and not batch["training_updates"]
    assert summarize(batch["records"])==batch["combined"]
    with (HERE/"regression/seeds.csv").open(newline="") as stream:
        validate_batch(batch,list(csv.DictReader(stream)))
    changes=read(HERE/"regression/CHANGES.json")
    assert changes["signature"]==signature and {r["seed"] for r in changes["changes"]}=={
        r["seed"] for r in batch["records"] if r["reason"]!=r["previous"]}
    assert inventory.build()==read(HERE/"coverage/BASELINE.json")
    now=current.build()
    assert now==read(HERE/"coverage/CURRENT.json")
    catalog=read(HERE/"coverage/CATALOG.json")
    assert len(catalog["records"])==sum(group["candidate_ids"] for group in catalog["families"].values())
    chest=read(HERE/"chest/RESULT.json")
    shop=read(HERE/"shop/RESULT.json")
    validate_chest(chest,signature)
    validate_shop(shop,signature)
    for branch in chest["branches"].values():
        for name, expected in branch["source_sha256"].items():
            assert sha(ROOT/name)==expected,name
    for name,branch in shop["branches"].items():
        directory=ROOT/shop["raw_root_pattern"].format(branch=name)
        for filename,expected in branch["raw"].items():
            assert sha(directory/filename)==expected,(name,filename)
    assert wheel_measure(release)==read(HERE/"wheel/RESULT.json")
    audited={}
    for file in sorted(HERE.rglob("*")):
        if file.is_file() and file.name!="RELEASE.json" and file.suffix in {".py",".cpp",".swift",".md",".json",".tsv",".csv"}:
            audited[file.relative_to(HERE).as_posix()]=sha(file)
    return dict(parent_commit=PARENT,parent_edition=PARENT_MANIFEST,signature=signature,changed_training_steps=0,
                release_sha256=frozen["components"],files=audited)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--seal",action="store_true")
    args=parser.parse_args()
    edition=build()
    manifest=HERE/"RELEASE.json"
    if args.seal:
        with manifest.open("x") as handle:
            json.dump(edition,handle,ensure_ascii=False,indent=2)
            handle.write("\n")
    else:
        assert edition==read(manifest)
    print("Verified",len(edition["files"]),"edition files, the sealed parent, original receipts and 704 game results.")
