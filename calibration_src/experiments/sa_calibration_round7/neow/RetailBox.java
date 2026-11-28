import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.cards.green.Strike_Green;
import com.megacrit.cardcrawl.characters.TheSilent;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.CardLibrary;
import com.megacrit.cardcrawl.random.Random;
import com.megacrit.cardcrawl.relics.AbstractRelic;
import com.megacrit.cardcrawl.relics.PandorasBox;
import com.megacrit.cardcrawl.screens.select.GridCardSelectScreen;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import org.apache.logging.log4j.LogManager;
import sun.misc.Unsafe;

/** Run the original onEquip, card draw, and insertion order. Capture its UI call without opening a window. */
public final class RetailBox {
    static Unsafe memory;
    static <T> T shell(Class<T> type) {
        try { return type.cast(memory.allocateInstance(type)); }
        catch (InstantiationException e) { throw new RuntimeException(e); }
    }
    static class Face extends Strike_Green {
        public AbstractCard makeCopy() { return card(cardID); }
    }
    static Face card(String name) {
        Face f=shell(Face.class);
        f.cardID=name;
        f.tags=new ArrayList<>();
        f.isSeen=true;
        return f;
    }
    static class Output extends GridCardSelectScreen {
        public void openConfirmationGrid(CardGroup group,String text) { targetGroup=group; }
    }
    static void set(Class<?> cls,String name,Object value) throws Exception {
        Field f=cls.getDeclaredField(name);
        memory.putObject(memory.staticFieldBase(f),memory.staticFieldOffset(f),value);
    }
    static CardGroup group() { return new CardGroup(CardGroup.CardGroupType.UNSPECIFIED); }
    static List<String> ids(CardGroup cards) {
        List<String> names=new ArrayList<>();
        for(AbstractCard card:cards.group) names.add(card.cardID);
        return names;
    }
    public static void main(String[] args) throws Exception {
        Field f=Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);memory=(Unsafe)f.get(null);
        CardLibrary.cards=new HashMap<>();
        set(com.megacrit.cardcrawl.unlock.UnlockTracker.class, "logger", LogManager.getLogger("R7"));
        AbstractDungeon.srcCommonCardPool=group();
        AbstractDungeon.srcUncommonCardPool=group();
        AbstractDungeon.srcRareCardPool=group();
        for(String line:Files.readAllLines(Paths.get(args[0]))) {
            String[] p=line.split("\t");
            Face proto=card(p[1]); CardLibrary.cards.put(p[1],proto);
            CardGroup dst=p[0].equals("common")?AbstractDungeon.srcCommonCardPool:
                    (p[0].equals("uncommon")?AbstractDungeon.srcUncommonCardPool:AbstractDungeon.srcRareCardPool);
            // The retained oracle records the live common pool, but the source pool for the other tiers.
            // initializeCardPools builds srcCommonCardPool by calling addToBottom on the live order.
            if(p[0].equals("common")) dst.addToBottom(proto); else dst.group.add(proto);
        }
        for(int i=1; i<args.length; i++) {
            long seed=Long.parseLong(args[i]);
            TheSilent player=shell(TheSilent.class);
            player.masterDeck=group(); player.relics=new ArrayList<AbstractRelic>();
            AbstractDungeon.player=player; AbstractDungeon.cardRandomRng=new Random(seed);
            player.masterDeck.group.add(card("AscendersBane"));
            for(int j=0;j<10;j++) {
                boolean attack=j<5; Face starter=card(attack?"Strike_G":"Defend_G");
                starter.tags.add(attack?AbstractCard.CardTags.STARTER_STRIKE:AbstractCard.CardTags.STARTER_DEFEND);
                player.masterDeck.group.add(starter);
            }
            player.masterDeck.group.add(card("Survivor"));player.masterDeck.group.add(card("Neutralize"));
            Output grid=shell(Output.class);AbstractDungeon.gridSelectScreen=grid;
            PandorasBox box=shell(PandorasBox.class);
            memory.putObject(box, memory.objectFieldOffset(AbstractRelic.class.getDeclaredField("DESCRIPTIONS")),new String[]{"","confirm"});
            box.onEquip();
            System.out.println("BOX\t"+seed+"\t"+String.join(",",ids(player.masterDeck))+"\t"+String.join(",",ids(grid.targetGroup)));
        }
    }
}
