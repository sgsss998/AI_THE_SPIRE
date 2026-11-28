import java.util.*;
import javassist.*;
import javassist.bytecode.*;

/** Rebuild the original library's HashMap from its original registration order and embedded card IDs. */
public final class RetailCardOrder {
    static Set<String> rarities(CtClass card) throws Exception {
        Set<String> found=new HashSet<>();
        for(CtConstructor constructor:card.getDeclaredConstructors()) {
            MethodInfo m=constructor.getMethodInfo();ConstPool p=m.getConstPool();CodeIterator it=m.getCodeAttribute().iterator();
            while(it.hasNext()) {
                int index=it.next();
                if(it.byteAt(index)!=178) continue;
                int ref=it.u16bitAt(index+1);
                if(p.getFieldrefClassName(ref).endsWith("AbstractCard$CardRarity")) found.add(p.getFieldrefName(ref));
            }
        }
        return found;
    }
    public static void main(String[] args) throws Exception {
        ClassPool cp=new ClassPool(true);cp.insertClassPath(args[0]);
        CtClass library=cp.get("com.megacrit.cardcrawl.helpers.CardLibrary");
        HashMap<String,String> cards=new HashMap<>();
        String[] groups={"Red","Green","Blue","Purple","Colorless","Curse"};
        for(String g:groups) {
            CtMethod method=library.getDeclaredMethod("add"+g+"Cards",new CtClass[0]);
            MethodInfo m=method.getMethodInfo();ConstPool constants=m.getConstPool();CodeIterator it=m.getCodeAttribute().iterator();
            while(it.hasNext()) {
                int i=it.next();if(it.byteAt(i)!=187) continue;
                CtClass card=cp.get(constants.getClassInfo(it.u16bitAt(i+1)));
                String id=(String)card.getDeclaredField("ID").getConstantValue();
                if(id==null || id.isEmpty()) throw new IllegalStateException(card.getName());
                Set<String> flags=rarities(card);
                String kind="";
                if(card.getName().contains(".cards.colorless.") || card.getName().contains(".cards.green.")) {
                    if(flags.size()!=1) throw new IllegalStateException(card.getName()+" "+flags);
                    String rarity=flags.iterator().next();
                    if(Arrays.asList("COMMON","UNCOMMON","RARE").contains(rarity)) kind=g+"_"+rarity;
                }
                if(cards.put(id,kind)!=null) throw new IllegalStateException("Duplicate "+id);
            }
        }
        System.out.println("SIZE\t"+cards.size());
        for(Map.Entry<String,String> e:cards.entrySet()) if(!e.getValue().isEmpty())
            System.out.println("CARD\t"+e.getValue()+"\t"+e.getKey());
    }
}
