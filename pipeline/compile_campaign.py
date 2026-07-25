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
# Fixed table anchors, measured off the real SCED scenario box (One Last Job,
# docs/art_reference/sced_objects/scenario_box_memory_bag.json). Hitting Place
# in TTS drops each stack where the official campaigns put it:
#   locations grid  x -30..-23, z -11..11   (rot 270, upright to the players)
#   encounter deck  x -3.85  z  5.72
#   agenda / act    x -2.94 / -1.79, z 0.36 / -5.02
#   set-aside       x  1.69  z 14.24        (rot 225, off to the corner)
PLACE = {
    "reference":   {"pos": (-12.22, 1.59, -8.90), "rot": 90},
    "agenda_deck": {"pos": (-2.94, 1.61, 0.36), "rot": 180},
    "act_deck":    {"pos": (-1.79, 1.40, -5.02), "rot": 0},
    "encounter":   {"pos": (-3.85, 1.75, 5.72), "rot": 270},
    "named":       {"pos": (-3.85, 1.60, -10.39), "rot": 270},
    "setup_aside": {"pos": (1.69, 1.56, 14.24), "rot": 225},
}
# locations lay out on the official two-column grid, top-left first
LOCATION_GRID = {"x0": -30.24, "dx": 6.60, "z0": 11.46, "dz": -7.65,
                 "rows": 4, "y": 1.53, "rot": 270}


def location_slot(i):
    """Nth location on the official grid: fills a column top-to-bottom, then
    steps right — the same shape the real scenario books lay out."""
    col, row = divmod(i, LOCATION_GRID["rows"])
    return ((LOCATION_GRID["x0"] + col * LOCATION_GRID["dx"],
             LOCATION_GRID["y"],
             LOCATION_GRID["z0"] + row * LOCATION_GRID["dz"]),
            LOCATION_GRID["rot"])


def guid(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:6]


def transform(x=0.0, z=0.0, y=1.5, ry=180, scale=1.15):
    return {"posX": x, "posY": y, "posZ": z, "rotX": 0, "rotY": ry, "rotZ": 0,
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


def build_deck(cards, nickname, key, x, z):
    """A TTS Deck object holding the cards of one stack (single card -> card)."""
    objs = [B.build_card(normalize(c)) for c in cards]
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
    return {
        "Name": "Deck", "Nickname": nickname, "Description": "",
        "GUID": guid("deck:" + key), "Tags": ["ScenarioCard"],
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
            # every location is placed individually on the official grid, the
            # way a real scenario lays its map out
            for n, cid in enumerate(ids):
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
        d = build_deck([cards[i] for i in ids],
                       "{} — {}".format(sc.get("name", sid), label),
                       "{}:{}".format(sid, stack), x, z)
        if d:
            d["Transform"] = transform(x, z, y=y, ry=rot)
            contained.append(d)
            ml[d["GUID"]] = {"lock": False,
                             "pos": {"x": round(x, 3), "y": round(y, 3),
                                     "z": round(z, 3)},
                             "rot": {"x": 0, "y": rot, "z": 0}}
    return {
        "Name": "Custom_Model_Bag",
        "Nickname": sc.get("name", sid),
        "Description": campaign_name or "Campaign",
        "GUID": guid("scenariobox:" + sid),
        "Tags": ["ScenarioBox"],
        "GMNotes": json.dumps({"id": sid, "type": "ScenarioBox",
                               "cycle": campaign_name}),
        "Transform": transform(scale=1.0),
        "ColorDiffuse": dict(B.COLOR_DIFFUSE),
        "LuaScriptState": json.dumps({"ml": ml}),
        "ContainedObjects": contained,
    }


def build_log_token(cards, campaign_name=None):
    """The campaign log as SCED's Custom_Token (GMNotes type CampaignLog)."""
    log = cards.get("sthr-campaign-log")
    art = B.ART_URLS.get("sthr-campaign-log", {})
    url = art.get("face") or B.face_ph("Campaign Log")
    return {
        "Name": "Custom_Token",
        "Nickname": "{} — Campaign Log".format(campaign_name or "Campaign"),
        "Description": "Page 1",
        "GUID": guid("campaignlog:" + (campaign_name or "c")),
        "Tags": ["CampaignLog"],
        "GMNotes": json.dumps({"id": "STHR-LOG", "type": "CampaignLog"}),
        "Transform": transform(9.0, 0.0, scale=1.0),
        "ColorDiffuse": dict(B.COLOR_DIFFUSE),
        "Locked": False, "Grid": True, "Snap": True, "Sticky": True,
        "CustomImage": {
            "ImageURL": url, "ImageSecondaryURL": "", "ImageScalar": 1.0,
            "WidthScale": 0.0,
            "CustomToken": {"Thickness": 0.2, "MergeDistancePixels": 15.0,
                            "StandUp": False, "Stackable": False},
        },
        "_note": "log fields: {}".format(
            ", ".join(k for k in ("player", "investigator1", "investigator2",
                                  "investigator3") if (log or {}).get(k))) if log else "",
    }


def build_guide_pdf(campaign_name=None):
    return {
        "Name": "Custom_PDF",
        "Nickname": "{} — Campaign Guide".format(campaign_name or "Campaign"),
        "Description": "fan content",
        "GUID": guid("guide:" + (campaign_name or "c")),
        "Tags": ["CampaignGuide"],
        "GMNotes": json.dumps({"id": "STHR-GUIDE", "type": "CampaignGuide"}),
        "Transform": transform(12.0, 0.0, scale=1.0),
        "ColorDiffuse": dict(B.COLOR_DIFFUSE),
        "CustomPDF": {"PDFUrl": "", "PDFPassword": "", "PDFPage": 0,
                      "PDFPageOffset": 0},
    }


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

    contained, ml, placed = [], {}, 0
    for i, sc in enumerate(scenarios):
        assign = assignments.get(sc["id"], {}) or {}
        box = build_scenario_box(sc, assign, cards, paths["name"])
        if not box["ContainedObjects"]:
            continue
        x = -14.0 + (i * 4.0)
        contained.append(box)
        ml[box["GUID"]] = {"lock": False,
                           "pos": {"x": round(x, 3), "y": 1.5, "z": 12.0},
                           "rot": {"x": 0, "y": 270, "z": 0}}
        placed += 1
    log_tok = build_log_token(cards, paths["name"])
    guide = build_guide_pdf(paths["name"])
    contained += [log_tok, guide]
    ml[log_tok["GUID"]] = {"lock": False,
                           "pos": {"x": 9.0, "y": 1.5, "z": -6.0},
                           "rot": {"x": 0, "y": 180, "z": 0}}
    ml[guide["GUID"]] = {"lock": False,
                         "pos": {"x": 12.5, "y": 1.5, "z": -6.0},
                         "rot": {"x": 0, "y": 180, "z": 0}}

    box = {
        "Name": "Custom_Model_Bag",
        "Nickname": paths["name"],
        "Description": "fan content — not for sale",
        "GUID": guid("campaignbox:" + campaign),
        "Tags": ["CampaignBox", "Reloadable"],
        "GMNotes": json.dumps({"filename": campaign, "id": "CB-" + campaign[:8].upper(),
                               "type": "CampaignBox"}),
        "Transform": transform(scale=1.0),
        "ColorDiffuse": dict(B.COLOR_DIFFUSE),
        "LuaScriptState": json.dumps({"ml": ml}),
        "ContainedObjects": contained,
    }
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
