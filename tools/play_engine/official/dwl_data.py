"""Data for the Dunwich Legacy benchmark (designer tooling).

The play engine (tools/play_engine) plays The Dunwich Legacy's opening pair --
1a Extracurricular Activity and 1b The House Always Wins -- on the same
emulated SCED table it uses for The Still Hour, as a baseline to read The
Still Hour's numbers against. This module turns the downloaded official data
(gitignored, under .cache/official/) into the two files the Lua side reads:

  * cards.json: every card the two scenarios and the official investigators
    use, in the shape tools/play_engine/cards.py gives The Still Hour's cards
    (fight, evade, health, shroud, clues, doom, victory, text, ...), read from
    ArkhamDB's card data (pack/dwl, pack/core). Nothing is copied by hand.
  * decks.json: the official investigators' decks. For a like-for-like
    benchmark each plays the 30 level-0 cards The Still Hour's starter deck of
    the same class holds (the cards and AI the Still Hour runs use), plus its
    own signature cards from SCED's All Player Cards and one random basic
    weakness (the same encoded list).

The SCED campaign box itself (.cache/official/dwl_sced.json) is loaded onto
the table by the Lua side; this module only lists its scenario cards (the
encoding target) and checks them against the effects table's coverage.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ENGINE))
OFFICIAL = os.path.join(ROOT, ".cache", "official")
SCED_BOX = os.path.join(OFFICIAL, "dwl_sced.json")
ARKHAMDB = os.path.join(OFFICIAL, "arkhamdb-json-data", "pack")
GUIDE = os.path.join(OFFICIAL, "arkham-cards-data", "campaigns", "dwl")
sys.path.insert(0, ENGINE)

SCENARIO_BOXES = {"1a": "1a: Extracurricular Activity", "1b": "1b: The House Always Wins"}

# official investigator -> The Still Hour starter deck of the same class (its 30 level-0 cards)
TEMPLATE = {"02001": "sthrelias", "02002": "sthrayako", "02003": "sthrcass", "02004": "sthrseraphine"}
SIGNATURES = {"02001": ["02006", "02007"], "02002": ["02008", "02009"], "02003": ["02010", "02011"],
              "02004": ["02012", "02013"]}
# a unique ally sharing the investigator's name cannot be in play with them: Jim Culver plays a
# level-0 Mystic card the engine encodes in its place (Holy Rosary)
REPLACE = {"02004": {"Jim Culver": "Holy Rosary"}}
PARTIES = {2: ["02001", "02002"], 3: ["02001", "02002", "02003"], 4: ["02001", "02002", "02003", "02004"]}

TYPES = {"enemy": "Enemy", "location": "Location", "act": "Act", "agenda": "Agenda", "treachery": "Treachery",
         "asset": "Asset", "event": "Event", "skill": "Skill", "investigator": "Investigator",
         "scenario": "Scenario", "story": "Story", "key": "Key"}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def clean(text):
    """ArkhamDB markup to plain rules text (keeps [action], [per_investigator] ...)."""
    t = text or ""
    t = re.sub(r"</?(b|i|em|strong|u|blockquote|cite)>", "", t)
    t = re.sub(r"<hr\s*/?>", " ", t)
    t = t.replace("–", "-").replace("—", "-")
    return t.strip()


def card_record(c):
    t = TYPES.get(c.get("type_code"), c.get("type_code"))
    r = {"id": c["code"], "type": t, "name": c.get("name"), "subtitle": c.get("subname"),
         "traits": c.get("traits", ""), "text": clean(c.get("text")), "back_text": clean(c.get("back_text")),
         "class": (c.get("faction_code") or "").capitalize(), "unique": bool(c.get("is_unique")),
         "quantity": c.get("quantity"), "encounter": c.get("encounter_code")}
    if t == "Enemy":
        r.update(fight=c.get("enemy_fight") or 0, evade=c.get("enemy_evade") or 0, health=c.get("health") or 1,
                 damage=c.get("enemy_damage") or 0, horror=c.get("enemy_horror") or 0, victory=c.get("victory") or 0)
        if c.get("health_per_investigator"):
            r["health"] = "%dperinv" % (c.get("health") or 1)
        m = re.search(r"gets \+(\d+) \[per_investigator\] health", c.get("text") or "")
        if m:   # The Experiment: printed health + X per investigator
            r["health_plus_per_investigator"] = int(m.group(1))
    elif t == "Location":
        r.update(shroud=c.get("shroud") or 0, clues=c.get("clues") or 0,
                 clues_per_investigator=not c.get("clues_fixed"), victory=c.get("victory") or 0)
    elif t == "Act":
        r.update(clues=c.get("clues") or 0, clues_per_investigator=bool(c.get("clues")) and not c.get("clues_fixed"))
    elif t == "Agenda":
        r.update(doom=c.get("doom") or 0)
    elif t == "Investigator":
        r.update(wil=c.get("skill_willpower"), int=c.get("skill_intellect"), com=c.get("skill_combat"),
                 agi=c.get("skill_agility"), health=c.get("health"), sanity=c.get("sanity"))
    else:
        r.update(cost=c.get("cost"), slot=c.get("slot"), health=c.get("health"), sanity=c.get("sanity"),
                 wilIcons=c.get("skill_willpower") or 0, intIcons=c.get("skill_intellect") or 0,
                 comIcons=c.get("skill_combat") or 0, agiIcons=c.get("skill_agility") or 0,
                 wildIcons=c.get("skill_wild") or 0,
                 weakness=c.get("subtype_code") in ("weakness", "basicweakness"))
    return {k: v for k, v in r.items() if v is not None}


def arkhamdb_cards():
    out = {}
    for rel in ("dwl/dwl.json", "dwl/dwl_encounter.json", "core/core.json", "core/core_encounter.json"):
        for c in _load(os.path.join(ARKHAMDB, rel)):
            out.setdefault(c["code"], card_record(c))
    return out


def sced_box():
    return _load(SCED_BOX)


def scenario_ids(box=None):
    """{"1a": [card ids], "1b": [...]}: every card SCED's scenario box holds (its decks and set-aside bag)."""
    box = box or sced_box()
    out = {}
    for key, name in SCENARIO_BOXES.items():
        sb = next(c for c in box["ContainedObjects"] if c.get("Nickname") == name)
        ids = set()

        def walk(o):
            g = (o.get("GMNotes") or "").strip()
            if g.startswith("{"):
                try:
                    md = json.loads(g)
                except ValueError:
                    md = {}
                if md.get("id") and md.get("type") not in ("ScenarioBox",):
                    ids.add(str(md["id"]))
            for x in o.get("ContainedObjects") or []:
                walk(x)
        for x in sb.get("ContainedObjects") or []:
            walk(x)
        out[key] = sorted(ids)
    return out


