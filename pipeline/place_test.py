#!/usr/bin/env python3
"""place_test.py — a small Saved Object that finds out WHY a scenario box's Place stops Tabletop Simulator.

The owner's game stopped when Place laid out The First Hour (39 objects, 43 card textures). That
was the first time TTS ever had to spawn this campaign's Card and Deck objects with their images,
and the cause could not be told from here (docs/design/PLACE_BUTTON_AUDIT.md). This file holds five
boxes. The first four are laid out by the same Place script as the campaign's own, so that pressing
them one by one on a fresh table says which part is responsible:

  1 One card         a single location card on its own 750 x 1050 images (2 textures)
  2 Structure only   The First Hour's objects and decks exactly, with every image replaced by ONE
                     shared image (1 texture, 43 deck ids)
  3 Sprite sheets    The First Hour as the build now makes it (4 textures)
  4 One image/card   The First Hour as the first build made it, one image per card (43 textures)

Press them in that order, Recall before the next. The first one that stops TTS names the cause
(a card, the object structure, the textures). The Lua log (Player.log) ends on the step that was
running. The fifth box separates the script from the content:

  5 SCED's own Place  the same cards and sprite sheets as 3, laid out by SCED's own, unmodified
                      MemoryBag script (it empties the box and Recall refills it, as every official
                      box does), with none of this campaign's code in the Place

On a fresh table, press it after a stop: if 5 stops TTS too, the script is not the cause; if 5 works
and 3 stopped TTS, the campaign's Place script is. Nothing here is the campaign: no Control token,
no log, no guide.

    python3 pipeline/place_test.py [--local]      ->  dist/saved_object_place_test.json
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_cards as B  # noqa: E402
import compile_campaign as CC  # noqa: E402
import table_presence as T  # noqa: E402

OUT = os.path.join(ROOT, "dist", "saved_object_place_test.json")
NAME = "The Still Hour — Place test"
BOX_ID = "CB-PTEST"


def prologue_box(sheets):
    """The First Hour's scenario box, built with or without sprite sheets."""
    paths = CC.campaign_paths()
    cards = CC.load_cards(paths)
    assignments = json.load(open(paths["assignments"], encoding="utf-8"))
    manifest = json.load(open(paths["manifest"], encoding="utf-8"))
    sc = next(s for s in manifest["scenarios"] if s["id"] == "prologue")
    saved = B.SHEETS
    if not sheets:
        B.SHEETS = {}
    try:
        return CC.build_scenario_box(sc, assignments.get(sc["id"], {}) or {}, cards, paths["name"])
    finally:
        B.SHEETS = saved


def strip_loop_tags(objs):
    """Remove the Prologue's own loop tags so the test box can bake its own."""
    for o in objs:
        o["Tags"] = [t for t in o.get("Tags") or [] if not (t == T.LOOP_TAG or t.startswith("StillHourBox_"))]
        strip_loop_tags(o.get("ContainedObjects") or [])


def reguid(objs, ml, seed):
    """New GUIDs for every object (the same cards sit in several test boxes on one table); ml follows."""
    new_ml = {}

    def walk(o, top):
        old = o["GUID"]
        o["GUID"] = T.guid(seed + ":" + old)
        if top:
            new_ml[o["GUID"]] = ml[old]
        for c in o.get("ContainedObjects") or []:
            walk(c, False)
    for o in objs:
        walk(o, True)
    return new_ml


def one_texture(objs, url):
    """Every CustomDeck entry points at the same image: the structure stays, the textures are one."""
    for o in objs:
        for entry in (o.get("CustomDeck") or {}).values():
            entry["FaceURL"] = url
            entry["BackURL"] = url
        one_texture(o.get("ContainedObjects") or [], url)


def variant(sid, box):
    """(objects, ml) of a copy of `box` for the test box `sid`: own GUIDs, no loop tags yet."""
    contained = copy.deepcopy(box["ContainedObjects"])
    ml = json.loads(box["LuaScriptState"])["ml"]
    strip_loop_tags(contained)
    return contained, reguid(contained, ml, sid)


def count_images(objs):
    urls = set()

    def walk(o):
        for e in (o.get("CustomDeck") or {}).values():
            urls.update((e["FaceURL"], e["BackURL"]))
        for c in o.get("ContainedObjects") or []:
            walk(c)
    for o in objs:
        walk(o)
    return len(urls)


def build():
    sheet_box = prologue_box(sheets=True)
    card_box = prologue_box(sheets=False)
    if not B.SHEETS:
        raise SystemExit("no sprite sheets in art_urls.json: run pipeline/publish_hosted.py first "
                         "(or pass --local for a private build without them)")
    boxes = []

    # 1: one card on its own images
    contained, ml = variant("ptest1", card_box)
    pick = next(o for o in contained if o.get("Name") == "Card"
                and "Location" in (o.get("Tags") or []))
    contained = [pick]
    ml = {pick["GUID"]: ml[pick["GUID"]]}
    boxes.append(T.scenario_box("Test 1 — one card", "ptest1", contained, ml))

    # 2: the structure, one shared image
    contained, ml = variant("ptest2", card_box)
    shared = (B.ART_URLS.get("_encounter_back") or "").strip()
    if isinstance(B.ART_URLS.get("_encounter_back"), dict):
        shared = B.ART_URLS["_encounter_back"].get("face") or shared
    shared = shared or B.ENCOUNTER_BACK
    one_texture(contained, shared)
    boxes.append(T.scenario_box("Test 2 — structure, one image", "ptest2", contained, ml))

    # 3: sprite sheets (the build)
    contained, ml = variant("ptest3", sheet_box)
    boxes.append(T.scenario_box("Test 3 — sprite sheets", "ptest3", contained, ml))

    # 4: one image per card (the first build)
    contained, ml = variant("ptest4", card_box)
    boxes.append(T.scenario_box("Test 4 — image per card", "ptest4", contained, ml))

    # 5: test 3's cards, laid out by SCED's own unmodified Place (script and mesh as the campaign box's)
    contained, ml = variant("ptest5", sheet_box)
    boxes.append(T.memory_bag("Test 5 — SCED's own Place", {"id": "ptest5", "type": "ScenarioBox"}, None,
                              T.MESH_SMALL, T.SCALE_SMALL, contained, ml))

    box = T.campaign_box(boxes, name=NAME, filename="place_test", box_id=BOX_ID, table=False)
    return {"SaveName": NAME, "GameMode": NAME, "ObjectStates": [box]}, boxes


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    B.add_local_flag(ap)
    a = ap.parse_args(argv)
    save, boxes = build()
    text = json.dumps(save, indent=2, ensure_ascii=False)
    B.release_guard(OUT, text, a.local)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    report = {"out": os.path.relpath(OUT, ROOT)}
    for b in boxes:
        report[b["Nickname"]] = {"objects": len(b["ContainedObjects"]), "images": count_images(b["ContainedObjects"])}
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
