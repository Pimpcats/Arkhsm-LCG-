"""The Control token's "Guide: ..." menu turns the campaign guide to a section.

src/StillHour/Guide.ttslua holds the page numbers as a build-time string; pipeline/bundle_mod.py fills it
from the guide PDF's own layout. These tests run the module in plain Lua with a fake guide, and check the
numbers the shipped Control carries against the shipped PDF."""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import bundle_mod as BM  # noqa: E402
from campaign_config import CFG  # noqa: E402

GUIDE_LUA = os.path.join(ROOT, "src", CFG.lua_dir, "Guide.ttslua")
LUA = shutil.which("lua5.4") or shutil.which("lua5.2") or shutil.which("lua")


def run_lua(chunk):
    r = subprocess.run([LUA, "-e", chunk], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip().splitlines()


def harness(pages, guide_present=True, set_page_fails=False):
    src = open(GUIDE_LUA, encoding="utf-8").read().replace(BM.GUIDE_PAGES_PLACEHOLDER, pages)
    return r'''
local out = {}
local function say(...) out[#out + 1] = table.concat({...}, " ") end
local turned = {}
local guide = { Book = { setPage = function(n) if %s then error("no book") end; turned[#turned + 1] = n end } }
function getObjectsWithTag(tag) if tag == "CampaignGuide" and %s then return { guide } end return {} end
function printToColor(msg, color) say("TO", color, msg) end
local items = {}
local obj = { addContextMenuItem = function(label, fn) items[#items + 1] = { label, fn } end }
local chunk = load([==[%s]==], "Guide")
local Guide = chunk()
Guide.addMenu(obj)
for _, it in ipairs(items) do say("ITEM", it[1]) end
if items[1] then items[1][2]("White") end
say("TURNED", table.concat(turned, ","))
for _, line in ipairs(out) do print(line) end
''' % ("true" if set_page_fails else "false", "true" if guide_present else "false", src)


@pytest.mark.skipif(LUA is None, reason="no Lua interpreter")
def test_the_menu_lists_the_known_sections_and_turns_to_the_zero_based_page():
    lines = run_lua(harness("rules=2,setup=7,prologue=8,loop=9,between=11,difficulty=34,decks=35"))
    items = [l[5:] for l in lines if l.startswith("ITEM ")]
    assert items == ["Guide: Campaign Setup", "Guide: The Prologue", "Guide: Loop Setup", "Guide: Between Loops",
                     "Guide: Campaign Rules", "Guide: Difficulty and Player Count", "Guide: Starting Decks"]
    assert "TURNED 6" in lines          # setup is page 7; Book.setPage is zero-based


@pytest.mark.skipif(LUA is None, reason="no Lua interpreter")
def test_without_page_numbers_the_menu_is_empty():
    lines = run_lua(harness(""))
    assert [l for l in lines if l.startswith("ITEM ")] == []


@pytest.mark.skipif(LUA is None, reason="no Lua interpreter")
def test_a_missing_guide_or_book_says_so_and_raises_nothing():
    absent = run_lua(harness("setup=7", guide_present=False))
    assert any(l.startswith("TO White The campaign guide is not on the table") for l in absent)
    broken = run_lua(harness("setup=7", set_page_fails=True))
    assert any("go to page 7" in l for l in broken)


def test_the_bundle_fills_the_placeholder_from_the_guide_build(tmp_path, monkeypatch):
    pages = {"Campaign Setup": 7, "Between Loops": 11, "The Loop": 9, "Campaign Rules": 2,
             "Prologue — The First Hour": 8, "Difficulty and Player Count": 34, "The Square": 24,
             "Appendix — Starting Decks": 35}
    d = tmp_path / "dist" / "guide"
    d.mkdir(parents=True)
    (d / (CFG.slug + "_campaign_guide_pages.json")).write_text(json.dumps({"pages": pages, "count": 38}))
    text = BM.guide_pages_text(str(tmp_path))
    assert dict(kv.split("=") for kv in text.split(",")) == {
        "rules": "2", "setup": "7", "prologue": "8", "loop": "9", "between": "11", "difficulty": "34",
        "decks": "35"}
    assert BM.guide_pages_text(str(tmp_path / "nowhere")) == ""


SAVED = os.path.join(ROOT, "dist", "saved_object_" + CFG.slug + ".json")


def test_the_shipped_control_carries_the_shipped_guides_pages():
    pdf = os.path.join(ROOT, "dist", "guide", CFG.slug + "_campaign_guide.pdf")
    pages_file = os.path.join(ROOT, "dist", "guide", CFG.slug + "_campaign_guide_pages.json")
    if not (os.path.exists(pdf) and os.path.exists(pages_file)):
        pytest.skip("no built guide")
    shipped = json.load(open(pages_file, encoding="utf-8"))["pages"]
    saved = open(SAVED, encoding="utf-8").read()
    # the Control's script sits JSON-escaped inside the Saved Object
    m = re.search(r'local PAGES = \\"([a-z]+=\d+(?:,[a-z]+=\d+)*)\\"', saved)
    if not m:
        pytest.skip("the shipped Control predates the guide menu (rebuild dist/)")
    carried = dict(kv.split("=") for kv in m.group(1).split(","))
    want = {CFG["guide_page_keys"][t]: str(shipped[t]) for t in CFG["guide_page_keys"]}
    assert carried == want
    pymupdf = pytest.importorskip("pymupdf")
    toc = {title: page for _lvl, title, page in pymupdf.open(pdf).get_toc()}
    assert {t: toc[t] for t in CFG["guide_page_keys"]} == {t: shipped[t] for t in CFG["guide_page_keys"]}
