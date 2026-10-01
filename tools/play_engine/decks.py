"""Starting decks for the play engine, built from SCED's own card pool.

Each deck is 30 real level-0 player cards taken from the "All Player Cards"
bag in the owner's SCED save (their SCED ids and metadata: class, level,
cost, icons, uses), chosen under the investigator's printed deckbuilding
options (the back of the investigator card), plus the three signature cards
and one random basic weakness (picked per game by the engine from the
encoded list below). Only cards whose effects the engine encodes are used
(tools/play_engine/lua/players.lua keys them by name).

    python3 tools/play_engine/decks.py --save "/home/user/sce480/Arkham SCE 4.8.0.json"
"""
import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# (name, copies); the order is the pick order. Off-class cards are checked
# against the investigator's limit.
LISTS = {
    "sthrelias": [
        ("Machete", 2), (".45 Automatic", 2), ("Physical Training", 2), ("Guard Dog", 2), ("Vicious Blow", 2),
        ("Beat Cop", 2), ("Dodge", 2), ("Evidence!", 2), ("First Aid", 2), ("Emergency Cache", 2),
        ("Unexpected Courage", 2), ("Guts", 2), ("Overpower", 2), ("Leather Coat", 2), ("Lucky!", 2)],
    "sthrayako": [
        ("Magnifying Glass", 2), ("Dr. Milan Christopher", 2), ("Deduction", 2), ("Working a Hunch", 2),
        ("Hyperawareness", 2), ("Medical Texts", 2), ("Old Book of Lore", 2), ("Mind over Matter", 2),
        ("Emergency Cache", 2), ("Unexpected Courage", 2), ("Perception", 2), ("Guts", 2), ("Flashlight", 2),
        ("Knife", 1), ("Ward of Protection", 2), ("Arcane Studies", 1)],
    "sthrcass": [
        ("Elusive", 2), ("Sneak Attack", 2), ("Pickpocketing", 2), ("Opportunist", 2), ("Hard Knocks", 2),
        ("Switchblade", 2), ("Leo De Luca", 1), ("Emergency Cache", 2), ("Unexpected Courage", 2),
        ("Manual Dexterity", 2), ("Overpower", 2), ("Perception", 2), ("Knife", 2), ("Flashlight", 2),
        ("Lucky!", 2), ("Dodge", 1)],
    "sthrseraphine": [
        ("Shrivelling", 2), ("Arcane Studies", 2), ("Ward of Protection", 2), ("Holy Rosary", 2), ("Fearless", 2),
        ("Blinding Light", 2), ("Drawn to the Flame", 2), ("Emergency Cache", 2), ("Unexpected Courage", 2),
        ("Guts", 2), ("Perception", 2), ("Knife", 2), ("Flashlight", 2), ("Magnifying Glass", 2), ("Deduction", 2)],
    "sthrbirdie": [
        ("Baseball Bat", 2), ("Lucky!", 2), ("Rabbit's Foot", 2), ("Stray Cat", 2), ("Dig Deep", 2),
        ("Survival Instinct", 2), ("Leather Coat", 2), ("Cunning Distraction", 1), ("Emergency Cache", 2),
        ("Unexpected Courage", 2), ("Guts", 2), ("Perception", 2), ("Manual Dexterity", 2), ("Knife", 2),
        ("Flashlight", 2), ("Magnifying Glass", 1)],
}

