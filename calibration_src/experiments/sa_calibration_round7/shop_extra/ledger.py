"""Match native noncard merchandise to a unique published object and displayed price."""
from ..shop.verify import view


def bind(row, frame, engine):
    g = row["before"]["raw"]["game_state"]
    index = row["aid"]-110
    if frame.page != "SHOP_SCREEN" or g["screen_type"] != "SHOP_SCREEN" or not 0 <= index < len(g["choice_list"]):
        return None
    name = view.norm(g["choice_list"][index])
    screen = g["screen_state"]
    backend = engine._source._backend
    visible = [(pos,r) for pos,r in view.options(frame) if r[5]]
    if name == "purge" and screen.get("purge_available"):
        price = screen["purge_cost"]
        matches = [pos for pos,r in visible if r[0] == 11 and r[3] == price]
        ident = "purge"
    else:
        matches = []
        retail = [(kind,x,table) for kind,key,table in ((2,"relics",backend.RELIC_NAMES),(3,"potions",backend.POTION_NAMES))
                  for x in screen[key] if view.norm(x["name"]) == name]
        if len(retail) != 1:
            return None
        kind, item, names = retail[0]
        price, ident = item["price"], item["id"]
        for pos,r in visible:
            if r[0] == kind and r[3] == price and 0 < r[1] <= len(names):
                if view.norm(names[r[1]-1]) in (name,view.norm(ident)):
                    matches.append(pos)
    if len(matches) == 1:
        return 110+matches[0],dict(binding="same typed shop row, object and price", retail_id=ident,price=price)
    return None
