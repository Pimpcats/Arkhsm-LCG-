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
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from cardforge.glyphs import FONT_PATH, MARKUP, glyphify  # noqa: E402
import template_render as T  # noqa: E402  (official-frame template mode)

FACES_DIR = os.path.join(ROOT, "art", "faces")


def load_art_index():
    """id -> chosen illustration path (CardForge's out/<campaign>/index.json)."""
    path = os.path.join(ROOT, "out", "still_hour", "index.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return {}


PLACEMENTS_PATH = os.path.join(ROOT, "out", "still_hour", "placements.json")


def load_placements():
    """id -> {scale, ox, oy}: owner-dragged art placement, relative to the
    cover baseline (scale 1.0 = exactly fills the window; ox/oy pan the art in
    window pixels). Stored as data so every recomposite starts from the
    ORIGINAL image — repeated adjustments never lose quality."""
    if os.path.exists(PLACEMENTS_PATH):
        return json.load(open(PLACEMENTS_PATH, encoding="utf-8"))
    return {}


# Art-window geometry per layout, shared with the Studio's placement editor.
def art_box(card_type):
    """(card_w, card_h, x0, y0, x1, y1) — the drag/scale target. Template mode
    (official frames present) uses the templates' art windows."""
    if T.has_template("investigator_front"):
        if card_type == "Investigator":
            return (750, 523) + T.INV_FRONT["art"]
        if card_type == "Enemy":
            return (419, 600) + T.ENEMY["art"]
        if card_type == "Treachery":
            return (419, 600) + T.TREACHERY["art"]
        return (419, 600, 54, 52, 407, 240)
    if card_type == "Investigator":
        return (750, 523, 24, 84, 264, 435)
    if card_type == "Enemy":
        return (419, 600, 12, 420, 407, 570)
    if card_type == "Treachery":
        return (419, 600, 12, 12, 407, 250)
    return (419, 600, 54, 52, 407, 240)          # Asset / Event / Skill


def paste_cover(img, art_path, box, placement=None):
    """Paste an illustration into an art window. Baseline = cover-crop (fills
    the window); `placement` scales/pans on top of that. Always resamples from
    the original file with Lanczos, so placement edits are lossless-in, one
    resample out."""
    try:
        art = Image.open(os.path.join(ROOT, art_path)).convert("RGB")
    except Exception:
        return False
    p = placement or {}
    bw, bh = box[2] - box[0], box[3] - box[1]
    scale = max(bw / art.width, bh / art.height) * float(p.get("scale", 1.0))
    art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))),
                     Image.LANCZOS)
    # center, then pan by the stored offsets (window pixels)
    px = (art.width - bw) / 2 - float(p.get("ox", 0))
    py = (art.height - bh) / 2 - float(p.get("oy", 0))
    canvas = Image.new("RGB", (bw, bh), (34, 31, 42))
    canvas.paste(art, (-round(px), -round(py)))
    img.paste(canvas, (box[0], box[1]))
    return True

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


# The official font stack (matches the SE plugin / Barnaby Files guide):
# Teutonic for titles (OFL — shipped in-repo), Arno Pro for body text
# (Adobe-licensed — NOT in git; drop your own ArnoPro*.otf files into
# assets/fonts/ and they're picked up automatically), DejaVu as fallback.
FONTS_DIR = os.path.join(ROOT, "assets", "fonts")
# Arkhamic (the community's OFL extension of Teutonic — same face, more
# glyphs) is preferred when installed; plain Teutonic ships in-repo.
TITLE_FONT_CANDIDATES = ["Arkhamic.ttf", "Arkhamic-Regular.ttf", "Teutonic.ttf"]
TITLE_FONT = os.path.join(FONTS_DIR, "Teutonic.ttf")

# Per-card manual font override (Studio card editor): campaigns/still_hour/
# font_overrides.json {card_id: {"title": file, "body": file}} — files are
# names inside assets/fonts/. Set per card by the render loop (serial).
FONT_OVERRIDE = {}
FONT_OVERRIDES_PATH = os.path.join(ROOT, "campaigns", "still_hour",
                                   "font_overrides.json")


