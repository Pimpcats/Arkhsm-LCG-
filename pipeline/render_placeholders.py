#!/usr/bin/env python3
"""render_placeholders.py — proper local placeholder faces with real Arkham glyphs.

Replaces the placehold.co text rectangles with rendered faces: class-colored
banner, name/subtitle/traits, type line, and — the point — the actual Arkham
symbols from assets/fonts/ArkhamFontWithCodex.ttf: investigator statlines,
skill icons, cost, Victory. Output goes to art/faces/{id}.png, i.e. straight
into the Frame-coverage -> Apply pipeline (CardForge Studio picks these up like
any framed face; Apply local mode puts them in the mod with file:/// URLs and
no network dependency at all).

These are placeholder-GRADE faces (no rules text, no frame art) — Strange Eons
still produces the real cards. They just make the mod look like a card game
instead of a spreadsheet while art is pending.

Run: python3 pipeline/render_placeholders.py   (from repo root)
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from cardforge.glyphs import FONT_PATH, MARKUP, glyphify, statline_runs  # noqa: E402

FACES_DIR = os.path.join(ROOT, "art", "faces")

CLASS_COLORS = {
    "Guardian": (43, 80, 140), "Seeker": (196, 132, 47), "Rogue": (55, 122, 83),
    "Mystic": (94, 63, 128), "Survivor": (150, 55, 51), "Neutral": (94, 94, 102),
    "Mythos": (40, 34, 48),
}
BG = (20, 20, 28)
INK = (232, 226, 207)
DIM = (138, 138, 153)
GOLD = (232, 178, 74)


def _font(size, glyph=False):
    if glyph:
        return ImageFont.truetype(FONT_PATH, size)
    for name in ("DejaVuSerif-Bold.ttf", "DejaVuSerif.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_runs(draw, runs, x, y, size, fill):
    """Draw glyphify runs, mixing the Arkham font with a text font, baseline-ish."""
    text_font = _font(size)
    glyph_font = _font(size, glyph=True)
    for is_glyph, chunk in runs:
        font = glyph_font if is_glyph else text_font
        draw.text((x, y), chunk, font=font, fill=fill)
        x += draw.textlength(chunk, font=font)
    return x


def render_card(c, dest):
    is_inv = c["type"] == "Investigator"
    w, h = (750, 523) if is_inv else (419, 600)
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    color = CLASS_COLORS.get(c.get("class", "Neutral"), CLASS_COLORS["Neutral"])

    # class banner + name
    d.rectangle([0, 0, w, 64], fill=color)
    d.text((16, 12), c["name"], font=_font(30 if len(c["name"]) < 22 else 24), fill=INK)
    if c.get("subtitle"):
        d.text((16, 70), c["subtitle"], font=_font(18), fill=GOLD)

    # type / class / traits block
    y = 108
    d.text((16, y), "{} · {}".format(c["type"], c.get("class", "")), font=_font(16), fill=DIM)
    y += 26
    if c.get("traits"):
        d.text((16, y), c["traits"], font=_font(16), fill=INK)
        y += 30

    # cost (top-right coin)
    if c.get("cost") is not None:
        d.ellipse([w - 58, 72, w - 14, 116], outline=GOLD, width=2)
        d.text((w - 44, 80), str(c["cost"]), font=_font(24), fill=GOLD)

    # the glyph content
    y += 12
    if is_inv:
        runs = statline_runs(c["wil"], c["int"], c["com"], c["agi"])
        draw_runs(d, runs, 20, y, 40, INK)
        y += 64
        d.text((20, y), "Health {}   Sanity {}".format(c["health"], c["sanity"]),
               font=_font(22), fill=INK)
    else:
        icon_runs = []
        for key, token in (("wilIcons", "[wil]"), ("intIcons", "[int]"),
                           ("comIcons", "[com]"), ("agiIcons", "[agi]"),
                           ("wildIcons", "[wild]")):
            for _ in range(c.get(key, 0)):
                icon_runs += [(True, MARKUP[token]), (False, " ")]
        if icon_runs:
            draw_runs(d, icon_runs, 20, y, 38, INK)
            y += 56
        if c.get("victory"):
            draw_runs(d, glyphify("Victory {} [codex]".format(c["victory"])),
                      20, y, 24, GOLD)
            y += 40
        if c.get("elite"):
            d.text((20, y), "ELITE", font=_font(18), fill=GOLD)
            y += 30

    # footer
    d.rectangle([0, h - 40, w, h], fill=(12, 12, 18))
    d.text((16, h - 32), "{}  ·  THE STILL HOUR  ·  placeholder".format(c["id"]),
           font=_font(13), fill=DIM)
    img.save(dest)


def main():
    cards = json.load(open(os.path.join(HERE, "stillhour_cards_spec.json")))
    enc = os.path.join(HERE, "stillhour_encounter_spec.json")
    if os.path.exists(enc):
        cards += json.load(open(enc))
    os.makedirs(FACES_DIR, exist_ok=True)
    for c in cards:
        render_card(c, os.path.join(FACES_DIR, c["id"] + ".png"))
        if c["type"] == "Investigator":
            # simple deckbuilding back
            img = Image.new("RGB", (750, 523), BG)
            d = ImageDraw.Draw(img)
            d.rectangle([0, 0, 750, 64], fill=CLASS_COLORS.get(c["class"], BG))
            d.text((16, 12), c["name"] + " — deckbuilding", font=_font(26), fill=INK)
            d.text((16, 90), "Deck size 30. See campaign guide for deckbuilding.",
                   font=_font(18), fill=DIM)
            img.save(os.path.join(FACES_DIR, c["id"] + "-back.png"))
    n = len([f for f in os.listdir(FACES_DIR) if f.endswith(".png")])
    print("rendered {} placeholder face(s) -> {}".format(n, os.path.relpath(FACES_DIR, ROOT)))


if __name__ == "__main__":
    main()
