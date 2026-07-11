#!/usr/bin/env python3
"""
build_cards.py — THE STILL HOUR card generator for SCED (Tabletop Simulator).

Turns the compact card spec into valid SCED `Card` objects (GMNotes metadata +
CustomDeck image refs + CardID/GUID/Tags). This is the authoring path described in
SCED_BUILD_BRIEF §4: spec -> SCED objects.

Usage:
    python3 build_cards.py                      # full deck -> dist/the_still_hour.json
    python3 build_cards.py --spec my.json       # alternate spec
    python3 build_cards.py --out path.json      # alternate output
    python3 build_cards.py --only sthr-elias sthr-lamp sthr-donebefore sthr-eighthgrave
                                                # Elias vertical slice -> dist/stillhour_starter.json

Structure verified against Arkham SCE 4.8.0:
  - Card object: Name="Card", Tags=[<Type>,"PlayerCard"], SidewaysCard=True only for Investigators.
  - CardID = int(deckId + 2-digit gridIndex). Each card uses its own 1x1 deck (index 00),
    except Investigators, which use a unique deckbuilding back (UniqueBack=True).
  - GMNotes = JSON *mechanical* metadata only; printed rules text lives on the ART, not here.

Deterministic GUIDs: GUID is derived from the card id (sha1) so re-running the
generator produces a stable diff instead of churning random GUIDs every build.
"""
import argparse
import hashlib
import re
import json
import os

ARKHAM_ICONS = {
    "Name": "font_arkhamicons", "Type": 1,
    "URL": "https://steamusercontent-a.akamaihd.net/ugc/16577956848173876106/49B31DA9BD35FC54A6B33926EA220FBBB2CAD038/",
}

# --- PLACEHOLDER art (swap for Strange Eons frames + generated art hosted on a CDN) ---
PH = "https://placehold.co"


def face_ph(name, land=False):
    dim = "750x523" if land else "419x600"
    return f"{PH}/{dim}/141428/e8b24a/png?text={name.replace(' ', '+')}"


PLAYER_BACK = f"{PH}/419x600/0c0c14/8a8a99/png?text=The+Still+Hour"
ENCOUNTER_BACK = f"{PH}/419x600/1a0f0f/8a8a99/png?text=The+Still+Hour+(Encounter)"

# GMNotes icon-field name map (spec key -> metadata key)
ICON_FIELDS = {
    "wil": "willpowerIcons", "int": "intellectIcons", "com": "combatIcons",
    "agi": "agilityIcons", "wild": "wildIcons",
}


def guid(card_id):
    """Stable 6-hex-char GUID derived from the card id, so builds are reproducible."""
    return hashlib.sha1(card_id.encode("utf-8")).hexdigest()[:6]


def transform():
    return {"posX": 0, "posY": 1.5, "posZ": 0, "rotX": 0, "rotY": 180, "rotZ": 0,
            "scaleX": 1.15, "scaleY": 1, "scaleZ": 1.15}


def build_gmnotes(c):
    """Emit only the metadata fields relevant to this card's type."""
    t = c["type"]
    m = {"id": c["id"], "type": t, "class": c["class"], "traits": c["traits"],
         "cycle": "The Still Hour"}
    if t == "Investigator":
        # real-SCED shape (docs/art_reference/sced_objects/investigator_front.json):
        # statline as *Icons keys, elderSignEffect {description, modifier}
        elder = {"description": c["elderSign"]}
        mod = re.match(r"\+(\d+)", c["elderSign"])
        if mod:
            elder["modifier"] = int(mod.group(1))
        m.update({
            "willpowerIcons": c["wil"], "intellectIcons": c["int"],
            "combatIcons": c["com"], "agilityIcons": c["agi"],
            "health": c["health"], "sanity": c["sanity"],
            "signatures": c["signatures"],
            "elderSignEffect": elder,
        })
    else:
        if "cost" in c:
            m["cost"] = c["cost"]
        if "level" in c:
            m["level"] = c["level"]
        for spec_key, meta_key in ICON_FIELDS.items():
            if c.get(spec_key + "Icons"):
                m[meta_key] = c[spec_key + "Icons"]
        if c.get("slot"):
            m["slot"] = c["slot"]
        if c.get("uses"):
            m["uses"] = c["uses"]
        if c.get("permanent"):
            m["permanent"] = True
        if c.get("startsInPlay"):
            m["startsInPlay"] = True
        if c.get("weakness"):
            m["weakness"] = True
        # Campaign-economy metadata: Memory price to add a Recollection to a deck.
        # Read by the StillHour interlude UI (mechanical, not printed rules text).
        if "memoryCost" in c:
            m["memoryCost"] = c["memoryCost"]
        # Encounter-card metadata (enemies/treacheries). Fight/health/evade live on
        # the art; only classification/flags belong here.
        if c.get("unique"):
            m["unique"] = True
        if c.get("elite"):
            m["elite"] = True
        if "quantity" in c:
            m["quantity"] = c["quantity"]
        # Victory X (Memory): banked once per campaign per named enemy when
        # defeated (loop campaigns respawn enemies; the log gates the claim).
        if "victory" in c:
            m["victory"] = c["victory"]
    return json.dumps(m, separators=(",", ":"))


