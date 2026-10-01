#!/usr/bin/env python3
"""build_library.py — the Arkham Horror: The Card Game reference library.

Everything a designer needs to check a rule or a card, in plain searchable
Markdown, built from public LCG data (never the board game):

  - the full Rules Reference, with every appendix and table
    (arkham-cards-data rules/en/rules.json, current version);
  - official errata, every FAQ entry and every taboo list;
  - every official card — player cards by class and level (0-5), encounter
    cards by cycle and encounter set, both sides with stats, text and flavor
    (arkhamdb-json-data packs);
  - every official campaign guide, scenario by scenario: story, setup,
    resolutions (arkham-cards-data campaigns; fan campaigns excluded);
  - structure figures per official scenario (doom, acts, location clues and
    shroud, encounter decks) from SCED's own campaign boxes.

The text is Fantasy Flight Games' copyright, so the library is BUILT LOCALLY
into library/ (git-ignored) and never committed; this script and the search
tool are. Rebuild any time (a few minutes; sources cached in .cache/official):

    python3 tools/library/build_library.py
    python3 tools/library/search.py "Concealed"        # then grep / open
"""
import collections
import csv
import glob
import json
import os
import re
import statistics as st
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, ".cache", "official")
OUT = os.path.join(ROOT, "library")
sys.path.insert(0, os.path.join(ROOT, "tools", "official_compare"))
import compare as C  # noqa: E402

SCED_CAMPAIGNS = C.CAMPAIGNS + ["edge_of_the_earth", "the_scarlet_keys", "the_feast_of_hemlock_vale",
                                "the_drowned_city"]
CLASS_ORDER = ["guardian", "seeker", "rogue", "mystic", "survivor", "neutral", "mythos"]
ICON = {"skill_willpower": "[wil]", "skill_intellect": "[int]", "skill_combat": "[com]",
        "skill_agility": "[agi]", "skill_wild": "[wild]"}


def fetch():
    C.fetch()
    for c in SCED_CAMPAIGNS:
        p = os.path.join(SRC, "tts", c + ".json")
        if not os.path.exists(p):
            urllib.request.urlretrieve(C.SCED_DL % c, p)


def clean(t):
    t = re.sub(r"<b>(.*?)</b>", r"**\1**", t or "")
    t = re.sub(r"<i>(.*?)</i>", r"*\1*", t)
    t = re.sub(r"</?(cite|u|center|blockquote)>", "", t)
    return t.replace("[[", "*").replace("]]", "*")


def write(rel, text):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text)
    return rel


# ------------------------------------------------------------------ rules
def rules():
    data = json.load(open(os.path.join(SRC, "acd", "rules", "en", "rules.json"), encoding="utf-8"))
    out = ["# Arkham Horror: The Card Game — Rules Reference\n",
           "*Built from arkham-cards-data (rules/en/rules.json): the current official Rules Reference, every entry, "
           "appendix and table. The Rules Reference takes precedence over the Learn to Play book (The Golden Rule).*\n"]
    toc = []

    def table(tb):
        rows = []
        for r in tb.get("row") or tb.get("rows") or []:
            cells = r.get("cell") or r.get("cells") or []
            rows.append("| " + " | ".join(clean(c.get("text", "")).replace("\n", " ") for c in cells) + " |")
        if rows:
            n = rows[0].count("|") - 1
            rows.insert(1, "|" + "---|" * n)
        return "\n".join(rows)

    def walk(entries, depth):
        for e in entries:
            title = e.get("title", "")
            anchor = e.get("id", title)
            toc.append(("  " * (depth - 2)) + "- [%s](#%s)" % (title, re.sub(r"[^a-z0-9]+", "-", anchor.lower()).strip("-")))
            out.append("%s %s\n" % ("#" * min(depth, 6), title))
            if e.get("text"):
                out.append(clean(e["text"]) + "\n")
            for tb in e.get("table") or []:
                out.append(table(tb) + "\n")
            if e.get("scenarios"):
                out.append("*Scenarios: %s*\n" % ", ".join(e["scenarios"]))
            walk(e.get("rules") or [], depth + 1)

    walk(data, 2)
    body = "\n".join(out)
    words = len(re.findall(r"\w+", body))
    write("rules/RULES_REFERENCE.md", body)
    write("rules/RULES_REFERENCE_CONTENTS.md", "# Rules Reference — contents\n\n" + "\n".join(toc) + "\n")
    return len(toc), words


