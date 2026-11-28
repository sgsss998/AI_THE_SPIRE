import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.CardLibrary;
import java.util.LinkedHashMap;
import com.megacrit.cardcrawl.random.Random;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Paths;
import sun.misc.Unsafe;

/** Original retail selection using its mixed live/source card pools and original per-floor RNG. */
public final class RetailTransform {
    public static void main(String[] args) throws Exception {
        Field field=Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        RetailBox.memory=(Unsafe)field.get(null);
        AbstractDungeon.commonCardPool=RetailBox.group();
        AbstractDungeon.srcUncommonCardPool=RetailBox.group();
        AbstractDungeon.srcRareCardPool=RetailBox.group();
        AbstractDungeon.srcColorlessCardPool=RetailBox.group();
        CardLibrary.cards=new LinkedHashMap<>();
        LinkedHashMap<String,AbstractCard> curses=new LinkedHashMap<>();
        RetailBox.set(CardLibrary.class,"curses",curses);
        for(String line:Files.readAllLines(Paths.get(args[0]))) {
            String[] part=line.split("\t");
            AbstractCard candidate=RetailBox.card(part[1]);
            CardLibrary.cards.put(part[1],candidate);
            if(part[0].equals("curse")) {curses.put(part[1],candidate);continue;}
            if(part[0].equals("colorless")) {AbstractDungeon.srcColorlessCardPool.group.add(candidate);continue;}
            CardGroup pool=part[0].equals("common")?AbstractDungeon.commonCardPool:
                    (part[0].equals("uncommon")?AbstractDungeon.srcUncommonCardPool:AbstractDungeon.srcRareCardPool);
            pool.group.add(candidate);
        }
        for(String line:Files.readAllLines(Paths.get(args[1]))) {
            String[] p=line.split("\t");
            long floorSeed=Long.parseUnsignedLong(p[0])+Integer.parseInt(p[1]);
            Random rng=new Random(floorSeed,Integer.parseInt(p[2]));
            if(rng.random.getState(0)!=Long.parseUnsignedLong(p[3]) || rng.random.getState(1)!=Long.parseUnsignedLong(p[4]))
                throw new IllegalStateException("Different per-floor RNG state at "+p[0]);
            AbstractCard original=RetailBox.card(p[5]);
            original.color=AbstractCard.CardColor.GREEN;
            AbstractCard result;
            String color=p.length>6?p[6]:"green";
            if(color.equals("colorless")) result=AbstractDungeon.returnTrulyRandomColorlessCardFromAvailable(original,rng);
            else if(color.equals("curse")) result=CardLibrary.getCurse(original,rng);
            else result=AbstractDungeon.returnTrulyRandomCardFromAvailable(original,rng);
            System.out.println("CARD\t"+p[0]+"\t"+result.cardID);
        }
    }
}
