"""dist/ is what the owner loads: it must be the build of the CURRENT card data.

The 2026-10-06 content audit found dist/ one redesign behind (29 cards changed or new in the specs,
none of it in the Saved Object, and no test noticed because tests/test_dist_hosted.py only checks
that URLs resolve). This rebuilds each shipped card's identity and metadata from the effective
specs (spec + print layer + the owner's overrides, exactly as the build reads them) and compares
it with what the Saved Object carries."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import build_cards as B  # noqa: E402
import compile_campaign as CC  # noqa: E402

SAVED = os.path.join(ROOT, "dist", "saved_object_the_still_hour.json")


def shipped_cards():
    data = json.load(open(SAVED, encoding="utf-8"))
    out = {}

    def walk(o):
        if o.get("Name") in ("Card", "CardCustom") and o.get("GMNotes", "").strip().startswith("{"):
            md = json.loads(o["GMNotes"])
            out.setdefault(md["id"], []).append(o)
        for c in o.get("ContainedObjects") or []:
            walk(c)
        for st in (o.get("States") or {}).values():
            walk(st)
    for o in data["ObjectStates"]:
        walk(o)
    return out


def test_every_card_in_the_saved_object_is_the_current_card():
    cards = CC.load_cards(CC.campaign_paths())
    shipped = shipped_cards()
    stale = []
    for cid, objs in shipped.items():
        if cid not in cards:                       # minicards, the campaign log's own objects
            continue
        c = CC.normalize(cards[cid])
        want = json.loads(B.build_gmnotes(c))
        for o in objs:
            have = json.loads(o["GMNotes"])
            if have != want:
                stale.append((cid, sorted(k for k in set(have) | set(want) if have.get(k) != want.get(k))))
            elif o.get("Nickname") != c["name"] or o.get("Description", "") != c.get("subtitle", ""):
                stale.append((cid, ["name/subtitle"]))
    assert not stale, "dist/ is behind the specs; rebuild it (pipeline/publish_hosted.py): %s" % stale[:8]


def test_every_player_card_in_the_specs_is_shipped():
    cards = CC.load_cards(CC.campaign_paths())
    shipped = shipped_cards()
    player_ids = [c["id"] for c in json.load(open(os.path.join(ROOT, "pipeline", "stillhour_cards_spec.json"),
                                                  encoding="utf-8"))]
    missing = [i for i in player_ids if i in cards and i not in shipped]
    assert not missing, "cards in the player spec missing from the Saved Object: %s" % missing


def test_the_shipped_control_carries_the_current_rules_code():
    saved = open(SAVED, encoding="utf-8").read()
    constants = open(os.path.join(ROOT, "src", "StillHour", "Constants.ttslua"), encoding="utf-8").read()
    # a marker of the portable-investigator redesign: the quest table lives in Constants.QUEST
    assert "Constants.QUEST" in constants
    assert "QUEST" in saved and "questUnlocked" in saved, "the shipped Control script predates the quest cards"