def errata_faq_taboos(cards):
    e = json.load(open(os.path.join(SRC, "acd", "errata", "en", "errata.json"), encoding="utf-8"))
    out = ["# Official errata\n"]
    for group in e.get("cards", []):
        if str(group.get("encounter_code", "")).startswith("z"):
            continue                                # fan content
        for item in group.get("cards", []):
            codes = item.get("code") or []
            names = ", ".join("%s (%s)" % (cards.get(c, {}).get("name", "?"), c) for c in codes)
            out.append("- **%s** — %s" % (names, clean(item.get("text", ""))))
    for k, v in e.items():
        if k != "cards" and isinstance(v, list):
            out.append("\n## %s\n" % k)
            for item in v:
                out.append("- " + clean(json.dumps(item, ensure_ascii=False)))
    write("rules/ERRATA.md", "\n".join(out) + "\n")
    n_faq = 0
    for f in sorted(glob.glob(os.path.join(SRC, "acd", "faq", "en", "*.json"))):
        name = os.path.splitext(os.path.basename(f))[0]
        out = ["# FAQ — %s\n" % name]
        for item in json.load(open(f, encoding="utf-8")):
            c = cards.get(item.get("code"), {})
            out.append("## %s (%s)\n\n%s\n" % (c.get("name", item.get("code")), item.get("code"), clean(item.get("text", ""))))
            n_faq += 1
        write("rules/faq/%s.md" % name, "\n".join(out))
    t = json.load(open(os.path.join(SRC, "acd", "taboos.json"), encoding="utf-8"))
    out = ["# Taboo lists (all versions)\n"]
    for lst in t:
        out.append("## %s (%s, from %s)\n" % (lst.get("name"), lst.get("code"), lst.get("date_start")))
        for c in lst.get("cards", []):
            card = cards.get(c.get("code"), {})
            bits = []
            if "xp" in c:
                bits.append("XP %+d" % c["xp"])
            for k in ("text", "exceptional", "forbidden", "deck_limit", "customization_text"):
                if c.get(k) not in (None, ""):
                    bits.append("%s: %s" % (k, clean(str(c[k]))))
            out.append("- **%s** (%s): %s" % (card.get("name", "?"), c.get("code"), "; ".join(bits)))
        out.append("")
    write("rules/TABOOS.md", "\n".join(out))
    return n_faq


# ------------------------------------------------------------------ cards
def load_cards():
    packs = {p["code"]: p for p in json.load(open(os.path.join(SRC, "adb", "packs.json"), encoding="utf-8"))}
    cycles = {c["code"]: c["name"] for c in json.load(open(os.path.join(SRC, "adb", "cycles.json"), encoding="utf-8"))}
    sets = {}
    p = os.path.join(SRC, "adb", "encounters.json")
    if os.path.exists(p):
        sets = {e["code"]: e["name"] for e in json.load(open(p, encoding="utf-8"))}
    cards = {}
    for f in glob.glob(os.path.join(SRC, "adb", "pack", "*", "*.json")):
        for c in json.load(open(f, encoding="utf-8")):
            if c.get("code"):
                c["_pack"] = packs.get(c.get("pack_code"), {}).get("name", c.get("pack_code"))
                c["_cycle"] = cycles.get(packs.get(c.get("pack_code"), {}).get("cycle_code"), "?")
                cards[c["code"]] = c
    return cards, sets


def card_md(c):
    head = "### %s%s%s" % ("✷ " if c.get("is_unique") else "", c.get("name", "?"),
                            (" — " + c["subname"]) if c.get("subname") else "")
    meta = [c.get("type_code", "").title()]
    for k, lab in (("faction_code", "class"), ("xp", "level"), ("cost", "cost"), ("slot", "slot"),
                   ("shroud", "shroud"), ("clues", "clues"), ("doom", "doom"), ("stage", "stage"),
                   ("enemy_fight", "fight"), ("health", "health"), ("enemy_evade", "evade"),
                   ("enemy_damage", "damage"), ("enemy_horror", "horror"), ("sanity", "sanity"),
                   ("victory", "Victory"), ("vengeance", "Vengeance"), ("quantity", "copies")):
        if c.get(k) not in (None, ""):
            v = c[k]
            if k == "clues" and not c.get("clues_fixed") and c.get("type_code") in ("location", "act"):
                v = "%s per investigator" % v
            if k == "health" and c.get("health_per_investigator"):
                v = "%s per investigator" % v
            meta.append("%s %s" % (lab, v))
    icons = " ".join(ICON[k] * int(c[k]) for k in ICON if c.get(k))
    if icons:
        meta.append("icons " + icons)
    lines = [head, "*%s* · code %s · %s" % (" · ".join(str(m) for m in meta), c["code"], c["_pack"])]
    if c.get("traits"):
        lines.append("**%s**" % c["traits"])
    for k, lab in (("text", ""), ("flavor", "*Flavor:* "), ("back_name", "**Back:** "), ("back_traits", "*Back traits:* "),
                   ("back_text", "*Back:* "), ("back_flavor", "*Back flavor:* "), ("customization_text", "*Customization:* ")):
        if c.get(k):
            lines.append(lab + clean(str(c[k])).replace("\n", "  \n"))
    for k in ("exceptional", "myriad", "permanent", "exile", "bonded_to", "restrictions", "deck_requirements",
              "deck_options", "errata_date"):
        if c.get(k) not in (None, "", False):
            lines.append("*%s: %s*" % (k, json.dumps(c[k], ensure_ascii=False) if not isinstance(c[k], (str, int, bool)) else c[k]))
    return "\n".join(lines) + "\n"


