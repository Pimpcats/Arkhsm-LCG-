"""The Control token's flow on a stubbed Tabletop Simulator.

tests/control_flow.lua loads the Control's script exactly as TTS gets it (the
bundle pipeline/bundle_mod.py builds from src/, so it tests the code in this
checkout, not the last publish) on a vanilla table and drives the owner's
buttons and the runner API: Reset Loop and Begin Next Loop in order, the
Between Loops panel, the Reset Loop question, the finale's loose ends, the
Sealed Study, the campaign log's state mirror, SCED's investigator counter, and
the labels the panels draw. It runs in about two seconds per Lua version.

The label sizes are measured here: every button label the panels draw (the
Lua run prints them) must fit its button when set in the font TTS draws button
text in (Arial; Liberation Sans, which has the same advance widths, is what
this checks with).
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

LUAS = [lua for lua in ("lua5.2", "lua5.4") if shutil.which(lua)]
FONTS = ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
         "C:/Windows/Fonts/arial.ttf", "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    import bundle_mod
    path = tmp_path_factory.mktemp("control") / "bundle.lua"
    path.write_text(bundle_mod.build_bundle(ROOT), encoding="utf-8")
    return str(path)


@pytest.fixture(scope="module")
def runs(bundle):
    out = {}
    for lua in LUAS:
        out[lua] = subprocess.run([shutil.which(lua), os.path.join(ROOT, "tests", "control_flow.lua"), bundle, ROOT],
                                  capture_output=True, text=True, encoding="utf-8", timeout=300, cwd=ROOT)
    return out


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
@pytest.mark.parametrize("lua", LUAS)
def test_control_flow_on_a_stub_table(lua, runs):
    r = runs[lua]
    fails = [ln for ln in r.stdout.splitlines() if ln.startswith("  FAIL")]
    assert r.returncode == 0 and not fails, "\n".join(fails) + "\n" + r.stdout[-1500:] + r.stderr[-1500:]
    m = re.search(r"control_flow: OK \((\d+) checks\)", r.stdout)
    assert m and int(m.group(1)) > 100, r.stdout[-500:]


def _labels(run):
    return [json.loads(ln[len("@@LABEL "):]) for ln in run.stdout.splitlines() if ln.startswith("@@LABEL ")]


def _font_path():
    for p in FONTS:
        if os.path.exists(p):
            return p
    return None


@pytest.mark.skipif(not LUAS, reason="no lua5.2 / lua5.4 installed")
def test_every_button_label_fits_its_button(runs):
    ImageFont = pytest.importorskip("PIL.ImageFont")
    path = _font_path()
    if not path:
        pytest.skip("no Arial or Liberation Sans font installed")
    labels = _labels(runs[LUAS[0]])
    assert len(labels) > 100, "the label sweep printed too few labels"
    kinds = {r["kind"] for r in labels}
    assert {"play", "prologue", "finale", "between", "interlude", "card"} <= kinds, kinds
    fonts = {}
    over = []
    worst = 0.0
    for r in labels:
        font = fonts.setdefault(r["font_size"], ImageFont.truetype(path, int(r["font_size"])))
        w = max(font.getlength(line) for line in r["label"].split("\n"))
        worst = max(worst, w / r["width"])
        if w > r["width"]:
            over.append("%s %r: %.0f of %d at font size %d" % (r["kind"], r["label"], w, r["width"], r["font_size"]))
        assert r["font_size"] >= 40, "a label this small cannot be read: %r" % r["label"]
    assert not over, "\n".join(over)
    assert worst <= 1.0


def test_label_fitter_uses_arial_advance_widths():
    """Board.fitFont's table is the advance width of each ASCII character in Arial (Liberation Sans)."""
    ImageFont = pytest.importorskip("PIL.ImageFont")
    path = _font_path()
    if not path:
        pytest.skip("no Arial or Liberation Sans font installed")
    src = open(os.path.join(ROOT, "src", "StillHour", "Board.ttslua"), encoding="utf-8").read()
    m = re.search(r"local ADVANCE = \{(.*?)\}", src, re.S)
    table = [int(x) for x in re.findall(r"\d+", m.group(1))]
    assert len(table) == 95
    font = ImageFont.truetype(path, 1000)
    for i, w in enumerate(table):
        ch = chr(32 + i)
        assert abs(font.getlength(ch) - w) <= 1, (ch, w, font.getlength(ch))
