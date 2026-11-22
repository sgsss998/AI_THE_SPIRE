"""Carry the immutable R5 branch register forward with per-sample R6 evidence."""
import argparse
from copy import deepcopy
from experiments.sa_calibration_round5.coverage.inventory import status_counts
from experiments.sa_calibration_round6.reference import HERE, R5, read, sha, write

CHECKED = "样本已核"
GAP = "有差异"
PENDING = "待验"


def apply_other_evidence(record, other, fresh, results):
    from experiments.sa_calibration_round3.fresh.replay import rows as journal_rows
    branched=results["branches/RESULT.json"]
    assert branched["original_actions"]==branched["matched_reward_masks"]==branched["stale_rejected"]==12
    assert {k:len(v["steps"]) for k,v in branched["branches"].items()}=={"potion":6,"skip":5,"leave":1}
    assert branched["map_control_gap"]==176 and not branched["heldout"]
    assert branched["freeze_sha256"]==sha(HERE/"FREEZE.json")
    official=read(HERE/"fresh/REPLAY.json")
    assert fresh["blank_start"] and fresh["original_completed_before_model"] and official["independent_holdout"]
    assert sha(HERE/"fresh/REPLAY.json")==fresh["replay_sha256"]
    assert sha(HERE/"fresh/ACTIONS.jsonl")==official["original_journal_sha256"]
    assert official["signature"]==results["INTERFACE.json"] and official["first_content"] is None
    assert official["substance_equal_frames"]==official["checked_frames"]==32
    assert official["completed_inputs"]==31 and official["stop"]["index"]==32
    assert fresh["original_inputs"]==120 and fresh["original_final"]["floor"]==6 and fresh["original_final"]["hp"]==0
    r=official["records"][-1]
    journal=journal_rows(HERE/"fresh/ACTIONS.jsonl")
    event,selected,confirm=journal[30:33]
    assert r["original_before"]==selected["before"]["raw_hash"] and r["actual_reported"]==[105,*range(110,124)]
    assert r["offered"]==[] and r["binding"]["face"]==["Strike_G",0] and r["binding"]["occurrence"]==0
    page=event["before"]["raw"]["game_state"]
    assert page["screen_state"]["event_id"]=="Living Wall" and page["choice_list"][event["aid"]-110]=="forget"
    orig=selected["before"]["raw"]["game_state"]
    g=orig["screen_state"]
    assert g["for_purge"] and not g["for_upgrade"] and not g["for_transform"] and len(g["cards"])==14
    assert [[i,[c["id"],c["upgrades"]]] for i,c in enumerate(g["cards"])]==r["binding"]["choices"]
    chosen=g["cards"][0]["uuid"]
    assert confirm["command"]=="confirm" and confirm["before"]["raw"]["game_state"]["screen_state"]["confirm_up"]
    deck0 = [c["uuid"] for c in orig["deck"]]
    deck1 = [c["uuid"] for c in confirm["after"]["raw"]["game_state"]["deck"]]
    assert len(deck0)==15 and len(deck1)==14 and deck1==[u for u in deck0 if u!=chosen]
    record("grid_other",PENDING,GAP,"R6 留空新局／第2层活墙选遗忘",
           "真机第31次选遗忘，正式S与原版可逐张读出相同的14个候选及次序，第32次选择第一张普通打击时，原版有14个选牌动作及丢药，模型给0个。原版第33次确认后永久牌组15→14，按实例核实第一张打击被移除。模型尚未到预览和确认，活墙变化/成长、星盘等其他来源仍待验。",
           "sa_calibration_round6/fresh/RESULT.json;sa_calibration_round6/fresh/REPLAY.json;sa_calibration_round6/fresh/ACTIONS.jsonl",
           原版动作证据="原版依次实按遗忘、首张打击、确认")
    evidence = "sa_calibration_round5/coverage/CURRENT.json;sa_calibration_round6/fresh/RESULT.json"
    fresh_mechanics=fresh["mechanics"]
    shuf=fresh_mechanics["shuffle"]
    targets=fresh_mechanics["targeted_in_multi_enemy_fight"]
    assert len(shuf["original_indices"])==8 and shuf["officially_replayed_indices"]==[14,23]
    assert targets["original_indices"]==targets["officially_replayed_indices"]==[6,9,13,15]
    record("shuffle",CHECKED,CHECKED,"历史样本＋R6 留空新局",
           "保留R2原版18次首抽与8次实例重洗记录。R6新局有8次由弃牌实例回到抽牌堆的洗牌迹象，前2次可经正式入口对照手牌和堆数，余6次在停点之后。",evidence)
    record("multi",CHECKED,CHECKED,"历史样本＋R6 留空新局",
           "保留R4多敌实战。R6新局第6、9、13、15次均在有多名活敌时对单个目标出牌，四次正式重放均执行。新局没有一次可观测的多敌同时掉血。",evidence)
    assert other["seed"]==9000033 and other["genuine_original"] and not other["unseen_random_holdout"]
    assert other["completed_inputs"]==other["original_inputs"]==21 and other["stop"] is None and other["first_content"] is None
    assert other["equal_frames"]==other["checked_frames"]==22
    reward_rows=other["records"][16:21]
    assert all(r["offered"]==r["actual_reported"] for r in reward_rows)
    assert all(r["before"]["original"]["relics"]==[["ringofthesnake",-1],["centennialpuzzle",-1]] for r in reward_rows)
    assert reward_rows[0]["after"]["original"]["resources"][2]==119 and reward_rows[3]["after"]["original"]["deck"][-1]==["Heel Hook",0]
    assert official["records"][27]["after"]["original"]["deck"][-1]==["Leg Sweep",0]
    record("loot",CHECKED,CHECKED,"历史样本＋R6 事先指定的异种子／留空新局",
           "种子9000033真机与正式入口从开局至首战领奖后回图共21步、22个检查点一致。蛇戒＋百年积木，拿20金、再生药，三张候选选第一张Heel Hook。R6留空新局首战仅持蛇戒，拿10金、爆炸药和扫腿。后者奖励用已有普通流程。",
           "sa_calibration_round5/coverage/CURRENT.json;sa_calibration_round6/cohort/INDEPENDENT.json;sa_calibration_round6/fresh/REPLAY.json")
    return dict(confirmed_removed_instance=chosen, native_grid_candidates=14, native_grid_actions=r["actual_reported"],
                model_grid_actions=r["offered"], native_after_confirm=14)


