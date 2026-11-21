"""Natural original/simulator pairs and original-JAR rules for the Split icon."""
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
from hashlib import sha256
import json
from experiments.sa_calibration_round2.diagnostic_slime import continue_route
from experiments.sa_calibration_round2.frontiers.session import _local_dependencies
from experiments.ordinary_reward_hooks193.audit import dump,JAR,RETAIL
from .cohort import HERE,ROOT,digest
from .split import split_markers

def main():
    cases={};unknown={}
    def observe(packet,raw,e):
        effect=continue_route.comparison(packet,raw,e)
        game=packet['raw']['game_state'];c=game.get('combat_state')
        if not c or not raw.state.vector[7]:return effect
        row=split_markers(raw.state.vector)
        for j,m in enumerate(c['monsters']):
            if j>=5:continue
            flag=[p['amount'] for p in m['powers'] if p['id']=='Split']
            key=(int(packet['sequence']),j)
            if row[j] is None:
                unknown[key]=dict(sequence=key[0],slot=j,id=m['id'],hp=m['current_hp'],raw_power=flag)
                continue
            assert row[j]==bool(flag) and (not flag or flag==[-1]),(key,m['id'],flag,row[j])
            cases[key]=dict(sequence=key[0],slot=j,id=m['id'],present=row[j],hp=m['current_hp'])
        return effect
    record=_local_dependencies(continue_route.run,comparison=observe)()
    assert record['final_kernel']['done'] and len(cases)>0
    names=('monsters.exordium.SlimeBoss','monsters.exordium.AcidSlime_L','monsters.exordium.SpikeSlime_L','powers.SplitPower')
    classes=dump(names);proof={}
    assert digest(JAR)==RETAIL
    with ZipFile(JAR) as jar:
        for name in names:
            methods=classes[name];binary='com/megacrit/cardcrawl/'+name.replace('.','/')+'.class'
            proof[name]=dict(sha256=sha256(jar.read(binary)).hexdigest())
            if name.startswith('monsters'):
                found={k:[line for line in v if 'SplitPower' in line or ('ArrayList.add' in line)] for k,v in methods.items() if k.startswith('<init>') and any('NEW com.megacrit.cardcrawl.powers.SplitPower' in s for s in v)}
                assert found and all(any('ArrayList.add' in l for l in lines) for lines in found.values());proof[name]['constructors']=found
            else:
                code=next(v for k,v in methods.items() if k.startswith('<init>'))
                assert any('ICONST_M1' in z for z in code);proof[name]['constructor']=code
    source=ROOT/'vendor/sts_lightspeed/src/combat/Monster.cpp'
    code=source.read_text().split('void Monster::onHpLost',1)[1].split('case MonsterId::THE_GUARDIAN',1)[0]
    assert 'curHp <= maxHp/2' in code and all(f'MMID::{n}_SPLIT' in code for n in ('SLIME_BOSS','ACID_SLIME_L','SPIKE_SLIME_L'))
    out=dict(seed=continue_route.probe.SEED,archive=digest(continue_route.probe.ARCHIVE/'raw.jsonl'),jar_sha256=RETAIL,
             original_class_proof=proof,cpp_half_hp_trigger=dict(sha256=digest(source),section=code),
             compared_unique_frame_slots=len(cases),counts=dict(Counter(x['id'] for x in cases.values() if x['present'])),unrepresented=len(unknown),
             samples=list(cases.values()),unknown_slots=list(unknown.values()),new_observation_width=0)
    (HERE/'SPLIT.json').write_text(json.dumps(out,indent=2)+'\n')
    print(out['compared_unique_frame_slots'],out['counts'],out['unrepresented'])
if __name__=='__main__':main()
