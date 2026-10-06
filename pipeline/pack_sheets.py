#!/usr/bin/env python3
"""pack_sheets.py — pack card faces and backs into Tabletop Simulator card sheets.

Why: SCED's own boxes show a scenario with a handful of textures. Over the 145
official scenario boxes the median is 9 card-sheet textures and the largest 27,
because their cards are packed into sprite sheets (a TTS CustomDeck is a grid of
cards in one image; CardID = deck id * 100 + the cell's index, row by row from
the top left). The Still Hour's cards were one image each: The First Hour needed
43 textures and The Square 57, more than any official box, all requested in the
frame its Place spawns them. Packed, a box needs four (a face sheet and a back
sheet for its portrait cards, the same for its landscape ones).

Layout, per box (a scenario box's id, or "player" / "investigators" for the
player-card bag):
  * portrait cards (everything but agendas, acts and investigators) go on
    portrait sheets, landscape ones (SidewaysCard) on landscape sheets, because
    one CustomDeck has one cell shape;
  * at most 7 x 5 portrait cells of 585 x 819 (4095 x 4095 px) or 5 x 7
    landscape cells of 819 x 585 (4095 x 4095 px) on a sheet; a sheet is only as
    big as its cards need (a box with 3 cards gets a 3 x 1 sheet);
  * the back sheet has the same grid; a card's cell holds its own back (a
    location's other side, an investigator's deckbuilding back) or the shared
    player / encounter back (UniqueBack true on every sheet);
  * one sheet = one CustomDeck id, assigned in sorted key order from DECK_BASE
    (clear of the per-card ids 95010-98999 and of every official id).

The sheets are baseline JPEGs: they carry no progressive scans for the game to
decode in several passes.

    python3 pipeline/pack_sheets.py --check     # what a build would pack (no images needed)
"""
import hashlib
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PORTRAIT = {"cols": 7, "rows": 5, "cell": (585, 819), "sideways": False, "tag": "p"}
LANDSCAPE = {"cols": 5, "rows": 7, "cell": (819, 585), "sideways": True, "tag": "l"}
DECK_BASE = 99100            # sheet deck ids: DECK_BASE .. (below the 99999 block's end)
JPEG_QUALITY = 88
ASPECT_TOLERANCE = 0.02      # a face whose shape is further than this from its cell's is an error


def sheet_key(box, geometry, n=0):
    """'prologue-p', 'prologue-p2' ... (the first sheet of a kind has no number)."""
    return "{}-{}{}".format(box, geometry["tag"], "" if n == 0 else n + 1)


def plan(boxes, sideways_of, id_digits=None):
    """boxes: {box key: [card ids in stage order]}; sideways_of(card id) -> bool.
    Returns a list of sheet specs, in sorted key order:
      {key, box, deck, sideways, cols, rows, cell, cells: [card ids]}
    A card id appears once per box even if the box holds several copies."""
    specs = []
    for box in sorted(boxes):
        seen, order = set(), []
        for cid in boxes[box]:
            if cid not in seen:
                seen.add(cid)
                order.append(cid)
        for geometry in (PORTRAIT, LANDSCAPE):
            ids = [c for c in order if bool(sideways_of(c)) == geometry["sideways"]]
            per = geometry["cols"] * geometry["rows"]
            for n, start in enumerate(range(0, len(ids), per)):
                chunk = ids[start:start + per]
                cols = min(geometry["cols"], len(chunk))
                rows = int(math.ceil(len(chunk) / float(cols)))
                specs.append({"key": sheet_key(box, geometry, n), "box": box,
                              "sideways": geometry["sideways"], "cols": cols, "rows": rows,
                              "cell": list(geometry["cell"]), "cells": chunk})
    for i, s in enumerate(sorted(specs, key=lambda s: s["key"])):
        s["deck"] = DECK_BASE + i
    assert DECK_BASE + len(specs) <= 99800, "too many sheets for the reserved deck id block (99800 up is the minicards')"
    return sorted(specs, key=lambda s: s["key"])


def card_id_of(spec, card_id):
    """TTS CardID of a card on a sheet: deck id * 100 + its cell index."""
    return spec["deck"] * 100 + spec["cells"].index(card_id)


def textures_per_box(specs):
    """{box: number of images its sheets load} (a face and a back image each)."""
    out = {}
    for s in specs:
        out[s["box"]] = out.get(s["box"], 0) + 2
    return out


