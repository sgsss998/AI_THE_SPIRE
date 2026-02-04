#!/usr/bin/env python3
"""
从 Raw_Data JSON 中提取所有唯一的 card/relic/potion/power/intent ID，
用于补充 encoder_v2_ids.yaml。
"""
import json
import sys
from pathlib import Path

def extract_from_obj(obj, cards, relics, potions, powers, intents, context=""):
    """递归提取 ID，根据父级 context 判断类型"""
    if isinstance(obj, dict):
        if "id" in obj:
            cid = obj.get("id")
            if cid:
                if context in ("deck", "hand", "draw_pile", "discard_pile"):
                    cards.add(cid)
                elif context == "relics":
                    relics.add(cid)
                elif context == "potions":
                    potions.add(cid)
                elif context == "powers":
                    powers.add(cid)
                else:
                    # 回退：根据字段推断
                    if "cost" in obj and "type" in obj:
                        cards.add(cid)
                    elif "counter" in obj:
                        relics.add(cid)
                    elif "can_use" in obj or "can_discard" in obj:
                        potions.add(cid)
                    elif "amount" in obj and "name" in obj:
                        powers.add(cid)
        if "intent" in obj:
            intents.add(obj["intent"])
        for k, v in obj.items():
            extract_from_obj(v, cards, relics, potions, powers, intents, k)
    elif isinstance(obj, list):
        for item in obj:
            extract_from_obj(item, cards, relics, potions, powers, intents, context)

def main():
    cards = set()
    relics = set()
    potions = set()
    powers = set()
    intents = set()

    data_dir = Path(__file__).parent.parent / "data" / "A20_Slient" / "Raw_Data_json_FORSL"
    for f in sorted(data_dir.glob("*.json")):
        print(f"Processing {f.name}...", file=sys.stderr)
        with open(f) as fp:
            data = json.load(fp)
        if isinstance(data, list):
            for frame in data:
                gs = frame.get("game_state") if isinstance(frame, dict) else None
                if gs:
                    extract_from_obj(gs, cards, relics, potions, powers, intents)
        else:
            extract_from_obj(data, cards, relics, potions, powers, intents)

    print("# ========== 从 Raw_Data 提取的 CARDS ==========")
    for x in sorted(cards):
        print(x)

    print("\n# ========== 从 Raw_Data 提取的 RELICS ==========")
    for x in sorted(relics):
        print(x)

    print("\n# ========== 从 Raw_Data 提取的 POTIONS ==========")
    for x in sorted(potions):
        print(x)

    print("\n# ========== 从 Raw_Data 提取的 POWERS ==========")
    for x in sorted(powers):
        print(x)

    print("\n# ========== 从 Raw_Data 提取的 INTENTS ==========")
    for x in sorted(intents):
        print(x)

    print(f"\n# 统计: cards={len(cards)}, relics={len(relics)}, potions={len(potions)}, powers={len(powers)}, intents={len(intents)}", file=sys.stderr)

if __name__ == "__main__":
    main()
