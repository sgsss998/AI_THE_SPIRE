#!/usr/bin/env python3
"""
验证编码器卡牌数量

从实际Mod日志数据中统计卡牌ID，与encoder_ids.yaml对比
"""
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set
import yaml


# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "A20_Silent" / "Raw_Data_json_FORSL"
IDS_PATH = PROJECT_ROOT / "configs" / "encoder_ids.yaml"


def normalize_id(raw: str) -> str:
    """ID归一化：忽略大小写、空格↔下划线互换"""
    if not raw or not isinstance(raw, str):
        return ""
    s = raw.strip().lower()
    s = re.sub(r"[\s_]+", "_", s)
    return s


# 中文名到英文ID的映射（Mod日志用中文名）
CN_TO_EN_CARD_MAP = {
    "进阶之灾": "AscendersBane",
    "笨拙": "Clumsy",
    "钟咒": "CurseOfTheBell",
    "腐朽": "Decay",
    "怀疑": "Doubt",
    "损伤": "Injury",
    "死灵契书": "Necronomicurse",
    "正常": "Normality",
    "疼痛": "Pain",
    "寄生": "Parasite",
    "傲慢": "Pride",
    "后悔": "Regret",
    "羞耻": "Shame",
    "扭动": "Writhe",
    "燃烧": "Burn",
    "迷茫": "Dazed",
    "黏液": "Slimed",
    "虚无": "Void",
    "创伤": "Wound",
    "打击": "Strike_G",
    "防御": "Defend_G",
    "中和": "Neutralize",
    "生存者": "Survivor",
    # 后续可以添加更多映射
}


def map_cn_to_en(card_name: str) -> str:
    """将中文名映射到英文ID"""
    return CN_TO_EN_CARD_MAP.get(card_name, card_name)


def load_yaml_cards() -> Dict[str, List[str]]:
    """加载encoder_ids.yaml中的卡牌定义"""
    with open(IDS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {
        "all": data.get("cards", []),
    }


def extract_card_ids_from_json(json_file: Path) -> Set[str]:
    """从Mod日志JSON中提取所有卡牌ID"""
    cards = set()

    # 尝试逐行解析JSON数组
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 修复常见JSON问题：文件可能被截断
        if not content.strip().endswith(']'):
            # 找到最后一个完整的对象
            content = content.rstrip()
            while content and not content.endswith('}'):
                content = content[:-1]
            content += '\n]'

        data = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"    ⚠️  {json_file.name}: JSON解析错误 - {e}")
        return cards

    # 遍历所有状态帧
    for frame in data:
        if "game_state" not in frame:
            continue

        gs = frame["game_state"]

        # 从战斗状态中提取卡牌
        if "combat_state" in gs and gs["combat_state"]:
            cs = gs["combat_state"]

            # 手牌
            for card in cs.get("hand", []):
                if "id" in card:
                    cards.add(normalize_id(card["id"]))
                if "name" in card:
                    # 处理中文名映射
                    name = card["name"]
                    en_name = map_cn_to_en(name)
                    cards.add(normalize_id(en_name))
                    cards.add(normalize_id(name))  # 同时保留原名

            # 抽牌堆
            for card in cs.get("draw_pile", []):
                if "id" in card:
                    cards.add(normalize_id(card["id"]))
                if "name" in card:
                    name = card["name"]
                    en_name = map_cn_to_en(name)
                    cards.add(normalize_id(en_name))
                    cards.add(normalize_id(name))

            # 弃牌堆
            for card in cs.get("discard_pile", []):
                if "id" in card:
                    cards.add(normalize_id(card["id"]))
                if "name" in card:
                    name = card["name"]
                    en_name = map_cn_to_en(name)
                    cards.add(normalize_id(en_name))
                    cards.add(normalize_id(name))

            # 消耗堆
            for card in cs.get("exhaust_pile", []):
                if "id" in card:
                    cards.add(normalize_id(card["id"]))
                if "name" in card:
                    name = card["name"]
                    en_name = map_cn_to_en(name)
                    cards.add(normalize_id(en_name))
                    cards.add(normalize_id(name))

        # 从选择列表中提取（奖励卡牌）
        for choice in gs.get("choice_list", []):
            if isinstance(choice, dict):
                if "id" in choice:
                    cards.add(normalize_id(choice["id"]))
                if "name" in choice:
                    name = choice["name"]
                    en_name = map_cn_to_en(name)
                    cards.add(normalize_id(en_name))
                    cards.add(normalize_id(name))

        # 从牌库中提取（deck字段）
        for card in gs.get("deck", []):
            if isinstance(card, dict):
                if "id" in card:
                    cards.add(normalize_id(card["id"]))
                if "name" in card:
                    name = card["name"]
                    en_name = map_cn_to_en(name)
                    cards.add(normalize_id(en_name))
                    cards.add(normalize_id(name))

    return cards


