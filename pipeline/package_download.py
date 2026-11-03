#!/usr/bin/env python3
"""
package_download.py — THE STILL HOUR download-box packaging (P8).

Ships the campaign the way SCED distributes custom content (SCED_BUILD_BRIEF §1,
§8; INTEGRATION §7):

  1. A **release asset** `the_still_hour.json` — ONE object, the campaign box,
     exactly what SCED's Global fetches as `{SOURCE_REPO}{filename}.json` and
     hands to spawnObjectJSON({json = request.text}) (src/Global/Global.ttslua,
     contentDownloadCallback) — so the file is the object itself, not a save
     with ObjectStates. The box is the real CampaignBox shape
     (docs/art_reference/sced_objects/campaign_box_memory_bag.json): SCED's box
     mesh + MemoryBag script (Place / Recall), Tags [CampaignBox],
     GMNotes {filename, id, type}. It holds the scenario books once every
     scenario is locked in (compile_campaign.py), the investigator minicards,
     the campaign log and the campaign guide (table_presence.py), plus the
     player-card bag, the encounter bag and the scripted Control token.

  2. A **placeholder download box** `the_still_hour_box.json` — the small object a
     user adds to their SCED game. Press Download: its Lua fetches the release asset
     from the address in its GMNotes ({"filename", "url"}) with WebRequest.get and
     spawns it in its place with spawnObjectJSON, as SCED's own Download menu does
     (the menu itself only reads SCED's own release, so it cannot load ours). The
     address is the build's own file on GitHub: the main branch by default,
     --download-ref names another branch or commit.

Card images, log pages and the guide PDF carry whatever URLs
pipeline/art_urls.json holds: hosted raw.githubusercontent URLs after
publish_hosted.py (which passes --require-hosted, so a machine-local file:///
URL fails the build), or local file:/// URLs for solo testing from the Studio
(which passes --local: without it, placeholder or file:/// image URLs in the
release files are refused).

Run: python3 pipeline/package_download.py [--require-hosted | --local]   (from repo root)
Outputs: dist/downloads/the_still_hour.json, dist/downloads/the_still_hour_box.json,
         dist/saved_object_the_still_hour.json
"""
import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_cards as B  # noqa: E402  (release_guard / --local)
import campaign_config  # noqa: E402
from campaign_config import CFG  # noqa: E402

FILENAME = CFG.slug   # the SCED-downloads release asset name

# The mod's Global fetches {filename}.json from this base (verify in your fork;
# for a custom campaign, host the asset at your own releases and point SOURCE_REPO
# there). Recorded here for documentation / the box's GMNotes.
SOURCE_REPO = "https://github.com/Chr1Z93/SCED-downloads/releases/latest/download/"   # SCED's own menu only reads this
REPO = "Pimpcats/Arkhsm-LCG-"

# Place spots for the loose content, beside the story-deck row the real
# campaign box uses (z -36.385).
# one spot per extra object (card bags, Control, Static token): two sharing a
# spot on Place would drop one into the other
# in the order of the mod's objects: Player Cards bag, The Appointed bag,
# Control, Static. They go in the open area inside SCED's grey lines above the
# scenario mat (owner's pick), beyond the row the scenario boxes use (x 12.25):
# the bags and the Static token in a row, the Control on its own to the left
# with room for its ~4.6-wide button panel (up to ~6.5 in the interlude).
EXTRA_PLACE = [{"x": 24.0, "y": 1.55, "z": -4.0},
               {"x": 24.0, "y": 1.55, "z": -9.0},
               {"x": 25.0, "y": 1.55, "z": 9.0},
               {"x": 24.0, "y": 1.55, "z": -17.0}]


def guid(seed):
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:6]


# the player-card pouches: a row from the old bag's spot toward the Static token, which moves past its end
POUCH_PLACE = [{"x": 24.0, "y": 1.55, "z": -1.0}]
POUCH_STEP = 2.4
# a pouch takes its investigator's class colour (Arkham's class colours)
CLASS_TINT = {"Guardian": (0.13, 0.38, 0.77), "Seeker": (0.92, 0.57, 0.14), "Rogue": (0.15, 0.55, 0.27),
              "Mystic": (0.47, 0.25, 0.64), "Survivor": (0.75, 0.16, 0.16), "Neutral": (0.55, 0.52, 0.47)}


