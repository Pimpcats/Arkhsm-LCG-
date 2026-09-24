#!/usr/bin/env python3
"""Phase 3 — compile the Scenarios board into a scripted SCED campaign box.

The Studio's board (campaigns/still_hour/scenario_assignments.json) says which
card sits in which stack of which scenario. This turns that into the object
hierarchy SCED actually expects, aligned to the vendored ground-truth objects
in docs/art_reference/sced_objects/:

    CampaignBox         Custom_Model_Bag, Tags [CampaignBox, Reloadable]
      ├── ScenarioBox   Custom_Model_Bag per scenario, GMNotes type ScenarioBox
      │     ├── Deck    one per non-empty stack (locations, act, agenda, …)
      │     └── …       memory-bag layout in LuaScriptState.ml (GUID -> pos/rot)
      ├── CampaignLog   Custom_Token, GMNotes type CampaignLog
      └── CampaignGuide Custom_PDF, Tags [CampaignGuide]

Usage: python3 pipeline/compile_campaign.py [--out dist/the_still_hour_campaign.json]
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_cards as B  # noqa: E402  (card object builder, ground-truth aligned)
import table_presence as T  # noqa: E402  (boxes, log, guide, minicards)

def campaign_paths(campaign="still_hour"):
    """Every path this compiler reads for ONE campaign, so any campaign - not
    just The Still Hour - compiles to its own box."""
    cdir = os.path.join(ROOT, "campaigns", campaign)
    if campaign == "still_hour":
        specs = ("stillhour_cards_spec.json", "stillhour_encounter_spec.json",
                 "stillhour_scenario_spec.json", "stillhour_imported_spec.json",
                 "stillhour_handmade_spec.json")
    else:
        specs = ("{}_cards_spec.json".format(campaign),
                 "{}_imported_spec.json".format(campaign))
    name = campaign.replace("_", " ").title()
    cfg = os.path.join(cdir, "campaign.json")
    if os.path.exists(cfg):
        try:
            name = json.load(open(cfg, encoding="utf-8")).get("name") or name
        except ValueError:
            pass
    return {"dir": cdir, "name": name,
            "assignments": os.path.join(cdir, "scenario_assignments.json"),
            "manifest": os.path.join(cdir, "scenario_manifest.json"),
            "specs": specs}

# stack -> deck nickname, in the order a scenario book lays out
STACK_ORDER = [
    ("reference", "Scenario Reference"),
    ("agenda_deck", "Agenda Deck"),
    ("act_deck", "Act Deck"),
    ("locations", "Locations"),
    ("encounter", "Encounter Deck"),
    ("named", "Named Enemies"),
    ("setup_aside", "Set Aside"),
]

# ---------------------------------------------------------------- placement --
# Table anchors = SCED's own snap points (argonui/SCED objects/MythosArea and
# PlayArea, converted to world coordinates). +x runs toward the scenario mat,
# +z runs to the players' LEFT. The mythos mat, left to right as you sit:
#   encounter discard z 10.38 · encounter deck 5.72 · agenda 0.36 ·
#   act -5.05 · scenario card -10.39   (x -3.85 / -2.94)
# with angled corner snaps at (1.69, 14.24) and (1.6, -13.75). Every anchor is
# checked against the official Drowned City boxes in
# docs/art_reference/sced_objects/official_layout_drowned_city.json.
PLACE = {
    "reference":   {"pos": (-3.85, 1.59, -10.39), "rot": 270},
    "agenda_deck": {"pos": (-2.94, 1.61, 0.36), "rot": 180},
    "act_deck":    {"pos": (-2.94, 1.61, -5.05), "rot": 180},
    "encounter":   {"pos": (-3.85, 1.75, 5.72), "rot": 270, "face_down": True},
    "setup_aside": {"pos": (1.69, 1.56, 14.24), "rot": 225, "face_down": True},
    # set-aside enemies: where the official boxes put them, beside the
    # encounter discard (Court of the Ancients / The Grand Vault, Drowned City)
    "named":       {"pos": (-3.83, 1.60, 14.98), "rot": 270, "face_down": True},
}
# Face-up stacks (agenda, act) show their LAST contained card on top, so the
# official boxes list stage 1 last; face-down stacks (encounter deck, set-aside
# cards: rot z 180 in every official box) draw their FIRST card.
# The play area's location snaps, at full card spacing: rows step 6.60 AWAY
# from the scenario mat starting just below it (x -17.04 .. -43.44), columns
# step 7.65 left to right (z 15.30 .. -15.30). A map slot [col, row] is exactly
# what the Studio's map editor shows: col = across, row = down.
LOCATION_GRID = {"x0": -17.04, "row_dx": -6.60, "z0": 15.30, "col_dz": -7.65,
                 "cols": 5, "rows": 5, "y": 1.53, "rot": 270}


def slot_xz(col, row):
    """Table position of map slot [col, row]."""
    return (round(LOCATION_GRID["x0"] + row * LOCATION_GRID["row_dx"], 3),
            round(LOCATION_GRID["z0"] + col * LOCATION_GRID["col_dz"], 3))


def location_slot(i):
    """Nth location when the scenario has no authored map: left to right
    across the middle row, then the rows below it."""
    row, col = divmod(i, LOCATION_GRID["cols"])
    row = min(2 + row, LOCATION_GRID["rows"] - 1)
    x, z = slot_xz(col, row)
    return (x, LOCATION_GRID["y"], z), LOCATION_GRID["rot"]


def guid(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:6]


def transform(x=0.0, z=0.0, y=1.5, ry=180, scale=1.15, rz=0):
    return {"posX": x, "posY": y, "posZ": z, "rotX": 0, "rotY": ry, "rotZ": rz,
            "scaleX": scale, "scaleY": 1, "scaleZ": scale}


def load_cards(paths):
    """Every card in the campaign, spec + editor overrides applied, by id."""
    sys.path.insert(0, HERE)
    import render_placeholders as rp
    cards, seen = {}, set()
    for name in paths["specs"]:
        p = os.path.join(HERE, name)
        if not os.path.exists(p):
            continue
        try:
            spec = json.load(open(p, encoding="utf-8"))
        except ValueError:
            continue
        for c in spec:
            if c.get("id") and c["id"] not in seen:
                seen.add(c["id"])
                cards[c["id"]] = c
    ovp = os.path.join(paths["dir"], "card_overrides.json")
    ov = {}
    if os.path.exists(ovp):
        try:
            ov = json.load(open(ovp, encoding="utf-8"))
        except ValueError:
            ov = {}
    print_text = {}
    ptp = os.path.join(HERE, "stillhour_print_text.json")
    if os.path.exists(ptp):
        print_text = json.load(open(ptp, encoding="utf-8"))
    out = {}
    for cid, c in cards.items():
        merged, _ = rp.apply_card_overrides(c, dict(print_text.get(cid, {})),
                                            ov.get(cid))
        out[cid] = merged
    return out


def normalize(c):
    """Fill the fields build_cards expects from any spec/imported card."""
    c = dict(c)
    c.setdefault("type", "Asset")
    c.setdefault("name", c.get("id", "Card"))
    c.setdefault("class", "Mythos" if c["type"] in
                 ("Enemy", "Treachery", "Location", "Agenda", "Act",
                  "Scenario", "Story", "CampaignLog") else "Neutral")
    c.setdefault("traits", "")
    if "deck" not in c:
        # stable per-card deck id outside the authored 95xxx range
        c["deck"] = 96000 + (int(guid(c["id"]), 16) % 3000)
    if c["type"] in ("Enemy", "Treachery", "Location", "Agenda", "Act",
                     "Scenario", "Story", "CampaignLog"):
        c.setdefault("encounter", True)
    return c


def build_deck(cards, nickname, key, x, z, face_down=False):
    """A TTS Deck object holding the cards of one stack (single card -> card),
    `cards` in stage order: the first one ends up on top either way."""
    objs = [B.build_card(normalize(c)) for c in cards]
    if not face_down:
        objs.reverse()
    if not objs:
        return None
    if len(objs) == 1:
        o = dict(objs[0])
        o["Transform"] = transform(x, z)
        return o
    deck_ids, custom = [], {}
    for o in objs:
        deck_ids.append(o["CardID"])
        custom.update(o["CustomDeck"])
    # TTS draws a deck by the Deck's own flag, not its cards': the official
    # agenda/act decks are SidewaysCard true, Hands false (The Drowned City box)
    sideways = all(o.get("SidewaysCard") for o in objs)
    return {
        "Name": "Deck", "Nickname": nickname, "Description": "",
        "GUID": guid("deck:" + key), "Tags": ["ScenarioCard"],
        "SidewaysCard": sideways, "Hands": False,
        "Transform": transform(x, z),
        "ColorDiffuse": dict(B.COLOR_DIFFUSE),
        "DeckIDs": deck_ids, "CustomDeck": custom,
        "ContainedObjects": objs,
    }


def build_scenario_box(sc, assign, cards, campaign_name="Campaign"):
    """One scenario = a memory-bag book that lays its stacks out on Place."""
    sid = sc["id"]
    contained, ml = [], {}
    for stack, label in STACK_ORDER:
        ids = [i for i in (assign.get(stack) or []) if i in cards]
        if not ids:
            continue
        if stack == "locations":
            # every location is placed individually. If the owner arranged the
            # scenario's map grid, those exact slots are scripted; otherwise
            # they fall onto the default grid in order.
            placed = assign.get("_map") or {}
            for n, cid in enumerate(ids):
                slot = placed.get(cid)
                if (isinstance(slot, (list, tuple)) and len(slot) == 2):
                    x, z = slot_xz(int(slot[0]), int(slot[1]))
                    y, rot = LOCATION_GRID["y"], LOCATION_GRID["rot"]
                else:
                    (x, y, z), rot = location_slot(n)
                o = B.build_card(normalize(cards[cid]))
                o["Transform"] = transform(x, z, y=y, ry=rot)
                contained.append(o)
                ml[o["GUID"]] = {"lock": False,
                                 "pos": {"x": round(x, 3), "y": round(y, 3),
                                         "z": round(z, 3)},
                                 "rot": {"x": 0, "y": rot, "z": 0}}
            continue
        anchor = PLACE.get(stack, {"pos": (0.0, 1.5, 0.0), "rot": 180})
        x, y, z = anchor["pos"]
        rot = anchor["rot"]
        rz = 180 if anchor.get("face_down") else 0
        d = build_deck([cards[i] for i in ids],
                       "{} — {}".format(sc.get("name", sid), label),
                       "{}:{}".format(sid, stack), x, z,
                       face_down=bool(rz))
        if d:
            d["Transform"] = transform(x, z, y=y, ry=rot, rz=rz)
            contained.append(d)
            ml[d["GUID"]] = {"lock": False,
                             "pos": {"x": round(x, 3), "y": round(y, 3),
                                     "z": round(z, 3)},
                             "rot": {"x": 0, "y": rot, "z": rz}}
    # SCED's scenario book: small box mesh + the MemoryBag script (Place /
    # Recall) reading ml. Connections travel on the cards' locationFront /
    # locationBack metadata, not in the box.
    return T.scenario_box(sc.get("name", sid), sid, contained, ml)


def build_log_token(cards=None, campaign_name=None):
    """The campaign log: SCED's CampaignLog Custom_Token (table_presence)."""
    return T.build_log(T.PLACE_LOG)


