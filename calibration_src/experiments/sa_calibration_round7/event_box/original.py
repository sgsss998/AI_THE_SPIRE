"""Check callback timing and each supported pickup's observable effect in the pinned original."""
from pathlib import Path
from experiments.ordinary_reward_hooks193.audit import dump,JAR,RETAIL
from experiments.sa_calibration_round6.reference import sha,write

HERE=Path(__file__).resolve().parent


def main():
    assert sha(JAR)==RETAIL
    classes=('events.exordium.BigFish','vfx.cardManip.ShowCardAndObtainEffect','rooms.AbstractRoom','relics.AbstractRelic',
             'relics.CeramicFish','relics.DarkstonePeriapt','relics.MoltenEgg2','relics.ToxicEgg2','relics.FrozenEgg2',
             'relics.Courier','relics.DuVuDoll','relics.Sundial','relics.PotionBelt')
    tables=dump(classes)
    facts={}
    def check(cls,method,need):
        lines=tables[cls][method]
        start=0
        found=[]
        for token in need:
            while token not in lines[start]:
                start+=1
            found.append(lines[start])
            start+=1
        facts[cls+'#'+method]=found
    check(classes[0],'buttonEffect(I)V',['.Regret.<init>','.ShowCardAndObtainEffect.<init>','ArrayList.add','.spawnRelicAndObtain'])
    check(classes[1],'<init>(Lcom/megacrit/cardcrawl/cards/AbstractCard;FFZ)V',['LDC Omamori','.hasRelic','.counter:I','.isDone:Z'])
    check(classes[2],'spawnRelicAndObtain(FFLcom/megacrit/cardcrawl/relics/AbstractRelic;)V',['.AbstractRelic.obtain()V'])
    check(classes[3],'obtain()V',['.AbstractPlayer.relics:','.ArrayList.size','.AbstractPlayer.relics:','.ArrayList.add'])
    check(classes[1],'update()V',['.duration:F','.AbstractPlayer.relics:','.onObtainCard','.onMasterDeckChange'])
    signature='onObtainCard(Lcom/megacrit/cardcrawl/cards/AbstractCard;)V'
    check(classes[4],signature,['BIPUSH 9','.gainGold'])
    check(classes[5],signature,['CardColor.CURSE','BIPUSH 6','.increaseMaxHp'])
    for name,kind in zip(classes[6:9],('ATTACK','SKILL','POWER'),strict=True):
        check(name,signature,['CardType.'+kind,'.canUpgrade','.upgrade('])
        check(name,'onEquip()V',['combatRewardScreen','.rewards:'])
    assert not any(k.startswith(('onEquip(','onObtainCard(','onMasterDeckChange(')) for k in tables[classes[9]])
    for method in ('onEquip()V','onMasterDeckChange()V'):
        check(classes[10],method,['ICONST_0','.counter:I','.masterDeck:','CardType.CURSE','IADD','.counter:I'])
    check(classes[11],'onEquip()V',['ICONST_0','.counter:I'])
    check(classes[12],'onEquip()V',['.potionSlots:I','ICONST_2','IADD','.potionSlots:I','.PotionSlot.<init>','.ArrayList.add','.PotionSlot.<init>','.ArrayList.add'])
    write(HERE/'ORIGINAL.json',dict(original_jar=RETAIL,methods=facts))


if __name__=='__main__':
    main()