def sced_cards_by_id():
    """SCED's own player-card objects (objects/AllPlayerCards.*/ in the pinned SCED checkout), by card id,
    with their GMNotes inlined: the starting decks are built from them, so every card is SCED's own."""
    import glob
    import starter_deck_ids as SD
    root = SD.sced_dir()
    folders = glob.glob(os.path.join(root, "objects", "AllPlayerCards.*"))
    folders = [f for f in folders if os.path.isdir(f)]
    if not folders:
        raise SystemExit("SCED's AllPlayerCards objects not found under " + root)
    out = {}
    for path in glob.glob(os.path.join(folders[0], "*.json")):
        d = json.load(open(path, encoding="utf-8"))
        gp = d.pop("GMNotes_path", None)
        if not gp:
            continue
        text = open(os.path.join(root, "objects", gp), encoding="utf-8").read()
        cid = json.loads(text).get("id")
        if cid and cid not in out:
            d["GMNotes"] = text
            out[cid] = d
    return out


def starting_deck(inv, name):
    """The investigator's starter deck (Appendix: Starting Decks; campaigns/<id>/starter_decks.json) as one
    Deck of SCED's own cards, each copy with its own GUID. The random basic weakness is drawn at the table."""
    lists = json.load(open(os.path.join(ROOT, "campaigns", CFG.id, "starter_decks.json"), encoding="utf-8"))
    if inv not in lists:
        return None
    sced = sced_cards_by_id()
    cards, custom, ids = [], {}, []
    for cid, qty in lists[inv]:
        src = sced.get(cid)
        if not src:
            raise SystemExit("starter card %s (%s) is not in SCED's AllPlayerCards" % (cid, inv))
        for k in range(qty):
            c = copy.deepcopy(src)
            c["GUID"] = guid("starter:%s:%s:%d" % (inv, cid, k))
            c["Transform"] = {"posX": 0, "posY": 0, "posZ": 0, "rotX": 0, "rotY": 180, "rotZ": 180,
                              "scaleX": 1, "scaleY": 1, "scaleZ": 1}
            cards.append(c)
            ids.append(c["CardID"])
            custom.update(c.get("CustomDeck") or {})
    return {"Name": "Deck", "Nickname": "%s — Starting Deck" % name,
            "Description": "Their starter deck (%d cards). Shuffle in 1 random basic weakness from SCED's player "
                           "card panel, then put the deck on your playmat's Deck spot." % len(cards),
            "GUID": guid("starterdeck:" + inv), "DeckIDs": ids, "CustomDeck": custom,
            "Transform": {"posX": 0, "posY": 0, "posZ": 0, "rotX": 0, "rotY": 180, "rotZ": 180,
                          "scaleX": 1, "scaleY": 1, "scaleZ": 1},
            "ContainedObjects": cards}


# The Investigators box's Place: one row per investigator, reading left to right along -z (as the scenario
# cards lie), rows down the table along +x, in the open area beside the campaign's loose objects.
LINEUP_X0, LINEUP_DX = 28.0, 4.4          # first row, row spacing
LINEUP_Z0 = 0.0                           # the investigator card
LINEUP_DZ = 2.7                           # each further card
LINEUP_Y = 1.6


def investigators_box(rows):
    """SCED's MemoryBag box holding every investigator; Place lays each one out in a row: investigator card,
    minicard, the cards their back requires (signatures and weakness), their quest card, its unlocked card
    face down, and their starting deck face down."""
    import table_presence as T
    contained, ml = [], {}

    def put(obj, pos, ry, rz=0):
        contained.append(obj)
        ml[obj["GUID"]] = T.ml_entry(pos, ry, rz)

    for i, (inv, row, mini, deck) in enumerate(rows):
        x = LINEUP_X0 + LINEUP_DX * i
        z = LINEUP_Z0
        kinds = {}
        for c in row:
            md = json.loads(c.get("GMNotes") or "{}")
            kinds.setdefault(md.get("type"), []).append((md, c))
        ordered = [c for md, c in kinds.get("Investigator", [])]
        quest = [c for md, c in sum(kinds.values(), []) if "-quest-" in md.get("id", "")]
        done = [c for md, c in sum(kinds.values(), []) if "-questdone-" in md.get("id", "")]
        weak = [c for md, c in sum(kinds.values(), []) if md.get("weakness") or md.get("type") == "Treachery"
                and c not in quest and c not in done]
        rest = [c for c in row if c not in ordered and c not in quest and c not in done and c not in weak]
        for c in ordered:
            put(c, {"x": x, "y": LINEUP_Y, "z": z}, 180)          # the sideways investigator card
            z -= 3.3
        if mini:
            put(mini, {"x": x, "y": LINEUP_Y, "z": z + 0.6}, 270)
            z -= LINEUP_DZ - 0.6
        for c in rest + weak + quest:
            put(c, {"x": x, "y": LINEUP_Y, "z": z}, 270)
            z -= LINEUP_DZ
        for c in done:
            put(c, {"x": x, "y": LINEUP_Y, "z": z}, 270, 180)     # face down until its quest is met
            z -= LINEUP_DZ
        if deck:
            put(deck, {"x": x, "y": LINEUP_Y, "z": z}, 270, 180)
    box = T.memory_bag(CFG.name + " — Investigators", {"id": "investigators", "type": "InvestigatorBox"}, None,
                       T.MESH_SMALL, T.SCALE_SMALL, contained, ml,
                       desc="Place lays out every investigator in a row: their card, minicard, signature cards, "
                            "weakness, quest card (its unlocked card face down beside it) and starting deck. Choose, "
                            "then each player takes their row to their playmat and shuffles 1 random basic weakness "
                            "(SCED's player card panel) into the deck.")
    box["GUID"] = guid("box:investigators:" + CFG.slug)
    return box