def build_guide_pdf(campaign_name=None):
    """The campaign guide: SCED's CampaignGuide Custom_PDF (table_presence)."""
    return T.build_guide(T.PLACE_GUIDE)


def compile_campaign(out_path, require_locked=True, campaign="still_hour"):
    paths = campaign_paths(campaign)
    cards = load_cards(paths)
    assignments = {}
    if os.path.exists(paths["assignments"]):
        assignments = json.load(open(paths["assignments"], encoding="utf-8"))
    manifest = {"scenarios": []}
    if os.path.exists(paths["manifest"]):
        manifest = json.load(open(paths["manifest"], encoding="utf-8"))
    scenarios = sorted(manifest.get("scenarios", []),
                       key=lambda s: s.get("order", 99))

    unlocked = [s["id"] for s in scenarios
                if not (assignments.get(s["id"], {}) or {}).get("_locked")]
    if require_locked and unlocked:
        return {"ok": False,
                "message": "not every scenario is locked in: "
                           + ", ".join(unlocked),
                "unlocked": unlocked}

    boxes, placed = [], 0
    for sc in scenarios:
        assign = assignments.get(sc["id"], {}) or {}
        box = build_scenario_box(sc, assign, cards, paths["name"])
        if not box["ContainedObjects"]:
            continue
        boxes.append(box)
        placed += 1
    # the campaign box carries the scenario books plus (for The Still Hour)
    # the investigator minicards, the campaign log and the campaign guide
    still = campaign == "still_hour"
    box = T.campaign_box(boxes, name=paths["name"],
                         filename=T.FILENAME if still else campaign,
                         box_id="CB-STHR" if still else "CB-" + campaign[:8].upper(),
                         table=still)
    save = {"SaveName": paths["name"], "GameMode": paths["name"],
            "ObjectStates": [box]}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save, f, indent=2)

    # validate the round trip
    d = json.load(open(out_path, encoding="utf-8"))
    top = d["ObjectStates"][0]
    assert json.loads(top["GMNotes"])["type"] == "CampaignBox"
    n_cards = 0
    for o in top["ContainedObjects"]:
        if o["Name"] != "Custom_Model_Bag":
            continue
        json.loads(o["GMNotes"])
        json.loads(o["LuaScriptState"])
        for deck in o["ContainedObjects"]:
            n_cards += len(deck.get("ContainedObjects") or [deck])
    return {"ok": True, "out": os.path.relpath(out_path, ROOT),
            "scenarios": placed, "cards": n_cards,
            "objects": len(top["ContainedObjects"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        ROOT, "dist", "the_still_hour_campaign.json"))
    ap.add_argument("--campaign", default="still_hour")
    ap.add_argument("--force", action="store_true",
                    help="compile even if scenarios aren't all locked")
    a = ap.parse_args()
    out = a.out if a.campaign == "still_hour" else os.path.join(
        ROOT, "dist", a.campaign + "_campaign.json")
    r = compile_campaign(out, require_locked=not a.force, campaign=a.campaign)
    print(json.dumps(r, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
