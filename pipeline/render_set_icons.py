#!/usr/bin/env python3
"""render_set_icons.py — draw a campaign's encounter-set symbols.

Official cards print a small black symbol for the encounter set each card
belongs to. These are drawn here as simple vector silhouettes (no generated
art, no lettering) and saved as transparent PNGs:

    campaigns/<id>/set_icons/<set_id>.png      (512 x 512, black on clear)

The renderer (render_placeholders.py) pastes them into each frame's
encounter-symbol slot; pipeline/encounter_sets.py decides which set every
card shows. A new campaign adds its own drawings to DRAW (keyed by the set
ids in its scenario_manifest.json); a set with no drawing prints no symbol.

Run: python3 pipeline/render_set_icons.py [--campaign ID]
"""
import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from campaign_config import CFG  # noqa: E402

S = 512                 # drawing size
INK = (0, 0, 0, 255)
CLEAR = (0, 0, 0, 0)


def _new():
    img = Image.new("RGBA", (S, S), CLEAR)
    return img, ImageDraw.Draw(img)


def _cut(img, draw_fn):
    """Erase whatever draw_fn paints (a mask) from img."""
    m = Image.new("L", img.size, 0)
    draw_fn(ImageDraw.Draw(m))
    img.putalpha(Image.composite(Image.new("L", img.size, 0), img.getchannel("A"), m))


def occultation():
    """An eclipse: a disc with a second disc biting into it, and a thin ring."""
    img, d = _new()
    d.ellipse([60, 60, 452, 452], outline=INK, width=26)
    d.ellipse([130, 130, 382, 382], fill=INK)
    _cut(img, lambda m: m.ellipse([196, 104, 420, 328], fill=255))
    return img


def echoes():
    """Ripples: a dot and three broken rings spreading from it."""
    img, d = _new()
    c = S // 2
    d.ellipse([c - 44, c - 44, c + 44, c + 44], fill=INK)
    for r, gap in ((110, 30), (170, 55), (230, 80)):
        for start in (90, 270):
            d.arc([c - r, c - r, c + r, c + r], start + gap, start + 180 - gap, fill=INK, width=30)
    return img


def static():
    """A jagged break across a disc's edge."""
    img, d = _new()
    d.ellipse([56, 56, 456, 456], outline=INK, width=28)
    pts = [(80, 300), (170, 210), (220, 290), (300, 170), (350, 250), (432, 190)]
    d.line(pts, fill=INK, width=40, joint="curve")
    return img


def hourglass():
    img, d = _new()
    d.rectangle([110, 50, 402, 92], fill=INK)
    d.rectangle([110, 420, 402, 462], fill=INK)
    d.polygon([(140, 92), (372, 92), (276, 256), (372, 420), (140, 420), (236, 256)], fill=INK)
    # the glass's hollow upper half, with sand left in the bottom
    d.polygon([(178, 116), (334, 116), (262, 238), (250, 238)], fill=CLEAR)
    d.polygon([(256, 300), (330, 396), (182, 396)], fill=INK)
    _cut(img, lambda m: m.polygon([(250, 276), (262, 276), (330, 396), (182, 396)], fill=0))
    _cut(img, lambda m: m.polygon([(240, 268), (272, 268), (300, 320), (212, 320)], fill=255))
    return img


def door():
    """An arched doorway standing open on darkness."""
    img, d = _new()
    d.pieslice([116, 40, 396, 320], 180, 360, fill=INK)
    d.rectangle([116, 180, 396, 470], fill=INK)
    _cut(img, lambda m: (m.pieslice([156, 80, 356, 280], 180, 360, fill=255),
                         m.rectangle([156, 180, 356, 470], fill=255)))
    d.polygon([(156, 180), (290, 210), (290, 456), (156, 470)], fill=INK)
    return img


def seal():
    """A wax seal with two ribbon tails."""
    img, d = _new()
    d.polygon([(190, 300), (130, 480), (190, 440), (230, 490), (260, 320)], fill=INK)
    d.polygon([(322, 300), (382, 480), (322, 440), (282, 490), (252, 320)], fill=INK)
    pts = []
    for i in range(24):
        a = math.pi * 2 * i / 24
        r = 170 if i % 2 == 0 else 150
        pts.append((256 + r * math.cos(a), 220 + r * math.sin(a)))
    d.polygon(pts, fill=INK)
    _cut(img, lambda m: m.ellipse([166, 130, 346, 310], outline=255, width=16))
    return img


