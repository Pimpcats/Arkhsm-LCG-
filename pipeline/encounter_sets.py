#!/usr/bin/env python3
"""encounter_sets.py — which encounter-set symbol and encounter number each
scenario card prints, as official cards do (the symbol in the frame's set
slot, "4/18" or "3–4/18" in the footer).

Derived, never hand-kept:
  - encounter cards (enemies, treacheries and the rest of a set) take the
    first set in scenario_manifest.json's campaign.encounter_sets that lists
    them (a card some later set reuses keeps its home set's symbol);
  - a box's own cards (locations, acts, set-aside story assets) take the set
    build.json's "encounter_symbols" names for that box;
  - agendas, the scenario reference and story cards take its "_default";
  - its "_cards" ({card id: set id}) overrides any of these.
Within a set, cards are numbered agendas, acts, locations, other set-aside
cards, then the encounter cards, each copy counted.

    python3 pipeline/encounter_sets.py          # prints the table
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from campaign_config import CFG  # noqa: E402

ORDER = {"Agenda": 0, "Act": 1, "Location": 2}


def assign(cards, assignments, manifest, symbols):
    """{card_id: (set_id, "a/total" or "a–b/total")}."""
    if not symbols:
        return {}
    default = symbols.get("_default")
    home = dict(symbols.get("_cards") or {})        # explicit card -> set
    sets = manifest.get("campaign", {}).get("encounter_sets", {})
    for sid, s in sets.items():
        for c in s.get("cards", []):
            home.setdefault(c["id"], sid)
    qty = collections.Counter()
    for s in sets.values():
        for c in s.get("cards", []):
            if home.get(c["id"]) and c["id"] not in qty:
                qty[c["id"]] = int(c.get("qty", 1) or 1)
    members = collections.OrderedDict()

    def put(cid, sid):
        if not sid or cid not in cards:
            return
        members.setdefault(sid, [])
        if cid not in members[sid]:
            members[sid].append(cid)

    placed = set()
    for box_id, box in assignments.items():
        if box_id.startswith("_"):
            continue
        box_set = symbols.get(box_id)
        for key in ("agenda_deck", "reference", "act_deck", "locations", "setup_aside", "named", "encounter"):
            for cid in box.get(key, []) or []:
                if cid in placed or cid not in cards:
                    continue
                t = cards[cid].get("type")
                if cid in home:
                    sid = home[cid]
                elif t in ("Agenda", "Scenario", "Story"):
                    sid = default
                else:
                    sid = box_set or default
                put(cid, sid)
                placed.add(cid)
    out = {}
    for sid, ids in members.items():
        ids.sort(key=lambda i: ORDER.get(cards[i].get("type"), 3) if i not in home else 4)   # stable
        n = 0
        spans = []
        for cid in ids:
            k = qty.get(cid) or int(cards[cid].get("quantity", 1) or 1)
            spans.append((cid, n + 1, n + k))
            n += k
        for cid, a, b in spans:
            out[cid] = (sid, ("{}/{}".format(a, n) if a == b else "{}–{}/{}".format(a, b, n)))
    return out


def load(campaign=None):
    import compile_campaign as CC
    paths = CC.campaign_paths(campaign)
    cards = CC.load_cards(paths)
    assignments = json.load(open(paths["assignments"], encoding="utf-8"))
    manifest = json.load(open(paths["manifest"], encoding="utf-8"))
    return assign(cards, assignments, manifest, CFG.get("encounter_symbols") or {})


def icon_path(set_id, campaign=None):
    p = os.path.join(os.path.dirname(HERE), "campaigns", campaign or CFG.id, "set_icons", set_id + ".png")
    return p if os.path.exists(p) else None


if __name__ == "__main__":
    for cid, (sid, num) in sorted(load().items(), key=lambda kv: (kv[1][0], kv[1][1])):
        print("{:20s} {:10s} {}".format(sid, num, cid))
