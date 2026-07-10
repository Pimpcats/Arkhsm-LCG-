#!/usr/bin/env python3
"""render_placeholders.py — placeholder faces in OFFICIAL card anatomy.

Layouts follow the reference cards in docs/art_reference/ (straight from the
game): investigator fronts with stat plates + health/sanity, investigator backs
with deck-size/deckbuilding text, treacheries with type/name banners and
Revelation text, enemies with fight/health/evade plates, keyword text,
Victory line, and damage/horror pips. Rules text comes from the print layer
(pipeline/stillhour_print_text.json) with [wil]-style markup drawn using the
real Arkham glyph font.

Placeholder-GRADE (flat colors, no frame art, no illustration) — Strange Eons
still makes the real cards. But the anatomy, content, and iconography match the
target so the mod reads like the game while art is pending.

Run: python3 pipeline/render_placeholders.py   (from repo root)
Out: art/faces/{id}.png  (flows through Frame coverage -> Apply)
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from cardforge.glyphs import FONT_PATH, MARKUP, glyphify  # noqa: E402

FACES_DIR = os.path.join(ROOT, "art", "faces")

CLASS_COLORS = {
    "Guardian": (43, 80, 140), "Seeker": (196, 132, 47), "Rogue": (55, 122, 83),
    "Mystic": (94, 63, 128), "Survivor": (150, 55, 51), "Neutral": (94, 94, 102),
    "Mythos": (52, 44, 62),
}
BG = (26, 24, 32)
PANEL = (238, 231, 214)     # parchment body box, like the references
PANEL_INK = (32, 28, 24)
INK = (232, 226, 207)
DIM = (150, 144, 130)
GOLD = (196, 152, 60)
RED = (168, 44, 38)
BLUE = (52, 84, 148)


def _font(size, bold=False, italic=False, glyph=False):
    if glyph:
        return ImageFont.truetype(FONT_PATH, size)
    names = (["DejaVuSerif-BoldItalic.ttf"] if bold and italic else []) + \
            (["DejaVuSerif-Bold.ttf"] if bold else []) + \
            (["DejaVuSerif-Italic.ttf"] if italic else []) + \
            ["DejaVuSerif.ttf", "DejaVuSans.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_runs(draw, text, size, max_width, italic=False):
    """Wrap [markup] text into lines of (is_glyph, chunk) runs."""
    tfont = _font(size, italic=italic)
    gfont = _font(size, glyph=True)
    lines = []
    for paragraph in text.split("\n"):
        words = []
        for is_glyph, chunk in glyphify(paragraph):
            if is_glyph:
                words.append((True, chunk))
            else:
                words.extend((False, w) for w in chunk.split(" ") if w != "")
        line, width = [], 0.0
        for is_glyph, w in words:
            font = gfont if is_glyph else tfont
            piece = w if is_glyph else (w + " ")
            plen = draw.textlength(piece, font=font)
            if line and width + plen > max_width:
                lines.append(line)
                line, width = [], 0.0
            line.append((is_glyph, piece))
            width += plen
        lines.append(line or [(False, "")])
    return lines


def draw_wrapped(draw, text, x, y, size, max_width, fill, italic=False, leading=1.25):
    tfont = _font(size, italic=italic)
    gfont = _font(size, glyph=True)
    for line in wrap_runs(draw, text, size, max_width, italic=italic):
        cx = x
        for is_glyph, piece in line:
            font = gfont if is_glyph else tfont
            draw.text((cx, y), piece, font=font, fill=fill)
            cx += draw.textlength(piece, font=font)
        y += int(size * leading)
    return y


def center_text(draw, text, cx, y, font, fill):
    w = draw.textlength(text, font=font)
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def banner(draw, y, w, text, color, height=40, text_fill=INK, size=24, x0=0, x1=None):
    x1 = x1 if x1 is not None else w
    draw.rectangle([x0, y, x1, y + height], fill=color)
    center_text(draw, text, (x0 + x1) / 2, y + (height - size) / 2 - 2,
                _font(size, bold=True), text_fill)
    return y + height


def stat_plate(draw, x, y, value, color, size=44):
    draw.polygon([(x, y + 8), (x + size / 2, y), (x + size, y + 8),
                  (x + size, y + size), (x + size / 2, y + size + 8), (x, y + size)],
                 fill=color, outline=(20, 20, 20))
    center_text(draw, str(value), x + size / 2, y + 8, _font(26, bold=True), INK)


def pips(draw, x, y, n, color, r=9):
    for k in range(n or 0):
        cx = x + k * (2 * r + 6)
        draw.ellipse([cx, y, cx + 2 * r, y + 2 * r], fill=color, outline=(15, 15, 15))
    return x + (n or 0) * (2 * r + 6)


def footer(draw, w, h, card_id):
    draw.rectangle([0, h - 26, w, h], fill=(14, 13, 18))
    draw.text((10, h - 22), "Illus. pending · THE STILL HOUR", font=_font(12), fill=DIM)
    t = card_id + " · placeholder"
    draw.text((w - 10 - draw.textlength(t, font=_font(12)), h - 22), t,
              font=_font(12), fill=DIM)


def body_box(draw, x0, y0, x1, y1):
    draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=PANEL,
                           outline=(90, 82, 66), width=2)


# ------------------------------------------------------------- layouts --

def render_investigator_front(c, pt, dest):
    w, h = 750, 523
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    color = CLASS_COLORS.get(c["class"], CLASS_COLORS["Neutral"])
    # name banner + subtitle
    banner(d, 0, w, c["name"], color, height=46, size=28)
    center_text(d, c["subtitle"], w / 2, 50, _font(17, italic=True), GOLD)
    # stat plates row (wil/int/com/agi with glyphs beneath)
    gfont = _font(20, glyph=True)
    x = 96
    for value, token in ((c["wil"], "[wil]"), (c["int"], "[int]"),
                         (c["com"], "[com]"), (c["agi"], "[agi]")):
        stat_plate(d, x, 84, value, color)
        center_text(d, MARKUP[token], x + 22, 140, gfont, INK)
        x += 150
    # body box: traits, ability, flavor
    body_box(d, 24, 176, w - 24, h - 88)
    center_text(d, c.get("traits", ""), w / 2, 184, _font(17, bold=True, italic=True), PANEL_INK)
    y = draw_wrapped(d, pt.get("text", ""), 40, 214, 15, w - 84, PANEL_INK)
    if pt.get("flavor"):
        draw_wrapped(d, pt["flavor"], 40, min(y + 8, h - 130), 14, w - 84,
                     (90, 74, 58), italic=True)
    # health / sanity
    d.ellipse([w / 2 - 90, h - 76, w / 2 - 42, h - 30], fill=RED, outline=(15, 15, 15))
    center_text(d, str(c["health"]), w / 2 - 66, h - 68, _font(24, bold=True), INK)
    d.ellipse([w / 2 + 42, h - 76, w / 2 + 90, h - 30], fill=BLUE, outline=(15, 15, 15))
    center_text(d, str(c["sanity"]), w / 2 + 66, h - 68, _font(24, bold=True), INK)
    footer(d, w, h, c["id"])
    img.save(dest)


def render_investigator_back(c, pt, dest):
    w, h = 750, 523
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    color = CLASS_COLORS.get(c["class"], CLASS_COLORS["Neutral"])
    banner(d, 0, w, c["name"], color, height=46, size=28)
    center_text(d, c["subtitle"], w / 2, 50, _font(17, italic=True), GOLD)
    body_box(d, 24, 84, w - 24, h - 40)
    y = draw_wrapped(d, pt.get("back_text", ""), 40, 100, 15, w - 84, PANEL_INK)
    if pt.get("back_flavor"):
        draw_wrapped(d, pt["back_flavor"], 40, y + 12, 14, w - 84, (90, 74, 58), italic=True)
    footer(d, w, h, c["id"] + "-back")
    img.save(dest)


def render_enemy(c, pt, dest):
    w, h = 419, 600
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    banner(d, 0, w, c["name"], (30, 28, 36), height=42, size=22)
    if c.get("subtitle"):
        center_text(d, c["subtitle"], w / 2, 46, _font(14, italic=True), GOLD)
    # fight / health / evade plates
    y0 = 74
    stat_plate(d, w / 2 - 120, y0, pt.get("fight", "-"), (120, 46, 40))
    stat_plate(d, w / 2 - 22, y0 - 6, pt.get("health") if pt.get("health") is not None else "—",
               (70, 66, 78), size=48)
    stat_plate(d, w / 2 + 76, y0, pt.get("evade", "-"), (46, 84, 60))
    # traits + text
    body_box(d, 16, 144, w - 16, h - 150)
    traits = c.get("traits", "") + ("  Elite." if c.get("elite") and
                                    "Elite" not in c.get("traits", "") else "")
    center_text(d, traits, w / 2, 152, _font(15, bold=True, italic=True), PANEL_INK)
    y = draw_wrapped(d, pt.get("text", ""), 30, 180, 13, w - 62, PANEL_INK)
    if pt.get("flavor"):
        y = draw_wrapped(d, pt["flavor"], 30, y + 6, 12, w - 62, (90, 74, 58), italic=True)
    if c.get("victory"):
        center_text(d, "Victory {}.".format(c["victory"]), w / 2, min(y + 8, h - 190),
                    _font(16, bold=True), PANEL_INK)
    # ENEMY banner + damage/horror pips
    banner(d, h - 144, w, "ENEMY", (30, 28, 36), height=30, size=16)
    px = w / 2 - ((pt.get("damage", 0) + pt.get("horror", 0)) * 24 + 12) / 2
    px = pips(d, px, h - 104, pt.get("damage", 0), RED)
    pips(d, px + 12, h - 104, pt.get("horror", 0), BLUE)
    footer(d, w, h, c["id"])
    img.save(dest)


def render_treachery(c, pt, dest):
    w, h = 419, 600
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    # art area with the encounter-set keyhole placeholder
    d.rectangle([12, 12, w - 12, 250], fill=(34, 31, 42))
    d.ellipse([w / 2 - 26, 196, w / 2 + 26, 248], outline=GOLD, width=2)
    center_text(d, "?", w / 2, 206, _font(26, bold=True), GOLD)
    y = banner(d, 258, w, c["type"].upper(), (30, 28, 36), height=30, size=16)
    y = banner(d, y + 4, w, c["name"], (48, 44, 58), height=36, size=20)
    if c.get("weakness"):
        y = banner(d, y + 4, w, "WEAKNESS", (86, 30, 30), height=24, size=13)
    body_box(d, 16, y + 10, w - 16, h - 60)
    center_text(d, c.get("traits", ""), w / 2, y + 18, _font(15, bold=True, italic=True), PANEL_INK)
    ty = draw_wrapped(d, pt.get("text", ""), 30, y + 46, 13, w - 62, PANEL_INK)
    if pt.get("flavor"):
        draw_wrapped(d, pt["flavor"], 30, min(ty + 8, h - 110), 12, w - 62,
                     (90, 74, 58), italic=True)
    footer(d, w, h, c["id"])
    img.save(dest)


def render_player_card(c, pt, dest):
    w, h = 419, 600
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    color = CLASS_COLORS.get(c.get("class", "Neutral"), CLASS_COLORS["Neutral"])
    banner(d, 0, w, c["name"], color, height=42, size=20)
    # cost coin
    if c.get("cost") is not None:
        d.ellipse([10, 6, 42, 38], fill=(24, 22, 30), outline=GOLD, width=2)
        center_text(d, str(c["cost"]), 26, 10, _font(18, bold=True), GOLD)
    # commit icons down the left edge
    gfont = _font(26, glyph=True)
    iy = 56
    for key, token in (("wilIcons", "[wil]"), ("intIcons", "[int]"),
                       ("comIcons", "[com]"), ("agiIcons", "[agi]"),
                       ("wildIcons", "[wild]")):
        for _ in range(c.get(key, 0)):
            d.rectangle([8, iy, 44, iy + 36], fill=color)
            center_text(d, MARKUP[token], 26, iy + 4, gfont, INK)
            iy += 42
    # art placeholder area
    d.rectangle([54, 52, w - 12, 240], fill=(34, 31, 42))
    center_text(d, c["type"], (54 + w - 12) / 2, 136, _font(16), DIM)
    body_box(d, 16, 250, w - 16, h - 60)
    center_text(d, c.get("traits", ""), w / 2, 258, _font(15, bold=True, italic=True), PANEL_INK)
    ty = draw_wrapped(d, pt.get("text", ""), 30, 286, 13, w - 62, PANEL_INK)
    if pt.get("flavor"):
        draw_wrapped(d, pt["flavor"], 30, min(ty + 8, h - 110), 12, w - 62,
                     (90, 74, 58), italic=True)
    if c.get("memoryCost") is not None:
        t = "Memory cost {}".format(c["memoryCost"])
        d.text((w - 24 - d.textlength(t, font=_font(13)), h - 52), t,
               font=_font(13), fill=GOLD)
    footer(d, w, h, c["id"])
    img.save(dest)


def main():
    cards = json.load(open(os.path.join(HERE, "stillhour_cards_spec.json")))
    enc = os.path.join(HERE, "stillhour_encounter_spec.json")
    if os.path.exists(enc):
        cards += json.load(open(enc))
    print_text = {k: v for k, v in
                  json.load(open(os.path.join(HERE, "stillhour_print_text.json"))).items()
                  if not k.startswith("_")}
    os.makedirs(FACES_DIR, exist_ok=True)
    missing_text = []
    for c in cards:
        pt = print_text.get(c["id"], {})
        if not pt.get("text"):
            missing_text.append(c["id"])
        dest = os.path.join(FACES_DIR, c["id"] + ".png")
        if c["type"] == "Investigator":
            render_investigator_front(c, pt, dest)
            render_investigator_back(c, pt, os.path.join(FACES_DIR, c["id"] + "-back.png"))
        elif c["type"] == "Enemy":
            render_enemy(c, pt, dest)
        elif c["type"] == "Treachery":
            render_treachery(c, pt, dest)
        else:
            render_player_card(c, pt, dest)
    n = len([f for f in os.listdir(FACES_DIR) if f.endswith(".png")])
    print("rendered {} face(s) -> {}".format(n, os.path.relpath(FACES_DIR, ROOT)))
    if missing_text:
        print("cards with NO rules text in the print layer: " + ", ".join(missing_text))


if __name__ == "__main__":
    main()
