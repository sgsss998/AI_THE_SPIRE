from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
R4=HERE.parent
EX=R4.parent
PARENT=EX/"sa_calibration_round3"
def read(p): return json.loads(p.read_bytes())
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
GRID={"BONFIRE_SPIRITS":"篝火精灵献祭","LIVING_WALL":"活墙","NEOW_SWAP_ASTROLABE":"涅奥换星盘","OMINOUS_FORGE":"不祥熔炉","PURIFIER":"净化神龛","REST":"营火","THE_CLERIC":"牧师","TRANSMORGRIFIER":"变化神龛","UPGRADE_SHRINE":"升级神龛","WHEEL_OF_CHANGE":"转盘"}
TASK={"transform":"变化一张","remove":"移除一张","upgrade":"升级一张","transform_and_upgrade":"变化并升级三张","bonfire_offering":"献一张牌"}
REWARD={"ELITE":"精英战后","MONSTER":"普通战后","LAB":"实验室","THE_WOMAN_IN_BLUE":"蓝衣女子","NEOW_SWAP_CALLING_BELL":"涅奥换召唤铃铛","NEOW_SWAP_TINY_HOUSE":"涅奥换小屋","TREASURE":"宝箱"}
KIND={"CARD":"牌","GOLD":"金币","POTION":"药水","RELIC":"遗物","KEY":"钥匙","SKIP":"跳过"}
def context(key):
    parts=key.split("/")
    if parts[0]=="grid":
        src,task=parts[1:3]
        label=GRID[src]+" · "+TASK[task]
        if src=="UPGRADE_SHRINE":
            return label,"种子42实测同名牌升级；本批牌组需逐例匹配","permanent_grid193/RETAIL_PAIR.json","目标位置、预览及确认后唯一变化"
        if src=="REST":
            return label,"第二轮营火升级实测片段","sa_calibration_round2/frontiers/FROZEN.json","携带遗物、牌组与本种子的合法候选和确认结果"
        if src=="THE_CLERIC":
            return label,"已有牧师报价、离开或治疗样本，不能替代这次付费删牌","grid_sources193/REPORT.md","扣费时点及被删同名实例"
        return label,"已有同机制研究，尚待这些停点的直接原版操作","grid_frontier_640/RESULT.json","当前来源、候选位置、所选实例和结算"
    label=REWARD[parts[1]]+" · "+"、".join(KIND[x] for x in parts[2].split("+"))
    if parts[1]=="MONSTER":
        return label,"已有种子35/36真机击杀、金币领取和离开样本","ordinary_reward_live193/RESULT.json","本局实际奖励与可领行；取走后重排、离开"
    if parts[1]=="TREASURE":
        return label,"已核两种宝箱原版领取遗物或钥匙的互斥","treasure_reward_640/ORIGINAL.json","本种子的钥匙、遗物和金币到达时点"
    return label,"本表只据独立重放定位，本组原版领取仍须绑定","", "核对来源、领取顺序及库存，实按后查下一决策"
def main():
    stops=read(HERE/"STOPS.json")
    with (HERE/"GROUPS.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        wr=csv.writer(stream,lineterminator="\n")
        wr.writerow(("停点类型","玩家操作与同屏选择","局数","代表种子","全部种子","已有证据及边界","源文件（相对 experiments）","下次需取得的证据"))
        for key,seeds in sorted(stops["groups"].items(),key=lambda x:(x[0].split("/")[0],-len(x[1]),x[0])):
            label,proof,path,gap=context(key)
            if path: assert (EX/path).is_file()
            wr.writerow(("选牌" if key.startswith("grid") else "奖励",label,len(seeds),seeds[0]," ".join(map(str,seeds)),proof,path,gap))
    batch=read(PARENT/"regression/RESULT.json")
    old=read(PARENT/"death/COHORT.json")["actual_replays"]
    fixes=read(PARENT/"fresh/RESULT.json")
    baseline={"public_commit":"e24f78449d883fbf74d6c2e41a4b2cc6cf4a5e50","source_sha256":{n:digest(PARENT/n) for n in ["RELEASE.json","INTERFACE.json","regression/RESULT.json","coverage/RESULT.json","death/COHORT.json","fresh/RESULT.json"]},
              "parent_release_files":len(read(PARENT/"RELEASE.json")["files"]), "interface":read(PARENT/"INTERFACE.json"),
              "free_policy":{k:v["outcomes"] for k,v in batch["summary"].items()},
              "batch_seed_count":{k:v["seeds"] for k,v in batch["summary"].items()},
              "fungi":{str(e["seed"]):{"cohort":e["cohort"],"floor":e["floor"],"lethal_action":e["lethal_action"],"old_followups":e["new_actions"],"trace":e["trace_sha256"]} for e in old},
              "holdout_reclassified_as_development":fixes["seed"]["display"],"known_missing_opening_action":112,
              "old_snake_reward_difference":52, "taxonomy":{"seeds":129,"groups":len(stops["groups"]),"trace_index_sha256":digest(HERE/"STOPS.json"),"csv_sha256":digest(HERE/"GROUPS.csv")}}
    save(R4/"BASELINE.json",baseline)
if __name__=="__main__":main()