# ------------------------------------------------------------ rendering --
def _open(path):
    from PIL import Image
    return Image.open(path).convert("RGB")


def _fit(img, cell, what):
    from PIL import Image
    w, h = img.size
    ratio = (w / float(h)) / (cell[0] / float(cell[1]))
    if abs(ratio - 1.0) > ASPECT_TOLERANCE:
        raise ValueError("{} is {}x{}: not the shape of a {}x{} cell".format(what, w, h, cell[0], cell[1]))
    return img if img.size == tuple(cell) else img.resize(tuple(cell), Image.LANCZOS)


def render(spec, face_path, back_path):
    """(face sheet, back sheet) PIL images for one planned sheet. face_path(card
    id) and back_path(box, card id) give the full-size source image of each cell."""
    from PIL import Image
    cw, ch = spec["cell"]
    size = (cw * spec["cols"], ch * spec["rows"])
    face = Image.new("RGB", size, (0, 0, 0))
    back = Image.new("RGB", size, (0, 0, 0))
    cache = {}
    for n, cid in enumerate(spec["cells"]):
        x, y = (n % spec["cols"]) * cw, (n // spec["cols"]) * ch
        face.paste(_fit(_open(face_path(cid)), spec["cell"], "face of " + cid), (x, y))
        bp = back_path(spec["box"], cid)
        if bp not in cache:
            cache[bp] = _fit(_open(bp), spec["cell"], "back of " + cid)
        back.paste(cache[bp], (x, y))
    return face, back


def save_jpeg(img, path):
    """A baseline JPEG; returns its short content hash (the ?v= of the hosted URL)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=False)
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:10]


def write_all(specs, out_dir, face_path, back_path):
    """Render and save every sheet as <key>-face.jpg / <key>-back.jpg under
    out_dir. Returns {key: {"face": hash, "back": hash}}."""
    hashes = {}
    for s in specs:
        face, back = render(s, face_path, back_path)
        hashes[s["key"]] = {
            "face": save_jpeg(face, os.path.join(out_dir, s["key"] + "-face.jpg")),
            "back": save_jpeg(back, os.path.join(out_dir, s["key"] + "-back.jpg"))}
    return hashes


# ------------------------------------------------------------ membership --
def membership(campaign=None):
    """{box key: [card ids]} for the release: every scenario box (what
    compile_campaign.build_scenario_box lays out, in its stack order), the
    player-card bag ("player") and the investigators ("investigators"). Reads
    the same specs, overrides and assignments the build does."""
    import campaign_config
    import compile_campaign as CC
    paths = CC.campaign_paths(campaign)
    cards = CC.load_cards(paths)
    assignments = {}
    if os.path.exists(paths["assignments"]):
        assignments = json.load(open(paths["assignments"], encoding="utf-8"))
    manifest = {"scenarios": []}
    if os.path.exists(paths["manifest"]):
        manifest = json.load(open(paths["manifest"], encoding="utf-8"))
    out = {}
    for sc in sorted(manifest.get("scenarios", []), key=lambda s: s.get("order", 99)):
        ids = CC.scenario_card_ids(sc, assignments.get(sc["id"], {}) or {}, cards)
        if ids:
            out[sc["id"]] = ids
    # the player-card bag is exactly the player spec (investigators, signatures,
    # weaknesses, the shared pool, Recollections, quest cards), as build_cards.generate builds it
    from campaign_config import CFG
    player_ids = [c["id"] for c in json.load(open(CFG.path("cards_spec"), encoding="utf-8"))
                  if c["id"] in cards]
    out["player"] = [i for i in player_ids if cards[i]["type"] != "Investigator"]
    out["investigators"] = [i for i in player_ids if cards[i]["type"] == "Investigator"]
    return {k: v for k, v in out.items() if v}, cards


def sideways_of_factory(cards):
    import build_cards as B

    def sideways(cid):
        return cards[cid]["type"] in B.SIDEWAYS_TYPES
    return sideways


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--check", action="store_true", help="print the sheets a build would make")
    a = ap.parse_args(argv)
    boxes, cards = membership()
    specs = plan(boxes, sideways_of_factory(cards))
    print(json.dumps({"sheets": len(specs),
                      "textures_per_box": textures_per_box(specs),
                      "plan": [dict({k: s[k] for k in ("key", "deck", "cols", "rows")}, cards=len(s["cells"]))
                               for s in specs]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