def player_pouches(bag, minicards=None):
    """The player-card bag split into pouches: one per investigator (their investigator card, the cards their
    back requires, their personal quest card and its unlocked card) in the campaign's order, then one with
    the Recollections and anything else. Every card keeps its data and GUID."""
    spec = json.load(open(CFG.path("cards_spec"), encoding="utf-8"))
    groups, names, classes = [], {}, {}
    for c in spec:
        if c.get("type") != "Investigator":
            continue
        ids = {c["id"]}
        for group in c.get("signatures") or []:
            ids.update(group.keys())
        short = c["id"][len(CFG.prefix):] if c["id"].startswith(CFG.prefix) else c["id"]
        ids.update({CFG.prefix + "-quest-" + short, CFG.prefix + "-questdone-" + short})
        groups.append((c["id"], ids))
        names[c["id"]] = c.get("name", c["id"])
        classes[c["id"]] = c.get("class") or c.get("faction") or "Neutral"
    owned = {}
    for inv, ids in groups:
        for cid in ids:
            owned.setdefault(cid, inv)
    by = {inv: [] for inv, _ in groups}
    rest = []
    for card in bag.get("ContainedObjects", []):
        try:
            cid = json.loads(card.get("GMNotes") or "{}").get("id")
        except ValueError:
            cid = None
        (by[owned[cid]] if cid in owned else rest).append(card)
    pouches = []

    def pouch(nickname, cards, tint, desc):
        r, g, b = tint
        return {"Name": "Bag", "Nickname": nickname, "Description": desc,
                "GUID": guid("pouch:" + nickname), "Tags": list(bag.get("Tags") or []),
                "ColorDiffuse": {"r": r, "g": g, "b": b}, "Transform": dict(bag.get("Transform") or {}),
                "ContainedObjects": cards}
    # every investigator in one box whose Place lays them all out, one row each (owner, 2026-11-03: see them
    # all to choose, then hand a row to its player; no seating step)
    rows = []
    for inv, _ in groups:
        row = list(by[inv])
        mini = (minicards or {}).get(inv)
        deck = starting_deck(inv, names[inv])
        rows.append((inv, row, mini, deck))
    pouches.append(investigators_box(rows))
    if rest:
        pouches.append(pouch("Recollections — Player Cards", rest, CLASS_TINT["Neutral"],
                             "Recollections, bought between loops: two of each (Anchor Point: one)."))
    return pouches


def transform(x=0.0):
    # above SCED's table surface (y ~1.48), so it drops on rather than through
    return {"posX": x, "posY": 2.5, "posZ": 0, "rotX": 0, "rotY": 180, "rotZ": 0,
            "scaleX": 1, "scaleY": 1, "scaleZ": 1}


def campaign_box():
    """The compiled campaign box when every scenario is locked in; otherwise
    the campaign box with the table-presence objects only."""
    import compile_campaign as cc
    import table_presence as T
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        r = cc.compile_campaign(tmp, require_locked=True)
        if r.get("ok"):
            return json.load(open(tmp, encoding="utf-8"))["ObjectStates"][0], True
    except Exception as e:                       # never block packaging on it
        print("note: campaign compile skipped ({})".format(e))
    finally:
        os.remove(tmp)
    return T.campaign_box(), False


def local_urls(obj):
    return json.dumps(obj).count("file:///")


