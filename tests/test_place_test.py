"""The Place test Saved Object (pipeline/place_test.py): five boxes that lay out the same first
scenario as one card, as its bare structure, on sprite sheets and one image per card, and (the
fifth) on sprite sheets by SCED's own Place script, so that pressing them one by one says which
part of a Place stops Tabletop Simulator."""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import build_cards as B  # noqa: E402
import pack_sheets as P  # noqa: E402
import place_test as PT  # noqa: E402
import table_presence as T  # noqa: E402


@pytest.fixture
def sheets(monkeypatch):
    boxes, cards = P.membership()
    specs = P.plan(boxes, P.sideways_of_factory(cards))
    urls = {s["key"]: {"box": s["box"], "deck": s["deck"], "cols": s["cols"], "rows": s["rows"],
                       "sideways": s["sideways"], "cells": s["cells"],
                       "face": "https://example.test/%s-face.jpg" % s["key"],
                       "back": "https://example.test/%s-back.jpg" % s["key"]} for s in specs}
    monkeypatch.setattr(B, "SHEETS", B._sheet_index({"_sheets": urls}))
    monkeypatch.setitem(B.ART_URLS, "_encounter_back", "https://example.test/encounter_back.jpg")
    return specs


def objects(box):
    out = []

    def walk(o):
        out.append(o)
        for c in o.get("ContainedObjects") or []:
            walk(c)
    for o in box["ContainedObjects"]:
        walk(o)
    return out


def test_the_test_boxes_differ_only_in_what_they_load(sheets):
    save, boxes = PT.build()
    top = save["ObjectStates"][0]
    assert json.loads(top["GMNotes"])["id"] == "CB-PTEST" and len(top["ContainedObjects"]) == 5
    one, bare, packed, per_card, sced = boxes
    # the fifth is the third's content under SCED's own, unmodified Place script
    assert sced["LuaScript"] == T.memory_bag_script() and sced["LuaScript"] != T.loop_box_script()
    assert [o["CustomDeck"] if "CustomDeck" in o else None for o in sced["ContainedObjects"]] == \
        [o["CustomDeck"] if "CustomDeck" in o else None for o in packed["ContainedObjects"]]
    boxes = [one, bare, packed, per_card]
    assert [PT.count_images(b["ContainedObjects"]) for b in boxes][:2] == [2, 1]
    assert PT.count_images(packed["ContainedObjects"]) <= 4
    assert PT.count_images(per_card["ContainedObjects"]) >= 30         # the first build's one image per card
    assert len(one["ContainedObjects"]) == 1
    # the structure test keeps the first scenario's objects and deck ids, with one image
    assert len(bare["ContainedObjects"]) == len(per_card["ContainedObjects"]) == len(packed["ContainedObjects"])
    ids = lambda b: sorted(  # noqa: E731
        k for o in objects(b) for k in (o.get("CustomDeck") or {}))
    assert ids(bare) == ids(per_card) and len(set(ids(bare))) >= 25
    # each box lays out and recalls on its own: own id, own tag, own GUIDs, nothing shared
    tags = set()
    guids = set()
    for b in boxes:
        sid = json.loads(b["GMNotes"])["id"]
        want = T.loop_tags(sid)
        tags.add(want[1])
        for o in objects(b):
            assert all(t in o["Tags"] for t in want), (sid, o.get("Nickname"))
            assert not any(t.startswith("StillHourBox_") and t != want[1] for t in o["Tags"])
        top_guids = [o["GUID"] for o in b["ContainedObjects"]]
        assert set(json.loads(b["LuaScriptState"])["ml"]) == set(top_guids)
        assert not (set(top_guids) & guids), sid
        guids |= set(top_guids)
    assert len(tags) == 4
    # the same Place script as the campaign's boxes
    assert all(b["LuaScript"] == T.loop_box_script() for b in boxes)
    # the fifth box shares no GUID with the others either, so all five can sit on one table
    assert not ({o["GUID"] for o in sced["ContainedObjects"]} & guids)