def cards_md(cards, sets):
    player = [c for c in cards.values() if not c.get("encounter_code") and c.get("type_code") in
              ("asset", "event", "skill", "investigator") and not c.get("duplicate_of")]
    by = collections.defaultdict(list)
    for c in player:
        by[(c.get("faction_code", "neutral"), c.get("xp") or 0 if c.get("type_code") != "investigator" else -1)].append(c)
    index = []
    for cls in CLASS_ORDER:
        for lvl in [-1, 0, 1, 2, 3, 4, 5]:
            cs = sorted(by.get((cls, lvl), []), key=lambda c: (c.get("type_code"), c.get("name")))
            if not cs:
                continue
            label = "investigators" if lvl < 0 else "level_%d" % lvl
            rel = write("cards/player/%s/%s.md" % (cls, label),
                        "# %s — %s (%d cards)\n\n" % (cls.title(), label.replace("_", " "), len(cs)) + "\n".join(card_md(c) for c in cs))
            index.append((rel, len(cs)))
    # weaknesses and other player-side cards (basic weaknesses, story assets in player packs)
    rest = [c for c in cards.values() if not c.get("encounter_code") and c not in player and not c.get("duplicate_of")]
    rel = write("cards/player/other_player_side.md", "# Weaknesses and other player-side cards (%d)\n\n" % len(rest)
                + "\n".join(card_md(c) for c in sorted(rest, key=lambda c: c.get("name", ""))))
    index.append((rel, len(rest)))
    enc = collections.defaultdict(list)
    for c in cards.values():
        if c.get("encounter_code") and not c.get("duplicate_of"):
            enc[(c["_cycle"], c["encounter_code"])].append(c)
    for (cycle, code), cs in sorted(enc.items()):
        cs.sort(key=lambda c: (c.get("encounter_position") or 0))
        slug = re.sub(r"[^a-z0-9]+", "_", cycle.lower()).strip("_")
        rel = write("cards/encounter/%s/%s.md" % (slug, code),
                    "# %s — encounter set: %s (%d cards)\n\n" % (cycle, sets.get(code, code), len(cs))
                    + "\n".join(card_md(c) for c in cs))
        index.append((rel, len(cs)))
    return index, len(player), sum(len(v) for v in enc.values())


# ------------------------------------------------------------------ campaign guides
OFFICIAL_GUIDES = ["notz", "dwl", "ptc", "tfa", "tcu", "tdea", "tdeb", "tic", "eoe", "tskc", "fhv", "tdc",
                   "fof", "gob", "boa", "cob", "side"]
SKIP_KEYS = {"id", "narration", "lang", "type", "condition", "effects", "encounter_sets", "investigator_status",
             "setup", "steps_ref", "input", "choices_input"}


def guide_text(x, depth=0):
    """Every human-readable string in a guide node, in order."""
    out = []
    if isinstance(x, dict):
        for k in ("title", "full_name", "header", "description", "prompt", "text", "name"):
            v = x.get(k)
            if isinstance(v, str) and v.strip() and not (k == "name" and x.get("text")):
                out.append(("**%s**" % v) if k in ("title", "full_name") else clean(v))
        if x.get("encounter_sets"):
            out.append("*Encounter sets: %s*" % ", ".join(x["encounter_sets"]))
        for k, v in x.items():
            if k in SKIP_KEYS or k in ("title", "full_name", "header", "description", "prompt", "text", "name"):
                continue
            if isinstance(v, (dict, list)):
                out += guide_text(v, depth + 1)
    elif isinstance(x, list):
        for v in x:
            out += guide_text(v, depth + 1)
    return out