# Recollections are bought from a shared pool, by any investigator, up to the
# usual 2 copies of a title per deck: ship that playset of 2 (the bag then holds
# about fifty cards, not a hundred and ten). A third copy, for another
# investigator, is a copy in Tabletop Simulator (hover, Ctrl+C, Ctrl+V); the
# guide says so. (The copies share their card sheet, so they add no textures.)
RECOLLECTION_COPIES = 2


def add_recollection_copies(bag):
    extra = []
    for card in bag.get("ContainedObjects", []):
        try:
            md = json.loads(card.get("GMNotes") or "{}")
        except ValueError:
            continue
        if "memoryCost" not in md:
            continue
        for k in range(1, RECOLLECTION_COPIES):
            c = copy.deepcopy(card)
            c["GUID"] = guid("{}-copy{}".format(md.get("id", card["GUID"]), k))
            extra.append(c)
    bag["ContainedObjects"].extend(extra)
    return len(extra)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--campaign", help="campaign id (campaigns/<id>/build.json); default $CAMPAIGN or still_hour")
    ap.add_argument("--require-hosted", action="store_true",
                    help="fail if any file:/// URL would ship (publish_hosted.py)")
    ap.add_argument("--download-ref", default=os.environ.get("DOWNLOAD_REF", "main"),
                    help="branch or commit the download box fetches the campaign from (default main)")
    B.add_local_flag(ap)
    a = ap.parse_args(argv)

    mod_path = os.path.join(ROOT, "dist", CFG.slug + "_mod.json")
    if not os.path.exists(mod_path):
        raise SystemExit("dist/%s_mod.json not found — run build_cards.py then bundle_mod.py first." % CFG.slug)
    objs = json.load(open(mod_path, encoding="utf-8"))["ObjectStates"]

    out_dir = os.path.join(ROOT, "dist", "downloads")
    os.makedirs(out_dir, exist_ok=True)

    # 1. Release asset: the campaign box (one object) holding all the content.
    box, compiled = campaign_box()
    import table_presence as T
    state = json.loads(box.get("LuaScriptState") or "{}")
    ml = state.setdefault("ml", {})
    assert len(objs) <= len(EXTRA_PLACE), "add a Place spot for every extra object"
    for i, o in enumerate(objs):
        # the mod's loose "The Appointed" bag is a test fixture for the relay;
        # every one of its cards already ships in the scenario boxes, and a
        # bag by that name in the campaign box would spoil the boss
        if any(n in (o.get("Nickname") or "") for n in CFG.skip_bags):
            continue
        o = copy.deepcopy(o)
        if "Player Cards" in (o.get("Nickname") or ""):
            add_recollection_copies(o)
            # each minicard rides in its investigator's pouch: the minicard deck leaves the box
            minicards = {}
            for k, b in enumerate(list(box["ContainedObjects"])):
                if b.get("Nickname") == "Investigator Minicards":
                    for m in b.get("ContainedObjects") or []:
                        mid = json.loads(m.get("GMNotes") or "{}").get("id", "")
                        if mid.endswith("-m"):
                            m = copy.deepcopy(m)
                            m["Transform"] = dict(m.get("Transform") or {}, rotX=0, rotZ=0)
                            minicards[mid[:-2]] = m
                    box["ContainedObjects"].remove(b)
                    ml.pop(b.get("GUID"), None)
            # one pouch per investigator and one of Recollections (owner): laid out in a row, each with its
            # own Place spot
            for j, pouch in enumerate(player_pouches(o, minicards)):
                pos = dict(POUCH_PLACE[0], z=POUCH_PLACE[0]["z"] - POUCH_STEP * j)
                pouch["Transform"] = T.transform(pos, 270, (1, 1, 1))
                box["ContainedObjects"].append(pouch)
                ml[pouch["GUID"]] = T.ml_entry(pos, lock=False)
            continue
        pos = EXTRA_PLACE[i]
        o["Transform"] = T.transform(pos, 270, (o["Transform"].get("scaleX", 1),
                                                o["Transform"].get("scaleY", 1),
                                                o["Transform"].get("scaleZ", 1)))
        box["ContainedObjects"].append(o)
        # Place keeps a locked object locked (the Control token is saved locked)
        ml[o["GUID"]] = T.ml_entry(pos, lock=o.get("Locked", False))
    box["LuaScriptState"] = json.dumps(state, indent=2)
    box["Description"] = ("An original " + CFG.genre + " campaign (fan content, not for "
                          "sale). Place lays out the log, guide and minicards.")
    release_path = os.path.join(out_dir, FILENAME + ".json")
    release_text = json.dumps(box, indent=2, ensure_ascii=False)
    # the same box as a TTS "Saved Object" (save-file shape), so the owner can
    # import the whole campaign by hand: Objects -> Saved Objects
    saved_path = os.path.join(ROOT, "dist", "saved_object_" + CFG.slug + ".json")
    saved_text = json.dumps({"SaveName": CFG.name, "GameMode": "", "Date": "",
                             "Table": "", "Sky": "", "Note": "", "Rules": "", "XmlUI": "",
                             "LuaScript": "", "LuaScriptState": "", "ObjectStates": [box]},
                            indent=2, ensure_ascii=False)
    # the release files carry hosted image URLs only (see build_cards.release_guard)
    B.release_guard(release_path, release_text, a.local)
    B.release_guard(saved_path, saved_text, a.local)
    with open(release_path, "w", encoding="utf-8") as f:
        f.write(release_text)
    with open(saved_path, "w", encoding="utf-8") as f:
        f.write(saved_text)

    # 2. Placeholder download box.
    box_lua = campaign_config.lua_text(os.path.join(ROOT, "src", "tts", "download_box.lua"))
    placeholder = {
        "Name": "Bag",
        "Nickname": CFG.upper_name + " — Download Box",
        "Description": "Click Download inside the SCED mod to fetch the campaign.",
        "GUID": guid(CFG.download_box_guid),
        # real campaign-box GMNotes shape: docs/art_reference/sced_objects/
        # campaign_box_memory_bag.json ("filename" is the placeholderDownload key)
        # not tagged CampaignBox or Reloadable: SCED's campaign exporter reads an empty
        # Bag with that tag as "the campaign box with all objects placed", and its
        # "Redownload this" asks SCED's own release for the file (the campaign box
        # itself is tagged CampaignBox only, see table_presence.campaign_box)
        "Tags": [CFG.tag],
        "ColorDiffuse": {"r": 0.13, "g": 0.11, "b": 0.18},
        # campaign-box area at the top of the SCED table, off the mats
        "Transform": dict(transform(63.0), posZ=8.0),
        "GMNotes": json.dumps({"filename": FILENAME, "id": CFG.box_id, "type": "DownloadBox",
                               "url": "https://raw.githubusercontent.com/{}/{}/dist/downloads/{}.json".format(
                                   REPO, a.download_ref, FILENAME)}, separators=(",", ":")),
        "LuaScript": box_lua,
        "LuaScriptState": "",
    }
    box_path = os.path.join(out_dir, FILENAME + "_box.json")
    with open(box_path, "w", encoding="utf-8") as f:
        json.dump({"ObjectStates": [placeholder]}, f, indent=2, ensure_ascii=False)

    # Validate.
    rel = json.load(open(release_path, encoding="utf-8"))
    assert rel["Name"] == "Custom_Model_Bag" and "ObjectStates" not in rel
    gm = json.loads(rel["GMNotes"])
    assert gm["type"] == "CampaignBox" and gm["filename"] == FILENAME
    assert "buttonClick_place" in rel["LuaScript"]
    for g in json.loads(rel["LuaScriptState"])["ml"]:
        assert any(o["GUID"] == g for o in rel["ContainedObjects"]), g
    kinds = sorted({o["Name"] for o in rel["ContainedObjects"]})
    b = json.load(open(box_path, encoding="utf-8"))["ObjectStates"][0]
    bgm = json.loads(b["GMNotes"])
    assert bgm["filename"] == FILENAME and bgm["url"].endswith("/dist/downloads/{}.json".format(FILENAME))
    assert "WebRequest.get" in b["LuaScript"] and "spawnObjectJSON" in b["LuaScript"]
    n_local = local_urls(rel)
    print("OK  release asset: {}  ({} objects: {}; scenarios {})".format(
        release_path, len(rel["ContainedObjects"]), ", ".join(kinds),
        "compiled" if compiled else "pending lock-in"))
    print("OK  download box:  {}  (filename='{}')".format(box_path, FILENAME))
    if n_local:
        msg = "{} machine-local file:/// URL(s) in the release asset".format(n_local)
        if a.require_hosted:
            raise SystemExit("FAIL: " + msg + " (run pipeline/publish_hosted.py)")
        print("WARN: " + msg + " — fine for solo testing, not for sharing")
    print("Next: commit and push dist/downloads/{0}.json; the download box fetches it from {1}.".format(
        FILENAME, bgm["url"]))


if __name__ == "__main__":
    main()
