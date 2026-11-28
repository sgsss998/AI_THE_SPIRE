"""Check old frontier seeds against original RNG, relic pools, HP rules and real timing receipts."""
import argparse
from importlib import import_module
from pathlib import Path
import subprocess

from experiments.common_relic193 import pools
from experiments.neow_rules_patch.verify import amounts, run_bytecode
from experiments.neow_transform_two193.random_audit import java_rng, load_pools
from experiments.ordinary_reward_hooks193.audit import dump
from experiments.remaining_neow193.rules import trace_reference
from experiments.sa_calibration_round6.reference import read, sha, write
from experiments.sa_calibration_round6.rewards.verify import step, view
from experiments.sa_calibration_round7.triage import rows, RUNS
from silent_env.runtime import StaleFrameError
from . import candidate
from .session import RELICS, settled

HERE = Path(__file__).resolve().parent


def oracle(seeds):
    recovered = [pools.read_save(n) for n in pools.SAVES]
    rolls = pools.permutations(sorted(set(seeds) | {seed for seed, _, _ in recovered}))
    canonical = None
    for seed, shuffled, _ in recovered:
        order = [v for _,v in sorted(zip(rolls[seed][2],shuffled[2],strict=True))]
        assert canonical is None or canonical == order
        canonical = order
    native,regular = load_pools()
    rng = java_rng()
    by_seed = {}
    for seed in seeds:
        rnd = subprocess.check_output([*rng,str(seed),"5","0",str(len(regular)),str(len(native["curse"]))],text=True)
        index = int(rnd.strip().split(",")[-1])
        by_seed[seed] = {"curse": native["curse"][index], "rare_relic": canonical[rolls[seed][2][0]]}
    return by_seed, [receipt for _,_,receipt in recovered]


def class_rules():
    classes = dump(tuple("relics."+cl for cl,_ in RELICS.values()))
    ids = {}
    for name,(cl,encoded) in RELICS.items():
        m = classes["relics."+cl]
        init = m["<init>()V"]
        rid, = [line[7:] for line in init if line.startswith("1: LDC ")]
        assert any("RelicTier.RARE:" in line for line in init)
        counter = [i for i,line in enumerate(init) if ".counter:I" in line]
        if encoded:
            i, = counter
            assert init[i-1].endswith("ICONST_"+str(encoded-1))
        else:
            assert not counter
        if name == "OLD_COIN":
            on=m["onEquip()V"]
            assert len(on)==8 and on[-3].endswith("SIPUSH 300") and on[-2].endswith("AbstractPlayer.gainGold(I)V")
        else:
            assert "onEquip()V" not in m
        ids[name] = rid
    return ids


def case(runtime, seed, actions, prediction, relics):
    e=runtime.make_engine()
    s=runtime.make_session(e)
    f=s.reset(seed)
    for a in actions:
        before=f
        f=step(s,f,a)
    assert before.page == "NEOW_OFFERS"
    slot=actions[-1]-110
    gift,cost=map(int,before.state.vector[323+6*slot:325+6*slot])
    out=dict(seed=seed, gift=gift, cost=cost, action=actions[-1], page=f.page)
    if f.page == "NEOW_RESULT_UNVERIFIED":
        assert gift == 19 and cost == 7 and not any(f.supported_actions)
        out["remaining"] = "Pandora's Box confirmation grid"
        return out
    assert f.page == "NEOW_RESULT" and view.allowed(f)==[110] and f.supported_actions==f.policy_mask
    shown = view.model(f,e)
    hp,maxhp,wallet=amounts(59,66,gift,cost)
    if gift == 14:
        name=e._source._backend.RELIC_NAMES[int(f.state.vector[34])-1]
        # Backend labels are display names, so identify by stable wire mapping.
        from experiments.common_relic193.rules import relic_id
        key, = [k for k in relics if relic_id(k)==f.state.vector[34]]
        assert prediction["rare_relic"] == relics[key], (seed,prediction,key,name)
        out["retail_relic"] = relics[key]
        wallet += 300 if key == "OLD_COIN" else 0
    if cost == 5:
        assert shown["deck"][-1] == [prediction["curse"],0] and len(shown["deck"]) == 14
        out["retail_curse"] = prediction["curse"]
    else:
        assert len(shown["deck"]) == 13
    assert shown["resources"][:3] == [hp,maxhp,wallet]
    final=step(s,f,110)
    try:
        s.step(110,frame_id=f.frame_id,action_version=f.action_version)
    except StaleFrameError:
        pass
    else:
        raise AssertionError("Old Neow leave frame accepted a second time")
    mapped=view.model(final,e)
    for k in ("resources","deck","potions","relics"):
        assert shown[k] == mapped[k], (seed,k)
    assert final.state.vector[6] == 5 and final.engine_steps == f.engine_steps == 1
    out.update(resources=[hp,maxhp,wallet],deck_size=len(shown["deck"]),map_columns=mapped["next_x"],duplicate_rejected=True)
    # A silent extra coin or a duplicated deck count must invalidate this exact settlement.
    old = before.state.vector[:3118]
    values = list(e._source._current.state.vector)
    assert settled(old, tuple(values), e._source._backend.CARD_IDS) is not None
    for offset in (2,22):
        broken = values.copy()
        broken[offset] += 1
        assert settled(old,tuple(broken),e._source._backend.CARD_IDS) is None
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime",default=candidate.__name__)
    parser.add_argument("--output",type=Path,default=HERE/"RESULT.json")
    args=parser.parse_args()
    runtime=import_module(args.runtime)
    baseline=[r for _,r in rows(RUNS/"pilot-r6") if r["page"]=="NEOW_RESULT_UNVERIFIED"]
    assert len(baseline)==21
    predictions,saves=oracle([r["seed"] for r in baseline])
    relics=class_rules()
    checked=[case(runtime,r["seed"],r["actions"],predictions[r["seed"]],relics) for r in baseline]
    original=trace_reference()
    timing=read(HERE.parents[1]/"neow_reward_640/PAIRED.json")
    data=dict(source={p.name:sha(p) for p in HERE.glob("*.py")}, runtime=args.runtime, original_classes=run_bytecode(),
              original_jar_sha256=sha(pools.JAR), rare_pool_saves=saves, real_leave_reference=original,
              curse_settlement_reference={"file":"experiments/neow_reward_640/PAIRED.json",
                                         "sha256":sha(HERE.parents[1]/"neow_reward_640/PAIRED.json"),"keys":list(timing)},
              repaired=sum(r["page"]=="NEOW_RESULT" for r in checked), remaining=sum("remaining" in r for r in checked),
              same_seed_graphical_runs=0, target_validation="original shipped RNG, recovered original pools and retail bytecode",
              cases=checked)
    assert data["repaired"]==18 and data["remaining"]==3
    write(args.output,data)
    print(data["repaired"],data["remaining"])


if __name__ == "__main__":
    main()
