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
     mesh + MemoryBag script (Place / Recall), Tags [CampaignBox, Reloadable],
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
               {"x": 24.0, "y": 1.55, "z": -14.0}]


def guid(seed):
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:6]


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
# usual 2 copies of a title per deck: ship 4 of each so two investigators can
# each take a full playset without copying cards in TTS.
RECOLLECTION_COPIES = 4


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
        pos = EXTRA_PLACE[i]
        o["Transform"] = T.transform(pos, 270, (o["Transform"].get("scaleX", 1),
                                                o["Transform"].get("scaleY", 1),
                                                o["Transform"].get("scaleZ", 1)))
        box["ContainedObjects"].append(o)
        ml[o["GUID"]] = T.ml_entry(pos)
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
        # real campaign-box tagging + GMNotes shape: docs/art_reference/
        # sced_objects/campaign_box_memory_bag.json ("Reloadable" lets SCED
        # re-fetch the download; "filename" is the placeholderDownload key)
        # not tagged CampaignBox or Reloadable: SCED's campaign exporter reads an empty
        # Bag with that tag as "the campaign box with all objects placed", and its
        # "Redownload this" asks SCED's own release for the file
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
