"""Export measured decisions, source and checksums to the separate GitHub checkout."""
import argparse
from pathlib import Path
import shutil

from .reference import HERE,read,write,sha


def copy(source,target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source,target)


def preserve_seed(value):
    if isinstance(value,dict):
        return {k:preserve_seed(v) for k,v in value.items()}
    if isinstance(value,list):
        return [preserve_seed(v) for v in value]
    if type(value) is int and abs(value)>2**53-1:
        return str(value)
    return value


def export(root):
    root=root.resolve()
    docs=root/"docs/calibration/r5"
    src=root/"calibration_src/experiments/sa_calibration_round5"
    copies={"README.md":"README.md","BASELINE.json":"baseline.json","INTERFACE.json":"interface.json","FREEZE.json":"freeze.json",
            "editions/rc1/FREEZE.json":"rc1-freeze.json",
            "coverage/branches.tsv":"baseline-branches.tsv","coverage/BASELINE.json":"coverage-baseline.json",
            "regression/seeds.csv":"seeds.csv","regression/CHANGES.json":"changed-seeds.json",
            "replay/control-receipts.json":"r4-replay.json","replay/result-receipts.json":"r5-replay.json",
            "wheel/RESULT.json":"wheel.json","shop/RESULT.json":"shop.json","chest/RESULT.json":"chest.json",
            "verify_public.py":"verify.py"}
    for name,target in copies.items():
        if name in ("chest/RESULT.json","shop/RESULT.json"):
            write(docs/target,preserve_seed(read(HERE/name)))
        else:
            copy(HERE/name,docs/target)
    article=(docs/"README.md").read_text()
    for local,published in (("regression/seeds.csv","seeds.csv"),("regression/CHANGES.json","changed-seeds.json"),
                            ("replay/result-receipts.json","r5-replay.json"),("replay/control-receipts.json","r4-replay.json")):
        article=article.replace("]("+local+")","]("+published+")")
    article+="\n仓库根目录运行 `python3 docs/calibration/r5/verify.py` 可独立复核本次公开版本、覆盖数、真机分支与 704 局结果。\n"
    (docs/"README.md").write_text(article)
    for path in (HERE/"coverage").iterdir():
        if path.is_file() and path.suffix in {".tsv",".csv",".md",".json"}:
            copy(path,docs/"coverage"/path.name)
    for name in ("chest","shop","wheel"):
        report=HERE/name/"REPORT.md"
        if report.is_file():
            dest=docs/name/"REPORT.md"
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(report.read_text().replace("](RESULT.json)","]("+f"../{name}.json"+")"))
    for path in HERE.rglob("*"):
        if "editions" in path.relative_to(HERE).parts:
            continue
        if path.is_file() and (path.suffix in {".py",".cpp",".swift"} or path==HERE/"wheel/build/BUILD.json"):
            copy(path,src/path.relative_to(HERE))
    batch=read(HERE/"regression/RESULT.json")
    write(docs/"batch.json",{k:v for k,v in batch.items() if k!="records"})
    files=sorted(p for directory in (src,docs) for p in directory.rglob("*") if p.is_file() and p.name!="SHA256.json")
    write(docs/"SHA256.json",dict(local_edition_sha256=sha(HERE/"RELEASE.json"),
                                   files={p.relative_to(root).as_posix():sha(p) for p in files}))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("checkout",type=Path)
    export(parser.parse_args().checkout)
