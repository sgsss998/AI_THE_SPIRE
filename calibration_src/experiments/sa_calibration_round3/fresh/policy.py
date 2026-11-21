"""Bounded lookahead on the visible map; all other decisions use the current original screen."""
from functools import lru_cache

def choices(g):
    return [s.lower() for s in g.get("choice_list",[])]

def route(g):
    if g["screen_state"].get("boss_available"):return 110
    nodes={(n["x"],n["y"]):n for n in g["map"]}
    fraction=g["current_hp"]/g["max_hp"]
    def value(n):
        return {"R":12 if fraction<.8 else 7,"T":8,"?":4,"M":1,"E":-12 if fraction<.8 else -5,
                "$":7 if g["gold"]>=70 else 1}.get(n["symbol"],2)
    @lru_cache(None)
    def score(x,y):
        n=nodes[x,y]
        kids=[score(k["x"],k["y"]) for k in n["children"] if (k["x"],k["y"]) in nodes]
        return value(n)+(.72*max(kids) if kids else 0)
    opts=g["screen_state"]["next_nodes"]
    return 110+max(range(len(opts)),key=lambda i:score(opts[i]["x"],opts[i]["y"]))

def fight(g,A,L):
    c=g["combat_state"];ms=c["monsters"];h=c["hand"]
    attacking=lambda m:m["current_hp"]>0 and not m["is_gone"] and m["intent"].startswith("ATTACK")
    incoming=sum(max(0,m["move_adjusted_damage"])*max(1,m["move_hits"]) for m in ms if attacking(m))
    gap=max(0,incoming-c["player"]["block"])
    living=[m for m in ms if m["current_hp"]>0 and not m["is_gone"]]
    potions=[a for a in L if 70<=a<105]
    if potions:
        candidates=[]
        for a in potions:
            action=A.from_id(a)
            potion=g["potions"][action.potion_index]
            tag=potion["name"].lower()
            if a>=75:
                target=ms[action.target_index-1]
                if target["current_hp"]<=0 or target["is_gone"]:continue
                priority=120-min(target["current_hp"],100)
            else:priority=0
            if any(t in tag for t in ("fire potion","explosive","poison potion")):
                if any(m["current_hp"]<=20 for m in living) or g["current_hp"]<g["max_hp"]*.65:priority+=300
            elif "block" in tag and gap>=8:priority+=370
            elif "dexterity" in tag or "strength" in tag or "cultist" in tag or "speed" in tag:
                if len(living)>1 or g["room_type"] in ("MonsterRoomElite","MonsterRoomBoss") or g["current_hp"]<40:priority+=250
            elif "regen" in tag and g["current_hp"]+12<g["max_hp"]:priority+=330
            elif "weak" in tag and gap>=7:priority+=280
            elif "energy" in tag and c["player"]["energy"]==0 and len(h)>2:priority+=240
            elif g["current_hp"]<24 and gap>=7 and "smoke" not in tag:priority+=200
            if priority>=200:candidates.append((priority,a))
        if candidates:return max(candidates)[1],"use a visible potion for damage, mitigation or survival"
    scored=[]
    for a in L:
        if not 0<=a<70:continue
        card=h[a%10];name=card["id"];cost=card["cost"];j=a//10-1
        m=ms[j] if j>=0 else None
        if m is not None and (m["current_hp"]<=0 or m["is_gone"]):continue
        if card["type"]=="ATTACK":
            base=(9 if card["upgrades"] else 6) if name=="Strike_G" else 3 if name=="Neutralize" else 8
            hp=m["current_hp"]+m["block"] if m else 70
            value=160 if hp<=base else 43
            if name=="Neutralize":value+=75 if m and attacking(m) else 58
            if m and attacking(m):value+=7
            if m:value-=min(hp,125)*.18
            if name in ("Dash","Leg Sweep"):value+=14 if gap>=4 else 3
            if name in ("Poisoned Stab","Dagger Throw","Dagger Spray","Predator"):value+=3
            if cost==0:value+=18
        elif card["type"]=="POWER":
            value=76 if gap<10 else 30
        elif name in ("Defend_G","Dodge and Roll","Backflip","Blur","Deflect","Leg Sweep","Cloak And Dagger","Cloak and Dagger"):
            value=100+min(gap,12) if gap>=4 else 50 if gap else 8
            if name!="Defend_G":value+=5
        elif name=="Survivor":
            if not gap or len(h)<=1:continue
            value=80 if gap>=5 else 35
            # Plain Defend is retained when it already covers the threatened hit.
            if gap>=8 and c["player"]["energy"]<=1:value+=40
        elif name=="Catalyst" and not any(any(p["id"]=="Poison" for p in n["powers"]) for n in living):continue
        else:value=49 if cost==0 else 44
        scored.append((value,-a,a))
    if scored:return max(scored)[2],"cover incoming damage, finish vulnerable targets, then build damage"
    return 170,"end turn"

