"""Sprite sheets (pipeline/pack_sheets.py): the cards of a hosted release are drawn
from a few sheet images per scenario box, as SCED's own boxes are, instead of one
image per card (43 textures for The First Hour, more than any official box)."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import build_cards as B  # noqa: E402
import compile_campaign as CC  # noqa: E402
import pack_sheets as P  # noqa: E402


def sideways(cid):
    return cid.startswith("land")


def fake_urls(specs):
    """art_urls.json's "_sheets" entries for a plan, with made-up URLs."""
    return {s["key"]: {"box": s["box"], "deck": s["deck"], "cols": s["cols"], "rows": s["rows"],
                       "sideways": s["sideways"], "cells": s["cells"],
                       "face": "https://example.test/%s-face.jpg" % s["key"],
                       "back": "https://example.test/%s-back.jpg" % s["key"]} for s in specs}


# ---------------------------------------------------------------- planning --
def test_plan_packs_by_box_and_card_shape():
    boxes = {"b1": ["p1", "land1", "p2", "p1", "land2"], "b2": ["p3"]}
    specs = P.plan(boxes, sideways)
    by = {s["key"]: s for s in specs}
    assert set(by) == {"b1-p", "b1-l", "b2-p"}
    assert by["b1-p"]["cells"] == ["p1", "p2"] and by["b1-l"]["cells"] == ["land1", "land2"]
    assert (by["b1-p"]["cols"], by["b1-p"]["rows"]) == (2, 1)       # only as big as its cards need
    assert by["b1-l"]["cell"] == [819, 585] and by["b1-p"]["cell"] == [585, 819]
    assert by["b2-p"]["cells"] == ["p3"]
    assert P.textures_per_box(specs) == {"b1": 4, "b2": 2}
    # one deck id per sheet, assigned in key order from the reserved block
    assert [s["deck"] for s in specs] == [P.DECK_BASE + i for i in range(3)]
    assert P.card_id_of(by["b1-p"], "p2") == by["b1-p"]["deck"] * 100 + 1


def test_a_box_over_one_sheets_capacity_gets_a_second_sheet():
    ids = ["p%d" % i for i in range(40)]
    specs = P.plan({"big": ids}, sideways)
    assert [s["key"] for s in specs] == ["big-p", "big-p2"]
    assert len(specs[0]["cells"]) == 35 and len(specs[1]["cells"]) == 5
    assert (specs[0]["cols"], specs[0]["rows"]) == (7, 5)
    assert specs[0]["cols"] * specs[0]["cell"][0] <= 4095 and specs[0]["rows"] * specs[0]["cell"][1] <= 4095
    landscape = P.plan({"big": ["land%d" % i for i in range(36)]}, sideways)
    assert (landscape[0]["cols"], landscape[0]["rows"]) == (5, 7)
    assert landscape[0]["cols"] * landscape[0]["cell"][0] <= 4095 and landscape[0]["rows"] * landscape[0]["cell"][1] <= 4095


# --------------------------------------------------------------- rendering --
def _solid(path, size, colour):
    from PIL import Image
    Image.new("RGB", size, colour).save(path)
    return path