# XP upgrades in the order a careful player buys them: (xp, level-0 card it
# replaces, upgraded card's SCED name, copies). Same-title upgrades keep the
# base name (the engine's effects apply; icons and uses come from the upgraded
# printing); cards the engine encodes under their full name keep it (FULL).
UPGRADES = {
    "sthrelias": [(4, "Vicious Blow", "Vicious Blow (2)", 2), (4, "Beat Cop", "Beat Cop (2)", 2),
                  (4, ".45 Automatic", "Shotgun (4)", 1), (3, "Lucky!", "Elder Sign Amulet (3)", 1),
                  (5, ".45 Automatic", "Lightning Gun (5)", 1), (3, "Leather Coat", "Bulletproof Vest (3)", 1)],
    "sthrayako": [(4, "Deduction", "Deduction (2)", 2), (2, "Magnifying Glass", "Magnifying Glass (1)", 2),
                  (3, "Arcane Studies", "Higher Education (3)", 1), (3, "Old Book of Lore", "Elder Sign Amulet (3)", 1),
                  (2, "Medical Texts", "Encyclopedia (2)", 1), (3, "Old Book of Lore", "Bulletproof Vest (3)", 1),
                  (2, "Medical Texts", "Encyclopedia (2)", 1)],
    "sthrcass": [(4, "Switchblade", "Switchblade (2)", 2), (1, "Leo De Luca", "Leo De Luca (1)", 1),
                 (4, "Opportunist", "Opportunist (2)", 2), (2, "Knife", ".41 Derringer (2)", 1),
                 (1, "Pickpocketing", "Hired Muscle (1)", 1), (4, "Knife", "Chicago Typewriter (4)", 1),
                 (3, "Pickpocketing", "Streetwise (3)", 1), (3, "Lucky!", "Elder Sign Amulet (3)", 1)],
    "sthrseraphine": [(6, "Shrivelling", "Shrivelling (3)", 2), (4, "Fearless", "Fearless (2)", 2),
                      (4, "Blinding Light", "Blinding Light (2)", 2), (2, "Shrivelling (3)", "Shrivelling (5)", 1),
                      (3, "Drawn to the Flame", "Elder Sign Amulet (3)", 1),
                      (3, "Drawn to the Flame", "Bulletproof Vest (3)", 1)],
    "sthrbirdie": [(4, "Lucky!", "Lucky! (2)", 2), (4, "Survival Instinct", "Survival Instinct (2)", 2),
                   (2, "Stray Cat", "Peter Sylvestre (2)", 1), (3, "Dig Deep", "Scrapper (3)", 1),
                   (3, "Rabbit's Foot", "Elder Sign Amulet (3)", 1), (3, "Leather Coat", "Bulletproof Vest (3)", 1)],
}
FULL = {"Shotgun (4)", "Lightning Gun (5)", "Elder Sign Amulet (3)", "Bulletproof Vest (3)", "Higher Education (3)",
        "Encyclopedia (2)", "Switchblade (2)", ".41 Derringer (2)", "Hired Muscle (1)", "Chicago Typewriter (4)",
        "Streetwise (3)", "Shrivelling (3)", "Shrivelling (5)", "Peter Sylvestre (2)", "Scrapper (3)"}
# XP each investigator has spent on cards by that night (about two-thirds of the
# Memory they earn; the rest buys Recollections): night 2, 3, 4, 6 and the finale
TIERS = {"n2": 4, "n3": 8, "n4": 12, "n6": 20, "fin": 26}

# basic weaknesses the engine encodes (one is drawn per investigator per game)
WEAKNESSES = ["Paranoia", "Amnesia", "Haunted", "Psychosis", "Hypochondria", "Mob Enforcer",
              "Silver Twilight Acolyte", "Stubborn Detective", "Indebted", "Internal Injury", "Chronophobia"]

PREFERRED_CYCLES = ("Revised Core", "Core", "The Dunwich Legacy")
CLASSES = ("Guardian", "Seeker", "Rogue", "Mystic", "Survivor")


def player_bag(save):
    d = json.load(open(save, encoding="utf-8"))
    for o in d.get("ObjectStates", []):
        if o.get("Nickname") == "All Player Cards":
            return o.get("ContainedObjects", [])
    raise SystemExit("no 'All Player Cards' bag in " + save)


def pool(save, upgraded=False):
    """name -> SCED metadata (level 0, preferred printing; upgraded=True: levels 1-5)."""
    best = {}
    for x in player_bag(save):
        try:
            md = json.loads(x.get("GMNotes") or "{}")
        except ValueError:
            continue
        name = x.get("Nickname")
        lv = md.get("level", 0) or 0
        if not name or (lv > 0) != upgraded or "Taboo" in name:
            continue
        rank = PREFERRED_CYCLES.index(md["cycle"]) if md.get("cycle") in PREFERRED_CYCLES else 9
        if name not in best or rank < best[name][0]:
            best[name] = (rank, dict(md, name=name))
    return {n: v[1] for n, v in best.items()}


def options(back_text):
    """(main class, off-class allowance {classes}, limit, max level) from the investigator's back."""
    t = back_text or ""
    m = re.search(r"up to (\d+) (?:other )?([A-Za-z ,/and]+?) cards? level 0(?:[–-](\d))?", t)
    if not m:
        m2 = re.search(r"up to (\d+) cards of any (?:other )?class at level 0", t)
        return {"limit": int(m2.group(1)) if m2 else 0, "classes": set(CLASSES), "level": 0}
    words = m.group(2)
    classes = {c for c in CLASSES if c in words}
    if "any" in words:
        classes = set(CLASSES)
    return {"limit": int(m.group(1)), "classes": classes, "level": int(m.group(3) or 0)}


