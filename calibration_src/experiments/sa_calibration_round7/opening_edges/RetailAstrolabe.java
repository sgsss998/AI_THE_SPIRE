import com.megacrit.cardcrawl.cards.*;
import com.megacrit.cardcrawl.characters.TheSilent;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.CardLibrary;
import com.megacrit.cardcrawl.random.Random;
import com.megacrit.cardcrawl.relics.*;
import com.megacrit.cardcrawl.screens.select.GridCardSelectScreen;
import com.megacrit.cardcrawl.ui.buttons.DynamicBanner;
import com.megacrit.cardcrawl.unlock.UnlockTracker;
import java.nio.file.*;
import java.lang.reflect.Field;
import java.util.*;
import org.apache.logging.log4j.LogManager;
import sun.misc.Unsafe;

/** Executes retail onEquip and transformCard using original ordered pools, substituting only UI/card rendering. */
public class RetailAstrolabe {
    static class Banner extends DynamicBanner { public void hide(){} }
    static class Grid extends GridCardSelectScreen {
        public void open(CardGroup g,int n,String tip,boolean a,boolean b,boolean c,boolean d) {
            if(n!=3||a||b||c||d) throw new AssertionError("Unexpected Astrolabe controls");
            targetGroup=g;
        }
    }
    static class Face extends RetailBox.Face {
        public AbstractCard makeCopy(){return face(cardID);}
        public void upgrade(){upgraded=true;}
    }
    static Face face(String name){
        Face c=RetailBox.shell(Face.class);
        c.cardID=name;c.color=AbstractCard.CardColor.GREEN;c.type=AbstractCard.CardType.SKILL;c.isSeen=true;
        return c;
    }
    public static void main(String[] args) throws Exception {
        Field m=Unsafe.class.getDeclaredField("theUnsafe");m.setAccessible(true);RetailBox.memory=(Unsafe)m.get(null);
        CardLibrary.cards=new LinkedHashMap<>();
        RetailBox.set(UnlockTracker.class,"logger",LogManager.getLogger("R7"));
        AbstractDungeon.commonCardPool=RetailBox.group();
        AbstractDungeon.srcUncommonCardPool=RetailBox.group();
        AbstractDungeon.srcRareCardPool=RetailBox.group();
        for(String line:Files.readAllLines(Paths.get(args[0]))) {
            String[] p=line.split("\t");
            AbstractCard c=face(p[1]);CardLibrary.cards.put(c.cardID,c);
            CardGroup pool=p[0].equals("common")?AbstractDungeon.commonCardPool:
                p[0].equals("uncommon")?AbstractDungeon.srcUncommonCardPool:AbstractDungeon.srcRareCardPool;
            pool.group.add(c);
        }
        TheSilent player=RetailBox.shell(TheSilent.class);AbstractDungeon.player=player;
        AbstractDungeon.dynamicBanner=RetailBox.shell(Banner.class);
        Grid grid=RetailBox.shell(Grid.class);AbstractDungeon.gridSelectScreen=grid;
        Astrolabe relic=RetailBox.shell(Astrolabe.class);
        RetailBox.memory.putObject(relic,RetailBox.memory.objectFieldOffset(AbstractRelic.class.getDeclaredField("DESCRIPTIONS")),new String[]{"","choose"});
        for(String line:Files.readAllLines(Paths.get(args[1]))) {
            String[] p=line.split("\t");
            long seed=Long.parseUnsignedLong(p[0]);
            Random misc=new Random(seed);misc.random(1);
            player.masterDeck=RetailBox.group();
            for(int i=0;i<13;i++)player.masterDeck.group.add(face(i==0?"AscendersBane":i<6?"Strike_G":i<11?"Defend_G":i==11?"Survivor":"Neutralize"));
            relic.onEquip();
            if(grid.targetGroup.size()!=12)throw new AssertionError("Count");
            for(int i=0;i<12;i++)if(grid.targetGroup.group.get(i)!=player.masterDeck.group.get(1+i))throw new AssertionError("Physical occurrence");
            List<String> results=new ArrayList<>();
            for(int i=1;i<=3;i++) {
                AbstractCard from=grid.targetGroup.group.get(Integer.parseInt(p[i]));
                AbstractDungeon.transformCard(from,true,misc);
                AbstractCard card=AbstractDungeon.getTransformedCard();
                if(!card.upgraded)throw new AssertionError("Absent upgrade");
                results.add(card.cardID);
            }
            System.out.println("CARDS\t"+p[0]+"\t"+String.join(",",results)+"\t"+Long.toUnsignedString(misc.random.getState(0))+"\t"+Long.toUnsignedString(misc.random.getState(1)));
        }
    }
}