def test_every_cell_holds_its_card_and_its_back(tmp_path):
    from PIL import Image
    ids = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]
    spec = P.plan({"box": ids}, sideways)[0]
    colour = {cid: (10 + 20 * i, 200 - 15 * i, 30 + 10 * i) for i, cid in enumerate(ids)}
    faces = {cid: _solid(str(tmp_path / (cid + ".png")), (750, 1050), colour[cid]) for cid in ids}
    shared = _solid(str(tmp_path / "shared.png"), (434, 600), (250, 250, 5))
    own = _solid(str(tmp_path / "own.png"), (750, 1050), (5, 5, 250))
    back = lambda box, cid: own if cid == "p3" else shared      # noqa: E731
    face_img, back_img = P.render(spec, lambda cid: faces[cid], back)
    assert face_img.size == (7 * 585, 2 * 819) == back_img.size
    for cid in ids:
        n = spec["cells"].index(cid)
        card_id = P.card_id_of(spec, cid)
        assert card_id % 100 == n
        x, y = (n % spec["cols"]) * 585, (n // spec["cols"]) * 819
        box = (x + 100, y + 100, x + 200, y + 200)           # well inside the cell
        assert max(abs(a - b) for a, b in zip(face_img.crop(box).getpixel((50, 50)), colour[cid])) <= 3
        want = (5, 5, 250) if cid == "p3" else (250, 250, 5)
        assert max(abs(a - b) for a, b in zip(back_img.crop(box).getpixel((50, 50)), want)) <= 3
    # the cells next to each other stay apart: nothing bleeds across the edge
    assert face_img.getpixel((585 - 2, 100)) != face_img.getpixel((585 + 2, 100))
    path = str(tmp_path / "sheet.jpg")
    h = P.save_jpeg(face_img, path)
    assert len(h) == 10
    jpeg = Image.open(path)
    assert jpeg.format == "JPEG" and "progressive" not in jpeg.info and "progression" not in jpeg.info


def test_a_face_of_the_wrong_shape_is_refused(tmp_path):
    spec = P.plan({"box": ["p1"]}, sideways)[0]
    wrong = _solid(str(tmp_path / "w.png"), (1050, 750), (1, 2, 3))         # landscape on a portrait sheet
    ok = _solid(str(tmp_path / "ok.png"), (750, 1050), (1, 2, 3))
    with pytest.raises(ValueError):
        P.render(spec, lambda cid: wrong, lambda box, cid: ok)


# -------------------------------------------------------------- card objects --
def _card(cid, ctype="Asset", **kw):
    c = {"id": cid, "type": ctype, "name": cid.title(), "class": "Neutral", "traits": "Item.",
         "deck": 95900 + len(cid), "cost": 1}
    c.update(kw)
    return c


def test_a_card_on_a_sheet_gets_its_cell_and_a_shared_deck(monkeypatch):
    specs = P.plan({"boxA": ["a1", "a2", "a3"]}, sideways)
    monkeypatch.setattr(B, "SHEETS", B._sheet_index({"_sheets": fake_urls(specs)}))
    objs = [B.build_card(_card(i), box="boxA") for i in ("a1", "a2", "a3")]
    deck = specs[0]["deck"]
    assert [o["CardID"] for o in objs] == [deck * 100, deck * 100 + 1, deck * 100 + 2]
    for o in objs:
        (key, entry), = o["CustomDeck"].items()
        assert key == str(deck) and entry["NumWidth"] == 3 and entry["NumHeight"] == 1
        assert entry["UniqueBack"] is True and entry["FaceURL"].endswith("boxA-p-face.jpg")
        assert entry["BackURL"].endswith("boxA-p-back.jpg")
    # a card with no cell on this box's sheets keeps its own 1x1 deck
    other = B.build_card(_card("zz"), box="boxA")
    assert other["CardID"] % 100 == 0 and list(other["CustomDeck"].values())[0]["NumWidth"] == 1
    # sheets=False (the Studio's live preview) always keeps the card's own deck
    single = B.build_card(_card("a1"), box="boxA", sheets=False)
    assert single["CardID"] == int(str(_card("a1")["deck"]) + "00")


def test_a_deck_of_sheet_cards_names_one_sheet(monkeypatch):
    specs = P.plan({"boxA": ["a1", "a2", "a3"]}, sideways)
    monkeypatch.setattr(B, "SHEETS", B._sheet_index({"_sheets": fake_urls(specs)}))
    deck = CC.build_deck([_card("a1"), _card("a2"), _card("a3")], "Stack", "k", 0, 0, box="boxA")
    sheet = specs[0]["deck"]
    assert set(deck["CustomDeck"]) == {str(sheet)}
    assert sorted(deck["DeckIDs"]) == [sheet * 100, sheet * 100 + 1, sheet * 100 + 2]
    assert [o["CardID"] for o in deck["ContainedObjects"]] == deck["DeckIDs"]


# ----------------------------------------------------------- the real release --
def test_the_release_plan_fits_the_official_texture_budget():
    boxes, cards = P.membership()
    specs = P.plan(boxes, P.sideways_of_factory(cards))
    textures = P.textures_per_box(specs)
    assert "prologue" in textures and "district_square" in textures and "player" in textures
    # official scenario boxes: median 9 sheet textures, at most 27 (145 boxes)
    assert max(textures.values()) <= 6, textures
    # every card the release builds has a cell, and the cell names it back
    for s in specs:
        assert len(set(s["cells"])) == len(s["cells"]) <= s["cols"] * s["rows"]
        assert s["cols"] <= 10 and s["rows"] <= 7                      # TTS's grid limit
        assert s["cols"] * s["cell"][0] <= 4095 and s["rows"] * s["cell"][1] <= 4095
    decks = [s["deck"] for s in specs]
    assert len(set(decks)) == len(decks)
    # clear of every per-card deck id (authored 95010-95128, derived 96000-98999)
    per_card = {CC.normalize(c)["deck"] for c in cards.values()}
    assert not (set(decks) & per_card), sorted(set(decks) & per_card)
    for box, ids in boxes.items():
        cells = {c for s in specs if s["box"] == box for c in s["cells"]}
        assert cells == set(ids), box


def test_a_compiled_campaign_draws_every_scenario_card_from_its_boxs_sheets(tmp_path, monkeypatch):
    boxes, cards = P.membership()
    specs = P.plan(boxes, P.sideways_of_factory(cards))
    monkeypatch.setattr(B, "SHEETS", B._sheet_index({"_sheets": fake_urls(specs)}))
    out = tmp_path / "campaign.json"
    assert CC.compile_campaign(str(out))["ok"]
    box = json.load(open(out, encoding="utf-8"))["ObjectStates"][0]
    by_deck = {s["deck"]: s for s in specs}
    checked = 0
    for sb in box["ContainedObjects"]:
        if sb.get("Name") != "Custom_Model_Bag" or json.loads(sb["GMNotes"]).get("type") != "ScenarioBox":
            continue
        sid = json.loads(sb["GMNotes"])["id"]
        urls = set()

        def walk(o):
            if o.get("Name") in ("Card", "CardCustom"):
                gm = json.loads(o["GMNotes"])
                sheet = by_deck[o["CardID"] // 100]
                assert sheet["box"] == sid, (sid, gm["id"])
                assert sheet["cells"][o["CardID"] % 100] == gm["id"], (sid, gm["id"])
                assert list(o["CustomDeck"]) == [str(sheet["deck"])]
                for e in o["CustomDeck"].values():
                    urls.update((e["FaceURL"], e["BackURL"]))
                nonlocal_checked[0] += 1
            for c in o.get("ContainedObjects") or []:
                walk(c)
        nonlocal_checked = [0]
        for o in sb["ContainedObjects"]:
            walk(o)
        checked += nonlocal_checked[0]
        assert 2 <= len(urls) <= 4, (sid, len(urls))                      # the whole box loads <= 4 textures
        for o in sb["ContainedObjects"]:                                   # decks name only their sheets
            if o.get("Name") == "Deck":
                assert len(o["CustomDeck"]) <= 2
                assert sorted(o["DeckIDs"]) == sorted(c["CardID"] for c in o["ContainedObjects"])
    assert checked >= 100


def test_every_object_in_a_scenario_box_has_its_own_guid(tmp_path):
    # Place keeps the GUIDs a box holds and SCED keys per-card state on them (which locations have
    # spawned their clues, ...), so a card listed several times in a deck must not repeat one
    out = tmp_path / "campaign.json"
    assert CC.compile_campaign(str(out))["ok"]
    box = json.load(open(out, encoding="utf-8"))["ObjectStates"][0]
    boxes = 0
    for sb in box["ContainedObjects"]:
        if sb.get("Name") != "Custom_Model_Bag" or json.loads(sb["GMNotes"]).get("type") != "ScenarioBox":
            continue
        boxes += 1
        seen = {}

        def walk(o, path):
            g = o.get("GUID")
            assert g not in seen, "%s: GUID %s on %s and %s" % (sb["Nickname"], g, seen[g], path)
            seen[g] = path
            for c in o.get("ContainedObjects") or []:
                walk(c, path + "/" + str(c.get("Nickname")))
        for o in sb["ContainedObjects"]:
            walk(o, str(o.get("Nickname")))
        # the memory list names direct children only, each once
        ml = json.loads(sb["LuaScriptState"])["ml"]
        assert set(ml) == {o["GUID"] for o in sb["ContainedObjects"]}, sb["Nickname"]
    assert boxes == 8
