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
     user adds to their SCED game; its GMNotes carries {"filename":"the_still_hour"}
     and its Lua calls GlobalApi.placeholderDownload(filename) to pull and spawn
     the release asset in place of the box.

Card images, log pages and the guide PDF carry whatever URLs
pipeline/art_urls.json holds: hosted raw.githubusercontent URLs after
publish_hosted.py (which passes --require-hosted, so a machine-local file:///
URL fails the build), or local file:/// URLs for solo testing from the Studio.

Run: python3 pipeline/package_download.py [--require-hosted]   (from repo root)
Outputs: dist/downloads/the_still_hour.json, dist/downloads/the_still_hour_box.json
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

FILENAME = "the_still_hour"   # the SCED-downloads release asset name

# The mod's Global fetches {filename}.json from this base (verify in your fork;
# for a custom campaign, host the asset at your own releases and point SOURCE_REPO
# there). Recorded here for documentation / the box's GMNotes.
SOURCE_REPO = "https://github.com/Chr1Z93/SCED-downloads/releases/latest/download/"

# Place spots for the loose content, beside the story-deck row the real
# campaign box uses (z -36.385).
EXTRA_PLACE = [{"x": 2.366, "y": 1.55, "z": -36.385},
               {"x": -3.959, "y": 1.55, "z": -36.385},
               {"x": 5.529, "y": 1.55, "z": -36.385}]


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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--require-hosted", action="store_true",
                    help="fail if any file:/// URL would ship (publish_hosted.py)")
    a = ap.parse_args(argv)

    mod_path = os.path.join(ROOT, "dist", "the_still_hour_mod.json")
    if not os.path.exists(mod_path):
        raise SystemExit("dist/the_still_hour_mod.json not found — run build_cards.py then bundle_mod.py first.")
    objs = json.load(open(mod_path, encoding="utf-8"))["ObjectStates"]

    out_dir = os.path.join(ROOT, "dist", "downloads")
    os.makedirs(out_dir, exist_ok=True)

    # 1. Release asset: the campaign box (one object) holding all the content.
    box, compiled = campaign_box()
    import table_presence as T
    state = json.loads(box.get("LuaScriptState") or "{}")
    ml = state.setdefault("ml", {})
    for i, o in enumerate(objs):
        o = copy.deepcopy(o)
        pos = EXTRA_PLACE[i % len(EXTRA_PLACE)]
        o["Transform"] = T.transform(pos, 270, (o["Transform"].get("scaleX", 1),
                                                o["Transform"].get("scaleY", 1),
                                                o["Transform"].get("scaleZ", 1)))
        box["ContainedObjects"].append(o)
        ml[o["GUID"]] = T.ml_entry(pos)
    box["LuaScriptState"] = json.dumps(state, indent=2)
    box["Description"] = ("An original loop-horror campaign (fan content, not for "
                          "sale). Place lays out the log, guide and minicards.")
    release_path = os.path.join(out_dir, FILENAME + ".json")
    with open(release_path, "w", encoding="utf-8") as f:
        json.dump(box, f, indent=2, ensure_ascii=False)

    # 2. Placeholder download box.
    box_lua = open(os.path.join(ROOT, "src", "tts", "download_box.lua"), encoding="utf-8").read()
    placeholder = {
        "Name": "Bag",
        "Nickname": "THE STILL HOUR — Download Box",
        "Description": "Click Download inside the SCED mod to fetch the campaign.",
        "GUID": guid("sthr-download-box"),
        # real campaign-box tagging + GMNotes shape: docs/art_reference/
        # sced_objects/campaign_box_memory_bag.json ("Reloadable" lets SCED
        # re-fetch the download; "filename" is the placeholderDownload key)
        "Tags": ["CampaignBox", "Reloadable", "StillHour"],
        "ColorDiffuse": {"r": 0.13, "g": 0.11, "b": 0.18},
        # campaign-box area at the top of the SCED table, off the mats
        "Transform": dict(transform(63.0), posZ=8.0),
        "GMNotes": json.dumps({"filename": FILENAME, "id": "CB-STHR",
                               "type": "CampaignBox"}, separators=(",", ":")),
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
    assert json.loads(b["GMNotes"])["filename"] == FILENAME
    assert "placeholderDownload" in b["LuaScript"]
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
    print("Next: upload {}.json as a release asset reachable at SOURCE_REPO,".format(FILENAME))
    print("      then add the download box object to the SCED game (verify GlobalApi.placeholderDownload).")


if __name__ == "__main__":
    main()
