"""Export inspected S/A evidence and the frozen edition, excluding installed game files."""
from pathlib import Path
import re
import shutil
import sys
from .reference import HERE, ROOT, R5, COMMIT, PARENT_SHA, read, write, sha
from . import release

DATA=("README.md","BASELINE.json","FREEZE.json","INTERFACE.json","branches/REPORT.md","branches/SOURCE.json.gz","branches/RESULT.json",
      "cohort/R5.json","cohort/R6.json","cohort/INDEPENDENT.json","cohort/STARTUP_CRASH.json","cohort/REPORT.md",
      "coverage/CURRENT.json","coverage/REPORT.md","rewards/RESULT.json","rewards/REPORT.md",
      "regression/CHANGES.json","regression/REPORT.md","regression/seeds.csv","replay/receipts.json","replay/RESULT.json","replay/history.json",
      "fresh/RESULT.json","fresh/REPLAY.json","fresh/receipts.json","fresh/original-inputs.json")

def export(checkout):
    docs=checkout/"docs/calibration/r6"
    src=checkout/"calibration_src/experiments/sa_calibration_round6"
    assert sha(R5/"RELEASE.json")==PARENT_SHA and release.source_hashes()==read(HERE/"FREEZE.json")["runtime"]
    assert read(HERE/"INTERFACE.json")==release.interface_signature().metadata()
    def copy(origin,target):
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(origin,target)
    for name in DATA:copy(HERE/name,docs/name)
    code=sorted(p for p in HERE.rglob("*") if p.suffix in {".py",".swift"})
    for f in code:copy(f,src/f.relative_to(HERE))
    copy(HERE/"verify_public.py",docs/"verify.py")
    # The branch verification entry links to source in the source tree.
    branches=docs/"branches/REPORT.md"
    branches.write_text(branches.read_text().replace("](verify.py)","](../../../../calibration_src/experiments/sa_calibration_round6/branches/verify.py)"))
    batch=read(HERE/"regression/RESULT.json")
    assert batch["signature"]==release.interface_signature().metadata()
    write(docs/"regression/RESULT.json",{k:v for k,v in batch.items() if k!="records"})
    report=docs/"README.md"
    report.write_text(report.read_text()+"\n在已下载的 GitHub 仓库中运行 `python3 docs/calibration/r6/verify.py` 可校验证据哈希、两个冻结运行文件、分项验收和逐局统计。\n")
    headline="## 静默 A20 第六轮校准（2026-11-22）"
    index=checkout/"README.md"
    if headline not in index.read_text():
        index.write_text(index.read_text().replace("## 静默 A20 第五轮校准",headline+"\n\n模型已能领取第 10 层三项战后奖励。新随机盲测在第 2 层活墙删牌时发现缺少动作，真机继续到第 6 层阵亡。704 局固定对照仍有 332 局卡在接口。[第六轮报告和逐局证据](docs/calibration/r6/README.md)\n\n## 静默 A20 第五轮校准",1).replace("[当前进度](#静默-a20-第五轮校准2026-11-22)","[当前进度](#静默-a20-第六轮校准2026-11-22)"))
    index=checkout/"calibration_src/README.md"
    if "sa_calibration_round6" not in index.read_text():
        first,rest=index.read_text().split("\n",1)
        index.write_text(first+"\n\nThe R6 ordinary reward adapter and its retail checks are in `experiments/sa_calibration_round6`. See the [R6 report](../docs/calibration/r6/README.md) for the fixed regression and the independent original game.\n"+rest)
    # Read-only local manifest keeps raw input and terminal evidence bound to the release.
    counts=read(HERE/"coverage/CURRENT.json"); fresh=read(HERE/"fresh/RESULT.json")
    sources=dict(fresh["source_sha256"])
    sources.update(read(HERE/"cohort/INDEPENDENT.json")["source_sha256"])
    for name,digest in sources.items():assert sha(ROOT/name)==digest,name
    local=list(DATA)+["regression/RESULT.json","fresh/START_INPUT.json","fresh/START_OUTPUT.json","fresh/ACTIONS.jsonl","fresh/TERMINAL.json",
                      "fresh/SEEDS_BEFORE.json","fresh/SEED.json","fresh/AUTOSAVE_SEED.json","fresh/FIRST_SIMULATOR_START.json","fresh/PHYSICAL.jsonl","fresh/CLOSE.json"]
    edition=dict(parent_commit=COMMIT,parent_manifest=PARENT_SHA,training_updates=0,coverage=dict(S=counts["state"],A=counts["action"]),
        files={p.relative_to(HERE).as_posix():sha(p) for p in sorted(set(code)|{HERE/n for n in local})})
    manifest=HERE/"RELEASE.json"
    if manifest.exists():assert read(manifest)==edition
    else:write(manifest,edition)
    for doc in docs.rglob("*.md"):
        for url in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            if "://" not in url and not url.startswith("#"):assert (doc.parent/url.split("#")[0]).exists(),(doc,url)
    public=[p for folder in (docs,src) for p in folder.rglob("*") if p.is_file() and p.name!="SHA256.json"]
    write(docs/"SHA256.json",dict(local_edition_sha256=sha(manifest),files={p.relative_to(checkout).as_posix():sha(p) for p in sorted(public)}))

if __name__=="__main__":export(Path(sys.argv[1]).resolve())