def load_font_overrides():
    if os.path.exists(FONT_OVERRIDES_PATH):
        return json.load(open(FONT_OVERRIDES_PATH, encoding="utf-8"))
    return {}


def list_fonts():
    """Installable font files the owner can pick from in the Studio."""
    if not os.path.isdir(FONTS_DIR):
        return []
    return sorted(f for f in os.listdir(FONTS_DIR)
                  if f.lower().endswith((".ttf", ".otf"))
                  and "ArkhamFontWithCodex" not in f)   # icon font, not text
BODY_FONTS = {
    (False, False): ["ArnoProRegular.otf", "ArnoPro-Regular.otf",
                     "MinionProMedium.ttf", "Minion_Pro_Medium.ttf"],
    (True, False): ["ArnoProBold.otf", "ArnoPro-Bold.otf",
                    "MinionProBold.ttf"],
    (False, True): ["ArnoProItalic.otf", "ArnoPro-Italic.otf",
                    "MinionProItalic.ttf"],
    (True, True): ["ArnoProBoldItalic.otf", "ArnoPro-BoldItalic.otf",
                   "MinionProBoldItalic.ttf"],
}


def _font(size, bold=False, italic=False, glyph=False, title=False):
    if glyph:
        return ImageFont.truetype(FONT_PATH, size)
    ov = FONT_OVERRIDE.get("title" if title else "body")
    if ov:
        try:
            return ImageFont.truetype(os.path.join(FONTS_DIR, os.path.basename(ov)), size)
        except OSError:
            pass
    if title:
        for n in TITLE_FONT_CANDIDATES:
            p = os.path.join(FONTS_DIR, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    continue
    for n in BODY_FONTS[(bold, italic)]:
        p = os.path.join(FONTS_DIR, n)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
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

def render_investigator_front(c, pt, dest, art_path=None, placement=None):
    w, h = 750, 523
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    color = CLASS_COLORS.get(c["class"], CLASS_COLORS["Neutral"])
    # name banner + subtitle
    banner(d, 0, w, c["name"], color, height=46, size=28)
    center_text(d, c["subtitle"], w / 2, 50, _font(17, italic=True), GOLD)
    # portrait window left (Joe Diamond layout)
    pbox = (24, 84, 264, h - 88)
    d.rectangle(list(pbox), fill=(34, 31, 42))
    if not (art_path and paste_cover(img, art_path, pbox, placement)):
        center_text(d, "portrait", (pbox[0] + pbox[2]) / 2, 260, _font(15), DIM)
    d.rectangle(list(pbox), outline=(70, 64, 82), width=2)
    # stat plates row over the body column
    gfont = _font(18, glyph=True)
    x = 292
    for value, token in ((c["wil"], "[wil]"), (c["int"], "[int]"),
                         (c["com"], "[com]"), (c["agi"], "[agi]")):
        stat_plate(d, x, 80, value, color, size=40)
        center_text(d, MARKUP[token], x + 20, 132, gfont, INK)
        x += 112
    # body box: traits, ability, flavor
    body_box(d, 280, 162, w - 20, h - 88)
    center_text(d, c.get("traits", ""), (280 + w - 20) / 2, 170,
                _font(16, bold=True, italic=True), PANEL_INK)
    y = draw_wrapped(d, pt.get("text", ""), 294, 198, 13, w - 20 - 294 - 14, PANEL_INK)
    if pt.get("flavor"):
        draw_wrapped(d, pt["flavor"], 294, min(y + 6, h - 130), 12,
                     w - 20 - 294 - 14, (90, 74, 58), italic=True)
    # health / sanity (under the body column)
    cx = (280 + w - 20) / 2
    d.ellipse([cx - 76, h - 80, cx - 32, h - 36], fill=RED, outline=(15, 15, 15))
    center_text(d, str(c["health"]), cx - 54, h - 74, _font(22, bold=True), INK)
    d.ellipse([cx + 32, h - 80, cx + 76, h - 36], fill=BLUE, outline=(15, 15, 15))
    center_text(d, str(c["sanity"]), cx + 54, h - 74, _font(22, bold=True), INK)
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


def render_enemy(c, pt, dest, art_path=None, placement=None):
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
    body_box(d, 16, 144, w - 16, 352)
    traits = c.get("traits", "") + ("  Elite." if c.get("elite") and
                                    "Elite" not in c.get("traits", "") else "")
    center_text(d, traits, w / 2, 152, _font(14, bold=True, italic=True), PANEL_INK)
    y = draw_wrapped(d, pt.get("text", ""), 30, 178, 12, w - 62, PANEL_INK)
    if pt.get("flavor"):
        y = draw_wrapped(d, pt["flavor"], 30, y + 4, 11, w - 62, (90, 74, 58), italic=True)
    if c.get("victory"):
        center_text(d, "Victory {}.".format(c["victory"]), w / 2, min(y + 4, 326),
                    _font(15, bold=True), PANEL_INK)
    # ENEMY banner + damage/horror pips
    banner(d, 358, w, "ENEMY", (30, 28, 36), height=28, size=15)
    px = w / 2 - ((pt.get("damage", 0) + pt.get("horror", 0)) * 24 + 12) / 2
    px = pips(d, px, 392, pt.get("damage", 0), RED)
    pips(d, px + 12, 392, pt.get("horror", 0), BLUE)
    # art window at the bottom (official enemy layout)
    abox = (12, 420, w - 12, h - 30)
    d.rectangle(list(abox), fill=(34, 31, 42))
    if not (art_path and paste_cover(img, art_path, abox, placement)):
        center_text(d, "art", w / 2, 500, _font(14), DIM)
    d.rectangle(list(abox), outline=(70, 64, 82), width=2)
    footer(d, w, h, c["id"])
    img.save(dest)


def render_treachery(c, pt, dest, art_path=None, placement=None):
    w, h = 419, 600
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    # art area with the encounter-set keyhole placeholder
    d.rectangle([12, 12, w - 12, 250], fill=(34, 31, 42))
    if art_path:
        paste_cover(img, art_path, (12, 12, w - 12, 250), placement)
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


def render_player_card(c, pt, dest, art_path=None, placement=None):
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
    # art window
    d.rectangle([54, 52, w - 12, 240], fill=(34, 31, 42))
    if not (art_path and paste_cover(img, art_path, (54, 52, w - 12, 240), placement)):
        center_text(d, c["type"], (54 + w - 12) / 2, 136, _font(16), DIM)
    d.rectangle([54, 52, w - 12, 240], outline=(70, 64, 82), width=2)
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


# ------------------------------------------------- template mode (official frames) --

def t_investigator_front(c, pt, dest, art_path=None, placement=None):
    img = T.open_template("investigator_front")
    d = ImageDraw.Draw(img)
    R = T.INV_FRONT
    color = T.CLASS_COLORS.get(c["class"], T.CLASS_COLORS["Neutral"])
    # class disc
    d.ellipse(list(R["class_disc"]), fill=color, outline=(25, 20, 16), width=2)
    center_text(d, c["class"][0], (R["class_disc"][0] + R["class_disc"][2]) / 2,
                R["class_disc"][1] + 12, _font(26, bold=True), T.SCROLL_INK)
    # name + subtitle over the scroll
    T.rrect(d, R["name"], T.SCROLL, radius=14)
    center_text(d, c["name"], (R["name"][0] + R["name"][2]) / 2, R["name"][1] + 4,
                _font(28, bold=True, title=True), T.SCROLL_INK)
    T.rrect(d, R["subtitle"], T.PARCH_DARK, radius=10)
    center_text(d, c["subtitle"], (R["subtitle"][0] + R["subtitle"][2]) / 2,
                R["subtitle"][1] + 3, _font(15, italic=True), T.INK)
    # stat strip base then coins
    T.rrect(d, R["stats_strip"], T.SCROLL, radius=14)
    skill_colors = [(58, 92, 148), (128, 66, 130), (150, 48, 44), (56, 116, 74)]
    for (box, val, sc) in zip(R["stats"], (c["wil"], c["int"], c["com"], c["agi"]), skill_colors):
        d.ellipse(list(box), fill=sc, outline=(20, 16, 12), width=2)
        center_text(d, str(val), (box[0] + box[2]) / 2, box[1] + 8, _font(22, bold=True), T.SCROLL_INK)
    # portrait
    if art_path:
        paste_cover(img, art_path, R["art"], placement)
    else:
        T.blank_art_window(d, R["art"])
    # body panel
    T.rrect(d, R["panel"], T.PARCH, radius=10)
    px0, py0, px1, _ = R["panel"]
    center_text(d, c.get("traits", ""), (px0 + px1) / 2, py0 + 8,
                _font(15, bold=True, italic=True), T.INK)
    y = draw_wrapped(d, pt.get("text", ""), px0 + 14, py0 + 34, 13, px1 - px0 - 28, T.INK)
    if pt.get("flavor"):
        draw_wrapped(d, pt["flavor"], px0 + 14, min(y + 6, R["hs_y"] - 60), 12,
                     px1 - px0 - 28, T.FLAVOR_INK, italic=True)
    # health / sanity
    cx = (px0 + px1) / 2
    d.ellipse([cx - 66, R["hs_y"], cx - 22, R["hs_y"] + 42], fill=T.RED, outline=(15, 12, 10), width=2)
    center_text(d, str(c["health"]), cx - 44, R["hs_y"] + 6, _font(22, bold=True), T.SCROLL_INK)
    d.ellipse([cx + 22, R["hs_y"], cx + 66, R["hs_y"] + 42], fill=T.BLUE, outline=(15, 12, 10), width=2)
    center_text(d, str(c["sanity"]), cx + 44, R["hs_y"] + 6, _font(22, bold=True), T.SCROLL_INK)
    T.cover_illus_credit(img, d, img.width, img.height, landscape=True)
    img.save(dest)


def t_investigator_back(c, pt, dest, art_path=None):
    img = T.open_template("investigator_back")
    d = ImageDraw.Draw(img)
    R = T.INV_BACK
    T.rrect(d, R["name"], T.SCROLL, radius=14)
    center_text(d, c["name"], (R["name"][0] + R["name"][2]) / 2, R["name"][1] + 4,
                _font(28, bold=True, title=True), T.SCROLL_INK)
    T.rrect(d, R["subtitle"], T.PARCH_DARK, radius=10)
    center_text(d, c["subtitle"], (R["subtitle"][0] + R["subtitle"][2]) / 2,
                R["subtitle"][1] + 3, _font(15, italic=True), T.INK)
    # polaroid portrait
    d.rectangle(list(R["polaroid"]), fill=(238, 234, 224))
    inner = (R["polaroid"][0] + 8, R["polaroid"][1] + 8, R["polaroid"][2] - 8, R["polaroid"][3] - 22)
    if art_path:
        paste_cover(img, art_path, inner)
    else:
        T.blank_art_window(d, inner, label="portrait")
    # deckbuilding column + full-width bio
    T.rrect(d, R["panel"], T.PARCH, radius=8)
    T.rrect(d, R["panel_low"], T.PARCH, radius=8)
    y = draw_wrapped(d, pt.get("back_text", ""), R["panel"][0] + 14, R["panel"][1] + 12,
                     13, R["panel"][2] - R["panel"][0] - 28, T.INK)
    draw_wrapped(d, pt.get("back_flavor", ""), R["panel_low"][0] + 14,
                 max(y + 10, R["panel_low"][1] + 12), 13,
                 R["panel_low"][2] - R["panel_low"][0] - 28, T.FLAVOR_INK, italic=True)
    T.cover_illus_credit(img, d, img.width, img.height, landscape=True)
    img.save(dest)


def t_treachery(c, pt, dest, art_path=None, placement=None):
    layout = "treachery_weakness" if c.get("weakness") else "treachery"
    img = T.open_template(layout if T.has_template(layout) else "treachery")
    d = ImageDraw.Draw(img)
    R = T.TREACHERY
    if art_path:
        paste_cover(img, art_path, R["art"], placement)
    else:
        T.blank_art_window(d, R["art"])
    # redraw the keyhole set-icon over the (new or blanked) art
    d.ellipse(list(R["keyhole"]), fill=(24, 20, 18), outline=T.PARCH_DARK, width=2)
    center_text(d, "?", (R["keyhole"][0] + R["keyhole"][2]) / 2,
                R["keyhole"][1] + 8, _font(22, bold=True), T.PARCH_DARK)
    T.rrect(d, R["type"], T.SCROLL, radius=6)
    center_text(d, c["type"].upper(), (R["type"][0] + R["type"][2]) / 2,
                R["type"][1] + 5, _font(14, bold=True), T.SCROLL_INK)
    T.rrect(d, R["name"], T.PARCH_DARK, radius=8)
    center_text(d, c["name"], (R["name"][0] + R["name"][2]) / 2, R["name"][1] + 3,
                _font(22, bold=True, title=True), T.INK)
    panel = R["panel"]
    if c.get("weakness"):
        T.rrect(d, R["weakness_bar"], (86, 28, 26), radius=6)
        center_text(d, "WEAKNESS", (R["weakness_bar"][0] + R["weakness_bar"][2]) / 2,
                    R["weakness_bar"][1] + 3, _font(12, bold=True), T.SCROLL_INK)
        panel = R["panel_weak"]
    T.rrect(d, panel, T.PARCH, radius=8)
    center_text(d, c.get("traits", ""), (panel[0] + panel[2]) / 2, panel[1] + 6,
                _font(14, bold=True, italic=True), T.INK)
    y = draw_wrapped(d, pt.get("text", ""), panel[0] + 12, panel[1] + 30, 12,
                     panel[2] - panel[0] - 24, T.INK)
    if pt.get("flavor"):
        draw_wrapped(d, pt["flavor"], panel[0] + 12, min(y + 6, panel[3] - 34), 11,
                     panel[2] - panel[0] - 24, T.FLAVOR_INK, italic=True)
    T.cover_illus_credit(img, d, img.width, img.height)
    img.save(dest)


def t_enemy(c, pt, dest, art_path=None, placement=None):
    layout = "enemy_elite" if c.get("elite") and T.has_template("enemy_elite") else "enemy"
    img = T.open_template(layout)
    d = ImageDraw.Draw(img)
    R = T.ENEMY
    T.rrect(d, R["name"], T.SCROLL, radius=10)
    center_text(d, c["name"], (R["name"][0] + R["name"][2]) / 2, R["name"][1] + 4,
                _font(23, bold=True, title=True), T.SCROLL_INK)
    # combat plates over the baked ones
    for key, val, color in (("fight", pt.get("fight", "-"), (140, 48, 42)),
                            ("health", pt.get("health") if pt.get("health") is not None else "—",
                             (72, 66, 60)),
                            ("evade", pt.get("evade", "-"), (58, 104, 66))):
        b = R[key]
        d.polygon([(b[0], b[1] + 8), ((b[0] + b[2]) / 2, b[1]), (b[2], b[1] + 8),
                   (b[2], b[3] - 8), ((b[0] + b[2]) / 2, b[3]), (b[0], b[3] - 8)],
                  fill=color, outline=(18, 14, 12))
        center_text(d, str(val), (b[0] + b[2]) / 2, (b[1] + b[3]) / 2 - 12,
                    _font(22, bold=True), T.SCROLL_INK)
    T.rrect(d, R["traits"], T.PARCH_DARK, radius=6)
    traits = c.get("traits", "") + ("  Elite." if c.get("elite")
                                    and "Elite" not in c.get("traits", "") else "")
    center_text(d, traits, (R["traits"][0] + R["traits"][2]) / 2, R["traits"][1] + 4,
                _font(13, bold=True, italic=True), T.INK)
    panel = R["panel"]
    T.rrect(d, panel, T.PARCH, radius=8)
    y = draw_wrapped(d, pt.get("text", ""), panel[0] + 12, panel[1] + 10, 12,
                     panel[2] - panel[0] - 24, T.INK)
    if pt.get("flavor"):
        y = draw_wrapped(d, pt["flavor"], panel[0] + 12, y + 4, 11,
                         panel[2] - panel[0] - 24, T.FLAVOR_INK, italic=True)
    if c.get("victory"):
        center_text(d, "Victory {}.".format(c["victory"]), (panel[0] + panel[2]) / 2,
                    min(y + 4, panel[3] - 22), _font(14, bold=True), T.INK)
    # ENEMY banner strip + damage/horror pips
    bs = R["banner_strip"]
    T.rrect(d, bs, T.PARCH, radius=8)
    T.rrect(d, (bs[0] + 30, bs[1] + 4, bs[2] - 30, bs[1] + 26), T.SCROLL, radius=6)
    center_text(d, "ENEMY", (bs[0] + bs[2]) / 2, bs[1] + 7, _font(13, bold=True), T.SCROLL_INK)
    total = (pt.get("damage", 0) or 0) + (pt.get("horror", 0) or 0)
    px = (bs[0] + bs[2]) / 2 - (total * 20 + 8) / 2
    px = pips(d, px, bs[1] + 30, pt.get("damage", 0), T.RED, r=8)
    pips(d, px + 8, bs[1] + 30, pt.get("horror", 0), T.BLUE, r=8)
    if art_path:
        paste_cover(img, art_path, R["art"], placement)
    else:
        T.blank_art_window(d, R["art"])
    T.cover_illus_credit(img, d, img.width, img.height)
    img.save(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="render only these card ids")
    ap.add_argument("--no-template", action="store_true",
                    help="force the drawn (non-template) placeholder look")
    args = ap.parse_args()
    use_tpl = (not args.no_template) and T.has_template("investigator_front")
    cards = json.load(open(os.path.join(HERE, "stillhour_cards_spec.json"), encoding="utf-8"))
    enc = os.path.join(HERE, "stillhour_encounter_spec.json")
    if os.path.exists(enc):
        cards += json.load(open(enc, encoding="utf-8"))
    if args.only:
        cards = [c for c in cards if c["id"] in set(args.only)]
    print_text = {k: v for k, v in
                  json.load(open(os.path.join(HERE, "stillhour_print_text.json"), encoding="utf-8")).items()
                  if not k.startswith("_")}
    art_index = load_art_index()
    placements = load_placements()
    os.makedirs(FACES_DIR, exist_ok=True)
    missing_text = []
    composed = 0
    font_overrides = load_font_overrides()
    global FONT_OVERRIDE
    for c in cards:
        FONT_OVERRIDE = font_overrides.get(c["id"], {})
        pt = print_text.get(c["id"], {})
        if not pt.get("text"):
            missing_text.append(c["id"])
        art = art_index.get(c["id"])
        place = placements.get(c["id"])
        composed += 1 if art else 0
        dest = os.path.join(FACES_DIR, c["id"] + ".png")
        back_dest = os.path.join(FACES_DIR, c["id"] + "-back.png")
        if c["type"] == "Investigator":
            if use_tpl:
                t_investigator_front(c, pt, dest, art_path=art, placement=place)
                t_investigator_back(c, pt, back_dest, art_path=art)
            else:
                render_investigator_front(c, pt, dest, art_path=art, placement=place)
                render_investigator_back(c, pt, back_dest)
        elif c["type"] == "Enemy":
            (t_enemy if use_tpl else render_enemy)(c, pt, dest, art_path=art, placement=place)
        elif c["type"] == "Treachery":
            (t_treachery if use_tpl else render_treachery)(c, pt, dest, art_path=art, placement=place)
        else:
            render_player_card(c, pt, dest, art_path=art, placement=place)
    n = len([f for f in os.listdir(FACES_DIR) if f.endswith(".png")])
    print("rendered {} face(s) ({} with chosen art composited) -> {}".format(
        n, composed, os.path.relpath(FACES_DIR, ROOT)))
    if missing_text:
        print("cards with NO rules text in the print layer: " + ", ".join(missing_text))


if __name__ == "__main__":
    main()