def categorize_cards(card_list: List[str]) -> Dict[str, List[str]]:
    """按类别分组卡牌"""
    categories = {
        "UNKNOWN": [],
        "CURSE": [],
        "STATUS": [],
        "SILENT_BASIC": [],
        "SILENT_COMMON": [],
        "SILENT_UNCOMMON": [],
        "SILENT_RARE": [],
        "SILENT_BONUS": [],
        "COLORLESS": [],
    }

    for card in card_list:
        norm = normalize_id(card)

        if norm == "unknown" or norm == "":
            categories["UNKNOWN"].append(card)
        elif norm in ["ascendersbane", "clumsy", "curseofthebell", "decay", "doubt",
                      "injury", "necronomicurse", "normality", "pain", "parasite",
                      "pride", "regret", "shame", "writhe", "curseofthebell"]:
            categories["CURSE"].append(card)
        elif norm in ["burn", "dazed", "slimed", "void", "wound"]:
            categories["STATUS"].append(card)
        elif norm in ["strike_g", "defend_g"]:
            categories["SILENT_BASIC"].append(card)
        elif norm in ["neutralize", "survivor"]:
            categories["SILENT_BASIC"].append(card)
        elif norm in ["acrobatics", "backflip", "bane", "blade_dance", "bouncing_flask",
                      "calculated_gamble", "caltrops", "catalyst", "choke",
                      "cloak_and_dagger", "concentrate", "crippling_cloud", "dash",
                      "deadly_poison", "deflect", "dodge_and_roll", "escape_plan",
                      "expertise", "finisher", "flying_knee", "heel_hook",
                      "infinite_blades", "leg_sweep", "masterful_stab",
                      "noxious_fumes", "outmaneuver", "poisoned_stab", "predator",
                      "prepared", "quick_slash", "riddle_with_holes", "setup", "shiv",
                      "skewer", "slice", "sneaky_strike", "sucker_punch", "terror",
                      "underhanded_strike", "well_laid_plans"]:
            categories["SILENT_COMMON"].append(card)
        elif norm in ["backstab", "blur", "burst", "corpse_explosion", "distraction",
                      "endless_agony", "eviscerate", "flechettes", "footwork",
                      "malaise", "nightmare", "phantasmal_killer", "piercing_wail",
                      "reflex", "tactician", "thousand_cuts", "tools_of_the_trade",
                      "unload", "wraith_form"]:
            categories["SILENT_UNCOMMON"].append(card)
        elif norm in ["after_image", "bullet_time", "die_die_die", "doppelganger",
                      "envenom", "glass_knife", "grand_finale", "storm_of_steel"]:
            categories["SILENT_RARE"].append(card)
        elif norm in ["adrenaline", "all_out_attack", "dagger_spray", "precise_strike",
                      "rapture", "throwing_knife"]:
            categories["SILENT_BONUS"].append(card)
        else:
            categories["COLORLESS"].append(card)

    return categories


def main():
    print("=" * 80)
    print("卡牌数量验证报告")
    print("=" * 80)

    # 1. 加载yaml中的卡牌
    print("\n【步骤1】加载 encoder_ids.yaml 中的卡牌定义...")
    yaml_cards = load_yaml_cards()
    all_yaml_cards = yaml_cards["all"]

    # 分类统计
    yaml_categories = categorize_cards(all_yaml_cards)

    print(f"\nencoder_ids.yaml 中的卡牌分类统计：")
    print("-" * 60)
    total_yaml = 0
    for cat, cards in yaml_categories.items():
        count = len(cards)
        total_yaml += count
        print(f"  {cat:20s}: {count:3d} 张")

    print(f"  {'总计':20s}: {total_yaml:3d} 张")

    # 2. 扫描实际数据
    print("\n【步骤2】扫描实际Mod日志数据...")
    json_files = list(DATA_DIR.glob("*.json"))
    print(f"找到 {len(json_files)} 个JSON文件")

    all_data_cards = set()
    for i, json_file in enumerate(json_files, 1):
        cards = extract_card_ids_from_json(json_file)
        all_data_cards.update(cards)
        print(f"  [{i}/{len(json_files)}] {json_file.name}: +{len(cards)} 张卡")

    print(f"\n实际数据中发现 {len(all_data_cards)} 个不同的卡牌ID")

    # 3. 对比分析
    print("\n【步骤3】对比分析...")
    yaml_card_norms = set(normalize_id(c) for c in all_yaml_cards)

    # 在数据中出现但yaml中没有的
    missing_in_yaml = all_data_cards - yaml_card_norms

    # 在yaml中但数据中没出现的（可能正常，只是没遇到）
    missing_in_data = yaml_card_norms - all_data_cards

    print(f"\n在实际数据中存在但 yaml 中缺失的卡牌 ({len(missing_in_yaml)} 张):")
    if missing_in_yaml:
        for card in sorted(missing_in_yaml):
            print(f"  - {card}")
    else:
        print("  (无)")

    print(f"\n在 yaml 中定义但数据中未出现的卡牌 ({len(missing_in_data)} 张):")
    if missing_in_data:
        for card in sorted(missing_in_data)[:20]:  # 只显示前20
            print(f"  - {card}")
        if len(missing_in_data) > 20:
            print(f"  ... 还有 {len(missing_in_data) - 20} 张")
    else:
        print("  (无)")

    # 4. 检查当前CARD_DIM设置
    print("\n【步骤4】检查当前维度设置...")
    try:
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.training.encoder_utils import CARD_DIM
        print(f"  encoder_utils.py 中 CARD_DIM = {CARD_DIM}")
        print(f"  yaml 中实际卡牌数量 = {total_yaml}")

        if CARD_DIM != total_yaml:
            print(f"  ⚠️  维度不匹配！相差 {CARD_DIM - total_yaml}")
        else:
            print(f"  ✅ 维度匹配")
    except ImportError as e:
        print(f"  ⚠️  无法导入 encoder_utils: {e}")
        print(f"  yaml 中实际卡牌数量 = {total_yaml}")

    if CARD_DIM != total_yaml:
        print(f"  ⚠️  维度不匹配！相差 {CARD_DIM - total_yaml}")
    else:
        print(f"  ✅ 维度匹配")

    # 5. 建议
    print("\n【建议】")
    if missing_in_yaml:
        print("  需要将以下卡牌添加到 encoder_ids.yaml:")
        for card in sorted(missing_in_yaml):
            print(f"    - {card}")

    print("\n" + "=" * 80)
    print("报告完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