CHUNK = r"""
local BOX = %s
local box = spawnObjectJSON({ json = BOX })
local out = {}
Wait.frames(function()
  out.inside = #box.getObjects()
  out.placed = box.call("buttonClick_place")
  Wait.frames(function()
    local n = 0
    for _, o in ipairs(getObjects()) do
      if o ~= box and o.hasTag(%s) then n = n + (o.type == "Deck" and #o.getObjects() or 1) end
    end
    out.onTable = n
    print("@@OUT " .. JSON.encode(out))
  end, 400)
end, 10)
"""


def test_every_test_box_places_in_the_emulator(sheets, tmp_path):
    lua = shutil.which("lua5.2")
    if not lua:
        pytest.skip("lua5.2 not installed")
    sys.path.insert(0, os.path.join(ROOT, "tools", "tts_relay"))
    import relay
    _, boxes = PT.build()
    for b in boxes[:4]:           # the fifth uses SCED's own script (its Place empties the box)
        sid = json.loads(b["GMNotes"])["id"]
        chunk = CHUNK % (relay.lua_long_string(json.dumps(b, ensure_ascii=False)), json.dumps(T.loop_tags(sid)[1]))
        path = tmp_path / (sid + ".lua")
        path.write_text(chunk, encoding="utf-8")
        r = subprocess.run([lua, os.path.join(ROOT, "tests", "tts_fake", "mock_tts.lua"), str(path)],
                           capture_output=True, text=True, cwd=ROOT, timeout=120)
        outs, errors = [], []
        for ln in r.stdout.splitlines():
            if ln.startswith("@@MSG "):
                m = json.loads(ln[6:])
                if m.get("message", "").startswith("@@OUT "):
                    outs.append(m["message"][6:])
                if m.get("messageID") == 3:
                    errors.append(m.get("error"))
        assert outs and not errors, (sid, errors[:2], r.stderr[-500:])
        out = json.loads(outs[-1])
        assert out["placed"] == out["inside"] == len(b["ContainedObjects"]), (sid, out)
        assert out["onTable"] >= out["placed"], (sid, out)


SCED_CHUNK = r"""
local BOX = %s
local GUIDS = %s
local box = spawnObjectJSON({ json = BOX })
local out = {}
Wait.frames(function()
  out.inside = #box.getObjects()
  box.call("buttonClick_place")
  Wait.frames(function()
    local n = 0
    for _, g in ipairs(GUIDS) do if getObjectFromGUID(g) ~= nil then n = n + 1 end end
    out.onTable = n
    out.left = #box.getObjects()
    print("@@OUT " .. JSON.encode(out))
  end, 120)
end, 10)
"""


def test_the_fifth_box_places_with_scedS_own_script(sheets, tmp_path):
    lua = shutil.which("lua5.2")
    if not lua:
        pytest.skip("lua5.2 not installed")
    sys.path.insert(0, os.path.join(ROOT, "tools", "tts_relay"))
    import relay
    _, boxes = PT.build()
    b = boxes[4]
    guids = [o["GUID"] for o in b["ContainedObjects"]]
    chunk = SCED_CHUNK % (relay.lua_long_string(json.dumps(b, ensure_ascii=False)),
                          "{" + ", ".join(json.dumps(g) for g in guids) + "}")
    path = tmp_path / "ptest5.lua"
    path.write_text(chunk, encoding="utf-8")
    r = subprocess.run([lua, os.path.join(ROOT, "tests", "tts_fake", "mock_tts.lua"), str(path)],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    outs, errors = [], []
    for ln in r.stdout.splitlines():
        if ln.startswith("@@MSG "):
            m = json.loads(ln[6:])
            if m.get("message", "").startswith("@@OUT "):
                outs.append(m["message"][6:])
            if m.get("messageID") == 3:
                errors.append(m.get("error"))
    assert outs and not errors, (errors[:2], r.stderr[-500:])
    out = json.loads(outs[-1])
    # SCED's Place takes every object out of the box: all on the table, the box empty
    assert out["inside"] == len(guids) and out["onTable"] == len(guids) and out["left"] == 0, out
