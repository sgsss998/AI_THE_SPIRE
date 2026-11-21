"""Archive relevant original methods and compare the actual compiled-simulator source branch."""
from hashlib import sha256
import json
from zipfile import ZipFile
from experiments.ordinary_reward_hooks193.audit import dump,JAR,RETAIL
from .cohort import HERE,ROOT,digest

def main():
    names=('powers.SporeCloudPower','monsters.exordium.FungiBeast','monsters.AbstractMonster','cards.green.DaggerSpray','cards.green.Strike_Green')
    assert digest(JAR)==RETAIL;classes=dump(names)
    signatures=('onDeath()V','usePreBattleAction()V','updateDeathAnimation()V','use(','use(')
    result={}
    with ZipFile(JAR) as z:
        for name,sig in zip(names,signatures):
            code=next(v for k,v in classes[name].items() if k.startswith(sig))
            result[name]=dict(method=sig,sha256=sha256(z.read('com/megacrit/cardcrawl/'+name.replace('.','/')+'.class')).hexdigest(),instructions=code)
    def index(i,part):return next(j for j,l in enumerate(result[names[i]]['instructions']) if part in l)
    assert index(0,'NEW com.megacrit.cardcrawl.powers.VulnerablePower') < index(0,'addToTop')
    assert index(1,'ICONST_2') < index(1,'SporeCloudPower.<init>')
    assert index(2,'powers:Ljava/util/ArrayList;') < index(2,'java.util.ArrayList.clear')
    cpp=ROOT/'vendor/sts_lightspeed/src/combat/Monster.cpp';code=cpp.read_text().split('if (hasStatus<MS::SPORE_CLOUD>())',1)[1].split('else if',1)[0]
    assert 'DebuffPlayer<PS::VULNERABLE>(2' in code
    (HERE/'RULES.json').write_text(json.dumps(dict(jar=RETAIL,methods=result,cpp=dict(file=str(cpp.relative_to(ROOT)),sha256=digest(cpp),spore_branch=code)),indent=2)+'\n')
if __name__=='__main__':main()