def build(save, cards_json=None):
    cards_json = cards_json or os.path.join(ROOT, ".cache", "play_engine", "cards.json")
    campaign = json.load(open(cards_json, encoding="utf-8"))["cards"]
    p = pool(save)
    up = pool(save, upgraded=True)
    out = {"decks": {}, "weaknesses": [], "problems": []}
    for inv, picks in LISTS.items():
        c = campaign[inv]
        klass = c["class"]
        opt = options(c.get("back_text", ""))
        deck, off = [], 0
        for name, n in picks:
            md = p.get(name)
            if not md:
                out["problems"].append("%s: %s not in SCED's player cards" % (inv, name))
                continue
            k = md.get("class")
            if k not in (klass, "Neutral"):
                if k not in opt["classes"] or md.get("level", 0) > opt["level"]:
                    out["problems"].append("%s: %s (%s) is not allowed" % (inv, name, k))
                    continue
                off += n
            for _ in range(n):
                deck.append({"name": name, "sced": md.get("id"), "type": md.get("type"), "class": k,
                             "cost": md.get("cost"), "traits": md.get("traits", ""), "slot": md.get("slot"),
                             "uses": md.get("uses"), "icons": {
                                 "wil": md.get("willpowerIcons", 0), "int": md.get("intellectIcons", 0),
                                 "com": md.get("combatIcons", 0), "agi": md.get("agilityIcons", 0),
                                 "wild": md.get("wildIcons", 0)}})
        if len(deck) != 30:
            out["problems"].append("%s: %d cards, not 30" % (inv, len(deck)))
        if off > opt["limit"]:
            out["problems"].append("%s: %d off-class cards (limit %d)" % (inv, off, opt["limit"]))
        # signatures come from the campaign's own cards
        sigs = []
        for s in (c.get("signatures") or [{}])[0].keys():
            sc = campaign[s]
            sigs.append({"name": sc["name"], "id": s, "type": sc["type"], "class": sc.get("class"),
                         "cost": sc.get("cost"), "traits": sc.get("traits", ""), "slot": sc.get("slot"),
                         "uses": sc.get("uses"), "weakness": sc.get("weakness", False), "signature": True,
                         "icons": {"wil": sc.get("wilIcons", 0), "int": sc.get("intIcons", 0),
                                   "com": sc.get("comIcons", 0), "agi": sc.get("agiIcons", 0),
                                   "wild": sc.get("wildIcons", 0)}})
        out["decks"][inv] = {"cards": deck, "signatures": sigs, "offclass": off, "limit": opt["limit"]}
        # upgraded decks for later nights: buy UPGRADES in order while the tier's XP lasts
        for tier, budget in TIERS.items():
            cur, spent = [dict(c) for c in deck], 0
            for xp, old, new, n in UPGRADES.get(inv, []):
                if spent + xp > budget:
                    break
                md = up.get(new)
                if not md:
                    out["problems"].append("%s: %s not in SCED's player cards" % (inv, new))
                    break
                k = md.get("class")
                if k not in (klass, "Neutral") and (k not in opt["classes"] or md.get("level", 0) > opt["level"]):
                    out["problems"].append("%s: %s (%s) is not allowed" % (inv, new, k))
                    break
                for _ in range(n):
                    i = next((j for j, c in enumerate(cur) if old in (c["name"], c.get("full"))), None)
                    if i is None:
                        out["problems"].append("%s: no %s to replace with %s" % (inv, old, new))
                        break
                    base = re.sub(r" \(\d\)$", "", new)
                    cur[i] = {"name": new if new in FULL else base, "full": new, "level": md.get("level"),
                              "sced": md.get("id"), "type": md.get("type"), "class": k, "cost": md.get("cost"),
                              "traits": md.get("traits", ""), "slot": md.get("slot"), "uses": md.get("uses"),
                              "icons": {"wil": md.get("willpowerIcons", 0), "int": md.get("intellectIcons", 0),
                                        "com": md.get("combatIcons", 0), "agi": md.get("agilityIcons", 0),
                                        "wild": md.get("wildIcons", 0)}}
                spent += xp
            out.setdefault("tiers", {}).setdefault(tier, {})[inv] = {"cards": cur, "signatures": sigs, "xp": spent}
    for name in WEAKNESSES:
        md = p.get(name)
        if md and md.get("weakness"):
            out["weaknesses"].append({"name": name, "sced": md.get("id"), "type": md.get("type"),
                                      "traits": md.get("traits", ""), "weakness": True, "icons": {}})
        else:
            out["problems"].append("basic weakness %s not found" % name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default="/home/user/sce480/Arkham SCE 4.8.0.json")
    ap.add_argument("--out", default=os.path.join(ROOT, ".cache", "play_engine", "decks.json"))
    a = ap.parse_args()
    d = build(a.save)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(d, open(a.out, "w", encoding="utf-8"), indent=1)
    for inv, deck in d["decks"].items():
        print(inv, len(deck["cards"]), "cards,", deck["offclass"], "off-class (limit %d)" % deck["limit"])
    for p in d["problems"]:
        print("PROBLEM:", p)
    print(a.out)


if __name__ == "__main__":
    main()