def build():
    baseline_file = R5 / "coverage/CURRENT.json"
    assert sha(baseline_file) == read(R5/"RELEASE.json")["files"]["coverage/CURRENT.json"]
    parent = read(baseline_file)
    files = {name: HERE/name for name in (
        "rewards/RESULT.json", "branches/RESULT.json", "cohort/R6.json", "cohort/INDEPENDENT.json",
        "regression/RESULT.json", "replay/RESULT.json", "fresh/RESULT.json", "INTERFACE.json")}
    results = {name:read(path) for name,path in files.items()}
    sig = results["INTERFACE.json"]
    replay = results["replay/RESULT.json"]
    reward = results["rewards/RESULT.json"]
    group = results["cohort/R6.json"]
    other = results["cohort/INDEPENDENT.json"]
    fresh = results["fresh/RESULT.json"]
    batch = results["regression/RESULT.json"]
    assert reward["interface"]==sha(files["INTERFACE.json"])
    assert sig==replay["signature"]==group["signature"]==batch["signature"]==other["signature"]
    assert batch["combined"]["seeds"]==len(batch["records"])==704 and batch["training_updates"]==0
    assert len(group["records"])==58 and group["opened"]==[9000033]
    assert len({r["seed"] for r in group["records"]})==58
    assert [s["index"] for s in reward["primary"]["steps"]]==list(range(129,134))
    assert replay["first_content"] is None and replay["stop"]["index"]==143 and not replay["used_kernel_fallback"]
    end=replay["records"][-1]
    assert end["offered"]==[] and end["actual_reported"]==[0,1,2,3,70,105,170] and end["binding"]["card"]==["Dodge and Roll",1]
    assert end["before"]["model"]["fungus_hp_spores_strength"]==end["before"]["original"]["fungus_hp_spores_strength"]==[[27,2,5],[0,2,5]]
    rows=deepcopy(parent["branches"])
    by_id={r["id"]:r for r in rows}
    changes=[]
    def record(key, s, a, scope, note, evidence, **fields):
        item=by_id[key]
        old=[item["S"],item["A"]]
        item.update(S=s,A=a, **fields)
        item["接口及范围"]=scope
        item["核对内容与未核范围"]=note
        item["证据路径（相对experiments）"]=evidence
        changes.append(dict(id=key,previous=old,current=[s,a],scope=scope,note=note))

    record("loot_floor10",CHECKED,CHECKED,"R6 正式／旧自然局、同源存档回放",
           "蛇戒＋墨水瓶。五次主线操作覆盖领20金、领再生药、看三张卡、拿后空翻、离开。分支另核先拿药，在选牌页弃药，拿飞膝，两次跳过重开与不拿奖励离开。第一张候选牌只审过身份，尚缺这条路线的实际领取。",
           "sa_calibration_round6/rewards/RESULT.json;sa_calibration_round6/branches/RESULT.json",
           原版动作证据="主线和三条同源存档分支实按")
    record("pdiscard",CHECKED,CHECKED,"历史样本＋R6 正式",
           "保留种子9000026和7000047的历史实按。R6旧自然局同源分支在三选一页实际丢弃第一格再生药，随后可拿飞膝。满槽且地上有药时先丢后拿仍缺对应回执。",
           "sa_calibration_round5/coverage/CURRENT.json;sa_calibration_round6/branches/RESULT.json")
    record("fungus_opts",CHECKED,GAP,"历史样本＋R6 正式旧自然局第143次操作前",
           "种子59留一只菌兽时缺丢药与结束回合。R6到第11层时两怪血量27、0，孢子/力量均2/5，玩家易伤2。该帧真机有7个动作，实际打出第4张升级闪躲翻滚。模型能识别这张牌，给出的动作数为0。保留两侧所查状态和模型的动作缺口。",
           "sa_calibration_round5/coverage/CURRENT.json;sa_calibration_round6/replay/RESULT.json",
           分支="一只菌兽已死时出非攻击牌、用药、丢药、结束回合",原版动作证据="该局实按闪躲翻滚+，其余操作仅在该局列出")
    record("corpse",GAP,"不适用","R4 底层／R6 正式到第143次操作前",
           "第143次操作前，死菌兽的2孢子、5力量仍同时存在于原版和模型。此前R4底层对照在该步之后看到原版清除、模拟仍残留。R6正式接口在这步出牌前停住，清除时机仍待正式复核。",
           "sa_calibration_round4/fresh/MECHANISMS.json;sa_calibration_round6/replay/RESULT.json")
    touches = [r["index"] for r in replay["records"] if "after" in r
               and ["inkbottle",9] in r["before"]["original"]["relics"] and ["inkbottle",0] in r["after"]["original"]["relics"]]
    assert touches==[111,126]
    record("inkcount",PENDING,"不适用","R6 正式旧局2/14",
           "该局14次第十张出牌触发中，第111、126次经正式入口与真机比较计数9→0和手牌。其余12次仍在第143次停点之后，保留待验。",
           "sa_calibration_round4/fresh/MECHANISMS.json;sa_calibration_round6/replay/RESULT.json")
    confirmed_grid=apply_other_evidence(record,other,fresh,results)
    open_ids=[r["id"] for r in rows if {r["S"],r["A"]} & {PENDING,GAP}]
    return dict(version="R6", previous=sha(baseline_file),references={name:sha(p) for name,p in files.items()},
                branch_count=len(rows),state=status_counts(rows,"S"),action=status_counts(rows,"A"),
                r5_open=parent["r5_open"],r6_open=len(open_ids),r6_open_ids=open_ids,changes=changes,branches=rows,
                fixed_policy_summary=batch["combined"],old_reward_stops=dict(restored=group["opened"],remaining=57),
                fresh_grid_deletion=confirmed_grid,
                scope="登记分支沿用R5，实按只认证记录中的对象和初态。旧路线、定向异种子与留空新局独立计数。完整静默A20的总体机制分母仍未建立。")


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    report=build()
    dest=HERE/"coverage/CURRENT.json"
    if args.check:
        assert report==read(dest)
    else:
        write(dest,report)
    print(report["state"], report["action"], report["r6_open"])
