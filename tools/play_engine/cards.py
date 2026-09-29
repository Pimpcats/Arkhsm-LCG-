"""The campaign's cards as the play engine reads them (designer tooling).

Every number and rules line the engine uses comes from here, never from a
copy in the engine: the card spec with the owner's overrides applied, then the
print layer (rules text, enemy combat stats) exactly as the rendered card shows
it (pipeline/scenario_content.load_full_cards: overrides win over print text).

    python3 tools/play_engine/cards.py            # writes .cache/play_engine/cards.json

The engine's effects table (tools/play_engine/lua/effects.lua) is keyed by
card id and checked against this list: a scenario card without an entry there
is reported as not encoded.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

KEEP = ("id", "type", "name", "subtitle", "class", "traits", "text", "back_text", "fight", "evade", "health",
        "sanity", "damage", "horror", "victory", "shroud", "back_shroud", "clues", "clues_per_investigator",
        "doom", "index", "number", "quantity", "wil", "int", "com", "agi", "elderSign", "tokens", "back_tokens",
        "cost", "level", "slot", "uses", "weakness", "unique", "elite", "memoryCost", "wildIcons", "wilIcons",
        "intIcons", "comIcons", "agiIcons", "permanent", "unrevealed", "signatures")

# the card types a scenario box lays out (the effects table must cover them)
SCENARIO_TYPES = ("Location", "Act", "Agenda", "Enemy", "Treachery", "Story", "Scenario")


def load_cards():
    import scenario_content as sc
    cards, assign, manifest = sc.load()
    out = {}
    for cid, c in cards.items():
        out[cid] = {k: c[k] for k in KEEP if k in c and c[k] is not None}
    return out, assign


def scenario_card_ids(assign):
    """Every card id a scenario box lays out (the encoding target)."""
    ids = set()
    for box in assign.values():
        for key in ("reference", "agenda_deck", "act_deck", "locations", "encounter", "named", "setup_aside"):
            for cid in box.get(key, []) or []:
                ids.add(cid)
    return ids


def write(path=None):
    cards, assign = load_cards()
    path = path or os.path.join(ROOT, ".cache", "play_engine", "cards.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {"cards": cards, "scenario_ids": sorted(scenario_card_ids(assign)), "assignments": assign}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    return path


if __name__ == "__main__":
    print(write(sys.argv[1] if len(sys.argv) > 1 else None))
