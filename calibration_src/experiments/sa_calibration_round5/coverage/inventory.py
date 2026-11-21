"""Build the R4 decision-branch baseline from versioned sources and case receipts."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parents[1]
R3 = EXPERIMENTS / "sa_calibration_round3"
R4 = EXPERIMENTS / "sa_calibration_round4"
LABELS = {"样本已核", "有差异", "待验", "不适用"}


def table(path, delimiter=","):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status_counts(rows, field):
    counts = Counter(row[field] for row in rows)
    return {"applicable": len(rows)-counts["不适用"], "counts": dict(sorted(counts.items()))}


def build():
    scene_path = R3 / "coverage/SCENES.csv"
    question_path = R3 / "coverage/QUESTIONS.csv"
    group_path = R4 / "coverage/GROUPS.csv"
    batch_index = R4 / "regression/RESULT.json"
    start_path = R4 / "fresh/START_INPUT.json"
    end_path = R4 / "fresh/TERMINAL.json"
    branch_source = HERE / "branches.tsv"
    sources = {scene_path, question_path, group_path, batch_index, start_path, end_path, branch_source}
    scenes = {row["场景"] for row in table(scene_path)}
    questions = table(question_path)
    branches = table(branch_source, "\t")
    assert len(branches) == len({r["id"] for r in branches})
    assert {r["场景"] for r in branches} == scenes
    assert len(questions) == len({q["编号"] for q in questions}) == 98
    assert len(scenes) == 18
    for row in branches:
        assert row["S"] in LABELS and row["A"] in LABELS and row["核对内容与未核范围"], row["id"]
        for name in row["证据路径（相对experiments）"].split(";"):
            path=(EXPERIMENTS / name).resolve()
            assert EXPERIMENTS in path.parents and path.is_file(), (row["id"], name)
            sources.add(path)

    groups = table(group_path)
    frequencies = Counter()
    case_seeds = set()
    for row in groups:
        seeds = set(map(int, row["全部种子"].split()))
        assert len(seeds)==int(row["局数"]) and not seeds.intersection(case_seeds)
        frequencies[row["停点类型"]] += len(seeds)
        case_seeds.update(seeds)
    assert frequencies == {"选牌": 76, "奖励": 53} and len(groups) == 23

    index = read(batch_index)
    full_path=batch_index.parent / index["path"]
    assert sha(full_path) == index["sha256"]
    sources.add(full_path)
    runs=read(full_path)["runs"]
    assert len(runs)==len({r["seed"] for r in runs})==704
    cohorts={}
    for tag, expected in index["summary"].items():
        items=[r["episode"] for r in runs if r["cohort"]==tag]
        outcomes=Counter(e["reason"] for e in items)
        assert outcomes==expected["outcomes"] and len(items)==expected["seeds"]
        cohorts[tag]={"seeds":len(items), "outcomes":dict(outcomes), "max_floor":max(e["engine_floor"] for e in items),
                      "losses_with_partial_action_sets":sum(e["reason"]=="loss" and e["incomplete_action_sets"]>0 for e in items),
                      "stop_pages":dict(Counter(e["page"] for e in items if e["reason"]=="unsupported"))}
    duration=(datetime.fromisoformat(read(end_path)["at"])-datetime.fromisoformat(read(start_path)["utc"])).total_seconds()
    return {
        "edition":"R4 baseline for round 5, Silent Ascension 20",
        "unit":"一行是写明范围的决策分支。部分分支含多个相近操作，样本已核只标记实际覆盖的对象、原版动作、版本和时点，不表示整行的所有内容组合通过。",
        "scene_count":len(scenes),"branches":branches,"branch_count":len(branches),
        "branches_with_known_gap_or_pending":sum(bool({r["S"],r["A"]} & {"有差异","待验"}) for r in branches),
        "state":status_counts(branches,"S"), "action":status_counts(branches,"A"),
        "historical_question_ids":[row["编号"] for row in questions],
        "historical_references":"98条历史问题包含多版本、重叠证据与旧判定。保留溯源，不与本表的分支相加。",
        "per_scene":{scene:[r["id"] for r in branches if r["场景"]==scene] for scene in sorted(scenes)},
        "r4_free_policy":cohorts,
        "r3_fixed_640_stops_replayed_in_r4":{"seeds":len(case_seeds),"groups":len(groups),"counts":dict(frequencies),
            "scope":"R3固定组的两类旧停点，由R4复现分类；不是R4全部331个停点的归因。"},
        "r4_retail_capture_seconds_for_one_339_input_run":round(duration,1),
        "sources_sha256":{p.relative_to(EXPERIMENTS).as_posix():sha(p) for p in sorted(sources)}
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    report=build()
    path=HERE / "BASELINE.json"
    if args.check:
        assert report==read(path)
    else:
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(f'{report["scene_count"]} scenes, {report["branch_count"]} scoped branches; S={report["state"]}, A={report["action"]}')


if __name__=="__main__":
    main()
