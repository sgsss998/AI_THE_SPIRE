import java.util.*;
import com.megacrit.cardcrawl.random.Random;

public final class ShuffleSkills {
    public static void main(String[] args) {
        for(String arg:args) {
            long seed=Long.parseUnsignedLong(arg);
            List<Integer> skills=new ArrayList<>(Arrays.asList(6,7,8,9,10,11));
            Random misc=new Random(seed);
            misc.random(1); // Exordium selects its initial music before Neow.
            Collections.shuffle(skills,new java.util.Random(misc.randomLong()));
            System.out.println(arg+"\t"+skills.get(0)+"\t"+skills.get(1));
        }
    }
}