# Optional real-art overlay written by CardForge Studio's Apply tab:
# pipeline/art_urls.json  {cardId: {"face": url, "back": url}} — URLs may be
# hosted (https://...) or local (file:///...) for private TTS testing.
def _load_art_urls():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art_urls.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return {}


ART_URLS = _load_art_urls()


def tags_for(c):
    """Real-SCED tagging (see docs/art_reference/sced_objects/): a type tag is
    added only where SCED scripting needs it (Investigator, Asset slots,
    Location connections); everything else carries just its deck tag."""
    t = c["type"]
    if t == "Investigator":
        return ["Investigator", "PlayerCard"]
    if c.get("encounter"):
        return [t, "ScenarioCard"] if t == "Location" else ["ScenarioCard"]
    if t == "Asset":
        return ["Asset", "PlayerCard"]
    return ["PlayerCard"]


# SCED's standard card tint (matches every vendored example object)
COLOR_DIFFUSE = {"r": 0.713235259, "g": 0.713235259, "b": 0.713235259}


def build_card(c):
    is_inv = c["type"] == "Investigator"
    is_encounter = bool(c.get("encounter"))
    deck_id = str(c["deck"])
    # campaign-wide back art: art_urls.json may carry "_player_back" /
    # "_encounter_back" (string URL or {"face": url}) — the owner's own backs
    def deck_back(key, default):
        v = ART_URLS.get(key)
        if isinstance(v, dict):
            v = v.get("face")
        return v or default
    if is_inv:
        back = face_ph(c["name"] + " (Deckbuilding)", land=True)
    elif is_encounter:
        back = deck_back("_encounter_back", ENCOUNTER_BACK)
    else:
        back = deck_back("_player_back", PLAYER_BACK)
    art = ART_URLS.get(c["id"], {})
    return {
        "Name": "Card", "Nickname": c["name"], "Description": c.get("subtitle", ""),
        "GUID": guid(c["id"]), "CardID": int(deck_id + "00"), "SidewaysCard": is_inv,
        "Tags": tags_for(c), "LuaScript": "", "LuaScriptState": "",
        "ColorDiffuse": dict(COLOR_DIFFUSE), "Hands": True,
        "HideWhenFaceDown": not is_inv,
        "GMNotes": build_gmnotes(c), "Transform": transform(),
        "CustomUIAssets": [ARKHAM_ICONS],
        "CustomDeck": {deck_id: {
            "FaceURL": art.get("face") or face_ph(c["name"], land=is_inv),
            "BackURL": art.get("back") or back,
            "NumWidth": 1, "NumHeight": 1, "Type": 0,
            "UniqueBack": is_inv, "BackIsHidden": is_inv}},
    }


def build_bag(cards, nickname):
    return {
        "Name": "Bag", "Nickname": nickname, "Description": "",
        "GUID": guid("bag:" + nickname), "Tags": ["StillHour"], "Transform": transform(),
        "ContainedObjects": cards,
    }


def generate(spec, out_path, nickname):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cards = [build_card(c) for c in spec]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"ObjectStates": [build_bag(cards, nickname)]}, f, indent=2)

    # Validate: round-trip + metadata parses + no duplicate CardIDs/ids.
    d = json.load(open(out_path, encoding="utf-8"))
    seen_ids, seen_cardids = set(), set()
    for card in d["ObjectStates"][0]["ContainedObjects"]:
        md = json.loads(card["GMNotes"])
        assert md["id"] not in seen_ids, f"duplicate card id {md['id']}"
        assert card["CardID"] not in seen_cardids, f"duplicate CardID {card['CardID']}"
        seen_ids.add(md["id"])
        seen_cardids.add(card["CardID"])
        print(f"OK  {card['Nickname']:28} CardID={card['CardID']} type={md['type']:12} id={md['id']}")
    print(f"Wrote {out_path}  ({len(cards)} cards in a bag)\n")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    ap = argparse.ArgumentParser(description="Generate SCED Card objects for THE STILL HOUR.")
    ap.add_argument("--spec", default=os.path.join(here, "stillhour_cards_spec.json"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", nargs="*", default=None,
                    help="Restrict output to these card ids (e.g. the Elias starter slice).")
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    if args.only:
        wanted = set(args.only)
        spec = [c for c in spec if c["id"] in wanted]
        missing = wanted - {c["id"] for c in spec}
        if missing:
            raise SystemExit(f"--only referenced unknown card ids: {sorted(missing)}")
        generate(spec, args.out or os.path.join(root, "dist", "stillhour_starter.json"),
                 "THE STILL HOUR — Starter Slice")
        return

    # Default full build: player cards, plus the encounter deck if its spec exists.
    generate(spec, args.out or os.path.join(root, "dist", "the_still_hour.json"),
             "THE STILL HOUR — Player Cards")
    enc_spec_path = os.path.join(here, "stillhour_encounter_spec.json")
    if args.out is None and os.path.exists(enc_spec_path):
        generate(json.load(open(enc_spec_path, encoding="utf-8")),
                 os.path.join(root, "dist", "the_still_hour_encounter.json"),
                 "THE STILL HOUR — The Appointed")


if __name__ == "__main__":
    main()
