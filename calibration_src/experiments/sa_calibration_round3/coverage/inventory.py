"""Build a scoped, versioned inventory from the original game and the evidence receipts."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
EXPERIMENTS = PROJECT / "experiments"
JAR = PROJECT / "native_runtime/compact_native_004/game/desktop-1.0.jar"
HISTORY = EXPERIMENTS / "sa_calibration_round1/coverage/全局场景校准表.csv"
JAR_HASH = "880ca5646d02065a061bbbdf7cc106dc1443d5afc6b9560f512486b098fd627b"
RETAIL_HASH = "dd60a613a6178e08f1a57bcb8d5747e33c21fd49e743b88d76e9d74042803b2a"
FAMILIES = ("cards", "relics", "potions", "monsters", "events", "powers")
HISTORICAL_LINKS = {6:"G-05", 12:"R3-03 / R3-04 / R3-05", 41:"R3-02",
                    43:"R3-01（另一种子）", 52:"R2-04", 53:"R2-03", 56:"R2-02",
                    58:"R2-01", 59:"R2-01（离开页仍单列）", 64:"R2-05", 65:"R2-06"}
def digest(data):
    return hashlib.sha256(data).hexdigest()

def file_hash(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def read_table(path, delimiter=","):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))

def write_table(filename, rows):
    with (HERE / filename).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

def original_assets():
    if file_hash(JAR) != JAR_HASH:
        raise ValueError("Original game differs from the calibrated build")
    scenes, objects, families = read_table(HERE / "scenes.tsv", "\t"), [], {}
    metadata = json.loads((JAR.parents[1] / "target.json").read_bytes())["files"]["game/desktop-1.0.jar"]
    retail = Path(metadata["source"])
    if file_hash(retail) != RETAIL_HASH:
        raise ValueError("Original retail archive differs from the reference build")
    with ZipFile(retail) as archive, ZipFile(JAR) as running:
        def verified_asset(key):
            data = archive.read(key)
            if data != running.read(key):
                raise ValueError("Gameplay asset differs between retail and isolated runtime: " + key)
            return data
        for row in scenes:
            key = "com/megacrit/cardcrawl/" + row["原版规则类"] + ".class"
            row["原版类SHA256"] = digest(verified_asset(key))
        for family in FAMILIES:
            key = "localization/eng/" + family + ".json"
            raw = verified_asset(key)
            ids = sorted(json.loads(raw.decode("utf-8-sig")))
            families[family] = dict(entries=len(ids), asset=key, sha256=digest(raw))
            for item in ids:
                objects.append({"原版目录":family, "原版标识":item,
                                "入选范围":"原版全角色资源目录；静默可遇性和行为逐项另验"})
    return scenes, objects, families

def evidence_ref(path):
    if path.is_relative_to(PROJECT):
        return str(path.relative_to(PROJECT))
    if path.is_relative_to(PROJECT.parent):
        return "../" + str(path.relative_to(PROJECT.parent))
    raise ValueError("Unexpected evidence root: " + path.name)

def main():
    scenes, objects, families = original_assets()
    history, reviewed = read_table(HISTORY), read_table(HERE / "reviewed.tsv", "\t")
    hashes, questions = {}, []
    for index, old in enumerate(history, 1):
        sources = [Path(p) for p in old["证据"].splitlines() if p.strip()]
        refs = [evidence_ref(p) for p in sources]
        for ref, path in zip(refs, sources):
            if ref not in hashes:
                hashes[ref] = file_hash(path)
        questions.append({"编号":f"R1-{index:02}", "场景":old["阶段"], "问题":old["具体问题"],
                          "真值及对照方法":old["原版所见或游戏内部可读"], "动作与核对结果":old["原版允许动作与目标"]+"；"+old["模型字段或行为"]+"；"+old["前后结果"],
                          "判定":old["状态"], "依据":"\n".join(refs), "证据类型":old["证据类型"],
                          "适用范围":old["修复情况或判定边界"], "后续核对":HISTORICAL_LINKS.get(index,"")})
    for row in reviewed:
        source = row["依据"]
        ref = "experiments/" + source if source else ""
        if source:
            hashes[ref] = file_hash(EXPERIMENTS / source)
        questions.append({"编号":row["编号"], "场景":row["场景"], "问题":row["问题"],
                          "真值及对照方法":row["真值及对照方法"], "动作与核对结果":row["操作及可观察结果"],
                          "判定":row["判定"], "依据":ref, "证据类型":"见依据及适用范围" if ref else "原版规则目录，尚待配对",
                          "适用范围":row["适用范围"], "后续核对":""})
    if len({q["编号"] for q in questions}) != len(questions):
        raise ValueError("Duplicate question ID")
    # Historical stages use broader headings. Keep this mapping explicit for audit.
    crosswalk = {"涅奥开局":[1,2,3,4,5], "地图与跨幕":[34,35,36,37,71], "手牌和回合":[6,7,8,9,14,17,49,50,51,63,69],
                 "手中选牌":[15,16,21,22], "永久牌组选牌":[18,19,41,43,54], "普通敌人死亡":[10,11,12,13,52,66],
                 "精英与钥匙":[], "药水":[20,21,22,24,26,53], "遗物":[9,25,54,55,67], "随机事件":[39,40,41,42,56,58,59,60],
                 "商店":[28,29,30], "营火":[31,32,33,61], "普通战利品":[23,24,25,26,62,70], "宝箱":[27,67],
                 "首领战":[57,64,65], "首领奖励":[], "第四幕与心脏":[38,45,46,47], "终局":[44,46,48,68]}
    for row in scenes:
        stage = row["场景"]
        refs = [f"R1-{i:02}" for i in crosswalk[stage]] + [q["编号"] for q in reviewed if q["场景"] == stage]
        row["可查问题"] = " / ".join(refs)
    linked = {int(id_) for group in crosswalk.values() for id_ in group}
    if linked != set(range(1, len(history)+1)):
        raise ValueError(f"Unmapped historical rows: {set(range(1,len(history)+1))-linked}")
    write_table("SCENES.csv", scenes)
    write_table("QUESTIONS.csv", questions)
    write_table("OBJECT_IDS.csv", objects)
    result = {"source_game_sha256":RETAIL_HASH, "isolated_game_sha256":JAR_HASH, "retail_equals_isolated_for_all_catalogued_sources":True, "scenes":len(scenes), "native_reference_only":families, "native_catalog_ids":len(objects),
              "historical_R1":{"questions":len(history), "as_recorded":dict(Counter(row["状态"] for row in history)), "source_sha256":file_hash(HISTORY)},
              "subsequent_versioned_questions":{p:dict(Counter(q["判定"] for q in reviewed if q["编号"].split("-")[0]==p)) for p in sorted({q["编号"].split("-")[0] for q in reviewed})},
              "total_versioned_rows":len(questions), "independent_source_files":hashes,
              "outputs":{n:file_hash(HERE/n) for n in ("SCENES.csv","QUESTIONS.csv","OBJECT_IDS.csv")},
              "interpretation":"历史问题保留当版结论，后续核对可追到具体新版本。目录包含其他角色和未使用对象。场景、问题或原版条目数均不代表全游戏正确率。"}
    (HERE/"RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(len(scenes), len(objects), len(questions))

if __name__ == "__main__":
    main()