GOOD=["glass knife","corpse explosion","wraith form","adrenaline","after image","footwork","backflip","dagger spray",
      "blade dance","dash","predator","crippling cloud","leg sweep","noxious fumes","poisoned stab","cloak and dagger","piercing wail","calculated gamble","terror","flying knee","dagger throw"]
def choose(g,A,L):
    g={k:v for k,v in g.items() if k!="seed"}
    ui=g["screen_type"]; opts=choices(g)
    if ui=="NONE":return fight(g,A,L)
    if ui=="MAP":return route(g),"choose visible route favoring healing, treasure and useful shops"
    if ui=="HAND_SELECT":
        if 172 in L:return 172,"confirm selected hand cards"
        ids=[a for a in L if 110<=a<170]
        return max(ids,key=lambda a:(any(x in opts[a-110] for x in ("bane","wound","dazed","slimed","burn")), ("defend" in opts[a-110]),-a)),"discard curse/status, then basic card"
    if ui=="CARD_REWARD":
        for pref in GOOD:
            for i,label in enumerate(opts):
                if pref in label:return 110+i,"take high-impact visible card"
        if len(g["deck"])<19:
            cards=g["screen_state"].get("cards",[])
            for i,card in enumerate(cards):
                if card["type"]=="ATTACK":return 110+i,"add early damage"
        if 177 in L:return 177,"skip weak card"
    if ui=="COMBAT_REWARD":
        for i,r in enumerate(g["screen_state"].get("rewards",[])):
            if 110+i in L and r["reward_type"]!="SAPPHIRE_KEY":
                if r["reward_type"]=="POTION" and all(x["id"]!="Potion Slot" for x in g["potions"]):continue
                return 110+i,"collect available prize"
        if 171 in L:return 171,"leave claimed rewards"
    if ui=="REST":
        if "rest" in opts and g["current_hp"]<g["max_hp"]*.82:return 110+opts.index("rest"),"recover at campfire"
        if "smith" in opts:return 110+opts.index("smith"),"upgrade at campfire"
    if ui=="GRID":
        if 172 in L:return 172,"confirm chosen card"
        cards=g["screen_state"].get("cards",[])
        if cards:
            pref=("Neutralize","Dodge and Roll","Survivor","Strike_G","Defend_G")
            if g["screen_state"].get("for_purge"):pref=("AscendersBane","Strike_G","Defend_G")
            for n in pref:
                for j,c in enumerate(cards):
                    if c["id"]==n and 110+j in L:return 110+j,"choose applicable upgrade or removal"
    if ui=="SHOP_SCREEN":
        cards=g["screen_state"].get("cards",[])
        for pref in GOOD:
            for c in cards:
                if pref==c["name"].lower() and c.get("price",10**5)<=g["gold"]:
                    i=next((j for j,o in enumerate(opts) if pref in o),None)
                    if i is not None and 110+i in L:return 110+i,"buy affordable high-impact card"
        if 171 in L:return 171,"leave shop after affordable upgrades"
        if 178 in L:return 178,"leave shop"
    if ui=="EVENT":
        state=g["screen_state"]
        rows={r["choice_index"]:r.get("text","").lower() for r in state.get("options",[]) if not r.get("disabled") and "choice_index" in r}
        for i,txt in rows.items():
            if ("heal" in txt or "restore" in txt) and not any(k in txt for k in ("lose","curse","damage","trade")):
                return 110+i,"take visible healing"
        if len(opts)>1:
            for i,x in enumerate(opts):
                if x.startswith(("leave","ignore","continue")):return 110+i,"avoid optional damage or curse"
    if ui=="BOSS_REWARD":
        for pref in ("pandora","astrolabe","coffee dripper","runic pyramid","cursed key","black star","empty cage"):
            for i,o in enumerate(opts):
                if pref in o:return 110+i,"take visible boss relic"
    for a in (110,172,171,177,178):
        if a in L:return a,"advance visible screen"
    raise ValueError((ui,opts,L))
