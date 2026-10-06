#!/usr/bin/env python3
"""synergy_scan.py - which cards can each Still Hour investigator legally take, and what do
those cards do with the investigator's own ability? (designer tooling, read-only)

The review of docs/design/DECKBUILDING_REVIEW.md was a hand search. This tool makes the
search repeatable and complete: it derives each investigator's legal card pool from the
deckbuilding options printed on the investigator's back, tags every card by mechanical
feature with regexes on its rules text, and marks which of the investigator's ability
HOOKS the card touches. The output is a card x investigator table (CSV and JSONL) and a
set of shortlists to read by hand. It does not decide anything: the regexes find
candidates, a person reads the card text (the shortlists print it) before a verdict.

Inputs (all local, none is committed; build them first):
  library/cards/player/**.md        official card text (tools/library/build_library.py)
  library/save_4.9.2/cards.jsonl    cards of the owner's SCED mod (class lists, weakness flag)
  library/save_4.9.2/fan_playercards_cards.jsonl   fan packs the SCED menu offers (metadata only,
                                    the rules text of a fan card is on its image, so fan cards are
                                    checked for legality and traits only)
  library/rules/TABOOS.md           taboo lists (the latest list is used for flags)
  .cache/official/adb/pack/*/*.json OPTIONAL: deck limits, second classes, subtype (when absent
                                    the tool falls back to the SCED class lists and to
                                    "2 copies, 1 if exceptional")
  pipeline/stillhour_cards_spec.json, pipeline/stillhour_print_text.json,
  campaigns/still_hour/card_overrides.json   our own investigators, signature cards, quest cards
                                    and Recollections (merged the way the build merges them)

Usage:
  python3 -I tools/library/synergy_scan.py scan --out DIR    # write tables and shortlists (default command)
  python3 -I tools/library/synergy_scan.py scan --out DIR --quiet --no-text
  python3 -I tools/library/synergy_scan.py show elias --flag self_mill --level 0-5
  python3 -I tools/library/synergy_scan.py show birdie --hook B.free_engine_event --text
  python3 -I tools/library/synergy_scan.py show seraphine --fan --level 0-2     # fan cards: metadata only
  python3 -I tools/library/synergy_scan.py flags             # list the feature flags and hooks
  python3 -I tools/library/synergy_scan.py starters          # check docs/STARTER_DECKS.md against the pools

Output of `scan` (DIR, default .cache/synergy_scan, which is not committed):
  card_x_investigator.csv / .jsonl   one row per (investigator, legal official or Recollection card):
                                     class, level, type, bucket (main / neutral / secondary / recollection),
                                     per-option limit, flags (mechanical features), hooks (which ability of
                                     the investigator the card touches), taboo state, rules text
  fan_x_investigator.csv             the same for the fan packs, from metadata only (no rules text exists
                                     for them, so no flags beyond traits, type, uses and exceptional)
  summary.json                       counts per pool, level, type, bucket, flag and hook
  shortlist_<investigator>.md        every hook with the cards that touch it and their text, to read by hand

Pools follow the Rules Reference: a card in an unlimited option never uses a limited option's slots
("other" options only take cards that fall in no other category); a card with no level (signature,
weakness, story) is never deck-legal through a level range; dual-class cards count as either class;
investigator-restricted and bonded cards are excluded. The taboo list used is the latest one in
library/rules/TABOOS.md (forbidden cards stay in the table, marked taboo=forbidden).

Deterministic: same inputs, same output (sorted, no clocks, no randomness).
"""
import argparse
import collections
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LIB = os.path.join(ROOT, "library")
ADB = os.path.join(ROOT, ".cache", "official", "adb")
SAVE = os.path.join(LIB, "save_4.9.2")

CLASSES = ("guardian", "seeker", "rogue", "mystic", "survivor")
INVESTIGATORS = ("elias", "ayako", "cass", "birdie", "seraphine")
INV_ID = {"elias": "sthrelias", "ayako": "sthrayako", "cass": "sthrcass", "birdie": "sthrbirdie",
          "seraphine": "sthrseraphine"}
INV_NAME = {"elias": "Elias Warde", "ayako": "Dr. Ayako Soma", "cass": "Cass Lindqvist",
            "birdie": "\"Birdie\" Okonkwo", "seraphine": "Seraphine Vale"}


# ======================================================================================
# 1. The official card library (markdown) plus the SCED / arkhamdb / taboo side data
# ======================================================================================

_ATTR_RE = re.compile(r"^\*(exceptional|myriad|permanent|exile|bonded_to|restrictions|deck_requirements|"
                      r"deck_options|errata_date): (.*)\*$")
_SEC_RE = re.compile(r"^\*(Flavor|Back flavor|Back traits|Back|Customization):\*\s?(.*)$")
_META_RE = re.compile(r"^\*(.+?)\* · code (\S+) · (.*)$")


def parse_card_block(block):
    """One '### Name' block of a library card file -> dict (None when it is not a card)."""
    lines = block.split("\n")
    if len(lines) < 2:
        return None
    head = lines[0][4:].strip()
    unique = head.startswith("✷")
    head = head.lstrip("✷ ").strip()
    name, _, sub = head.partition(" — ")
    m = _META_RE.match(lines[1])
    if not m:
        return None
    fields = m.group(1).split(" · ")
    card = {"name": name.strip(), "subname": sub.strip(), "unique": unique, "type": fields[0].strip().lower(),
            "code": m.group(2), "pack": m.group(3).strip()}
    for f in fields[1:]:
        k, _, v = f.partition(" ")
        if k == "icons":
            card["icons"] = {s: v.count("[" + s + "]") for s in ("wil", "int", "com", "agi", "wild")}
        elif k in ("level", "cost", "health", "sanity", "copies", "fight", "evade", "damage", "horror", "shroud"):
            try:
                card[k] = int(v)
            except ValueError:
                card[k] = v
        else:
            card[k] = v
    buf = collections.defaultdict(list)
    sect = "text"
    body = lines[2:]
    if body and re.match(r"^\*\*[^*].*\*\*$", body[0].strip()):
        card["traits_line"] = body[0].strip().strip("*").strip()
        body = body[1:]
    for ln in body:
        am = _ATTR_RE.match(ln.strip())
        if am:
            card.setdefault("attrs", {})[am.group(1)] = am.group(2)
            continue
        sm = _SEC_RE.match(ln)
        if sm:
            sect = sm.group(1).lower().replace(" ", "_")
            buf[sect].append(sm.group(2))
            continue
        buf[sect].append(ln)
    for k, v in buf.items():
        card[k] = "\n".join(v).strip()
    card.setdefault("text", "")
    card["traits"] = [t.strip().lower() for t in re.split(r"\.\s*", card.get("traits_line", "")) if t.strip()]
    return card


def parse_cards_text(text, source=""):
    out = []
    for blk in re.split(r"\n(?=### )", text)[1:]:
        c = parse_card_block(blk)
        if c:
            c["file"] = source
            out.append(c)
    return out


def load_markdown_cards(lib=LIB):
    cards = []
    files = sorted(glob.glob(os.path.join(lib, "cards", "player", "*", "*.md")))
    files.append(os.path.join(lib, "cards", "player", "other_player_side.md"))
    for f in files:
        if os.path.exists(f):
            rel = os.path.relpath(f, os.path.join(lib, "cards", "player"))
            cards += parse_cards_text(open(f, encoding="utf-8").read(), rel)
    return cards


