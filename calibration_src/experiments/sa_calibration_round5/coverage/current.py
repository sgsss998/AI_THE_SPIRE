"""Apply only explicitly paired fifth-round changes to the immutable baseline claims."""
import argparse
from pathlib import Path
import json
from .inventory import HERE, read, sha, status_counts


def build():
    base=read(HERE/"BASELINE.json")
    parent=HERE.parent
    files={topic:parent/topic/"RESULT.json" for topic in ("chest","shop","wheel","replay","regression")}
    data={key:read(path) for key,path in files.items()}
    replay=data["replay"]
    assert replay["signature"]==data["regression"]["signature"]==data["chest"]["release"]==data["shop"]["formal_interface"]
    buys=data["shop"]["branches"]
    assert set(buys)=={"mirror","flex","fear","weak"}
    for tag,cost in (("mirror",172),("flex",56),("fear",55),("weak",57)):
        sale=buys[tag]["items"][0]
        assert sale["before"]["gold"]==229 and sale["after"]["gold"]==229-cost
    assert buys["mirror"]["items"][1]["label"]=="copy_second_strike"
    rejected=buys["flex"]["full_slots"]
    assert rejected["after_original_gold"]==118 and not rejected["model_sale_supported"]
    assert rejected["original_game_message"]=="NOT ENOUGH POTION SLOTS"
    counts=[buys["mirror"]["items"][0]["before"],buys["flex"]["items"][-1]["after"],buys["mirror"]["items"][-1]["after"]]
    assert [(r["original_affordable"],r["model_affordable"]) for r in counts]==[(12,12),(8,8),(0,0)]
    rows={r["index"]:r for r in replay["records"]}
    assert not replay["independent_holdout"] and not replay["used_kernel_fallback"]
    assert replay["first_content"]["index"]==128 and replay["stop"]["index"]==129
    assert rows[98]["after"]["model"]["relics"]==rows[98]["after"]["original"]["relics"]
    assert rows[98]["after"]["model"]["relics"][-1]==["inkbottle",0]
    assert rows[98]["after"]["model"]["keys"]==[False]*3 and rows[98]["after"]["model"]["rewards"]==[]
    assert rows[51]["offered"]==rows[51]["actual_reported"]
    assert [(r["input"],r["after_hp"]) for r in data["wheel"]["receipts"]]==[(45,65),(46,65),(47,66),(48,66)]
    control=data["chest"]["branches"]
    assert set(control)=={"ink","key","leave"} and control["key"]["passive_key"]["additional_inputs"]==0
    assert control["key"]["passive_key"]["keys"]["sapphire"] and any(not a["immediate_keys_equal"] for a in control["key"]["actions"])
    waited=data["chest"]["blue_key_wait"]["elapsed_from_first_receipt"]
    assert not waited[0]["sapphire"] and waited[1]["sapphire"] and 0.36<waited[1]["elapsed"]<0.38
    assert rows[128]["after"]["original"]["rewards"]==[["GOLD",20],["POTION","regenpotion"],["CARD",None]]
    assert rows[128]["after"]["model"]["rewards"]==rows[129]["offered"]==[]
    for i in (111,126):
        for phase,count in (("before",9),("after",0)):
            for side in ("model","original"):
                assert ["inkbottle",count] in rows[i][phase][side]["relics"]
                assert "hand" not in rows[i][phase]["differences"]
    records={r["id"]:dict(r) for r in base["branches"]}
    changes=[]
    def update(id_,s,a,scope,note,evidence):
        item=records[id_]
        previous=[item["S"],item["A"]]
        item.update({"S":s,"A":a,"接口及范围":scope,"原版动作证据":"实按","核对内容与未核范围":note,"证据路径（相对experiments）":evidence})
        changes.append({"id":id_,"from":previous,"to":[s,a],"note":note})
    formal="R5 正式"
    checked="样本已核"
    update("ink",checked,checked,formal,"蓝钥匙、墨水瓶、离开均有独立原版分支；取钱后实领墨水瓶，计数0，钥匙未得，关联行一起消失。先领遗物再取钱为模拟扩展。","sa_calibration_round5/chest/RESULT.json;sa_calibration_round5/replay/RESULT.json")
    update("wheel",checked,checked,formal,"原版和模型第46次均维持65血，第47次才到66。仅验这次治疗结果，其他奖项另需样本。","sa_calibration_round5/wheel/RESULT.json")
    update("shopmirror",checked,checked,formal,"从本层同一原版货架实际买镜，复制第二张打击，核对实扣金与复制实例。其他遗物和其他复制对象不由此覆盖。","sa_calibration_round5/shop/RESULT.json")
    update("shoppot",checked,checked,formal,"同一货架分别实买三种药水。另实测买两瓶后118金、两槽已满，点第三瓶被拒绝，查询和离店后钱与药均保持；模型屏蔽该次无效点击。初始、满槽、只剩1金时，S中的可成交选项数分别为12、8、0，均与本次真机实物资格一致。其他价格与遗物组合仍待验。","sa_calibration_round5/shop/RESULT.json")
    update("inkcount","待验","不适用","R5 正式已达2/14，余12为R4诊断","第111、126次正式/原版计数均9→0，所查手牌一致。其余12次尚在R5首个停点之后；保留整条为待验。","sa_calibration_round5/replay/RESULT.json;sa_calibration_round4/fresh/MECHANISMS.json")
    def add(id_,scene,branch,s,a,note,evidence):
        records[id_]={"id":id_,"场景":scene,"分支":branch,"S":s,"A":a,"接口及范围":formal,"原版动作证据":"实按","核对内容与未核范围":note,"证据路径（相对experiments）":evidence}
        changes.append({"id":id_,"from":None,"to":[s,a],"note":note})
    add("chest_key_timing","宝箱","拿蓝钥匙直至原版自动刷新持有位","有差异",checked,"快速离开时真机回地图后无输入才刷新，另一慢路径在奖励页首次查询已为真。正式模型即时置真；关联行移除与最终持有一致。","sa_calibration_round5/chest/RESULT.json")
    add("loot_floor10","普通战利品","本次第10层战后20金/再生药水/卡包","有差异","有差异","第128步动作后，真机显示三行、模型空白；第129步真机取20金，模型没有动作。未选的再生药与卡包另需实按。","sa_calibration_round5/replay/RESULT.json")
    values=list(records.values())
    outstanding=[r["id"] for r in values if {r["S"],r["A"]} & {"待验","有差异"}]
    return {"version":"R5","r4_baseline_sha256":sha(HERE/"BASELINE.json"),"references":{k:sha(v) for k,v in files.items()},
            "branch_count":len(values),"state":status_counts(values,"S"),"action":status_counts(values,"A"),
            "r4_open":base["branches_with_known_gap_or_pending"],"r5_open":len(outstanding),"r5_open_ids":outstanding,
            "scope":"沿用其他分支的历史取证范围。样本已核仅指所列实际对象与结果。修过的旧种子计开发回放，未作独立新盲测。",
            "changes":changes,"branches":values}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    report=build()
    p=HERE/"CURRENT.json"
    if args.check:assert read(p)==report
    else:p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("R4 outstanding",report["r4_open"],"R5",report["r5_open"],"of",report["branch_count"])
