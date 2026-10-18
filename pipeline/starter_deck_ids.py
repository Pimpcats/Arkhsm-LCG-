#!/usr/bin/env python3
"""starter_deck_ids.py — the starter decks of docs/STARTER_DECKS.md as SCED card ids.

The Control token seats an investigator with their starter deck (src/tts/control.lua seatInvestigator):
the official cards come out of SCED's own All Player Cards bag by id (AllCardsBagApi.getCardById), the
way SCED's deck importer loads an ArkhamDB deck. This resolves each list row (quantity, name, pack) to
the id SCED files that card under, from the SCED checkout's objects/AllPlayerCards.*/ metadata
(.cache/sced/<pinned commit>, or $SCED_DIR), and writes campaigns/<id>/starter_decks.json:

    {"sthrelias": [["01020", 2], ...], ...}

Every row must resolve to one level 0 card, or the script stops and names the row.

Run: python3 pipeline/starter_deck_ids.py
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from campaign_config import CFG  # noqa: E402

DOC = os.path.join(ROOT, "docs", "STARTER_DECKS.md")
OUT = os.path.join(ROOT, "campaigns", CFG.id, "starter_decks.json")

# a pack as the list names it -> the cycle SCED files its cards under
PACK_CYCLE = {
    "Core Set": "Core", "Core Set (2026)": "Core 2026",
    "Edge of the Earth Investigator Expansion": "Edge of the Earth",
    "The Scarlet Keys Investigator Expansion": "The Scarlet Keys",
    "The Forgotten Age": "The Forgotten Age", "Heart of the Elders": "The Forgotten Age",
    "The Dunwich Legacy": "The Dunwich Legacy", "The Essex County Express": "The Dunwich Legacy",
    "The Path to Carcosa": "The Path to Carcosa", "Echoes of the Past": "The Path to Carcosa",
    "The Pallid Mask": "The Path to Carcosa",
    "The Circle Undone": "The Circle Undone",
    "A Thousand Shapes of Horror": "The Dream-Eaters", "The Search for Kadath": "The Dream-Eaters",
    "Harvey Walters Investigator Starter Deck": "Investigator Packs",
    "Winifred Habbamock Investigator Starter Deck": "Investigator Packs",
}

# the list's investigator headings -> card ids
INVESTIGATORS = {"Elias Warde": "sthrelias", "Dr. Ayako Sōma": "sthrayako", "Cass Lindqvist": "sthrcass",
                 '"Birdie" Okonkwo': "sthrbirdie", "Seraphine Vale": "sthrseraphine"}


def sced_dir():
    if os.environ.get("SCED_DIR"):
        return os.environ["SCED_DIR"]
    sys.path.insert(0, os.path.join(ROOT, "tests", "sced_real"))
    import sced_table
    return os.path.join(ROOT, ".cache", "sced", sced_table.PINNED)


def norm(name):
    name = name.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", name).strip().lower()


def card_index(root):
    """name (lower case) -> [(id, cycle)] of level 0 player cards, taboo versions left out."""
    index = {}
    folders = glob.glob(os.path.join(root, "objects", "AllPlayerCards.*"))
    folders = [f for f in folders if os.path.isdir(f)]
    if not folders:
        raise SystemExit("no objects/AllPlayerCards.* in " + root + " (set SCED_DIR to a SCED checkout)")
    for path in glob.glob(os.path.join(folders[0], "*.json")):
        obj = json.load(open(path, encoding="utf-8"))
        gm_path = obj.get("GMNotes_path")
        if not gm_path:
            continue
        try:
            gm = json.load(open(os.path.join(root, "objects", gm_path), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cid = str(gm.get("id") or "")
        if not cid or cid.endswith("-t") or gm.get("level", 0) not in (0, None):
            continue
        index.setdefault(norm(obj.get("Nickname") or ""), []).append((cid, gm.get("cycle")))
    return index


def parse_doc():
    decks, who = {}, None
    for line in open(DOC, encoding="utf-8"):
        m = re.match(r"## (.+?) \(", line)
        if m:
            who = INVESTIGATORS.get(m.group(1).strip())
            if who:
                decks[who] = []
            continue
        m = re.match(r"\| (\d+) \| (.+?) \| (\w+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|", line)
        if m and who:
            decks[who].append((int(m.group(1)), m.group(2).strip(), m.group(6).strip()))
    return decks


def resolve(index, name, pack):
    # a title with its subtitle ("Dr. Milan Christopher — Professor of Entomology") is filed by its title
    candidates = index.get(norm(name)) or index.get(norm(re.split(r"\s+[—-]\s+", name)[0])) or []
    if not candidates:
        raise SystemExit("no level 0 card named %r in SCED's player cards" % name)
    want = PACK_CYCLE.get(pack)
    exact = [c for c in candidates if want and c[1] == want]
    pick = sorted(exact or candidates, key=lambda c: (c[1] != "Core", c[0]))[0]
    return pick[0]


def build():
    index = card_index(sced_dir())
    out = {}
    for who, rows in parse_doc().items():
        out[who] = [[resolve(index, name, pack), qty] for qty, name, pack in rows]
        total = sum(q for _, q in out[who])
        if total != 30:
            raise SystemExit("%s: the list holds %d cards, not 30" % (who, total))
    if set(out) != set(INVESTIGATORS.values()):
        raise SystemExit("missing starter decks: " + ", ".join(sorted(set(INVESTIGATORS.values()) - set(out))))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    return out


if __name__ == "__main__":
    res = build()
    print(json.dumps({k: sum(q for _, q in v) for k, v in res.items()}))