def lighthouse():
    img, d = _new()
    d.polygon([(206, 150), (306, 150), (340, 470), (172, 470)], fill=INK)
    d.rectangle([196, 96, 316, 150], fill=INK)
    d.polygon([(186, 96), (326, 96), (256, 40)], fill=INK)
    _cut(img, lambda m: m.rectangle([220, 108, 292, 140], fill=255))
    for y in (230, 330):
        _cut(img, lambda m, y=y: m.rectangle([150, y, 362, y + 26], fill=255))
    # the beam
    d.polygon([(316, 112), (500, 60), (500, 170)], fill=INK)
    d.polygon([(196, 112), (12, 60), (12, 170)], fill=INK)
    return img


def bell():
    img, d = _new()
    d.ellipse([226, 40, 286, 100], outline=INK, width=22)
    d.pieslice([126, 80, 386, 340], 180, 360, fill=INK)
    d.polygon([(126, 210), (386, 210), (430, 400), (82, 400)], fill=INK)
    d.ellipse([216, 380, 296, 460], fill=INK)
    return img


def milestone():
    """A roadside marker stone beside a road running off."""
    img, d = _new()
    d.pieslice([150, 70, 362, 282], 180, 360, fill=INK)
    d.rectangle([150, 175, 362, 420], fill=INK)
    d.rectangle([90, 420, 422, 462], fill=INK)
    for y in (200, 270, 340):
        _cut(img, lambda m, y=y: m.rectangle([200, y, 312, y + 22], fill=255))
    return img


def clock():
    """A town-clock face standing at eleven."""
    img, d = _new()
    d.ellipse([48, 48, 464, 464], outline=INK, width=34)
    for i in range(12):
        a = math.pi * 2 * i / 12
        r0, r1 = 150, 190
        d.line([(256 + r0 * math.sin(a), 256 - r0 * math.cos(a)),
                (256 + r1 * math.sin(a), 256 - r1 * math.cos(a))], fill=INK, width=22)
    d.line([(256, 256), (256, 92)], fill=INK, width=26)
    a = -math.pi * 2 / 12
    d.line([(256, 256), (256 + 120 * math.sin(a), 256 - 120 * math.cos(a))], fill=INK, width=34)
    d.ellipse([228, 228, 284, 284], fill=INK)
    return img


def wheel():
    """A great wheel on its stand."""
    img, d = _new()
    c, r = (256, 220), 180
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=INK, width=26)
    for i in range(8):
        a = math.pi * 2 * i / 8
        d.line([c, (c[0] + r * math.cos(a), c[1] + r * math.sin(a))], fill=INK, width=14)
        x, y = c[0] + r * math.cos(a), c[1] + r * math.sin(a)
        d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=INK)
    d.ellipse([c[0] - 34, c[1] - 34, c[0] + 34, c[1] + 34], fill=INK)
    d.line([c, (130, 480)], fill=INK, width=26)
    d.line([c, (382, 480)], fill=INK, width=26)
    return img


def book():
    """An open book."""
    img, d = _new()
    d.polygon([(40, 150), (256, 190), (256, 440), (40, 400)], fill=INK)
    d.polygon([(472, 150), (256, 190), (256, 440), (472, 400)], fill=INK)
    for k in range(3):
        y = 230 + 50 * k
        _cut(img, lambda m, y=y: (m.line([(80, y - 10), (220, y + 16)], fill=255, width=14),
                                  m.line([(432, y - 10), (292, y + 16)], fill=255, width=14)))
    _cut(img, lambda m: m.line([(256, 186), (256, 444)], fill=255, width=10))
    return img


def hand():
    """A clock hand drawn like a blade, point down."""
    img, d = _new()
    d.polygon([(256, 480), (210, 250), (256, 120), (302, 250)], fill=INK)
    d.ellipse([206, 50, 306, 150], fill=INK)
    _cut(img, lambda m: m.ellipse([236, 80, 276, 120], fill=255))
    d.line([(160, 300), (352, 300)], fill=INK, width=24)
    return img


# set id -> drawing (The Still Hour's sets; another campaign adds its own)
DRAW = {
    "occultation_skips": occultation,
    "echoes": echoes,
    "static": static,
    "weight_of_years": hourglass,
    "appointed": door,
    "named": seal,
    "node_lighthouse": lighthouse,
    "node_church": bell,
    "node_road": milestone,
    "node_square": clock,
    "node_fairground": wheel,
    "node_almanac": book,
    "strays": hand,
}


def out_dir(campaign=None):
    return os.path.join(os.path.dirname(HERE), "campaigns", campaign or CFG.id, "set_icons")


def main():
    out = out_dir()
    os.makedirs(out, exist_ok=True)
    for sid, fn in DRAW.items():
        fn().save(os.path.join(out, sid + ".png"))
    print("drew {} set symbol(s) -> {}".format(len(DRAW), os.path.relpath(out)))


if __name__ == "__main__":
    main()
