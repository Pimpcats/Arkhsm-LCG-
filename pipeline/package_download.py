#!/usr/bin/env python3
"""
package_download.py — THE STILL HOUR download-box packaging (P8).

Ships the campaign the way SCED distributes custom content (SCED_BUILD_BRIEF §1,
§8; INTEGRATION §7):

  1. A **release asset** `the_still_hour.json` — the campaign content (player-card
     bag + The Appointed encounter bag + the scripted Control token), wrapped in a
     single campaign box. Upload this as a GitHub release asset so the mod's
     placeholderDownload can fetch it.

  2. A **placeholder download box** `the_still_hour_box.json` — the small object a
     user adds to their SCED game; its GMNotes carries {"filename":"the_still_hour"}
     and its Lua calls GlobalApi.placeholderDownload(filename) to pull and spawn
     the release asset in place of the box.

Inputs come from the already-built mod save (dist/the_still_hour_mod.json), so run
build_cards.py + bundle_mod.py first.

Run: python3 pipeline/package_download.py   (from repo root)
Outputs: dist/downloads/the_still_hour.json, dist/downloads/the_still_hour_box.json
"""
import hashlib
import json
import os

FILENAME = "the_still_hour"   # the SCED-downloads release asset name

# The mod's Global fetches {filename}.json from this base (verify in your fork;
# for a custom campaign, host the asset at your own releases and point SOURCE_REPO
# there). Recorded here for documentation / the box's GMNotes.
SOURCE_REPO = "https://github.com/Chr1Z93/SCED-downloads/releases/latest/download/"


def guid(seed):
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:6]


def transform(x=0.0):
    return {"posX": x, "posY": 1.2, "posZ": 0, "rotX": 0, "rotY": 180, "rotZ": 0,
            "scaleX": 1, "scaleY": 1, "scaleZ": 1}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    mod_path = os.path.join(root, "dist", "the_still_hour_mod.json")
    if not os.path.exists(mod_path):
        raise SystemExit("dist/the_still_hour_mod.json not found — run build_cards.py then bundle_mod.py first.")

    objs = json.load(open(mod_path, encoding="utf-8"))["ObjectStates"]

    out_dir = os.path.join(root, "dist", "downloads")
    os.makedirs(out_dir, exist_ok=True)

    # 1. Release asset: one campaign box holding all the content.
    campaign_box = {
        "Name": "Bag",
        "Nickname": "THE STILL HOUR",
        "Description": "An original loop-horror campaign. Card bags + the scripted Control token.",
        "GUID": guid("sthr-campaign-box"),
        "Tags": ["StillHour"],
        "Transform": transform(0),
        "ContainedObjects": objs,
    }
    release_path = os.path.join(out_dir, FILENAME + ".json")
    with open(release_path, "w", encoding="utf-8") as f:
        json.dump({"ObjectStates": [campaign_box]}, f, indent=2, ensure_ascii=False)

    # 2. Placeholder download box.
    box_lua = open(os.path.join(here, "..", "src", "tts", "download_box.lua"), encoding="utf-8").read()
    box = {
        "Name": "Bag",
        "Nickname": "THE STILL HOUR — Download Box",
        "Description": "Click Download inside the SCED mod to fetch the campaign.",
        "GUID": guid("sthr-download-box"),
        # real campaign-box tagging + GMNotes shape: docs/art_reference/
        # sced_objects/campaign_box_memory_bag.json ("Reloadable" lets SCED
        # re-fetch the download; "filename" is the placeholderDownload key)
        "Tags": ["CampaignBox", "Reloadable", "StillHour"],
        "ColorDiffuse": {"r": 0.13, "g": 0.11, "b": 0.18},
        "Transform": transform(0),
        "GMNotes": json.dumps({"filename": FILENAME, "id": "CB-STHR",
                               "type": "CampaignBox"}, separators=(",", ":")),
        "LuaScript": box_lua,
        "LuaScriptState": "",
    }
    box_path = os.path.join(out_dir, FILENAME + "_box.json")
    with open(box_path, "w", encoding="utf-8") as f:
        json.dump({"ObjectStates": [box]}, f, indent=2, ensure_ascii=False)

    # Validate.
    rel = json.load(open(release_path, encoding="utf-8"))
    contained = rel["ObjectStates"][0]["ContainedObjects"]
    n_cards = sum(len(o.get("ContainedObjects", [])) for o in contained if o.get("ContainedObjects"))
    b = json.load(open(box_path, encoding="utf-8"))["ObjectStates"][0]
    assert json.loads(b["GMNotes"])["filename"] == FILENAME
    assert "placeholderDownload" in b["LuaScript"]
    print("OK  release asset: {}  ({} objects, {} cards)".format(release_path, len(contained), n_cards))
    print("OK  download box:  {}  (filename='{}')".format(box_path, FILENAME))
    print("Next: upload {}.json as a release asset reachable at SOURCE_REPO,".format(FILENAME))
    print("      then add the download box object to the SCED game (verify GlobalApi.placeholderDownload).")


if __name__ == "__main__":
    main()
