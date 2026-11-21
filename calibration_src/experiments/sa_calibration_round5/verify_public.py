"""Verify the portable fifth-round receipts using the Python standard library."""
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def validate_replay(baseline, previous, current):
    assert baseline["recorded_original"]["seed"] == current["seed"] == previous["seed"]
    assert previous["original_journal_sha256"] == current["original_journal_sha256"] == baseline["sources"]["fresh/ACTIONS.jsonl"]
    assert current["independent_holdout"] is False and not current["used_kernel_fallback"]
    assert previous["completed_inputs"] == 97 and previous["stop"]["index"] == 98
    assert previous["first_content"]["index"] == 46 and current["first_content"]["index"] == 128
    assert current["stop"]["index"] == 129 and current["stop"]["floor"] == 10
    records=current["records"]
    assert [r["index"] for r in records] == list(range(1,130))
    assert current["completed_inputs"] == sum(r["status"]!="stopped" for r in records) == 128
    assert current["official_actions"] == sum(len(r["actions_executed"]) for r in records)
    for before,after in zip(previous["records"],records):
        for name in ("index","command","original_before","original_after"):
            assert before[name]==after[name]
    for i,expected in enumerate((65,65,66,66),45):
        after=records[i-1]["after"]
        assert after["model_resources"][0] == after["original_resources"][0] == expected
    assert set(range(118,122)).issubset(records[50]["offered"])
    picked=records[97]
    assert picked["binding"]["reward"] == ["RELIC","inkbottle"] and picked["actions_executed"]==[110]
    for side in ("model","original"):
        state=picked["after"]["key_and_rewards"][side]
        assert ["inkbottle",0] in state["relics"] and state["keys"][2] is False and state["rewards"]==[]
        assert picked["after"][side+"_resources"][2] == 237
    assert records[-2]["after"]["key_and_rewards"]["model"]["rewards"] == []
    assert records[-2]["after"]["key_and_rewards"]["original"]["rewards"] == [["GOLD",20],["POTION","regenpotion"],["CARD",None]]
    assert records[-1]["status"]=="stopped" and records[-1]["offered"]==[]


def validate_batch(summary, rows):
    assert len(rows)==len({int(r["seed"]) for r in rows})==704
    for group,n in (("fixed",640),("additional",64)):
        batch=[r for r in rows if r["cohort"]==group]
        actual=summary["summary"][group]
        assert len(batch)==actual["seeds"]==n
        assert Counter(r["reason"] for r in batch)==actual["outcomes"]
        assert Counter(r["previous"]+"->"+r["reason"] for r in batch)==actual["transitions"]
        assert sum(int(r["decisions"]) for r in batch)==actual["decisions"]
        assert max(int(r["engine_floor"]) for r in batch)==actual["max_floor"]
    assert Counter(r["reason"] for r in rows)==summary["combined"]["outcomes"]


def validate_chest(chest, interface):
    assert chest["release"]==interface and set(chest["branches"])=={"ink","key","leave"}
    for kind,action in (("ink",110),("key",111),("leave",171)):
        branch=chest["branches"][kind]
        before,after=[r for r in branch["actions"] if r["input"]==98]
        assert before["stage"]=="before" and after["stage"]=="after" and before["aid"]==after["aid"]==action
        assert set((110,111,171))<=set(before["supported"])
        assert before["values"]["resources"]==after["values"]["resources"]==[56,66,237,9,1,20]
        assert after["values"]["relics"] == before["values"]["relics"]+([["inkbottle",0]] if kind=="ink" else [])
    key=chest["branches"]["key"]
    assert not next(r for r in key["actions"] if r["input"]==98 and r["stage"]=="after")["immediate_keys_equal"]
    assert key["passive_key"]["keys"]["sapphire"] and key["passive_key"]["additional_inputs"]==0


def validate_shop(shop, interface):
    assert shop["formal_interface"]==interface
    branches=shop["branches"]
    assert set(branches)=={"mirror","weak","fear","flex"}
    assert len({b["same_original_save"] for b in branches.values()})==1
    for name,price in (("mirror",172),("flex",56),("fear",55),("weak",57)):
        b=branches[name]
        receipt=b["items"][0]
        assert b["initial_cost"]==price and receipt["before"]["gold"]==229 and receipt["after"]["gold"]==229-price
        assert receipt["before"]["shop_rows_match"] and receipt["before"]["model_affordable"]==12
        for item in b["items"]:
            assert item["stale_rejected"]
            for side in ("before","after"):
                data=item[side]
                if "shop_rows_match" in data:
                    assert data["shop_rows_match"] and data["original_affordable"]==data["model_affordable"]
    mirror=branches["mirror"]
    assert mirror["copied"]["new_uuid"]!=mirror["copied"]["original_uuid"] and mirror["copied"]["originals_preserved"]==15
    after=mirror["items"][-1]["after"]
    assert after["gold"]==1 and after["model_affordable"]==0 and after["deck_count"]==16
    stock=branches["flex"]["items"][-1]["after"]
    assert stock["model_affordable"]==8 and stock["model_supported_shop_choices"]==7
    failed=branches["flex"]["full_slots"]
    assert not failed["model_sale_supported"] and failed["after_original_gold"]==stock["gold"]==118


def main():
    here=Path(__file__).resolve().parent
    root=here.parents[2]
    manifest=read(here/"SHA256.json")
    for name, expected in manifest["files"].items():
        path=(root/name).resolve()
        assert path.is_relative_to(root) and sha256(path.read_bytes()).hexdigest()==expected, name
    frozen=read(here/"freeze.json")
    assert sha256((here/"rc1-freeze.json").read_bytes()).hexdigest()==frozen["supersedes"]
    for name,expected in frozen["components"].items():
        assert sha256((root/"calibration_src/experiments/sa_calibration_round5"/name).read_bytes()).hexdigest()==expected,name
    coverage=read(here/"coverage/CURRENT.json")
    assert len(coverage["branches"])==coverage["branch_count"]==43
    for key in ("S","A"):
        reduced=Counter(r[key] for r in coverage["branches"])
        field="state" if key=="S" else "action"
        assert reduced==coverage[field]["counts"]
    assert sum(bool({r["S"],r["A"]} & {"待验","有差异"}) for r in coverage["branches"])==coverage["r5_open"]==17
    previous=read(here/"r4-replay.json")
    current=read(here/"r5-replay.json")
    validate_replay(read(here/"baseline.json"),previous,current)
    batch=read(here/"batch.json")
    assert batch["signature"]==current["signature"]==read(here/"interface.json")
    validate_chest(read(here/"chest.json"),batch["signature"])
    validate_shop(read(here/"shop.json"),batch["signature"])
    wheel=read(here/"wheel.json")["receipts"]
    assert [r["after_hp"] for r in wheel]==[65,65,66,66] and len({r["gold"] for r in wheel})==1
    with (here/"seeds.csv").open(newline="") as fp:
        validate_batch(batch,list(csv.DictReader(fp)))
    print(f"Verified {len(manifest['files'])} files, 704 seeds and the first 129 original inputs.")


if __name__=="__main__":
    main()
