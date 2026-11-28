import com.megacrit.cardcrawl.audio.SoundMaster;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.cards.green.Strike_Green;
import com.megacrit.cardcrawl.characters.TheSilent;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.screens.select.HandCardSelectScreen;
import com.megacrit.cardcrawl.ui.buttons.CardSelectConfirmButton;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import sun.misc.Unsafe;

/** Execute retail's selection method without creating a window or playing audio. */
public final class RetailSwap {
    static Unsafe memory;
    static class Quiet extends SoundMaster {
        public long play(String name) { return 0L; }
    }
    static class Hand extends CardGroup {
        Hand() { super(CardGroupType.HAND); }
        public void refreshHandLayout() {}
    }
    static class Button extends CardSelectConfirmButton {
        public void enable() {}
        public void disable() {}
        Button() { super(); }
    }
    static <T> T empty(Class<T> type) throws Exception {
        return type.cast(memory.allocateInstance(type));
    }
    static void set(Object target, Class<?> type, String name, Object value) throws Exception {
        Field field=type.getDeclaredField(name);
        field.setAccessible(true);
        field.set(target,value);
    }
    public static void main(String[] args) throws Exception {
        Field field=Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        memory=(Unsafe)field.get(null);
        AbstractDungeon.player=empty(TheSilent.class);
        CardCrawlGame.sound=empty(Quiet.class);
        Method click=HandCardSelectScreen.class.getDeclaredMethod("selectHoveredCard");
        click.setAccessible(true);
        // Probe every legal new slot and retain identity even for indistinguishable card faces.
        for (int length=2;length<=10;length++) for(int target=0;target<length-1;target++) {
            HandCardSelectScreen screen=empty(HandCardSelectScreen.class);
            Hand hand=new Hand();
            AbstractDungeon.player.hand=hand;
            set(screen,HandCardSelectScreen.class,"hand",hand);
            set(screen,HandCardSelectScreen.class,"button",empty(Button.class));
            screen.numCardsToSelect=1;
            screen.selectedCards=new CardGroup(CardGroup.CardGroupType.UNSPECIFIED);
            ArrayList<AbstractCard> original=new ArrayList<>();
            for(int i=0;i<length;i++) original.add(empty(Strike_Green.class));
            hand.group.addAll(original.subList(0,length-1));
            AbstractCard prior=original.get(length-1), wanted=original.get(target);
            screen.selectedCards.group.add(prior);
            set(screen,HandCardSelectScreen.class,"hoveredCard",wanted);
            click.invoke(screen);
            original.remove(target);
            if(hand.group.size()!=original.size() || screen.selectedCards.size()!=1 ||
                    screen.selectedCards.group.get(0)!=wanted) throw new AssertionError("Wrong occurrence or order");
            for(int i=0;i<original.size();i++) if(hand.group.get(i)!=original.get(i))
                throw new AssertionError("Wrong remaining card instance");
        }
        System.out.println("RETAIL_SWAP 45");
    }
}
