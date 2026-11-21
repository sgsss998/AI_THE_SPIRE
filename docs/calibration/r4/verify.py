"""Verify the GitHub snapshot with just standard Python; run from any directory."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def read(name):
    return json.loads((HERE/name).read_bytes())
def rows(name):
    with (HERE/name).open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))
def verify_fresh_receipts(fresh, trace, mechanisms, interface):
    """Three readings of one immutable journal, with separately delimited authority."""
    assert fresh["valid"] and fresh["model_interface"] == interface
    assert fresh["started_blank"] and fresh["start_dispatches"] == 1 and not fresh["in_original_inventory"]
    assert fresh["original_completed_before_model"] and fresh["training_steps"] == 0
    assert int(fresh["seed_unsigned"]) == int(fresh["seed_signed"]) % (1 << 64)
    assert str(trace["original_seed"]) == str(fresh["seed_signed"])
    assert trace["original_journal_sha256"] == fresh["source_files"]["ACTIONS.jsonl"]["sha256"] == mechanisms["original_sha256"]
    assert trace["original_terminal_sha256"] == fresh["source_files"]["TERMINAL.json"]["sha256"]
    inputs = trace["inputs"]
    assert fresh["original_inputs"] == len(inputs) == 339
    assert [r["index"] for r in inputs] == list(range(1,340))
    assert fresh["original_final"] == dict(hp=0,max_hp=66,gold=254,floor=16,loss=True,native_score=184)
    semantic = fresh["reconciled_official"]
    diagnostic = fresh["diagnostic"]
    assert not fresh["official_model_endpoint"]["done"] and fresh["official_model_endpoint"]["resources"][3] == 1
    assert fresh["first_unmapped_or_failed_input"] == 33 and fresh["first_public_content_difference"]["index"] == 10
    assert not semantic["endpoint"]["done"] and semantic["endpoint"]["resources"][3] == 9
    assert semantic["stopped_at"] == semantic["first_unavailable"]["index"] == 98
    assert semantic["first_unavailable"]["requested"] == 110 and semantic["first_unavailable"]["supported"] == [111,171]
    assert [e["input"] for e in semantic["extra_card_actions"]] == [10,66]
    assert diagnostic["used_kernel"] and diagnostic["stop"] is None and diagnostic["endpoint"]["lost"]
    assert diagnostic["endpoint"]["resources"] == [0,66,254,16,1,20]
    assert diagnostic["endpoint"]["enemies"] == [["hexaghost",107,264,0]]
    modes = (("first_literal",fresh["official_replay"],33,False,fresh["model_actions"]),
             ("official_semantic",semantic,98,False,semantic["replayed_receipts"]),
             ("diagnostic",diagnostic,339,True,diagnostic["replayed"]))
    assert set(trace["evidence_modes"]) == {v[0] for v in modes}
    for name, ref, last, kernel, n in modes:
        mode=trace["evidence_modes"][name]
        assert mode["source_sha256"] == ref["sha256"] and mode["diagnostic_used"] is kernel
        assert mode["stop"] == (None if kernel else last) and mode["inputs_replayed"] == n
        records=[(r["index"],r["comparisons"][name]) for r in inputs if name in r["comparisons"]]
        assert [i for i,_ in records] == list(range(1,last+1))
        assert sum(row["status"]=="physical_action_replayed" for _,row in records) == n
        if not kernel:
            assert all(row.get("model_layer") not in {"kernel_diagnostic","typed_chest_diagnostic"} and not row.get("kernel_fallback") for _,row in records)
    assert mechanisms["public"]["sha256"] == semantic["sha256"]
    assert mechanisms["diagnostic"]["sha256"] == diagnostic["sha256"]
    assert len({ref["sha256"] for _,ref,_,_,_ in modes}) == 3
    assert inputs[97]["comparisons"]["official_semantic"]["physical_binding"]["reward"] == ["RELIC","inkbottle"]
    assert "InkBottle" in {name for name,_ in inputs[97]["original"]["relics"]}
    for key,group,expected_scopes in (("actual_shuffle","records",{"formal":4,"diagnostic":11}),
                                      ("ink_bottle","counter_wraps",{"diagnostic":14})):
        collection=mechanisms[key]
        assert len(collection[group])==collection["count"] and Counter(x["scope"] for x in collection[group]) == collection["by_scope"] == expected_scopes
        for item in collection[group]:
            linked=inputs[item["index"]-1]
            assert linked["before_sha256"]==item["original_before_hash"] and linked["after_sha256"]==item["original_after_hash"]
            assert item["scope"]==("formal" if item["index"]<98 else "diagnostic")
    boss=mechanisms["boss"]
    assert boss["range"]==[253,339] and boss["actions"]==87 and boss["by_scope"]=={"diagnostic":87}
    assert boss["last"]["original_after_hash"]==inputs[-1]["after_sha256"]
    assert not mechanisms["simultaneous_multi_enemy_damage"]["recorded_multi_hp_drops"]


def main():
    m=read("SHA256.json")
    for name,expected in m["files"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    frozen=read("runtime-freeze.json")
    for name,expected in frozen["components"].items():
        p=ROOT/"calibration_src/experiments/sa_calibration_round4"/name
        assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
    interface=read("interface.json")
    source=read("batch.json")
    assert source["signature"]==interface==read("neow.json")["interface"]==read("death.json")["interface"]==read("events.json")["signature"]
    assert (interface["observation_dimension"],interface["actions"])==(3122,193)
    seeds=rows("seeds.csv");assert len(seeds)==len({x["seed"] for x in seeds})==704
    total=Counter()
    for tag,group in source["summary"].items():
        subset=[x for x in seeds if x["cohort"]==tag]
        assert len(subset)==group["seeds"]
        assert Counter(x["R4"] for x in subset)==group["outcomes"]
        assert Counter(x["R3"]+"->"+x["R4"] for x in subset)==group["transitions"]
        assert sum(int(x["literal_complete"]) for x in subset)==group["complete_literal"]
        assert sum(int(x["unique_aligned_complete"]) for x in subset)==group["complete_after_unique_alignment"]
        total.update(group["transitions"])
    assert total["loss->unsupported"]==5 and total["unsupported->loss"]==4
    assert len(rows("groups.csv"))==23 and sum(int(r["局数"]) for r in rows("groups.csv"))==129
    assert read("neow.json")["affirmed_curse_ordered_pairs"]+read("neow.json")["previous_noncursed_ordered_pairs"]==1716
    assert read("death.json")["fixed_now_open"]==6 and read("state-readings.json")["paired_decisions"]==15
    fresh=read("fresh.json")
    verify_fresh_receipts(fresh,read("fresh-trace.json"),read("mechanisms.json"),interface)
    print(f'Validated {len(m["files"])} published sources and receipts, 704 seeds, and 339 original inputs.')
if __name__=="__main__":main()