def guides():
    n = 0
    for code in OFFICIAL_GUIDES:
        d = os.path.join(SRC, "acd", "campaigns", code)
        if not os.path.isdir(d):
            continue
        camp = json.load(open(os.path.join(d, "campaign.json"), encoding="utf-8"))
        cname = (camp.get("campaign") or camp).get("name", code)
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            name = os.path.splitext(os.path.basename(f))[0]
            data = json.load(open(f, encoding="utf-8"))
            head = data.get("full_name") or data.get("scenario_name") or name
            body = ["# %s — %s\n" % (cname, head)]
            for k in ("setup", "steps", "resolutions"):
                if data.get(k):
                    body.append("## %s\n" % k.title())
                    body += [t + "\n" for t in guide_text(data[k])]
            if name == "campaign":
                body += [t + "\n" for t in guide_text(data)]
            write("campaigns/%s/%s.md" % (code, name), "\n".join(body))
            n += 1
    return n


# ------------------------------------------------------------------ structure figures
def structure(cards):
    rows = []
    for camp in SCED_CAMPAIGNS:
        found = []
        C.boxes(json.load(open(os.path.join(SRC, "tts", camp + ".json"), encoding="utf-8")), found)
        for name, cs in found:
            ag = [g for p, g in cs if g["type"] == "Agenda" and "set-aside" not in p]
            ac = [g for p, g in cs if g["type"] == "Act" and "set-aside" not in p]
            locs = [g for p, g in cs if g["type"] == "Location"]
            enc = [g for p, g in cs if "encounter deck" in p and g["type"] in ("Enemy", "Treachery")]
            def a(g, k):
                return cards.get(g["id"], {}).get(k)
            doom = [x for x in (a(g, "doom") or g.get("doomThreshold") for g in ag) if isinstance(x, int)]
            clue_acts = [a(g, "clues") or g.get("clueThresholdPerInvestigator") for g in ac]
            clue_acts = [x for x in clue_acts if isinstance(x, int) and x > 0]
            lc = [a(g, "clues") for g in locs if isinstance(a(g, "clues"), int)]
            sh = [a(g, "shroud") for g in locs if isinstance(a(g, "shroud"), int) and a(g, "shroud") >= 0]
            vic = [g for g in locs if a(g, "victory")]
            rows.append({"campaign": camp, "scenario": name, "agendas": len(ag), "total_doom": sum(doom),
                         "acts": len(ac), "clue_acts": len(clue_acts), "act_clues_per_inv": "/".join(map(str, clue_acts)),
                         "locations": len(locs), "victory_locations": len(vic),
                         "loc_clues_mean": round(st.mean(lc), 2) if lc else "", "loc_clues_range": "%s-%s" % (min(lc), max(lc)) if lc else "",
                         "shroud_mean": round(st.mean(sh), 2) if sh else "", "shroud_range": "%s-%s" % (min(sh), max(sh)) if sh else "",
                         "encounter_deck": len(enc)})
    os.makedirs(os.path.join(OUT, "stats"), exist_ok=True)
    with open(os.path.join(OUT, "stats", "scenario_structure.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main():
    fetch()
    cards, sets = load_cards()
    n_rules, words = rules()
    n_faq = errata_faq_taboos(cards)
    index, n_player, n_enc = cards_md(cards, sets)
    n_guides = guides()
    n_scn = structure(cards)
    lines = ["# Arkham Horror: The Card Game — reference library (LCG only)\n",
             "Built by `tools/library/build_library.py` from public LCG data. Not committed (copyright). Search with "
             "`python3 tools/library/search.py <words>`.\n",
             "- `rules/RULES_REFERENCE.md` — the full Rules Reference: %d entries, %d words (contents: `rules/RULES_REFERENCE_CONTENTS.md`)" % (n_rules, words),
             "- `rules/ERRATA.md`, `rules/TABOOS.md`, `rules/faq/*.md` (%d FAQ entries)" % n_faq,
             "- `cards/player/<class>/level_<0-5>.md` and `investigators.md` — %d player cards" % n_player,
             "- `cards/encounter/<cycle>/<set>.md` — %d encounter cards, both sides" % n_enc,
             "- `campaigns/<code>/<scenario>.md` — %d official campaign-guide files (story, setup, resolutions)" % n_guides,
             "- `stats/scenario_structure.csv` — %d official scenarios: doom, acts, clue acts, locations, clues, shroud, deck" % n_scn,
             "", "## Card files", ""] + ["- `%s` (%d)" % (r, n) for r, n in index]
    write("INDEX.md", "\n".join(lines) + "\n")
    print("\n".join(lines[:9]))


if __name__ == "__main__":
    main()