def _jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def norm_name(n):
    n = re.sub(r"\s*\((?:taboo|\d)\)", "", n or "", flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", n.lower().split(" — ")[0]).strip()


def load_sced(save=SAVE):
    """The 'All Player Cards' bag of the owner's SCED save: list of dicts (id, name, meta)."""
    p = os.path.join(save, "cards.jsonl")
    out = []
    if not os.path.exists(p):
        return out
    for d in _jsonl(p):
        if d.get("container") != "All Player Cards":
            continue
        m = d.get("meta") or {}
        if m.get("type") in ("Minicard", "UpgradeSheet", None):
            continue
        out.append({"id": m.get("id"), "name": d.get("name"), "meta": m})
    return out


def load_adb(adb=ADB):
    """Optional arkhamdb json (the source of the library): code -> raw card."""
    out = {}
    for f in sorted(glob.glob(os.path.join(adb, "pack", "*", "*.json"))):
        try:
            for c in json.load(open(f, encoding="utf-8")):
                if c.get("code"):
                    out[c["code"]] = c
        except ValueError:
            continue
    return out


def load_taboo(lib=LIB):
    """code -> dict for the LATEST taboo list in library/rules/TABOOS.md."""
    p = os.path.join(lib, "rules", "TABOOS.md")
    if not os.path.exists(p):
        return {}, ""
    txt = open(p, encoding="utf-8").read()
    lists = re.split(r"\n(?=## Taboo List)", txt)[1:]
    if not lists:
        return {}, ""
    last = lists[-1]
    title = last.split("\n", 1)[0].lstrip("# ").strip()
    out = {}
    for ent in re.split(r"\n(?=- \*\*)", last):
        m = re.match(r"- \*\*(.+?)\*\* \((\w+)\): (.*)", ent, re.S)
        if not m:
            continue
        bits = m.group(3).strip()
        d = {"name": m.group(1), "raw": bits}
        x = re.match(r"XP ([+-]\d+)", bits)
        if x:
            d["xp"] = int(x.group(1))
        t = re.search(r"text: (.*?)(?:; (?:exceptional|forbidden|deck_limit|customization_text):|$)", bits, re.S)
        if t:
            d["text"] = t.group(1).strip()
        if "deck_limit: 0" in bits:
            d["forbidden"] = True
        out[m.group(2)] = d
    return out, title


class OfficialDB(object):
    """Official player cards (one logical card per library code) with SCED and arkhamdb side data."""

    def __init__(self, lib=LIB, adb=ADB, save=SAVE):
        self.cards = load_markdown_cards(lib)
        self.adb = load_adb(adb)
        self.sced = load_sced(save)
        self.taboo, self.taboo_title = load_taboo(lib)
        self.by_code = {c["code"]: c for c in self.cards}
        self._join_sced()
        self._enrich()

    def _join_sced(self):
        bykey = collections.defaultdict(list)
        for c in self.cards:
            bykey[(norm_name(c["name"]), c.get("level"))].append(c)
        self.sced_unmapped = []
        for c in self.cards:
            c["sced_ids"] = []
            c["sced_classes"] = set()
            c["sced_weakness"] = False
        for s in self.sced:
            m = s["meta"]
            sid = s["id"] or ""
            base = re.sub(r"-(t|m|p|pf|pb|c)$", "", sid)
            tgt = self.by_code.get(sid) or self.by_code.get(base)
            if tgt is None:
                key = (norm_name(s["name"]), m.get("level"))
                cand = bykey.get(key) or bykey.get((norm_name(s["name"]), None))
                tgt = cand[0] if cand else None
            if tgt is None:
                self.sced_unmapped.append(s)
                continue
            tgt["sced_ids"].append(sid)
            for k in (m.get("class") or "").split("|"):
                if k:
                    tgt["sced_classes"].add(k.lower())
            if m.get("weakness"):
                tgt["sced_weakness"] = True

    def _enrich(self):
        for c in self.cards:
            a = self.adb.get(c["code"], {})
            attrs = c.get("attrs", {})
            classes = [c.get("class", "neutral")]
            for k in ("faction2_code", "faction3_code"):
                if a.get(k):
                    classes.append(a[k])
            for k in sorted(c["sced_classes"]):
                if k not in classes:
                    classes.append(k)
            c["classes"] = [k for k in classes if k]
            sub = a.get("subtype_code")
            c["weakness"] = bool(sub in ("weakness", "basicweakness") or c["sced_weakness"])
            c["basic_weakness"] = sub == "basicweakness"
            c["exceptional"] = "exceptional" in attrs or bool(a.get("exceptional"))
            c["myriad"] = "myriad" in attrs or bool(a.get("myriad"))
            c["permanent"] = "permanent" in attrs or bool(a.get("permanent")) or bool(re.search(r"\bPermanent\.", c["text"]))
            c["exile"] = "exile" in attrs or bool(a.get("exile"))
            c["restrictions"] = attrs.get("restrictions", "")
            c["bonded_to"] = attrs.get("bonded_to", "")
            c["customizable"] = bool(c.get("customization")) or bool(re.search(r"\bCustomizable\b", c["text"]))
            if a.get("deck_limit") is not None:
                c["deck_limit"] = a["deck_limit"]
            elif c["exceptional"]:
                c["deck_limit"] = 1
            elif c["myriad"]:
                c["deck_limit"] = 3
            else:
                c["deck_limit"] = 2
            lim = re.search(r"\bLimit (\d) per (?:investigator|deck)", c["text"])
            c["limit_per"] = int(lim.group(1)) if lim else None
            c["taboo"] = self.taboo.get(c["code"])


# ======================================================================================
# 2. Our own cards (investigators, signature cards, quest cards, Recollections)
# ======================================================================================

def load_campaign_cards(root=ROOT, campaign="still_hour"):
    """Merge spec + print text + overrides the way the build does (overrides win)."""
    spec = json.load(open(os.path.join(root, "pipeline", "stillhour_cards_spec.json"), encoding="utf-8"))
    pt_path = os.path.join(root, "pipeline", "stillhour_print_text.json")
    ov_path = os.path.join(root, "campaigns", campaign, "card_overrides.json")
    pt = json.load(open(pt_path, encoding="utf-8")) if os.path.exists(pt_path) else {}
    ov = json.load(open(ov_path, encoding="utf-8")) if os.path.exists(ov_path) else {}
    out = {}
    for c in spec:
        m = dict(c)
        m.update(pt.get(c["id"], {}))
        m.update(ov.get(c["id"], {}))
        out[c["id"]] = m
    return out


def campaign_as_card(c):
    """A campaign player card in the same shape as a library card."""
    icons = {"wil": c.get("wilIcons", 0), "int": c.get("intIcons", 0), "com": c.get("comIcons", 0),
             "agi": c.get("agiIcons", 0), "wild": c.get("wildIcons", 0)}
    traits = [t.strip().lower() for t in re.split(r"\.\s*", c.get("traits", "")) if t.strip()]
    text = c.get("text", "") or ""
    uses = c.get("uses") or []
    if uses and not re.search(r"\bUses\b", text):
        text = "Uses (%d %s).\n" % (uses[0].get("count", 0), uses[0].get("type", "charge").lower() + "s") + text
    card = {"name": c.get("name", c["id"]), "subname": c.get("subtitle", ""), "unique": bool(c.get("unique")),
            "type": c.get("type", "asset").lower(), "code": c["id"], "pack": "The Still Hour", "level": c.get("level", 0),
            "cost": c.get("cost"), "slot": c.get("slot", ""), "icons": icons, "traits": traits, "text": text,
            "classes": [c.get("class", "Neutral").lower()], "weakness": bool(c.get("weakness")),
            "basic_weakness": False, "exceptional": False, "myriad": False,
            "permanent": bool(c.get("permanent")) or "Permanent." in text, "exile": False, "restrictions": "",
            "bonded_to": "", "customizable": False, "deck_limit": 2, "limit_per": None, "taboo": None,
            "sced_ids": [], "file": "campaign", "campaign": True, "memory_cost": c.get("memoryCost")}
    if "class" in c:
        card["class"] = c["class"].lower()
    return card


def campaign_player_cards(camp):
    """The Recollections (deck-legal for all five investigators) as library-shaped cards."""
    return [campaign_as_card(c) for c in camp.values()
            if c.get("memoryCost") is not None and "recollection" in c.get("traits", "").lower()]


# ======================================================================================
# 3. Deckbuilding options: parse the printed back text, evaluate arkhamdb-style options
# ======================================================================================

_CLASS_WORDS = {"guardian": "guardian", "seeker": "seeker", "rogue": "rogue", "mystic": "mystic",
                "survivor": "survivor", "neutral": "neutral"}


def _classes_in(s):
    return [k for k in CLASSES if re.search(r"\b" + k + r"\b", s, re.I)]


def _level_range(s):
    m = re.search(r"level (\d)(?:\s*[–—-]\s*(\d))?", s)
    if not m:
        return [0, 5]
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    return [lo, hi]


def parse_back_text(back_text, own_class):
    """Our investigators' printed back -> {'deck_size', 'options', 'requirements'}.

    options use the arkhamdb deck_options vocabulary (faction/trait lists, level {min,max},
    limit) plus a 'bucket' label. Phrases understood (the ones the five backs use):
      'Guardian cards level 0-5'            'Neutral cards level 0-5'
      'up to 5 Survivor cards level 0-2'    'up to 5 other A, B, C and/or D cards level 0-1'
      'up to 5 cards of any other class at level 0'   'any number of Recollection cards'
    """
    t = back_text or ""
    size = re.search(r"Deck Size:\s*(\d+)", t)
    opt_m = re.search(r"Deckbuilding Options:\s*(.*?)(?:\n|$)", t)
    req_m = re.search(r"Deckbuilding Requirements[^:]*:\s*(.*?)(?:\n|$)", t)
    options = []
    if opt_m:
        body = opt_m.group(1).strip().rstrip(".")
        parts = [p.strip() for p in re.split(r",\s*(?=(?:up to|any number|[A-Z]))", body) if p.strip()]
        # the class list inside 'up to 5 other A, B, C and/or D' contains commas: re-join those
        merged = []
        for p in parts:
            if merged and re.match(r"^(?:Guardian|Seeker|Rogue|Mystic|Survivor|Neutral)\b", p, re.I) and \
                    re.match(r"^up to \d+ other", merged[-1]) and "level" not in merged[-1]:
                merged[-1] += ", " + p
            elif merged and re.match(r"^and/or ", p) and "level" not in merged[-1]:
                merged[-1] += ", " + p
            else:
                merged.append(p)
        for p in merged:
            opt = {"text": p}
            lim = re.match(r"up to (\d+)\s+(?:other\s+)?(.*)", p)
            rest = p
            if lim:
                opt["limit"] = int(lim.group(1))
                rest = lim.group(2)
            if re.search(r"any number of (\w+) cards", p):
                opt["trait"] = [re.search(r"any number of (\w+) cards", p).group(1).lower()]
                opt["level"] = {"min": 0, "max": 5}
                opt["bucket"] = "recollection"
            elif re.search(r"any other class", p):
                opt["faction"] = [k for k in CLASSES if k != own_class]
                opt["level"] = dict(zip(("min", "max"), _level_range(p)))
                opt["bucket"] = "secondary"
            else:
                fac = _classes_in(rest)
                if re.search(r"\bNeutral\b", rest, re.I):
                    fac = ["neutral"] + fac
                opt["faction"] = fac
                opt["level"] = dict(zip(("min", "max"), _level_range(p)))
                if "limit" in opt:
                    opt["bucket"] = "secondary"
                elif fac == ["neutral"]:
                    opt["bucket"] = "neutral"
                else:
                    opt["bucket"] = "main"
            options.append(opt)
    reqs = []
    if req_m:
        for r in re.split(r",\s*", req_m.group(1).strip().rstrip(".")):
            r = r.strip()
            if r and not re.match(r"1 random basic weakness", r, re.I):
                reqs.append(r)
    return {"deck_size": int(size.group(1)) if size else 30, "options": options, "requirements": reqs}


def option_matches(card, opt):
    """Does the (library-shaped) card satisfy one arkhamdb-style option? (no limit logic)"""
    if "faction" in opt and opt["faction"]:
        classes = set(card.get("classes") or [card.get("class", "neutral")])
        if not classes & set(opt["faction"]):
            return False
    if "trait" in opt and opt["trait"]:
        if not set(opt["trait"]) & set(card.get("traits", [])):
            return False
    if "type" in opt and opt["type"]:
        if card.get("type") not in opt["type"]:
            return False
    lv = card.get("level")
    if "level" in opt and opt["level"] is not None:
        if lv is None:
            return False
        if not (opt["level"].get("min", 0) <= lv <= opt["level"].get("max", 5)):
            return False
    if "text" in opt and isinstance(opt["text"], list):
        if not any(re.search(rx, card.get("text", "")) for rx in opt["text"]):
            return False
    if "uses" in opt and opt["uses"]:
        if not any(re.search(r"\bUses \(\d+ " + re.escape(u) + r"\b", card.get("text", ""), re.I) for u in opt["uses"]):
            return False
    if "permanent" in opt and opt["permanent"] is not None:
        if bool(card.get("permanent")) != bool(opt["permanent"]):
            return False
    return True


def classify(card, options):
    """(bucket, limit) of the first matching option; unlimited options win over limited ones
    (Rules Reference, Deckbuilding Options: 'other' categories only take cards that fall into no
    other category). None when the card is not legal."""
    for o in options:
        if o.get("not"):
            if option_matches(card, o):
                return None
    free = [o for o in options if not o.get("limit") and not o.get("not") and option_matches(card, o)]
    if free:
        return free[0].get("bucket", "main"), None
    lim = [o for o in options if o.get("limit") and not o.get("not") and option_matches(card, o)]
    if lim:
        return lim[0].get("bucket", "secondary"), lim[0]["limit"]
    return None


def restriction_kinds(card):
    """The kinds ('investigator', 'trait', 'faction') of a card's deck restrictions, with their values."""
    out = []
    for part in (card.get("restrictions") or "").split(","):
        k, _, v = part.strip().partition(":")
        if k:
            out.append((k.strip(), v.strip().lower()))
    return out


def restriction_allows(card, traits, own_class):
    """May an investigator with these traits (lower-case set) and class take the card? 'X, Y deck only'
    cards (trait:x, trait:y) are legal for an investigator who has ANY of the listed traits; a faction
    restriction needs that class; an investigator restriction is a signature card of someone else."""
    ks = restriction_kinds(card)
    if not ks:
        return True
    if any(k == "investigator" for k, _ in ks):
        return False
    ok = True
    tr = [v for k, v in ks if k == "trait"]
    if tr:
        ok = bool(set(tr) & set(traits))
    fa = [v for k, v in ks if k == "faction"]
    if fa:
        ok = ok and own_class in fa
    return ok


def deck_legal_card(card):
    """Rule-level eligibility before any investigator option: a standard player card that has a
    level, is not a weakness, a bonded card or a story card, and is not the signature card of an
    official investigator. Trait-restricted cards ('Sorcerer deck only') stay candidates: whether an
    investigator has the trait is decided per investigator (restriction_allows)."""
    if card.get("type") not in ("asset", "event", "skill"):
        return False
    if card.get("weakness") or card.get("bonded_to"):
        return False
    if any(k == "investigator" for k, _ in restriction_kinds(card)):
        return False
    if card.get("level") is None:
        return False
    return True


# ======================================================================================
# 4. Text normalisation and feature tags
# ======================================================================================

_ICON_WORDS = [
    ("[action]", "<action>"), ("[reaction]", "<reaction>"), ("[fast]", "<free>"), ("[free]", "<free>"),
    ("[willpower]", "willpower"), ("[wil]", "willpower"), ("[intellect]", "intellect"), ("[int]", "intellect"),
    ("[combat]", "combat"), ("[com]", "combat"), ("[agility]", "agility"), ("[agi]", "agility"),
    ("[wild]", "wild"), ("[skull]", "skull"), ("[cultist]", "cultist"), ("[tablet]", "tablet"),
    ("[elder_thing]", "elder_thing"), ("[elder_sign]", "elder_sign"), ("[auto_fail]", "auto_fail"),
    ("[bless]", "bless"), ("[curse]", "curse"), ("[frost]", "frost"), ("[per_investigator]", "per_investigator"),
    ("[guardian]", "guardian"), ("[seeker]", "seeker"), ("[rogue]", "rogue"), ("[mystic]", "mystic"),
    ("[survivor]", "survivor"),
]


def norm_text(t):
    """Lower-case rules text with markdown and icon markup turned into plain words.
    Triggered-ability icons become <action>, <reaction>, <free> (the library prints a free
    triggered ability as [fast]; the 'Fast.' keyword stays the word 'fast')."""
    t = t or ""
    t = t.replace("**", "").replace("*", "")
    for a, b in _ICON_WORDS:
        t = t.replace(a, b)
    t = t.replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[ \t]+", " ", t)
    return t.lower()


def split_lines(ntext):
    return [ln.strip() for ln in ntext.split("\n") if ln.strip()]


def split_ability(line):
    """('action'|'reaction'|'free'|'forced', cost-or-trigger, effect) or None."""
    m = re.match(r"^<(action|reaction|free)>(.*)$", line)
    kind = None
    rest = None
    if m:
        kind, rest = m.group(1), m.group(2)
    else:
        m = re.match(r"^forced - (.*)$", line)
        if m:
            kind, rest = "forced", m.group(1)
    if kind is None:
        return None
    cost, sep, effect = rest.partition(":")
    if not sep:
        return kind, "", rest.strip()
    return kind, cost.strip(), effect.strip()


_PLAY_COND = re.compile(r"^(?:fast\. )?(?:play|commit) (?:only )?(?:when|after|before|during|if|at|as|between|immediately)\b|^commit only\b|^play only\b")


def card_parts(card):
    """(all, cost, effect) normalised text of the card. 'cost' = what is before the colon of its
    triggered/forced abilities plus its 'additional cost' sentences; 'effect' = the rest. Sentences that only
    say WHEN a card may be played ('Fast. Play when you draw...') are in 'all' but in neither of the other two,
    so a trigger condition is not mistaken for an effect."""
    text = card.get("text", "")
    cust = card.get("customization", "") or ""
    ntext = norm_text(text)
    ncust = norm_text(cust)
    cost_parts, eff_parts = [], []
    for ln in split_lines(ntext):
        ab = split_ability(ln)
        if ab:
            cost_parts.append(ab[1])
            eff_parts.append(ab[2])
        else:
            for sent in re.split(r"(?<=[.!?]) ", ln):
                if "additional cost" in sent:
                    cost_parts.append(sent)
                elif _PLAY_COND.match(sent.strip()):
                    continue
                else:
                    eff_parts.append(sent)
    return ntext + ("\n" + ncust if ncust else ""), "\n".join(cost_parts), "\n".join(eff_parts) + ("\n" + ncust if ncust else "")


_N = r"(?:\d+|x|an?|one|two|three|four|five|six|up to \d+|that many|twice that many|all|each)"

# (flag, scope, regex, description)
FEATURES = []


def _f(flag, scope, rx, desc):
    FEATURES.append((flag, scope, re.compile(rx, re.I | re.S), desc))


# ---- resources, cards, actions, tempo
_f("gain_resources", "effect", r"\bgains? (?:up to |an additional |a total of |\d+ additional |that many |twice that many |double )?(?:\d+|x|an?|one|two|three)?[^.:;]{0,18}\bresources?\b|\bgain resources\b|\btake (?:control of )?(?:\d+|x) resources? from\b|\bresources equal to\b|\bresource for each\b",
   "gains resources (effect)")
_f("resource_boost_upkeep", "all", r"additional resource during (?:each )?the upkeep|collect (?:\d+ )?additional resource", "extra upkeep income")
_f("draw_cards", "effect", r"\bdraws? (?:up to )?(?:\d+|x|an?|one|two|three|that many|cards|each|the top|1 additional)\b|\bdraw (?:\d+ )?additional\b|\bdraws? it\b|\band draw\b|\bdraw 1 card\b|\bdraw cards\b",
   "draws cards")
_f("search_deck", "all", r"\bsearch (?:your |the top |each |the )?(?:\d+ |x )?(?:cards? of )?(?:your )?(?:deck|investigator deck|top)\b|\bsearch your deck\b|\bsearch the top\b", "searches the deck")
_f("extra_action", "all", r"\b(?:take|gain|get|have|receive|perform|giving) (?:an |one |1 |2 |two |3 |three |x |that many |up to \d+ )?(?:\d+ )?(?:additional|extra|bonus) actions?\b|\b(?:immediately )?take an action as if it were (?:your|their|his or her) turn|\btake another action\b|\bmay take (?:\d+|that many) additional actions|\badditional (?:\d+ )?actions? (?:this|during)\b|\bgains? 1 additional action",
   "grants an extra action")
_f("action_refund", "all", r"without spending an action|ignoring (?:its |their |the |all )?(?:\[?action\]? )?costs?|ignore (?:its |their |the )?(?:action )?costs?|does not (?:cost|take) an action|do not count toward the number of actions|this action does not count|for no actions?|at no (?:action )?cost|does not count as an action|without paying|\bundo that action\b",
   "performs something without its action cost (or undoes an action)")
_f("free_ability", "all", r"(?:^|\n)<free>", "has a free triggered ability")
_f("fast_event", "all", r"(?:^|\n)fast\b", "Fast event or asset (played for no action)")
_f("action_ability", "all", r"(?:^|\n)<action>", "has an [action] ability")
_f("reaction_ability", "all", r"(?:^|\n)<reaction>", "has a reaction ability")
_f("ready", "effect", r"\bready\b(?! of| to)(?!ing its)", "readies an exhausted card")
_f("exhaust_cost", "cost", r"\bexhaust\b", "exhausts as a cost")
_f("cost_reduction", "all", r"\breduc(?:e|es|ed|ing) (?:its|the|their|that card's|this card's|your)?[^.]{0,30}\bcost\b|\bat -\d+ cost|\bcosts? (?:\d+|x) (?:resources? )?(?:less|fewer)\b|\b(?:pay|spend) (?:\d+|x) (?:resources? )?(?:less|fewer)\b|\bfor free\b|\bwithout (?:paying|spending)[^.]{0,15}\bcost|\bignoring all costs?\b|\bcost[^.]{0,20}\bis reduced\b",
   "reduces or removes resource costs")
_f("return_to_hand", "all", r"\breturns? (?:it|that|this|them|[a-z' ]{1,40}) to (?:its owner's|your|their|his or her|an investigator's) hand|\badd (?:it|that|them|this|[a-z' ]{1,40}) to (?:your|its owner's|their) hand|\bshuffle[^.]{0,30}into your hand",
   "returns a card to hand")
_f("return_from_discard", "all", r"\b(?:from|in) (?:your|their|an investigator's|his or her) discard pile\b[^.]{0,60}\b(?:to|into) (?:your|their|its owner's) (?:hand|deck)|\bfrom your discard pile\b[^.]{0,40}\b(?:add|return|draw|take|put)|\b(?:add|return|take|draw) [^.]{0,40}from your discard pile",
   "retrieves from the discard pile")
_f("play_from_discard", "all", r"\bplay (?:an? |a |the |one |up to \d+ |each )?[^.]{0,50}\bfrom your discard pile|\bplayed? from your discard pile|can only be played from your discard pile|\bfrom your discard pile[^.]{0,40}\bplay\b",
   "plays a card from the discard pile")
_f("discard_pile_payoff", "all", r"\bcards? in your discard pile\b|\bdiscard pile\b.{0,40}\b(?:for each|number of|equal to)|\b(?:for each|number of|equal to)[^.]{0,40}\bdiscard pile",
   "counts or uses the discard pile")
_f("self_mill", "all", r"\bdiscards? (?:the )?top (?:\d+|x|cards?|one|two|three)[^.]{0,30}of your deck|\bdiscard (?:the )?top card[^.]{0,20}of your deck|\bdiscard cards? from the top of your deck|\bdiscard [^.]{0,30}from (?:the top of )?your deck\b|\bdiscard (?:the )?top (?:\d+|x) cards",
   "discards from the top of its own deck")
_f("deck_refill", "all", r"\bshuffle (?:your |a |the |that |it |them |each |up to |\d+ )?[^.]{0,50}\b(?:into|back into|in) your deck|\bshuffle your discard pile|\bplace[^.]{0,40}\bon the bottom of your deck|\bput[^.]{0,40}\bon (?:top|the bottom) of your deck|\bplace[^.]{0,30}on top of your deck|\breturn[^.]{0,40}to your deck",
   "puts cards back into the deck")
_f("top_deck_look", "all", r"\blook at the top|\breveal the top|\bplay with the top card|\bthe top (?:\d+|x)? ?cards? of your deck\b", "looks at or reveals deck cards")
_f("deck_out", "all", r"\b(?:your deck|investigator deck) (?:is empty|has no cards|runs out)|\bno cards in your deck|\bempty deck", "mentions an empty deck")
_f("discard_from_hand_cost", "cost", r"\bdiscard (?:an? |\d+ |x |up to \d+ |one |two |each |all |any number of )?(?:[a-z*\- ]{0,25})?cards?(?: with[^:]{0,40})? from (?:your )?hand|\bdiscard (?:a|an|\d+|x|one|two) [a-z]+ cards?\b|\bdiscard \d+ cards?",
   "discards cards from hand as a cost")
_f("discard_from_hand_effect", "effect", r"\bdiscards? (?:\d+|x|an?|one|two|three|all|up to \d+|that many|any number of) [^.]{0,30}cards? (?:at random )?from (?:your|their|his or her) hand|\bdiscard (?:your|their) hand",
   "discards cards from hand as an effect")
_f("hand_size", "all", r"maximum hand size|max hand size|hand size", "changes hand size")
_f("spend_resources_cost", "cost", r"\bspend (?:\d+|x|up to \d+|any number of) resources?|\bpay (?:\d+|x) resources?", "pays resources as a cost")
_f("spend_resources_effect", "effect", r"\bspend (?:\d+|x|up to \d+|any number of) resources?", "spends resources as an effect")

# ---- defence and health
_f("prevent_damage", "all", r"\bprevent\b[^.]{0,40}\b(?:damage|horror)|\bprevent (?:that|the|all|up to|\d+)\b", "prevents damage/horror")
_f("cancel_damage_horror", "all", r"\bcancels? (?:up to |all |that much |\d+ |x |that |the )?[^.]{0,30}\b(?:damage|horror)\b|\bcancel [^.]{0,30}damage|\breduce[^.]{0,20}(?:damage|horror)[^.]{0,20}by",
   "cancels or reduces damage/horror just dealt")
_f("cancel_attack", "all", r"\bcancel (?:that|the|an|this) (?:enemy )?attack\b|\bcancel that attack|\bcancel the attack", "cancels an enemy attack")
_f("cancel_revelation", "all", r"\bcancel (?:its|that|a|the|that card's|a card's|this card's|the card's) (?:card's )?(?:revelation|effect)|\bcancel (?:its|that|the) revelation|\bcancel[^.]{0,30}\brevelation", "cancels a revelation or effect")
_f("cancel_other", "all", r"\bcancel(?:s|led|ed|ing)?\b", "mentions cancel")
_f("soak_health_sanity", "all", r"\bassign(?:ed|s)? (?:it|that|the|up to \d+|\d+|any|as much|damage|horror)[^.]{0,30}(?:to|from)|\bassigned to (?:an|the|your|this)|\bdamage[^.]{0,20}(?:to|on) (?:an? |another )?(?:ally|asset)[^.]{0,15}instead|\btake (?:that|the) damage instead|\binstead of (?:you|the investigator|them)[^.]{0,20}(?:taking|take)|\bmove[^.]{0,30}(?:damage|horror)[^.]{0,30}(?:to|from)|\breassign",
   "reassigns or soaks damage/horror")
_f("heal_damage", "all", r"\bheals? (?:up to |all |that much |that |\d+ |x |1 )?[^.]{0,40}\bdamage\b|\bheal (?:\d+|x|all|1) (?:damage|horror)|\bheal that much damage|\bheals? damage",
   "heals damage")
_f("heal_horror", "all", r"\bheals? (?:up to |all |that much |that |\d+ |x |1 )?[^.]{0,40}\bhorror\b|\bheals? (?:\d+|x|all|1) (?:damage and |damage or )?horror|\bheal that much horror|\bheals? horror",
   "heals horror")
_f("max_health_sanity", "all", r"\bmaximum (?:health|sanity)\b|\b\+\d+ (?:maximum )?(?:health|sanity)\b|\bget(?:s)? \+\d+ (?:maximum )?(?:health|sanity)|\bgain(?:s)? \+\d+ (?:maximum )?(?:health|sanity)",
   "changes maximum health or sanity")
_f("immune_cannot_take", "all", r"\bcannot (?:take|be dealt|be assigned) (?:damage|horror|any damage|any horror)|\bimmune to|\bcannot be (?:damaged|dealt damage)|\bdoes not take (?:damage|horror)|\bcannot be defeated\b|\bnot defeated\b|\byou are not defeated",
   "cannot take damage/horror or be defeated")
_f("direct_damage", "all", r"\bdirect damage\b", "direct damage")
_f("direct_horror", "all", r"\bdirect horror\b", "direct horror")
_f("take_damage_cost", "cost", r"\b(?:you )?(?:take|suffer) (?:up to )?(?:\d+|x|1|an?) (?:direct )?(?:physical )?damage\b|\btake (?:up to )?\d+ damage|\btake damage\b",
   "the investigator pays damage as a cost")
_f("take_horror_cost", "cost", r"\b(?:you )?(?:take|suffer) (?:up to )?(?:\d+|x|1|an?) (?:direct )?(?:mental )?horror\b|\btake (?:up to )?\d+ horror|\btake horror\b",
   "the investigator pays horror as a cost")
_f("asset_damage_cost", "cost", r"\bdeal (?:\d+|x|1) (?:damage|horror) to (?:it|him|her|this|[a-z' ]{2,30})\b",
   "an asset pays damage/horror as a cost")
_f("take_damage_effect", "effect", r"\b(?:you |that investigator |each investigator |an investigator )?(?:takes?|suffers?) (?:\d+|x|1|an? |that much|up to \d+)[^.]{0,12}(?:direct )?damage\b|\bdeals? (?:\d+|x|1) (?:direct )?damage to (?:you|that investigator|an investigator|each investigator)",
   "causes damage to an investigator")
_f("take_horror_effect", "effect", r"\b(?:you |that investigator |each investigator |an investigator )?(?:takes?|suffers?) (?:\d+|x|1|an? |that much|up to \d+)[^.]{0,12}(?:direct )?horror\b|\bdeals? (?:\d+|x|1) (?:direct )?horror to (?:you|that investigator|an investigator|each investigator)",
   "causes horror to an investigator")
_f("trigger_on_damage", "all", r"\b(?:after|when|if) (?:you|your investigator|an investigator|another investigator|an investigator at your location)[^.:]{0,40}\b(?:take|takes|taken|are dealt|is dealt|dealt|placed on you|are assigned)[^.:]{0,25}\bdamage\b|\bafter (?:1 or more )?damage is placed on|\bwhen (?:you are |an investigator is )?dealt damage|\bfor each damage on (?:you|him|her)|\bdamage on (?:you|your investigator)\b|\bwhen you are dealt damage|\bafter you take damage",
   "triggers on damage taken")
_f("trigger_on_horror", "all", r"\b(?:after|when|if) (?:you|your investigator|an investigator|another investigator|an investigator at your location)[^.:]{0,40}\b(?:take|takes|taken|are dealt|is dealt|dealt|placed on you|are assigned)[^.:]{0,25}\bhorror\b|\bafter (?:1 or more )?horror is placed on|\bwhen (?:you are |an investigator is )?dealt horror|\bfor each horror on (?:you|him|her)|\bhorror on (?:you|your investigator)\b|\bwhen you are dealt damage and/or horror|\bafter you take damage and/or horror|\bafter you take horror",
   "triggers on horror taken")
_f("trigger_on_damage_horror", "all", r"\b(?:after|when) you (?:are dealt|take|have taken|have been dealt) damage and/or horror|\bwhen[^.:]{0,30}is dealt damage and/or horror|\bwhen damage and/or horror",
   "triggers on damage and/or horror")
_f("lose_or_defeat", "all", r"\byou would be defeated\b|\bwould be defeated\b|\bdefeated by (?:damage|horror)", "defeat prevention window")

# ---- tests, stats, tokens
_f("skill_bonus", "all", r"\b(?:you )?gets? \+\d+ (?:skill value|willpower|intellect|combat|agility|wild|to each of your skills|[a-z]+ for)|\+\d+ (?:skill value|willpower|intellect|combat|agility)|\bskill value\b",
   "adds skill value")
_f("stat_substitution", "all", r"\bin place of (?:your |their )?(?:printed )?(?:willpower|intellect|combat|agility)|\binstead of (?:your |their )?(?:printed )?(?:willpower|intellect|combat|agility) (?:for|when|while)|\buse (?:your |their )?(?:willpower|intellect|combat|agility) (?:instead|in place)|\btest (?:willpower|intellect|combat|agility) (?:instead|in place)|\bsubstitut",
   "substitutes one skill for another")
_f("fight_action", "all", r"\bfight\b", "fights an enemy")
_f("evade_action", "all", r"\bevade\b|\bevading\b|\bevasion\b|\bevaded\b", "evades / evasion")
_f("investigate_action", "all", r"\binvestigate\b|\binvestigat(?:ing|ion)\b", "investigates")
_f("auto_succeed", "all", r"\bautomatically succeed|\bautomatically evade|\bautomatically (?:succeeds|win)", "automatic success or evade")
_f("auto_fail_self", "all", r"\bautomatically fail|\bauto-?fail (?:this|the|that) (?:skill )?test|\bwould fail", "mentions automatic failure or would-fail")
_f("discover_clue", "all", r"\bdiscovers? (?:(?:\d+|x|an?|one|two|three|up to \d+|that many|\d+ additional|1 additional|an additional|all|each|the last|a total of \d+|\d+ total) )?(?:additional |total )?clues?\b|\bdiscover (?:clues|a clue)\b",
   "discovers clues")
_f("clue_manip", "all", r"\bplaces? (?:\d+|x|1|that many|up to \d+)? ?(?:of )?(?:your )?clues?\b|\btake (?:a|1) clue|\bmove (?:\d+|1|x|that many)? ?clues?|\bclues? from (?:an enemy|your location|an investigator)|\bspend (?:\d+|x|1) clues?|\bgain (?:\d+|x|1) clues?|\bplace [^.]{0,20}clue",
   "moves, spends or gains clues")
_f("damage_to_enemy", "all", r"\bdeals? (?:\d+|x|1|an? |that much |up to \d+|that many )?(?:additional |extra )?(?:direct )?damage to (?:an? |that |the |each |another )?(?:non-elite )?(?:enemy|enemies|attacked enemy|targeted enemy)|\bdeals? \+?\d+ damage|\bdeals? damage|\bthis attack deals \+?\d+|\+\d+ damage\b",
   "deals damage to enemies / extra damage")
_f("enemy_disable", "all", r"\bdisengage\b|\bexhaust (?:that|the|an|target|each|attached)? ?(?:non-elite )?enem|\bprevent[^.]{0,40}(?:ready|attack)|\bdoes not ready\b|\bcannot (?:attack|ready|move|engage)",
   "disables enemies")
_f("engage_enemy", "all", r"\bengage\b|\bengaged with\b|\bmove (?:that|an|the) enemy\b|\bto your location\b[^.]{0,20}\bengage", "engages or moves enemies")
_f("enemy_at_location", "all", r"\benem(?:y|ies) (?:at|engaged with|in) your location|\benemy at your location|\benemy engaged with you|\bat a location (?:with|containing) an? enemy|\bwhile an enemy", "mentions enemies at or engaged with you")
_f("at_your_location", "all", r"\bat your location\b", "affects investigators at your location")
_f("if_fail", "all", r"\bfail(?:s|ed|ing)?\b|\bif you do not succeed\b|\bnot successful\b|\bunsuccessful\b",
   "mentions failing a test (triggered or modified by failure)")
_f("fail_trigger", "all", r"\b(?:after|when) you fail|\bif you fail(?: a skill test)? by|\bif you failed|\bhave failed\b", "reacts to your failing a test")
_f("succeed_trigger", "all", r"\b(?:after|when) you (?:successfully |succeed)|\bif you succeed|\bif this test succeeds|\bif this skill test is successful|\bsucceeds? by", "reacts to success")
_f("margin_trigger", "all", r"\bby (?:exactly )?\d+ or (?:more|less)\b|\bby exactly \d\b|\bfail(?:s|ed)? by\b|\bsucceed(?:s|ed)? by\b", "depends on the margin of a test")
_f("token_cancel", "all", r"\bcancel(?:s)? (?:that|the|a|this|any|each|up to \d+|1 or more|those)?[^.]{0,20}(?:chaos )?tokens?\b|\bcancel (?:it|that)\b[^.]{0,30}\btoken|\b(?:cancel|ignore)[^.]{0,30}(?:chaos token|token)\b",
   "cancels or ignores chaos tokens")
_f("token_reroll", "all", r"\breturn (?:it|that token|the token)[^.]{0,20}(?:to the (?:chaos )?bag|to the token pool)[^.]{0,20}reveal (?:a|another|new|1)|\breveal (?:a new|another) (?:chaos )?token|\breveal (?:a|1) new\b",
   "redraws a chaos token")
_f("token_reveal_extra", "all", r"\breveal (?:\d+|x|an? additional|1 additional|another|two|three|\w+) (?:additional |random )?(?:chaos )?tokens?|\bone additional (?:chaos )?token|\bresolve (?:\d|two|three) (?:chaos )?tokens",
   "reveals extra chaos tokens")
_f("token_seal", "all", r"\bseals?\b|\bsealed\b", "seals chaos tokens")
_f("token_look", "all", r"\blook at (?:the )?(?:top )?(?:\d+|x)? ?(?:chaos )?tokens?|\b(?:choose|name) (?:a|an|one|1)[^.]{0,20}(?:chaos )?token|\bsearch the chaos bag|\bchaos bag\b",
   "looks at, names or searches chaos tokens")
_f("symbol_token", "all", r"\bsymbol\b|\bskull\b|\bcultist\b|\btablet\b|\belder_thing\b", "mentions symbol tokens")
_f("elder_sign_token", "all", r"\belder_sign\b", "mentions the elder sign token")
_f("auto_fail_token", "all", r"\bauto_fail\b|\bautofail\b", "mentions the auto-fail token")
_f("token_reveal_trigger", "all", r"\b(?:after|when) (?:you |an investigator |a player )?(?:reveal|reveals|revealed) (?:an? |1 or more |one or more |that )?(?:non-)?(?:\w+ )?(?:chaos )?(?:symbol |token|tokens)|\bwhen (?:a|an|1 or more) [^.:]{0,40}(?:symbol|token)[^.:]{0,20} (?:is|are) revealed|\bafter (?:a|an|1 or more|you reveal)[^.:]{0,40}(?:symbol|token)",
   "triggers when a chaos token is revealed")
_f("bless_curse", "all", r"\bbless\b|\bcurse\b|\bblessed\b|\bcursed\b", "bless/curse tokens")
_f("add_bless_curse", "all", r"\badd (?:\d+|x|1|an? |up to \d+|1-3|that many)[^.]{0,20}(?:bless|curse)|\bremove (?:\d+|x|1|an? |up to \d+)[^.]{0,20}(?:bless|curse)", "adds or removes bless/curse tokens")

# ---- doom, uses, limits, misc
_f("doom_manip", "all", r"\bdoom\b", "places, moves or removes doom")
_f("uses_charges", "all", r"\buses \(\d+ charges?\)|\buses \(x charges?\)", "has charges")
_f("uses_ammo", "all", r"\buses \(\d+ ammo\)", "has ammo")
_f("uses_secrets", "all", r"\buses \(\d+ secrets?\)", "has secrets")
_f("uses_supplies", "all", r"\buses \(\d+ supplies?\)|\buses \(\d+ supply\)", "has supplies")
_f("uses_other", "all", r"\buses \(\d+ (?!charges?|ammo|secrets?|supplies?|supply)[a-z]+\)", "has another kind of use")
_f("replenish", "all", r"\breplenish|\bplace (?:\d+|x|1) (?:charges?|secrets?|ammo|supplies|supply|evidence|offerings?|resources?)[^.]{0,30}\bon\b|\badd (?:\d+|x|1) (?:charges?|secrets?|ammo|supplies) to",
   "refills uses")
_f("limit_round", "all", r"limit (?:once |twice |\d+ times? |one time |1 time )?per round|\bonce per round|\blimit once per round|\blimit twice per round|\bmax(?:imum)? (?:once|twice|\d+) per round|\bmax \d per round|\(limit \d per round|\blimit \d+ per round|\blimit once each round",
   "has a per-round limit")
_f("limit_game", "all", r"\bmax(?:imum)? (?:once|twice|\d+) per (?:game|scenario)|\blimit (?:once |twice |\d+ times? |1 )?per (?:game|scenario)|\bonce per (?:game|scenario)|\bonce each game|\blimit once per game|max once per game",
   "has a per-game limit")
_f("limit_turn_phase", "all", r"\blimit (?:once |twice |\d+ times? )?per (?:turn|phase)|\bonce per (?:turn|phase)|\bmax(?:imum)? (?:once|twice|\d+) per (?:turn|phase)|\bonce each turn|\blimit once per turn|\blimit once per phase",
   "has a per-turn or per-phase limit")
_f("limit_test", "all", r"\blimit (?:once |twice |\d+ times? )?per (?:test|attack|ability)|\bmax(?:imum)? (?:once|1|\d+) (?:committed )?per (?:skill )?test|\bmax 1 committed|\bonce per test",
   "has a per-test limit")
_f("no_limit_wording", "all", r"\byou may do this any number of times|\bany number of times\b", "may repeat any number of times")
_f("remove_from_game", "all", r"\bremove [^.]{0,30}from the game|\bexile\b|\bremoved from the game", "removes itself from the game")
_f("play_restriction", "all", r"\bplay only\b|\bonly (?:during|if|when|after|before)\b", "has play restrictions")
_f("repeat_ability", "all", r"\b(?:resolve|trigger|use|activate|perform)[^.]{0,40}\b(?:again|a second time|twice)\b|\bagain\b[^.]{0,30}\b(?:ability|action|effect)\b|\banother time\b",
   "repeats an ability or action")
_f("parley_action", "all", r"\bparley\b", "parley")
_f("move_action", "all", r"\bmove (?:to|up to|\d+|x|an investigator|that investigator|you|another investigator)\b|\bmoves? (?:to )?(?:a|an) (?:connecting )?location|\bmove to\b", "moves investigators")
_f("copy_ability", "all", r"\bcopy\b|\bas if (?:you were|it were|they were) (?:at|a copy|the)|\btreat [^.]{0,30} as if", "copies or treats-as effects")
_f("optional_self_harm_for_value", "all", r"\byou may (?:take|suffer) (?:\d+|1|an?) (?:direct )?(?:damage|horror)[^.]{0,20}\.? ?(?:if you do|to)|\btake (?:1|\d+) (?:damage|horror)[^.]{0,30}to (?:gain|draw|ready|deal|discover|get|cancel|reduce|play|ignore|place)",
   "takes damage/horror for a bonus")
_f("heal_other_investigator", "all", r"\bhealed? [^.]{0,40}(?:another investigator|investigator at your location|from an investigator)|\bchoose (?:an|another) investigator at your location[^.]{0,40}heal", "heals other investigators")
_f("any_investigator_at_location", "all", r"\binvestigators? at your location|\banother investigator at your location|\bat your location\b", "works for investigators at your location")
_f("ally_asset", "all", r"\bally\b", "mentions allies")
_f("commit_effect", "all", r"\bwhen you commit|\bwhile (?:this card |[a-z ]+ )?is committed|\bcommitted to (?:a|this|your) skill test|\bcommit(?:ted)? (?:this|it)", "has an effect when committed")
_f("skill_icons_wild", "all", r"\bwild\b", "mentions wild icons")
_f("play_event_trigger", "all", r"\b(?:after|when) you play (?:an?|a) (?:\w+ )?(?:event|spell|asset|card)|\bafter you play\b", "triggers on playing cards")
_f("evade_trigger", "all", r"\b(?:after|when) you (?:successfully )?evade", "triggers on evading")
_f("defeat_trigger", "all", r"\b(?:after|when) you (?:defeat|kill)|\bafter an? (?:enemy|non-elite enemy) (?:at your location )?is defeated", "triggers on defeating an enemy")
_f("discover_trigger", "all", r"\b(?:after|when) you (?:successfully )?(?:investigate|discover)|\bafter you discover", "triggers on investigating/discovering")
_f("draw_trigger", "all", r"\b(?:after|when) you draw|\bwhen you draw|\bafter you draw", "triggers on drawing")
_f("shuffle_deck", "all", r"\bshuffle your deck\b|\bshuffle the (?:remaining )?cards? (?:back )?into your deck", "shuffles the deck")
_f("xp_effect", "all", r"\bexperience\b", "gains, saves or changes experience (Memory in this campaign)")
_f("trauma_effect", "all", r"\btrauma\b", "refers to trauma (the campaign has none)")
_f("campaign_log_ref", "all", r"\bcampaign log\b|\bcampaign mode\b|\brecord (?:in|that)|\bresearched\b", "refers to the Campaign Log or campaign mode")
_f("checkbox_effect", "all", r"\bcheckbox|\bupgrade sheet", "marks customization checkboxes")
_f("doom_on_card", "all", r"\bplace (?:\d+|x|1) doom on|\badd (?:\d+|x|1) doom to|\bplaces? 1 doom|\bdoom on (?:it|this|him|her)\b", "puts doom on a card (counts toward the Hour threshold)")
_f("agenda_ref", "all", r"\b(?:the |current |final )?agenda\b|\bdoom threshold\b", "refers to the agenda (the Hours)")
_f("symbol_dig", "all", r"\buntil a (?:token with a )?symbol\b|\buntil a (?:\[?skull|symbol)|\buntil (?:a|you reveal a) (?:skull|symbol)|\bsymbol token is revealed\b[^.]{0,30}resolve that token|reveal tokens (?:from the chaos bag )?until", "digs the bag for a symbol token (the Static token is one)")
_f("self_defeat", "all", r"\byou are defeated\b|\bis defeated and suffer|\bsuffer \d+ (?:physical|mental) trauma", "defeats or eliminates the investigator")
_f("exile_kw", "all", r"\bexile\b", "exiles itself (must be bought again)")
_f("spell_engine", "all", r"(?:\bspell\b|\britual\b).{0,280}(?:\bagain\b|\bignoring\b|without paying (?:its|their) [<\[]?action[>\]]? cost|\badd \d+ charges?\b|\breplenish\b|\bready\b)|(?:\bagain\b|\bignoring\b|\breplenish\b|\bready\b).{0,280}(?:\bspell\b|\britual\b)",
   "repeats, readies, refills or discounts Spell abilities")
_f("pay_life_for_value", "all", r"\btake (?:1|\d+) (?:direct )?(?:damage|horror)[^.:]{0,40}:", "pays damage/horror before the colon")


def tag_card(card):
    """Set of feature flags for a library-shaped card (rules text only; fan cards have none)."""
    allt, cost, eff = card_parts(card)
    tab = {"all": allt, "cost": cost, "effect": eff}
    flags = {flag for flag, scope, rx, _ in FEATURES if rx.search(tab[scope])}
    traits = set(card.get("traits", []))
    for tr in ("spell", "weapon", "tool", "ally", "charm", "relic", "tome", "item", "insight", "tactic", "trick",
               "gambit", "ritual", "talent", "illicit", "improvised", "fortune", "favor", "occult", "science",
               "spirit", "blessed", "cursed", "firearm", "melee", "supply", "innate", "practiced", "expert",
               "composure", "developed", "recollection"):
        if tr in traits:
            flags.add("trait_" + tr)
    typ = card.get("type")
    flags.add("type_" + str(typ))
    if card.get("permanent"):
        flags.add("permanent")
    if card.get("exceptional"):
        flags.add("exceptional")
    if card.get("myriad"):
        flags.add("myriad")
    if card.get("customizable"):
        flags.add("customizable")
    if card.get("exile"):
        flags.add("exile")
    if card.get("taboo"):
        flags.add("taboo")
        if card["taboo"].get("forbidden"):
            flags.add("taboo_forbidden")
    if typ == "asset" and card.get("health") not in (None, ""):
        flags.add("has_health")
    if typ == "asset" and card.get("sanity") not in (None, ""):
        flags.add("has_sanity")
    if typ == "asset" and "ally" in traits and "has_sanity" in flags:
        flags.add("ally_sanity_soak")
    return flags


def positive_value(flags):
    """Flags that make a repeated play of an event worth something by itself."""
    return flags & {"gain_resources", "draw_cards", "extra_action", "discover_clue", "heal_damage", "heal_horror",
                    "action_refund", "ready", "cost_reduction", "search_deck", "skill_bonus", "damage_to_enemy",
                    "cancel_damage_horror", "cancel_attack", "cancel_revelation", "token_cancel", "token_reroll"}


# ======================================================================================
# 5. Hooks: where a card touches an investigator's own ability
# ======================================================================================
# Derived from docs/design/PORTABLE_INVESTIGATORS.md (fronts as printed). Each entry is
# (hook id, why it matters, predicate(card, flags)).

def _any(*names):
    return lambda c, f: bool(f & set(names))


def _all(*names):
    return lambda c, f: set(names) <= f


HOOKS = {
    "elias": [
        ("E.mill_deck", "discards its own deck from the top: stacks with his 3-card prevention spend and his elder sign (deck-out)",
         _any("self_mill")),
        ("E.deck_cycle", "draws or searches the deck: spends the same resource his prevention does (deck-out pressure)",
         lambda c, f: bool(f & {"draw_cards", "search_deck", "top_deck_look", "shuffle_deck"}) and c.get("type") != "skill"),
        ("E.deck_refill", "puts cards back into the deck: refills what his ability spends",
         _any("deck_refill")),
        ("E.discard_payoff", "uses or counts the discard pile he fills (the reason for the Survivor slots)",
         _any("play_from_discard", "return_from_discard", "discard_pile_payoff")),
        ("E.mitigation", "prevents, cancels, soaks or reassigns damage: stacks or competes with his once-per-round prevention",
         _any("prevent_damage", "cancel_damage_horror", "soak_health_sanity", "immune_cannot_take", "cancel_attack")),
        ("E.damage_payoff", "pays off when damage is taken or dealt: wants the damage his ability prevents",
         _any("trigger_on_damage", "trigger_on_damage_horror")),
        ("E.self_damage", "damage taken as a cost or for value: prevention could pay it back",
         _any("take_damage_cost", "optional_self_harm_for_value")),
        ("E.heal_damage", "heals damage: stacks with his elder sign heal",
         _any("heal_damage")),
        ("E.elder_sign", "names the elder sign token: interacts with his +3 / discard-2 elder sign",
         _any("elder_sign_token")),
    ],
    "ayako": [
        ("A.stat_swap", "swaps one skill for another: redundant with, or stacking on, her int-for-combat/agility swap",
         _any("stat_substitution")),
        ("A.damage_source", "attack or damage card whose bonus her intellect 5 can use",
         lambda c, f: bool(f & {"fight_action"}) and bool(f & {"damage_to_enemy", "skill_bonus", "uses_ammo", "trait_weapon"})),
        ("A.evade_source", "evasion card whose bonus her intellect 5 can use",
         _any("evade_action")),
        ("A.enemy_presence", "brings, engages, disables or keeps an enemy at her location (the translation token needs one)",
         _any("engage_enemy", "enemy_disable", "enemy_at_location")),
        ("A.success_engine", "guarantees or cheapens successes (every success with an enemy tags it, once a round)",
         _any("auto_succeed")),
        ("A.token_on_enemy", "puts tokens on enemies: stacks with her translation tokens",
         lambda c, f: bool(re.search(r"\b(?:place|seal|put)\b[^.]{0,40}\bon (?:an?|that|the|each|attached) (?:non-elite )?enem", norm_text(c.get("text", ""))))),
        ("A.elder_sign", "names the elder sign token: interacts with her elder sign (token or card)",
         _any("elder_sign_token")),
    ],
    "cass": [
        ("C.symbol_reveal", "triggers on a symbol/chaos token reveal: stacks with her reveal reaction (gain 1 resource)",
         _any("token_reveal_trigger")),
        ("C.token_cancel", "cancels, ignores or redraws chaos tokens: stacks with her named-symbol cancel",
         _any("token_cancel", "token_reroll")),
        ("C.token_extra_reveal", "reveals extra tokens: more symbol and elder sign hits per test",
         _any("token_reveal_extra")),
        ("C.token_seal_look", "seals, names, looks at or searches the bag: steers the reveals she builds on",
         _any("token_seal", "token_look")),
        ("C.resource_gain", "gains resources: feeds the 2-resource cancel and her elder sign",
         _any("gain_resources", "resource_boost_upkeep")),
        ("C.elder_sign", "names the elder sign token: her elder sign gains 2 resources",
         _any("elder_sign_token")),
        ("C.bless_curse", "adds bless/curse tokens: changes how often a symbol is revealed",
         _any("add_bless_curse")),
    ],
    "birdie": [
        ("B.fail_payoff", "pays on, or counts, failed tests: resolve fodder and elder sign enabler",
         _any("fail_trigger", "if_fail")),
        ("B.fail_negation", "stops a failure from happening: no failure, no resolve",
         lambda c, f: bool(re.search(r"\bwould fail\b|\bdo not fail\b|\binstead of failing\b|\bsucceed instead\b", norm_text(c.get("text", ""))))),
        ("B.event_target", "an event she can return to hand once a round for 2 resolve",
         lambda c, f: c.get("type") == "event"),
        ("B.engine_event", "event with a value that repeats each round (resources, cards, actions, clues, heals, cancels)",
         lambda c, f: c.get("type") == "event" and bool(positive_value(f)) and not (f & {"remove_from_game", "limit_game"})),
        ("B.free_engine_event", "FAST event with a repeating value: the strongest recursion target (no action to replay)",
         lambda c, f: c.get("type") == "event" and "fast_event" in f and bool(positive_value(f)) and not (f & {"remove_from_game", "limit_game"})),
        ("B.dead_target", "event she cannot recur (removes itself or is once per game)",
         lambda c, f: c.get("type") == "event" and bool(f & {"remove_from_game", "limit_game"})),
        ("B.discard_recursion", "other discard-pile recursion: competes with or stacks on her return",
         _any("return_from_discard", "play_from_discard")),
        ("B.elder_sign", "names the elder sign token",
         _any("elder_sign_token")),
    ],
    "seraphine": [
        ("S.horror_offset", "heals, cancels or prevents horror: offsets her 1 direct horror price (an Ally's sanity cannot: direct horror is not assigned to assets)",
         lambda c, f: bool(f & {"heal_horror", "immune_cannot_take", "cancel_damage_horror", "prevent_damage"})),
        ("S.ally_soak_irrelevant", "Ally or asset with sanity: soaks ordinary horror but never her direct horror (guideline 14)",
         lambda c, f: "has_sanity" in f),
        ("S.horror_payoff", "pays off when horror is taken: her price becomes income",
         _any("trigger_on_horror", "trigger_on_damage_horror")),
        ("S.horror_user", "takes or deals horror as a cost or effect: stacks with her price",
         _any("take_horror_cost", "take_horror_effect", "direct_horror")),
        ("S.extra_action", "grants extra actions or refunds actions: stacks with her extra-action mode",
         _any("extra_action", "action_refund")),
        ("S.spell_ready", "Spell asset with an exhaust cost: a target for 'ready a Spell' (elder sign and ability)",
         lambda c, f: c.get("type") == "asset" and "trait_spell" in f and "exhaust_cost" in f),
        ("S.spell_engine", "repeats, readies, refills or discounts Spell abilities: stacks with 'ready a Spell' and her extra action",
         _any("spell_engine")),
        ("S.spell_asset", "Spell asset (what 'ready a Spell' needs on the table)",
         lambda c, f: c.get("type") == "asset" and "trait_spell" in f),
        ("S.skill_bonus", "adds skill value: stacks with her +2 mode",
         _any("skill_bonus")),
        ("S.elder_sign", "names the elder sign token",
         _any("elder_sign_token")),
    ],
}

# generic loop detectors, independent of the investigator
GENERIC_HOOKS = [
    ("G.free_resource_engine", "free ability or Fast play that gains resources",
     lambda c, f: bool(f & {"free_ability", "fast_event"}) and "gain_resources" in f),
    ("G.free_draw_engine", "free ability or Fast play that draws cards",
     lambda c, f: bool(f & {"free_ability", "fast_event"}) and "draw_cards" in f),
    ("G.free_action_engine", "free ability or Fast play that grants actions or refunds one",
     lambda c, f: bool(f & {"free_ability", "fast_event"}) and bool(f & {"extra_action", "action_refund"})),
    ("G.ready_engine", "readies cards", _any("ready")),
    ("G.repeat_effect", "repeats an ability or action", _any("repeat_ability")),
    ("G.return_engine", "returns cards to hand or plays them from the discard pile",
     _any("return_to_hand", "return_from_discard", "play_from_discard")),
]


def hooks_for(inv, card, flags):
    out = [h for h, _, pred in HOOKS[inv] if pred(card, flags)]
    out += [h for h, _, pred in GENERIC_HOOKS if pred(card, flags)]
    return out


# ======================================================================================
# 6. Fan packs (metadata only)
# ======================================================================================

def load_fan(save=SAVE):
    """Fan player cards the SCED menu offers: library-shaped dicts WITHOUT rules text.
    Dedup by (pack, id); cards with no level key are kept with level None (usually signature,
    story or weakness cards: not deck-legal by class and level)."""
    p = os.path.join(save, "fan_playercards_cards.jsonl")
    out, seen = [], set()
    if not os.path.exists(p):
        return out
    for d in _jsonl(p):
        m = d.get("meta") or {}
        if m.get("type") not in ("Asset", "Event", "Skill"):
            continue
        key = (d.get("box"), m.get("id") or d.get("name"), d.get("name"))
        if key in seen:
            continue
        seen.add(key)
        classes = [k.lower() for k in (m.get("class") or "neutral").split("|") if k] or ["neutral"]
        icons = {"wil": m.get("willpowerIcons", m.get("wilpowerIcons", m.get("willIcons", 0))) or 0,
                 "int": m.get("intellectIcons", 0) or 0, "com": m.get("combatIcons", 0) or 0,
                 "agi": m.get("agilityIcons", m.get("agilityicons", 0)) or 0, "wild": m.get("wildIcons", 0) or 0}
        uses = m.get("uses") or []
        if isinstance(uses, dict):
            uses = [uses]
        traits = [t.strip().lower() for t in re.split(r"\.\s*", m.get("traits") or "") if t.strip()]
        out.append({"name": d.get("name") or "", "subname": d.get("subtitle") or "", "unique": False,
                    "type": m["type"].lower(), "code": str(m.get("id") or ""), "pack": d.get("box_name") or "",
                    "author": d.get("author") or "", "level": m.get("level"), "cost": m.get("cost"),
                    "slot": m.get("slot", ""), "icons": icons, "traits": traits, "text": "",
                    "classes": classes, "weakness": bool(m.get("weakness")), "basic_weakness": False,
                    "exceptional": bool(m.get("exceptional")), "myriad": False,
                    "permanent": bool(m.get("permanent")), "exile": False, "restrictions": "",
                    "bonded_to": "bonded" if m.get("bonded") else "", "customizable": False,
                    "deck_limit": m.get("deck_limit", 2), "limit_per": None, "taboo": None,
                    "uses_meta": uses, "file": "fan", "fan": True, "has_text": False})
    return out


def fan_flags(card):
    """Flags a fan card's metadata alone supports."""
    f = set()
    for tr in card.get("traits", []):
        if tr in ("spell", "weapon", "tool", "ally", "charm", "relic", "tome", "item", "insight", "tactic", "trick",
                  "gambit", "ritual", "talent", "illicit", "improvised", "fortune", "favor", "occult", "science",
                  "spirit", "blessed", "cursed", "firearm", "melee", "supply"):
            f.add("trait_" + tr)
    f.add("type_" + card["type"])
    if card.get("permanent"):
        f.add("permanent")
    if card.get("exceptional"):
        f.add("exceptional")
    for u in card.get("uses_meta") or []:
        t = (u.get("type") or "").lower()
        if t in ("charge", "charges"):
            f.add("uses_charges")
        elif t == "ammo":
            f.add("uses_ammo")
        elif t in ("secret", "secrets"):
            f.add("uses_secrets")
        elif t in ("supply", "supplies"):
            f.add("uses_supplies")
        else:
            f.add("uses_other")
    f.add("no_rules_text")
    return f


# ======================================================================================
# 7. The scan: pools, rows, summaries
# ======================================================================================

class Scan(object):
    """Everything the tool computes, held in memory (tests build this from synthetic data)."""

    def __init__(self, db=None, camp=None, fan=None):
        self.db = db if db is not None else OfficialDB()
        self.camp = camp if camp is not None else load_campaign_cards()
        self.fan = fan if fan is not None else load_fan()
        self.inv = {}
        for key in INVESTIGATORS:
            c = self.camp[INV_ID[key]]
            own = c["class"].lower()
            parsed = parse_back_text(c.get("back_text", ""), own)
            traits = {t.strip().lower() for t in re.split(r"\.\s*", c.get("traits", "") or "") if t.strip()}
            self.inv[key] = {"id": c["id"], "name": c["name"], "class": own, "card": c, "options": parsed["options"],
                             "deck_size": parsed["deck_size"], "requirements": parsed["requirements"], "traits": traits}
        self.official = [c for c in self.db.cards if deck_legal_card(c)]
        self.recollections = campaign_player_cards(self.camp)
        self.flags = {}
        for c in self.official + self.recollections:
            self.flags[id(c)] = tag_card(c)
        for c in self.fan:
            self.flags[id(c)] = fan_flags(c)
        self._pools = {}

    def card_flags(self, card):
        return self.flags[id(card)]

    def pool(self, key, source="official"):
        """Rows [(card, bucket, limit)] legal for the investigator. source: official | fan | campaign."""
        k = (key, source)
        if k in self._pools:
            return self._pools[k]
        opts = self.inv[key]["options"]
        cards = {"official": self.official, "campaign": self.recollections,
                 "fan": [c for c in self.fan if deck_legal_card(c)]}[source]
        rows = []
        for c in cards:
            if not restriction_allows(c, self.inv[key]["traits"], self.inv[key]["class"]):
                continue
            r = classify(c, opts)
            if r:
                rows.append((c, r[0], r[1]))
        rows.sort(key=lambda t: (t[0].get("level") or 0, t[0]["name"].lower(), t[0]["code"]))
        self._pools[k] = rows
        return rows

    def required_cards(self, key):
        """Signature, weakness and quest cards named on the investigator's back, from the campaign."""
        by_name = {c.get("name"): c for c in self.camp.values()}
        out = []
        for name in self.inv[key]["requirements"]:
            c = by_name.get(name)
            out.append(campaign_as_card(c) if c else {"name": name, "missing": True})
        return out

    def row(self, key, card, bucket, limit):
        flags = self.card_flags(card)
        fan = bool(card.get("fan"))
        hooks = [] if fan else hooks_for(key, card, flags)
        t = card.get("taboo") or {}
        return {
            "investigator": key, "source": "fan" if fan else ("campaign" if card.get("campaign") else "official"),
            "code": card["code"], "name": card["name"] + (" - " + card["subname"] if card.get("subname") else ""),
            "classes": "|".join(card.get("classes") or []), "level": card.get("level"), "type": card.get("type"),
            "cost": card.get("cost"), "slot": card.get("slot", ""), "traits": ".".join(card.get("traits", [])),
            "bucket": bucket, "limit": limit if limit else "", "deck_limit": card.get("deck_limit"),
            "starter_legal": (card.get("level") == 0 and not card.get("campaign")),
            "exceptional": bool(card.get("exceptional")), "myriad": bool(card.get("myriad")),
            "permanent": bool(card.get("permanent")), "exile": bool(card.get("exile")),
            "customizable": bool(card.get("customizable")),
            "taboo": ("forbidden" if t.get("forbidden") else (("xp%+d" % t["xp"]) if "xp" in t else ("text" if t.get("text") else ""))) if t else "",
            "restriction": card.get("restrictions", ""),
            "pack": card.get("pack", ""), "flags": ";".join(sorted(flags - {"type_" + str(card.get("type"))})),
            "hooks": ";".join(hooks), "n_hooks": len(hooks), "text": " ".join(card.get("text", "").split()),
        }

    def rows(self, key, sources=("official", "campaign")):
        out = []
        for s in sources:
            for card, bucket, limit in self.pool(key, s):
                out.append(self.row(key, card, bucket, limit))
        return out

    def summary(self):
        out = {"taboo_list": self.db.taboo_title, "official_cards_parsed": len(self.db.cards),
               "official_deck_legal_base": len(self.official), "sced_cards": len(self.db.sced),
               "sced_unmapped_story_or_weakness": len(self.db.sced_unmapped),
               "fan_cards_total": len(self.fan), "fan_cards_with_level": sum(1 for c in self.fan if c.get("level") is not None),
               "recollections": len(self.recollections), "investigators": {}}
        for key in INVESTIGATORS:
            rows = self.rows(key)
            off = [r for r in rows if r["source"] == "official"]
            fan_rows = [self.row(key, c, b, l) for c, b, l in self.pool(key, "fan")]
            flagc = collections.Counter()
            hookc = collections.Counter()
            for r in off:
                for f in r["flags"].split(";"):
                    if f:
                        flagc[f] += 1
                for h in r["hooks"].split(";"):
                    if h:
                        hookc[h] += 1
            out["investigators"][key] = {
                "deck_size": self.inv[key]["deck_size"], "options": [o["text"] for o in self.inv[key]["options"]],
                "official_legal": len(off), "starter_legal_level0": sum(1 for r in off if r["starter_legal"]),
                "traits": sorted(self.inv[key]["traits"]),
                "trait_restricted_legal": sorted(r["name"] + " L" + str(r["level"]) for r in off if r["restriction"]),
                "taboo_forbidden": sorted(r["name"] for r in off if r["taboo"] == "forbidden"),
                "by_bucket": dict(collections.Counter(r["bucket"] for r in off)),
                "by_level": {str(k): v for k, v in sorted(collections.Counter(r["level"] for r in off).items())},
                "by_type": dict(collections.Counter(r["type"] for r in off)),
                "recollections_legal": sum(1 for r in rows if r["source"] == "campaign"),
                "fan_legal_by_class_and_level": len(fan_rows),
                "required": [c.get("name") for c in self.required_cards(key)],
                "flag_counts": dict(sorted(flagc.items())), "hook_counts": dict(sorted(hookc.items())),
            }
        return out


# ======================================================================================
# 8. Output
# ======================================================================================

CSV_COLUMNS = ["investigator", "source", "code", "name", "classes", "level", "type", "cost", "slot", "traits",
               "bucket", "limit", "deck_limit", "starter_legal", "exceptional", "myriad", "permanent", "exile",
               "customizable", "taboo", "restriction", "pack", "flags", "hooks", "n_hooks", "text"]


def write_tables(scan, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    allrows = []
    for key in INVESTIGATORS:
        allrows += scan.rows(key)
    with open(os.path.join(out_dir, "card_x_investigator.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(allrows)
    with open(os.path.join(out_dir, "card_x_investigator.jsonl"), "w", encoding="utf-8") as fh:
        for r in allrows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    fanrows = []
    for key in INVESTIGATORS:
        for card, bucket, limit in scan.pool(key, "fan"):
            fanrows.append(scan.row(key, card, bucket, limit))
    fan_cols = CSV_COLUMNS[:-1]
    with open(os.path.join(out_dir, "fan_x_investigator.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fan_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(fanrows)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(scan.summary(), fh, indent=1, sort_keys=True, ensure_ascii=False)
    return len(allrows), len(fanrows)


def shortlist_md(scan, key, hooks=None, text=True):
    """Markdown shortlist for one investigator: each hook, its cards, and (optionally) their text."""
    lines = ["# %s: cards touching each hook" % scan.inv[key]["name"], ""]
    rows = scan.rows(key)
    by_hook = collections.defaultdict(list)
    for r in rows:
        for h in r["hooks"].split(";"):
            if h:
                by_hook[h].append(r)
    desc = {h: d for hs in HOOKS.values() for h, d, _ in hs}
    desc.update({h: d for h, d, _ in GENERIC_HOOKS})
    for h in sorted(by_hook):
        if hooks and h not in hooks:
            continue
        lines.append("## %s (%d cards): %s" % (h, len(by_hook[h]), desc.get(h, "")))
        lines.append("")
        for r in by_hook[h]:
            lines.append("- **%s** [%s L%s %s c%s, %s%s]" % (r["name"], r["classes"], r["level"], r["type"], r["cost"], r["bucket"],
                                                              (" limit " + str(r["limit"])) if r["limit"] else ""))
            if text:
                lines.append("  " + r["text"][:900])
        lines.append("")
    return "\n".join(lines)


def write_shortlists(scan, out_dir, text=True):
    for key in INVESTIGATORS:
        p = os.path.join(out_dir, "shortlist_%s.md" % key)
        open(p, "w", encoding="utf-8").write(shortlist_md(scan, key, text=text))


# ---- starter decks: a cross-check of the pool derivation (docs/STARTER_DECKS.md)

_STARTER_HEAD = re.compile(r"^## (.+?) \((\w+)\)\s*$")


def parse_starter_decks(text):
    """docs/STARTER_DECKS.md -> {investigator key: [(copies, card name, class, level 0)]}."""
    out, cur = {}, None
    for ln in text.split("\n"):
        m = _STARTER_HEAD.match(ln)
        if m:
            nm = m.group(1).lower()
            cur = next((k for k in INVESTIGATORS if nm.split()[0].strip('"') in INV_NAME[k].lower().replace('\u014d', 'o')
                        or nm.startswith(INV_NAME[k].split()[0].lower())), None)
            if cur:
                out[cur] = []
            continue
        if cur and ln.startswith("|") and not ln.startswith("|---") and not ln.startswith("| Qty"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[0].isdigit():
                out[cur].append((int(cells[0]), cells[1], cells[3]))
    return out


def check_starter_decks(scan, text):
    """Problems found when each listed starter deck is checked against the derived pools.
    A deck is 30 cards, at most deck_limit copies of a title, only level-0 cards, at most the
    limited bucket's size from the secondary classes, only cards in the pool."""
    problems = []
    decks = parse_starter_decks(text)
    for key, lines in decks.items():
        pool = {}
        for card, bucket, limit in scan.pool(key):
            pool.setdefault(norm_name(card["name"]), []).append((card, bucket, limit))
        total, secondary, caps = 0, 0, None
        for n, name, klass in lines:
            total += n
            hits = [h for h in pool.get(norm_name(name), []) if h[0].get("level") == 0]
            if not hits:
                problems.append("%s: %s is not a legal level 0 card" % (key, name))
                continue
            card, bucket, limit = hits[0]
            if n > card.get("deck_limit", 2):
                problems.append("%s: %d copies of %s (limit %s)" % (key, n, name, card.get("deck_limit")))
            if bucket == "secondary":
                secondary += n
                caps = limit
        if total != scan.inv[key]["deck_size"]:
            problems.append("%s: %d cards, deck size %d" % (key, total, scan.inv[key]["deck_size"]))
        if caps and secondary > caps:
            problems.append("%s: %d secondary-class cards (limit %d)" % (key, secondary, caps))
    return problems


def starter_census(scan, text):
    """{investigator: {hook: [card names]}} for the cards of each listed starter deck."""
    decks = parse_starter_decks(text)
    out = {}
    for key, lines in decks.items():
        rows = {norm_name(r["name"].split(" - ")[0]): r for r in scan.rows(key) if r["level"] == 0}
        hooks = collections.defaultdict(list)
        for n, name, _ in lines:
            r = rows.get(norm_name(name))
            if not r:
                continue
            for h in r["hooks"].split(";"):
                if h:
                    hooks[h].append("%dx %s" % (n, name))
        out[key] = dict(sorted(hooks.items()))
    return out


def parse_levels(s):
    if not s:
        return None
    m = re.match(r"^(\d)(?:-(\d))?$", s)
    if not m:
        raise SystemExit("--level wants N or N-M")
    return int(m.group(1)), int(m.group(2) or m.group(1))


def cmd_show(scan, a):
    rows = scan.rows(a.investigator, sources=("official", "campaign") if not a.fan else ("fan",))
    lv = parse_levels(a.level)
    n = 0
    for r in rows:
        if lv and not (r["level"] is not None and lv[0] <= r["level"] <= lv[1]):
            continue
        flags = set(r["flags"].split(";"))
        hooks = set(r["hooks"].split(";"))
        if a.flag and not all(f in flags for f in a.flag):
            continue
        if a.hook and not all(h in hooks for h in a.hook):
            continue
        if a.type and r["type"] != a.type:
            continue
        if a.name and not re.search(a.name, r["name"], re.I):
            continue
        n += 1
        print("%s [%s L%s %s c%s %s] %s" % (r["name"], r["classes"], r["level"], r["type"], r["cost"], r["bucket"],
                                           r["hooks"]))
        if a.text:
            print("    " + r["text"][:1200])
    print("(%d cards)" % n)


def cmd_flags():
    print("feature flags")
    for flag, scope, rx, desc in FEATURES:
        print("  %-26s [%s] %s" % (flag, scope, desc))
    print("hooks")
    for key, hs in HOOKS.items():
        for h, d, _ in hs:
            print("  %-26s %s" % (h, d))
    for h, d, _ in GENERIC_HOOKS:
        print("  %-26s %s" % (h, d))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    scan_p = sub.add_parser("scan", help="write the tables and shortlists (default)")
    scan_p.add_argument("--out", default=os.path.join(ROOT, ".cache", "synergy_scan"))
    scan_p.add_argument("--quiet", action="store_true")
    scan_p.add_argument("--no-text", action="store_true", help="shortlists without card text")
    show_p = sub.add_parser("show", help="print an investigator's legal cards, filtered")
    show_p.add_argument("investigator", choices=INVESTIGATORS)
    show_p.add_argument("--flag", action="append", default=[])
    show_p.add_argument("--hook", action="append", default=[])
    show_p.add_argument("--level")
    show_p.add_argument("--type", choices=("asset", "event", "skill"))
    show_p.add_argument("--name")
    show_p.add_argument("--text", action="store_true")
    show_p.add_argument("--fan", action="store_true")
    sub.add_parser("flags", help="list the feature flags and hooks")
    st_p = sub.add_parser("starters", help="check docs/STARTER_DECKS.md against the derived pools and print its hook census")
    st_p.add_argument("--file", default=os.path.join(ROOT, "docs", "STARTER_DECKS.md"))
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("scan", "show", "flags", "starters", "-h", "--help"):
        argv = ["scan"] + argv
    a = ap.parse_args(argv)
    if a.cmd == "flags":
        cmd_flags()
        return 0
    if not os.path.isdir(LIB):
        raise SystemExit("library/ is not built: python3 tools/library/build_library.py")
    scan = Scan()
    if a.cmd == "show":
        cmd_show(scan, a)
        return 0
    if a.cmd == "starters":
        probs = check_starter_decks(scan, open(a.file, encoding="utf-8").read())
        for pr in probs:
            print("PROBLEM:", pr)
        print("%d starter deck problem(s)" % len(probs))
        for key, hooks in starter_census(scan, open(a.file, encoding="utf-8").read()).items():
            print("%s starter deck, cards touching each hook:" % key)
            for h, names in hooks.items():
                print("   %-24s %s" % (h, ", ".join(names)))
        return 1 if probs else 0
    n, nf = write_tables(scan, a.out)
    write_shortlists(scan, a.out, text=not a.no_text)
    if not a.quiet:
        s = scan.summary()
        print("taboo list: %s; %d official cards parsed, %d deck-legal before options" % (
            s["taboo_list"], s["official_cards_parsed"], s["official_deck_legal_base"]))
        for key in INVESTIGATORS:
            i = s["investigators"][key]
            print("%-10s official legal %4d (level 0: %3d) buckets %s; Recollections %d; fan legal by class/level %d" % (
                key, i["official_legal"], i["starter_legal_level0"], i["by_bucket"], i["recollections_legal"],
                i["fan_legal_by_class_and_level"]))
        print("wrote %d rows (+%d fan rows) to %s" % (n, nf, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