def write_cards(path):
    cards = arkhamdb_cards()
    ids = scenario_ids()
    data = {"cards": cards, "scenario_ids": sorted(set(ids["1a"]) | set(ids["1b"])), "scenarios": ids}
    _write_json(path, data, ensure_ascii=False, indent=1, sort_keys=True)
    return path


def write_decks(still_hour_decks, save, path):
    """Official investigators with The Still Hour's same-class level-0 starter cards (see TEMPLATE)."""
    import decks as decks_mod
    sh = _load(still_hour_decks)
    by_id = decks_mod.pool_by_id(save)
    cards = arkhamdb_cards()
    out = {"decks": {}, "weaknesses": sh["weaknesses"], "upgrade_steps": {}, "problems": [], "template": TEMPLATE}
    for inv, tmpl in TEMPLATE.items():
        base = sh["decks"][tmpl]["cards"]
        rep = REPLACE.get(inv, {})
        donor = {c["name"]: c for d in sh["decks"].values() for c in d["cards"]}
        deck = []
        for c in base:
            if c["name"] in rep:
                deck.append(dict(donor[rep[c["name"]]]))
            else:
                deck.append(dict(c))
        sigs = []
        for sid in SIGNATURES[inv]:
            md = by_id.get(sid)
            if not md:
                out["problems"].append("%s: signature %s not in SCED's player cards" % (inv, sid))
                continue
            ad = cards.get(sid, {})
            uses = md.get("uses")
            sigs.append({"name": md["name"], "id": sid, "sced": sid, "type": md.get("type"), "class": md.get("class"),
                         "cost": md.get("cost"), "traits": md.get("traits", ""), "slot": ad.get("slot"),
                         "uses": uses, "weakness": md.get("type") == "Treachery", "signature": True,
                         "icons": {"wil": md.get("willpowerIcons", 0) or 0, "int": md.get("intellectIcons", 0) or 0,
                                   "com": md.get("combatIcons", 0) or 0, "agi": md.get("agilityIcons", 0) or 0,
                                   "wild": md.get("wildIcons", 0) or 0}})
        if len(deck) != 30:
            out["problems"].append("%s: %d cards, not 30" % (inv, len(deck)))
        off = sum(1 for c in deck if not decks_mod.in_class(c.get("class"), cards[inv]["class"]))
        if off > 5:
            out["problems"].append("%s: %d off-class cards (limit 5)" % (inv, off))
        if inv == "02002" and any("Fortune" in (c.get("traits") or "") for c in deck):
            out["problems"].append("Rex Murphy: a Fortune card in the deck")
        out["decks"][inv] = {"cards": deck, "signatures": sigs, "offclass": off, "limit": 5, "template": tmpl}
        # the same XP upgrade path as the Still Hour template (decks.py UPGRADES), for campaign-order runs
        out["upgrade_steps"][inv] = (sh.get("upgrade_steps") or {}).get(tmpl, [])
    _write_json(path, out, indent=1)
    return out


def _write_json(path, data, **kw):
    """Atomically (a game process starting at the same moment reads either the old or the new file)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, **kw)
    os.replace(tmp, path)


def guide(name):
    return _load(os.path.join(GUIDE, name + ".json"))


def resolution_steps():
    """{scenario: {resolution id: [step ids]}} from the campaign guide data (arkham-cards-data)."""
    out = {}
    for key, name in (("1a", "extracurricular_activity"), ("1b", "the_house_always_wins")):
        g = guide(name)
        out[key] = {r["id"]: r.get("steps", []) for r in g["resolutions"]}
    return out


if __name__ == "__main__":
    print(write_cards(os.path.join(ROOT, ".cache", "play_engine", "official", "dwl_cards.json")))
