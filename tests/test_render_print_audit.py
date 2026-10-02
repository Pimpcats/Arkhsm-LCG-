"""Print audit for the card renderer (pipeline/render_placeholders.py).

The renderer records every piece of text it draws on a face and checks the
finished face for text the frame hides: dark rules on ornament or a border
(the frame's visible-parchment mask), ink of too little contrast with what is
under it, text an icon or set symbol was pasted over, two text blocks touching
(rules into the credit line), and ink off the card edge. These tests prove the
check catches each defect on a real frame, then render every face and require
none.
"""
import os
import subprocess
import sys

import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import render_placeholders as rp  # noqa: E402

pytestmark = pytest.mark.skipif(not rp.has_se_frames(),
                                reason="Strange Eons frame kit not present")


@pytest.fixture
def asset_face(tmp_path):
    """A blank Asset face on the real Seeker frame, registered for layout
    and audit like a rendered card."""
    frame = rp._se_img("templates", "AHLCG-Asset-K").resize((750, 1050), Image.LANCZOS)
    img = Image.new("RGB", frame.size, (210, 200, 180))
    img.paste(frame, (0, 0), frame)
    rp._register_frame(img, "Asset-K", frame)
    rp.PRINT_ISSUES.clear()
    rp._AUDIT_RECS.clear()
    rp.CURRENT_CARD[0] = "test-card"
    yield img, rp._Draw(img), str(tmp_path / "face.png")
    rp.CURRENT_CARD[0] = None
    rp.PRINT_ISSUES.clear()


def kinds():
    return {k for _cid, k, _t, _b in rp.PRINT_ISSUES}


def test_clean_body_text_passes(asset_face):
    img, d, dest = asset_face
    rp._flow_body(d, (40, 690, 712, 1014), "Exhaust: Draw 1 card.",
                  "A short line of flavour.")
    rp._finish(img, dest)
    assert rp.PRINT_ISSUES == []


def test_rules_on_the_bottom_ornament_are_caught(asset_face):
    img, d, dest = asset_face
    with rp._audit_role("body"):
        # the plugin's Body region runs to y 920, below the visible parchment
        rp._draw_line(d, 60, 930, [(False, "hidden under the ornament")],
                      rp.BODY_PX, rp.PSD_INK)
    rp._finish(img, dest)
    assert {"frame", "contrast"} & kinds()


def test_text_covered_by_a_pasted_icon_is_caught(asset_face):
    img, d, dest = asset_face
    d.text((300, 760), "covered", font=rp._font(rp.BODY_PX), fill=rp.PSD_INK)
    img.paste((40, 30, 30), (290, 750, 420, 800))
    rp._finish(img, dest)
    assert "covered" in kinds()


def test_rules_touching_the_credit_line_are_caught(asset_face):
    img, d, dest = asset_face
    d.text((60, 760), "Illus. Somebody", font=rp._font(18, bold=True), fill=rp.PSD_INK)
    with rp._audit_role("body"):
        rp._draw_line(d, 70, 752, [(False, "rules run into it")], rp.BODY_PX,
                      rp.PSD_INK)
    rp._finish(img, dest)
    assert "collision" in kinds()


def test_text_off_the_card_edge_is_caught(asset_face):
    img, d, dest = asset_face
    d.text((700, 760), "clipped text", font=rp._font(rp.BODY_PX), fill=rp.PSD_INK)
    rp._finish(img, dest)
    assert "clipped" in kinds()


def test_layout_keeps_rules_inside_the_visible_parchment(asset_face):
    """Dense rules shrink (or drop flavour) instead of running onto the
    frame: every line's ink stays clear of the ornament."""
    img, d, dest = asset_face
    text = " ".join(["Exhaust this card: an effect of some length happens."] * 9)
    rp._flow_body(d, (40, 690, 712, 1014), text, "Flavour that may be dropped.")
    rp._finish(img, dest)
    assert rp.PRINT_ISSUES == []


def test_every_face_prints_clean():
    """Render every face (into a temporary folder) and require no hidden,
    covered, colliding, clipped or overflowing text."""
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "pipeline", "render_placeholders.py"),
                        "--check"],
                       cwd=ROOT, capture_output=True, text=True, timeout=1800)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-4000:]
    assert "PRINT AUDIT" not in out and "TEXT OVERFLOW" not in out, out[-4000:]
