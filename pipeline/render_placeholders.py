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
import glob
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


def overrides_path(campaign=None):
    """Where a campaign's hand edits live. Every campaign keeps its own, so
    deleting one can never take another's work with it — and so the compiler,
    which reads the campaign's own folder, sees exactly what the editor wrote."""
    return os.path.join(ROOT, "campaigns", campaign or "still_hour",
                        "card_overrides.json")


CARD_OVERRIDES_PATH = overrides_path()      # the default campaign's file

# owner-editable fields, routed to the spec dict vs the print layer
OV_SPEC_KEYS = ("name", "subtitle", "traits", "cost", "level", "victory",
                "wil", "int", "com", "agi", "slot", "health", "sanity",
                "shroud", "clues", "doom")
OV_PT_KEYS = ("text", "flavor", "back_text", "back_flavor", "fight", "evade",
              "damage", "horror", "player", "investigator1", "xp1",
              "investigator2", "xp2", "investigator3", "xp3")
# fields that are only ever str()-formatted onto the card (an "X" cost or "—"
# is legal, so these aren't forced to int)…
OV_NUMERIC_KEYS = ("cost", "level", "victory", "wil", "int", "com", "agi",
                   "health", "sanity", "fight", "evade",
                   "shroud", "clues", "doom")
# …vs pip counts, which feed range() in the renderers and MUST be small ints
OV_PIP_KEYS = ("damage", "horror")
# location "element" fields — the own symbol, its colour, whether clues are per
# investigator, and the connection list — all editable from the Studio so any
# spot on a location can be swapped without touching JSON
OV_LOC_KEYS = ("icons", "color", "clues_per_investigator", "connections")
# "card properties" — the rest of what an official card carries: its class (and
# so its frame colour), the elite/unique/weakness marks, act & agenda numbering,
# encounter set and deck quantity, asset uses and memory cost, skill wild icons,
# an investigator's elder-sign effect and signature cards. Everything here is
# editable from the Studio, so a whole campaign can be typed in by hand.
OV_FLAG_KEYS = ("elite", "unique", "weakness", "permanent",
                "clues_per_investigator")
OV_COUNT_KEYS = ("quantity", "memoryCost", "wildIcons")
# index is what prints ("Agenda 1"), number is the encounter number ("1/9") —
# both are free text on real cards, so neither is forced to an int
OV_PROP_KEYS = ("class", "deck", "difficulty", "encounter", "uses",
                "elderSign", "signatures", "campaign_name", "index", "number")

# owner watermark, printed in the official footer text/format on every card
WATERMARK = "Pimpcats ACE"


def _wm(art_path):
    """The watermark prints only on illustrated cards; blank templates stay
    clean (an empty string makes _box_text a no-op)."""
    return WATERMARK if art_path else ""
MAX_PIPS = 5                       # the plugin frames carry Damage1..5/Horror1..5


def pip_count(v):
    """A damage/horror count is always a bounded int, no matter what junk a
    stale override or a hand-edited file holds — never let it reach range()
    as a string, None, or an absurd value."""
    try:
        return max(0, min(MAX_PIPS, int(v or 0)))
    except (TypeError, ValueError):
        return 0


def load_card_overrides(campaign=None):
    """Per-card content edits from the Studio's card editor: name, rules
    text, combat values, damage/horror pips… merged over spec + print layer
    at render time (and by the SE bundle). Tolerant of a transient partial
    read (concurrent write) — a bad parse yields no overrides, not a crash.

    With no campaign it reads every campaign's file, newest last, so a render
    pass over the whole repo still finds each card's own edits."""
    if campaign is not None:
        path = overrides_path(campaign)
        if os.path.exists(path):
            try:
                return json.load(open(path, encoding="utf-8"))
            except ValueError:
                return {}
        return {}
    merged = {}
    camp_root = os.path.join(ROOT, "campaigns")
    for name in sorted(os.listdir(camp_root)) if os.path.isdir(camp_root) else []:
        path = overrides_path(name)
        if not os.path.exists(path):
            continue
        try:
            merged.update(json.load(open(path, encoding="utf-8")))
        except ValueError:
            continue
    return merged


def apply_card_overrides(c, pt, ov):
    if not ov:
        return c, pt
    c = dict(c)
    pt = dict(pt)
    for k in OV_SPEC_KEYS:
        if k in ov and not (k in ("health", "sanity") and c.get("type") == "Enemy"):
            c[k] = ov[k]
    for k in OV_LOC_KEYS + OV_FLAG_KEYS + OV_COUNT_KEYS + OV_PROP_KEYS:
        if k in ov:
            c[k] = ov[k]
    if "tokens" in ov:
        c["tokens"] = ov["tokens"]
    for k in OV_PT_KEYS:
        if k in ov:
            pt[k] = ov[k]
    if c.get("type") == "Enemy" and "health" in ov:
        pt["health"] = ov["health"]
    return c, pt


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
    """(card_w, card_h, x0, y0, x1, y1) — the drag/scale target. PSD blanks
    (true frames, native res) outrank the scanned templates."""
    if has_se_frames():
        se_map = {"Investigator": ("Investigator",
                                   "TransparentPortrait-portrait-clip", 1050, 750),
                  "Enemy": ("Enemy", "Portrait-portrait-clip", 750, 1050),
                  "Treachery": ("Treachery", "Portrait-portrait-clip", 750, 1050),
                  "Location": ("Location", "Portrait-portrait-clip", 750, 1050),
                  "Scenario": ("Scenario", "Portrait-portrait-clip", 750, 1050),
                  "Story": ("Story", "Portrait-portrait-clip", 750, 1050),
                  "Agenda": ("Agenda", "Portrait-portrait-clip", 1050, 750),
                  "Act": ("Act", "Portrait-portrait-clip", 1050, 750)}
        if card_type in se_map:
            kind, key, w, h = se_map[card_type]
            box = se_reg(kind, key)
            if box:
                return (w, h) + box
    psd_map = {"Investigator": ("character_card_front", 1048, 738),
               "Enemy": ("scenario_enemy", 733, 1050),
               "Treachery": ("scenario_treachery", 733, 1050)}
    if card_type in psd_map:
        layout, w, h = psd_map[card_type]
        if has_psd(layout):
            return (w, h) + PSD_ART[layout]
    if card_type in ("Asset", "Event", "Skill") and has_se_frames():
        r = _se_regions()
        clip = (r.get("AHLCG-" + card_type, {})
                .get("AHLCG-{}-Portrait-portrait-clip".format(card_type)))
        if clip:
            x, y, w, h = clip
            return (750, 1050, x * 2, y * 2, (x + w) * 2, (y + h) * 2)
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


def frame_underlay(frame):
    """Fill for the art window when a card has no art yet: the frame's own
    average tone, lightened — never a black placeholder box. The template
    reads as an empty space waiting for art, per class palette."""
    small = frame.convert("RGBA").resize((40, 56))
    px = [p for p in small.getdata() if p[3] > 200]
    if not px:
        return (206, 198, 184)
    n = len(px)
    return tuple(min(255, int((sum(p[i] for p in px) / n) * 0.82 + 255 * 0.18))
                 for i in range(3))


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
    base = max(bw / art.width, bh / art.height)
    sx = base * float(p.get("scale", 1.0))
    sy = base * float(p.get("scale_y") or p.get("scale", 1.0))
    art = art.resize((max(1, round(art.width * sx)), max(1, round(art.height * sy))),
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
# newest Arkhamic first — drop a newer Arkhamic_vX.Y.ttf in assets/fonts
# and it is preferred automatically; Teutonic is the last-resort base face
TITLE_FONT_CANDIDATES = ["Arkhamic_v2.2.ttf", "Arkhamic.ttf",
                         "Arkhamic-Regular.ttf", "Teutonic.ttf"]
# an empty investigator art window uses one neutral manila tone for EVERY class
# (else the Guardian's blue frame averages to a dark grey box, unlike the rest)
INV_ART_UNDERLAY = (208, 196, 173)
# the display title fonts don't carry macron vowels (Japanese romanisation etc.)
TITLE_FOLD = str.maketrans({"ō": "o", "ū": "u", "ā": "a", "ī": "i", "ē": "e",
                            "Ō": "O", "Ū": "U", "Ā": "A", "Ī": "I", "Ē": "E"})
# Bolton is the official cards' big stat-numeral face (enemy fight/health/
# evade, investigator skill values, health/sanity chits)
STAT_FONT_CANDIDATES = ["BoltonBold.ttf", "Bolton.ttf"]
TITLE_FONT = os.path.join(FONTS_DIR, "Teutonic.ttf")

# Per-card manual font override (Studio card editor): campaigns/still_hour/
# font_overrides.json {card_id: {"title": file, "body": file}} — files are
# names inside assets/fonts/. Set per card by the render loop (serial).
FONT_OVERRIDE = {}
FONT_OVERRIDES_PATH = os.path.join(ROOT, "campaigns", "still_hour",
                                   "font_overrides.json")


def load_font_overrides():
    if os.path.exists(FONT_OVERRIDES_PATH):
        try:
            return json.load(open(FONT_OVERRIDES_PATH, encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def list_fonts():
    """Installable font files the owner can pick from in the Studio."""
    if not os.path.isdir(FONTS_DIR):
        return []
    return sorted(f for f in os.listdir(FONTS_DIR)
                  if f.lower().endswith((".ttf", ".otf"))
                  and "ArkhamFontWithCodex" not in f)   # icon font, not text
BODY_FONTS = {
    # Nimbus Roman No9 L (from the element kit) is the DEFAULT body font — a
    # complete family (regular/italic/bold/bold-italic), freely redistributable,
    # committed in-repo, so every card renders body text in one consistent serif
    # with real bold + italic (no DejaVu last resort). Arno/Minion remain listed
    # so the owner can still pick their licensed copies from the font dropdown.
    (False, False): ["NimbusRomNo9L-Reg.otf", "ArnoProRegular.otf",
                     "ArnoPro-Regular.otf", "MinionProMedium.ttf",
                     "Minion_Pro_Medium.ttf"],
    (True, False): ["NimbusRomNo9L-Med.otf", "ArnoProBold.otf",
                    "ArnoPro-Bold.otf", "MinionProBold.ttf"],
    (False, True): ["NimbusRomNo9L-RegIta.otf", "ArnoProItalic.otf",
                    "ArnoPro-Italic.otf", "MinionProItalic.ttf"],
    (True, True): ["NimbusRomNo9L-MedIta.otf", "ArnoProBoldItalic.otf",
                   "ArnoPro-BoldItalic.otf", "MinionProBoldItalic.ttf"],
}


def _font(size, bold=False, italic=False, glyph=False, title=False,
          stat=False, font_file=None):
    if glyph:
        return ImageFont.truetype(FONT_PATH, size)
    # per-field override (a specific font file chosen for one text area) wins
    if font_file:
        try:
            return ImageFont.truetype(
                os.path.join(FONTS_DIR, os.path.basename(font_file)), size)
        except OSError:
            pass
    # manual override (per-card editor or global default): one file per role
    ov = FONT_OVERRIDE.get("stat" if stat else "title" if title else "body")
    if ov:
        try:
            return ImageFont.truetype(os.path.join(FONTS_DIR, os.path.basename(ov)), size)
        except OSError:
            pass
    if stat:
        for n in STAT_FONT_CANDIDATES:
            p = os.path.join(FONTS_DIR, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    continue
        bold = True                       # graceful fallback: bold body
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


def wrap_runs(draw, text, size, max_width, italic=False, bold=False,
              font_file=None):
    """Wrap [markup] text into lines of (is_glyph, chunk) runs."""
    tfont = _font(size, italic=italic, bold=bold, font_file=font_file)
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


def draw_wrapped(draw, text, x, y, size, max_width, fill, italic=False,
                 leading=1.25, bold=False, font_file=None):
    tfont = _font(size, italic=italic, bold=bold, font_file=font_file)
    gfont = _font(size, glyph=True)
    for line in wrap_runs(draw, text, size, max_width, italic=italic,
                          bold=bold, font_file=font_file):
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
    n = pip_count(n)
    for k in range(n):
        cx = x + k * (2 * r + 6)
        draw.ellipse([cx, y, cx + 2 * r, y + 2 * r], fill=color, outline=(15, 15, 15))
    return x + n * (2 * r + 6)


def footer(draw, w, h, card_id):
    draw.rectangle([0, h - 26, w, h], fill=(14, 13, 18))
    draw.text((10, h - 22), WATERMARK + " · THE STILL HOUR", font=_font(12), fill=DIM)
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
    for value, token in ((c.get("wil", "-"), "[wil]"), (c.get("int", "-"), "[int]"),
                         (c.get("com", "-"), "[com]"), (c.get("agi", "-"), "[agi]")):
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
    center_text(d, str(c.get("health", "-")), cx - 54, h - 74, _font(22, bold=True), INK)
    d.ellipse([cx + 32, h - 80, cx + 76, h - 36], fill=BLUE, outline=(15, 15, 15))
    center_text(d, str(c.get("sanity", "-")), cx + 54, h - 74, _font(22, bold=True), INK)
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
    px = w / 2 - ((pip_count(pt.get("damage")) + pip_count(pt.get("horror"))) * 24 + 12) / 2
    px = pips(d, px, 392, pt.get("damage"), RED)
    pips(d, px + 12, 392, pt.get("horror"), BLUE)
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
    for (box, val, sc) in zip(R["stats"], (c.get("wil", "-"), c.get("int", "-"), c.get("com", "-"), c.get("agi", "-")), skill_colors):
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
    center_text(d, str(c.get("health", "-")), cx - 44, R["hs_y"] + 6, _font(22, bold=True), T.SCROLL_INK)
    d.ellipse([cx + 22, R["hs_y"], cx + 66, R["hs_y"] + 42], fill=T.BLUE, outline=(15, 12, 10), width=2)
    center_text(d, str(c.get("sanity", "-")), cx + 44, R["hs_y"] + 6, _font(22, bold=True), T.SCROLL_INK)
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


# ------------------------------------------------------------- PSD templates --
# The community AHTCG PSD pack (assets/frames/psd/, extracted by
# tools/extract_psd_blanks.py) provides TRUE blank frames with transparent
# art windows + text regions auto-measured from the PSDs' own type layers.
# When present, these outrank every other card base: art composites UNDER
# the frame, text is typeset straight onto real card material.

PSD_DIR = os.path.join(ROOT, "assets", "frames", "psd")
PSD_INK = (30, 25, 20)
PSD_ART = {
    "character_card_front": (0, 100, 572, 738),
    "scenario_enemy": (0, 520, 733, 1050),
    "scenario_treachery": (0, 0, 733, 615),
}
_PSD_CACHE = {}


def has_psd(layout):
    return (os.path.exists(os.path.join(PSD_DIR, layout + ".png"))
            and os.path.exists(os.path.join(PSD_DIR, layout + "_regions.json")))


def psd_assets(layout):
    if layout not in _PSD_CACHE:
        frame = Image.open(os.path.join(PSD_DIR, layout + ".png")).convert("RGBA")
        regions = json.load(open(os.path.join(PSD_DIR, layout + "_regions.json"),
                                 encoding="utf-8"))
        _PSD_CACHE[layout] = (frame, regions)
    frame, regions = _PSD_CACHE[layout]
    return frame.copy(), regions


def _psd_compose(layout, art_path, placement, label="place art"):
    frame, regions = psd_assets(layout)
    artbox = PSD_ART[layout]
    if frame.getchannel("A").getextrema()[0] < 250:
        # windowed frame: art underneath, ornate borders mask it perfectly
        img = Image.new("RGB", frame.size, frame_underlay(frame))
        if art_path:
            paste_cover(img, art_path, artbox, placement)
        img.paste(frame, (0, 0), frame)
    else:
        # opaque frame (char front): art into its rectangle on top
        img = frame.convert("RGB")
        if art_path:
            paste_cover(img, art_path, artbox, placement)
        else:
            T.blank_art_window(ImageDraw.Draw(img), artbox, label)
    return img, regions


# per-text-area typography overrides, set per-card in the render loop:
#   {field_key: {"font": file, "size": scale, "bold": bool, "italic": bool}}
# empty means every field renders with the card/role defaults.
FIELD_STYLE = {}


def _field_style(key):
    return FIELD_STYLE.get(key) if key else None


def _box_text(d, text, box, fill=PSD_INK, title=False, bold=False, italic=False,
              grow=1.5, min_size=13, max_w_factor=None, max_size=None,
              align="center", stat=False, key=None):
    """Center text on a region bbox, auto-sized. Region bboxes come from the
    template's example text, so start from the box height and shrink to fit.
    Titles must stay inside their region (they sit between the art and the
    border); body/stat text is allowed a little overflow past the example.

    `key` names the editable area (name/subtitle/traits/…); if the owner has set
    a per-area typography override it applies here (font file, size scale,
    bold/italic)."""
    if not text:
        return
    if stat and key is None:
        key = "stats"
    st = _field_style(key)
    font_file = None
    size_scale = 1.0
    if st:
        font_file = st.get("font") or None
        size_scale = float(st.get("size") or 1.0)
        if "bold" in st:
            bold = bool(st["bold"])
        if "italic" in st:
            italic = bool(st["italic"])
    if max_w_factor is None:
        max_w_factor = 1.02 if title else 1.45
    if title:
        # the display title fonts (Arkhamic/Teutonic) lack macron vowels; fold
        # them to their ASCII base so names like "Sōma" read as "Soma" instead
        # of dropping the glyph
        text = text.translate(TITLE_FOLD)
    bw = box[2] - box[0]
    size = max(int((box[3] - box[1]) * grow), min_size)
    if max_size:
        size = min(size, max_size)
    while size > min_size:
        f = _font(size, bold=bold, italic=italic, title=title, stat=stat,
                  font_file=font_file)
        if d.textlength(text, font=f) <= bw * max_w_factor:
            break
        size -= 1
    if size_scale != 1.0:
        size = max(min_size, int(round(size * size_scale)))
    f = _font(size, bold=bold, italic=italic, title=title, stat=stat,
              font_file=font_file)
    w = d.textlength(text, font=f)
    bb = f.getbbox(text)
    if align == "left":
        x = box[0]
    elif align == "right":
        x = box[2] - w
    else:
        x = (box[0] + box[2]) / 2 - w / 2
    d.text((x, (box[1] + box[3]) / 2 - (bb[1] + bb[3]) / 2),
           text, font=f, fill=fill)


def _box_block(d, text, box, fill=PSD_INK, start=30, min_size=15,
               italic=False, leading=1.18, bold=False, key=None):
    """Wrapped [markup] text fitted into a box (shrinks until it fits).

    `key` names the editable area; a per-area typography override (font/size/
    bold/italic) applies here just like on single-line fields."""
    if not text:
        return box[1]
    st = _field_style(key)
    font_file = None
    if st:
        font_file = st.get("font") or None
        if "bold" in st:
            bold = bool(st["bold"])
        if "italic" in st:
            italic = bool(st["italic"])
        start = max(min_size, int(round(start * float(st.get("size") or 1.0))))
    bw = box[2] - box[0]
    size = start
    for size in range(start, min_size - 1, -1):
        n = len(wrap_runs(d, text, size, bw, italic=italic, bold=bold,
                          font_file=font_file))
        if n * int(size * leading) <= box[3] - box[1]:
            break
    return draw_wrapped(d, text, box[0], box[1], size, bw, fill,
                        italic=italic, leading=leading, bold=bold,
                        font_file=font_file)


def _flow_around(d, text, box, obstacle, start=22, min_size=13, fill=PSD_INK,
                 leading=1.24, gap=18, italic=False):
    """Wrapped [markup] text that flows to the RIGHT of an obstacle (the
    portrait) while beside it, then full width once past its bottom — so the
    story text never runs over the investigator-back portrait. Shrinks to fit."""
    if not text:
        return box[1]
    left, top, right, bottom = box
    ob_r = obstacle[2] + gap
    ob_b = obstacle[3]

    def avail(y):
        lx = ob_r if y < ob_b else left
        return lx, right - lx

    def layout(size):
        tfont = _font(size, italic=italic)
        gfont = _font(size, glyph=True)
        lh = int(size * leading)
        y = top
        placed = []
        fits = True
        for para in text.split("\n"):
            words = []
            for is_g, chunk in glyphify(para):
                if is_g:
                    words.append((True, chunk))
                else:
                    words += [(False, w) for w in chunk.split(" ") if w != ""]
            lx, aw = avail(y)
            line, lw = [], 0.0
            for is_g, w in words:
                font = gfont if is_g else tfont
                piece = w if is_g else w + " "
                pl = d.textlength(piece, font=font)
                if line and lw + pl > aw:
                    placed.append((y, lx, line))
                    y += lh
                    if y + lh > bottom:
                        fits = False
                    lx, aw = avail(y)
                    line, lw = [], 0.0
                line.append((is_g, piece, font))
                lw += pl
            placed.append((y, lx, line))
            y += lh
            if y + lh > bottom and para != text.split("\n")[-1]:
                fits = False
        return placed, y, fits

    placed, endy = None, top
    for size in range(start, min_size - 1, -1):
        placed, endy, fits = layout(size)
        if fits:
            break
    for ly, lx, line in placed:
        cx = lx
        for is_g, piece, font in line:
            d.text((cx, ly), piece, font=font, fill=fill)
            cx += d.textlength(piece, font=font)
    return endy


def p_investigator_front(c, pt, dest, art_path=None, placement=None):
    img, R = _psd_compose("character_card_front", art_path, placement,
                          label="investigator art")
    d = ImageDraw.Draw(img)
    _box_text(d, c["name"], R["Character Name"], title=True, key="name")
    _box_text(d, c.get("subtitle", ""), R["Archetype"], italic=True, key="subtitle")
    for key, stat in (("Willpower", "wil"), ("Intellect", "int"),
                      ("Combat", "com"), ("Agility", "agi")):
        _box_text(d, str(c.get(stat, "-")), R[key], stat=True, grow=1.2, key="stats")
    _box_text(d, c.get("traits", ""), R["Keywords"], bold=True, italic=True,
              max_size=26)
    a = R["Ability Text"]
    _box_block(d, pt.get("text", ""), (a[0], a[1], a[2], a[3] + 40), key="text")
    fl = R["Flavor Text"]
    _box_block(d, pt.get("flavor", ""), (fl[0], fl[1], fl[2], fl[3] + 30),
               fill=(84, 66, 50), italic=True, start=24, key="flavor")
    _box_text(d, str(c.get("health", "-")), R["Health"], fill=(255, 246, 240),
              stat=True, grow=0.85)
    _box_text(d, str(c.get("sanity", "-")), R["Sanity"], fill=(240, 246, 255),
              stat=True, grow=0.85)
    # class disc over the template's custom faction icon
    cc = CLASS_COLORS.get(c.get("class", "Neutral"), (94, 94, 102))
    d.ellipse([16, 10, 86, 80], fill=cc, outline=(20, 16, 12), width=3)
    _box_text(d, c.get("class", "?")[0], (16, 10, 86, 80),
              fill=(245, 240, 230), bold=True, grow=0.8)
    _box_text(d, _wm(art_path), R["Artist Credit"], fill=(70, 58, 46))
    _box_text(d, ("\u00a9 " + WATERMARK) if art_path else "", R["Copyright"], fill=(70, 58, 46))
    img.save(dest)


def p_enemy(c, pt, dest, art_path=None, placement=None):
    img, R = _psd_compose("scenario_enemy", art_path, placement)
    d = ImageDraw.Draw(img)
    _box_text(d, c["name"], R["Title"], title=True, key="name")
    for key, val in (("Combat Value", pt.get("fight")),
                     ("Health Value", pt.get("health")),
                     ("Evade Value", pt.get("evade"))):
        blank = val in (None, "", "None")
        _box_text(d, "\u2014" if blank else str(val),
                  R[key], stat=not blank, bold=blank, grow=1.0)
    traits = c.get("traits", "") + ("  Elite." if c.get("elite")
                                    and "Elite" not in c.get("traits", "") else "")
    _box_text(d, traits, R["Keywords"], bold=True, italic=True, max_size=30)
    e2, e1 = R["Effect Text 2"], R["Effect Text"]
    _box_block(d, pt.get("text", ""), (40, e2[1], 693, e1[3] + 70), start=27, key="text")
    if c.get("victory"):
        _box_text(d, "Victory {}.".format(c["victory"]), R["Victory Points"],
                  bold=True, key="victory")
    # damage / horror counts beside the baked heart & brain chits
    for val, x, fill in ((pt.get("damage"), 300, (255, 235, 232)),
                         (pt.get("horror"), 484, (232, 240, 255))):
        if val:
            d.text((x, 560), str(val), font=_font(40, stat=True), fill=fill,
                   stroke_width=3, stroke_fill=(20, 16, 14))
    _box_text(d, _wm(art_path), R["Illustrator Credit"],
              fill=(70, 58, 46))
    img.save(dest)


def p_treachery(c, pt, dest, art_path=None, placement=None):
    img, R = _psd_compose("scenario_treachery", art_path, placement)
    d = ImageDraw.Draw(img)
    _box_text(d, c["name"], R["Title"], title=True, key="name")
    if c.get("weakness"):
        _box_text(d, "—  W E A K N E S S  —", (233, 662, 501, 680),
                  fill=(92, 40, 104), bold=True)
        _box_text(d, c.get("traits", ""), (233, 684, 501, 708),
                  bold=True, italic=True)
    else:
        _box_text(d, c.get("traits", ""), R["Keywords"], bold=True, italic=True,
                  max_size=30)
    e2 = R["Effect Text 2"]
    _box_block(d, pt.get("text", ""), (52, e2[1], 681, 878), start=27, key="text")
    p = R["Plot Text"]
    _box_block(d, pt.get("flavor", ""), (p[0], p[1], p[2], 992),
               fill=(84, 66, 50), italic=True, start=24, key="flavor")
    _box_text(d, _wm(art_path), R["Illustrator Credit"],
              fill=(70, 58, 46))
    img.save(dest)


# ---------------------------------------------------------- SE plugin frames --
# Authentic per-class Asset/Event/Skill frames + exact element regions from
# the Arkham SE plugin (assets/frames/se/, extracted by
# tools/extract_se_plugin.py from assets/plugins/ArkhamHorrorLCG.seext).
# Region coordinates are the plugin's own (375x525 base), rendered at 2x.

SE_FRAMES_DIR = os.path.join(ROOT, "assets", "frames", "se")
SE_SCALE = 2
_SE_CACHE = {}

CLASS_LETTER = {"Guardian": "G", "Seeker": "K", "Rogue": "R", "Mystic": "M",
                "Survivor": "V", "Neutral": "N"}
SKILL_ICON_LETTER = {"wil": "W", "int": "I", "com": "C", "agi": "A", "wild": "D"}
SLOT_OVERLAY = {"Ally": "Slot-Ally", "Hand": "Slot-1 Hand",
                "Hand x2": "Slot-2 Hands", "Arcane": "Slot-1 Arcane",
                "Arcane x2": "Slot-2 Arcane", "Accessory": "Slot-Accessory",
                "Body": "Slot-Body", "Tarot": "Slot-Tarot"}


def has_se_frames():
    return os.path.exists(os.path.join(SE_FRAMES_DIR, "regions.json"))


def _se_regions():
    if "regions" not in _SE_CACHE:
        _SE_CACHE["regions"] = json.load(
            open(os.path.join(SE_FRAMES_DIR, "regions.json"), encoding="utf-8"))
    return _SE_CACHE["regions"]


def se_reg(kind, key, letter=""):
    """Region lookup at render scale. Keys are globally unique in the plugin
    (each settings file prefixes its own), so resolve against a flat index:
    most specific candidate first, shared Game regions as the last resort."""
    if "flat" not in _SE_CACHE:
        flat = {}
        for grp in _se_regions().values():
            flat.update(grp)
        _SE_CACHE["flat"] = flat
    flat = _SE_CACHE["flat"]
    for k in ("AHLCG-{}-{}{}".format(kind, key, letter),
              "AHLCG-{}-{}".format(kind, key),
              "AHLCG-" + key):
        if k in flat:
            x, y, w, h = flat[k]
            return (max(0, x) * SE_SCALE, max(0, y) * SE_SCALE,
                    (x + w) * SE_SCALE, (y + h) * SE_SCALE)
    return None


def _se_img(sub, name):
    key = sub + "/" + name
    if key not in _SE_CACHE:
        p = os.path.join(SE_FRAMES_DIR, sub, name + ".png")
        _SE_CACHE[key] = Image.open(p).convert("RGBA") if os.path.exists(p) else None
    return _SE_CACHE[key]


VITALS_DIR = os.path.join(ROOT, "assets", "stat", "vitals")


def _vital_chit(kind, value):
    """Health-heart / sanity-brain chit for an investigator (official stat
    elements kit). Returns (image, number_baked_in). Values 5-9 ship
    pre-numbered; anything else uses the empty chit + an overlaid numeral."""
    key = "vitals/" + kind
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = None
    if v is not None and 5 <= v <= 9:
        p = os.path.join(VITALS_DIR, "{}_{}.png".format(kind, v))
        k = key + str(v)
        if k not in _SE_CACHE:
            _SE_CACHE[k] = Image.open(p).convert("RGBA") if os.path.exists(p) else None
        if _SE_CACHE[k] is not None:
            return _SE_CACHE[k], True
    p = os.path.join(VITALS_DIR, kind + ".png")
    if key not in _SE_CACHE:
        _SE_CACHE[key] = Image.open(p).convert("RGBA") if os.path.exists(p) else None
    return _SE_CACHE[key], False


def _paste_region(img, overlay, box):
    if overlay is None or box is None:
        return
    w, h = box[2] - box[0], box[3] - box[1]
    ov = overlay.resize((w, h), Image.LANCZOS)
    img.paste(ov, (box[0], box[1]), ov)


# Arkham location connection symbols -> the plugin's own icon assets
LOC_SYMBOL = {"circle": "Circle", "square": "Square", "triangle": "Triangle",
              "diamond": "Diamond", "moon": "Moon", "star": "Star",
              "heart": "Heart", "hourglass": "Hourglass", "cross": "Cross",
              "quote": "Quote", "slash": "Slash", "doubleslash": "DoubleSlash",
              "spade": "Spade", "clover": "Clover", "t": "T", "tee": "T",
              "plus": "Cross"}


def loc_symbol_img(name):
    key = LOC_SYMBOL.get(str(name or "").strip().lower().replace(" ", ""))
    return _se_img("icons", "AHLCG-Loc" + key) if key else None


# named location colours (the official system tints each location a colour so
# connected symbols visually match across the map); hex also accepted
# deep, muted official palette — calibrated against the real Crystalline Cavern
# discs (red≈(156,0,12), purple/aubergine≈(56,0,36), teal≈near-black). Arkham's
# location colours are richer and darker than a "web bright" palette.
LOC_COLORS = {"red": (150, 14, 18), "orange": (184, 84, 24),
              "yellow": (190, 148, 40), "green": (44, 102, 60),
              "teal": (26, 96, 94), "blue": (32, 72, 132),
              "purple": (92, 36, 110), "pink": (168, 56, 110),
              "brown": (108, 72, 46), "grey": (98, 94, 100),
              "gray": (98, 94, 100), "gold": (170, 142, 70)}


def parse_color(c, default=(176, 150, 74)):
    if not c:
        return default
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        return tuple(int(x) for x in c[:3])
    s = str(c).strip().lower()
    if s in LOC_COLORS:
        return LOC_COLORS[s]
    if s.startswith("#") and len(s) == 7:
        try:
            return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    return default


def _tint_icon(overlay, color):
    """Recolour a monochrome plugin symbol to `color`, keeping its shape (alpha)
    and edge softness — this is how a location's symbols get their colour."""
    if overlay is None:
        return overlay
    a = overlay.convert("RGBA").getchannel("A")
    solid = Image.new("RGBA", overlay.size, color + (255,))
    solid.putalpha(a)
    return solid


# official location discs: the shroud is a black disc (white number), clues a
# tan disc (dark number), and each connection is a solid disc in the connecting
# location's colour with a contrasting (cream/dark) symbol punched into it —
# calibrated from the real Crystalline Cavern circle cutouts.
DISC_CREAM = (238, 230, 205)
DISC_DARK = (44, 36, 28)
# official location stat discs (ref: Scarlet Keys / Rainy London Streets):
#   shroud = dark navy disc, WHITE number
#   clue   = cream/tan disc, dark navy number + small per-investigator hat
SHROUD_DISC = (10, 10, 12)
SHROUD_NUM = (244, 242, 236)
CLUE_DISC = (214, 202, 170)
CLUE_INK = (20, 24, 52)


def _luma(color):
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def _shade(color, factor):
    """Scale toward black (factor<1) or white (factor>1), clamped."""
    if factor <= 1:
        return tuple(max(0, int(round(v * factor))) for v in color[:3])
    return tuple(min(255, int(round(v + (255 - v) * (factor - 1))))
                 for v in color[:3])


def _disc(diam, fill, rim=None, rim_w=0, vignette=0.0):
    """A smooth filled circle (optional darker rim), supersampled for clean
    anti-aliased edges. `vignette` (0..1) darkens toward the edge so the disc
    reads as a printed token rather than a flat digital fill."""
    ss = 4
    D = max(1, diam) * ss
    im = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    if rim and rim_w > 0:
        dd.ellipse([0, 0, D - 1, D - 1], fill=tuple(rim) + (255,))
        p = rim_w * ss
        dd.ellipse([p, p, D - 1 - p, D - 1 - p], fill=tuple(fill) + (255,))
    else:
        dd.ellipse([0, 0, D - 1, D - 1], fill=tuple(fill) + (255,))
    if vignette > 0:
        # smooth radial shade: transparent centre -> darker edge (computed at
        # low res, scaled up), so the disc reads as a printed token
        g = 64
        grad = Image.new("L", (g, g), 0)
        gp = grad.load()
        c = (g - 1) / 2.0
        for y in range(g):
            for x in range(g):
                r = ((x - c) ** 2 + (y - c) ** 2) ** 0.5 / c
                gp[x, y] = int(round(vignette * 255 * min(1.0, r) ** 2.2))
        shade_a = grad.resize((D, D), Image.BILINEAR)
        disc_a = im.getchannel("A")
        # apply darkening only where the disc is opaque
        shade = Image.new("RGBA", (D, D), (0, 0, 0, 0))
        shade.putalpha(Image.composite(shade_a, Image.new("L", (D, D), 0),
                                       disc_a))
        im = Image.alpha_composite(im, shade)
    return im.resize((max(1, diam), max(1, diam)), Image.LANCZOS)


def _expand_box(box, scale):
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    hw = (box[2] - box[0]) * scale / 2.0
    hh = (box[3] - box[1]) * scale / 2.0
    return (int(round(cx - hw)), int(round(cy - hh)),
            int(round(cx + hw)), int(round(cy + hh)))


def _paste_disc(img, disc, center_box):
    """Centre a disc image on the centre of a region box."""
    cx = (center_box[0] + center_box[2]) // 2
    cy = (center_box[1] + center_box[3]) // 2
    img.paste(disc, (cx - disc.width // 2, cy - disc.height // 2), disc)


def _conn_disc(symbol_name, color, diam):
    """A connection well: a solid disc in the connecting location's colour with
    its symbol in a contrasting fill (cream on dark, dark on light)."""
    disc = _disc(diam, color, rim=_shade(color, 0.6),
                 rim_w=max(2, diam // 30), vignette=0.32)
    sym = loc_symbol_img(symbol_name)
    if sym:
        fill = DISC_DARK if _luma(color) > 140 else DISC_CREAM
        sym = _tint_icon(sym, fill)
        target = int(diam * 0.54)
        s = min(target / sym.width, target / sym.height)
        w, h = max(1, round(sym.width * s)), max(1, round(sym.height * s))
        sym = sym.resize((w, h), Image.LANCZOS)
        disc.alpha_composite(sym, ((diam - w) // 2, (diam - h) // 2))
    return disc


def _paste_icon_fit(img, overlay, box):
    """Paste an icon centered in a box, preserving its aspect (symbols are not
    always square, and the region boxes aren't either)."""
    if overlay is None or box is None:
        return
    bw, bh = box[2] - box[0], box[3] - box[1]
    s = min(bw / overlay.width, bh / overlay.height)
    w, h = max(1, round(overlay.width * s)), max(1, round(overlay.height * s))
    ov = overlay.resize((w, h), Image.LANCZOS)
    img.paste(ov, (box[0] + (bw - w) // 2, box[1] + (bh - h) // 2), ov)


def s_player_card(kind, c, pt, dest, art_path=None, placement=None):
    """Asset / Event / Skill on the plugin's authentic per-class frame."""
    letter = "W" if c.get("weakness") else CLASS_LETTER.get(c.get("class"), "N")
    frame = _se_img("templates", "AHLCG-{}-{}".format(kind, letter)) \
        or _se_img("templates", "AHLCG-{}-N".format(kind))
    W, H = 375 * SE_SCALE, 525 * SE_SCALE
    frame2 = frame.resize((W, H), Image.LANCZOS)
    img = Image.new("RGB", (W, H), frame_underlay(frame))
    clip = se_reg(kind, "Portrait-portrait-clip")
    if art_path:
        paste_cover(img, art_path, clip, placement)
    img.paste(frame2, (0, 0), frame2)
    d = ImageDraw.Draw(img)

    # commit-icon column (skill boxes + stat icons)
    icons = []
    for stat in ("wil", "int", "com", "agi", "wild"):
        icons += [stat] * int(c.get(stat + "Icons", 0) or 0)
    box_ov = _se_img("overlays", "AHLCG-SkillBox-" + letter)
    for i, stat in enumerate(icons[:6]):
        _paste_region(img, box_ov, se_reg(kind, "Skill{}".format(i + 1)))
        gl = SKILL_ICON_LETTER[stat]
        icon = (_se_img("overlays", "AHLCG-SkillIcon-" + gl + "W")
                if letter == "W" else None) \
            or _se_img("overlays", "AHLCG-SkillIcon-" + gl)
        _paste_region(img, icon, se_reg(kind, "SkillIcon{}".format(i + 1)))

    if kind in ("Asset", "Event") and c.get("cost") is not None:
        _box_text(d, str(c["cost"]), se_reg(kind, "Cost"),
                  fill=(238, 232, 216), title=True, grow=0.95)
    if c.get("level"):
        _box_text(d, str(c["level"]), se_reg(kind, "Level"),
                  fill=(238, 232, 216), stat=True, grow=0.9)

    _box_text(d, c["name"], se_reg(kind, "Name", letter), title=True, grow=1.15, key="name")
    if c.get("subtitle"):
        _box_text(d, c["subtitle"],
                  se_reg(kind, "SubtitleText", letter)
                  or se_reg(kind, "Subtitle", letter), italic=True, key="subtitle")

    # body: traits line, rules, flavor — stacked inside the Body region
    b = se_reg(kind, "Body")
    y = b[1]
    if c.get("traits"):
        _box_text(d, c["traits"], (b[0], y, b[2], y + 30),
                  bold=True, italic=True, max_size=24, key="traits")
        y += 36
    y = _box_block(d, pt.get("text", ""), (b[0], y, b[2], b[3] + 24), start=25, key="text")
    if pt.get("flavor") and y < b[3]:
        _box_block(d, pt.get("flavor", ""), (b[0], y + 8, b[2], b[3] + 40),
                   fill=(84, 66, 50), italic=True, start=21, key="flavor")
    if c.get("victory"):
        _box_text(d, "Victory {}.".format(c["victory"]),
                  (b[0], b[3] + 24, b[2], b[3] + 52), bold=True, max_size=22, key="victory")

    if kind == "Asset" and c.get("slot") in SLOT_OVERLAY:
        _paste_region(img, _se_img("overlays", "AHLCG-" + SLOT_OVERLAY[c["slot"]]),
                      se_reg(kind, "Slot"))
    if kind == "Asset":
        if c.get("health") is not None:
            _box_text(d, str(c["health"]), se_reg(kind, "Stamina"),
                      fill=(250, 244, 238), stat=True, grow=0.9)
        if c.get("sanity") is not None:
            _box_text(d, str(c["sanity"]), se_reg(kind, "Sanity"),
                      fill=(240, 246, 255), stat=True, grow=0.9)

    _box_text(d, _wm(art_path), se_reg(kind, "Artist"),
              fill=(225, 218, 202), grow=1.0)
    _box_text(d, "THE STILL HOUR", se_reg(kind, "Copyright"),
              fill=(225, 218, 202), grow=1.0)
    img.save(dest)


def _se_frame_compose(tpl_name, kind, clip_key, art_path, placement,
                      landscape=False, underlay=None):
    """Template + art: windowed frames get art UNDER, opaque ones get art
    pasted into the clip rect. `underlay` overrides the empty-window fill (used
    to keep the art window a consistent tone across classes). Returns (img,
    draw)."""
    frame = _se_img("templates", tpl_name)
    W = (525 if landscape else 375) * SE_SCALE
    H = (375 if landscape else 525) * SE_SCALE
    frame2 = frame.resize((W, H), Image.LANCZOS)
    clip = se_reg(kind, clip_key)
    windowed = frame.getchannel("A").getextrema()[0] < 250
    if windowed:
        img = Image.new("RGB", (W, H), underlay or frame_underlay(frame))
        if art_path:
            paste_cover(img, art_path, clip, placement)
        img.paste(frame2, (0, 0), frame2)
    else:
        img = frame2.convert("RGB")
        if art_path and clip:
            paste_cover(img, art_path, clip, placement)
        elif underlay and clip:
            # no art: neutral placeholder in the art window so every class reads
            # the same (else e.g. the Guardian's dark-blue backdrop looks like a
            # grey filler box next to the warmer classes)
            ImageDraw.Draw(img).rectangle(list(clip), fill=underlay)
    return img, ImageDraw.Draw(img)


def _se_body(d, c, pt, kind, letter="", extra_bottom=26, text_start=25,
             victory=True):
    """Traits + rules + flavor (+ Victory) stacked in the Body region. Pass
    victory=False when the card places its Victory line at a fixed spot (enemies
    print it centred just above the damage/horror row, not after the text)."""
    b = se_reg(kind, "Body", letter)
    y = b[1]
    if c.get("traits"):
        traits = c["traits"] + ("  Elite." if c.get("elite")
                                and "Elite" not in c["traits"] else "")
        _box_text(d, traits, (b[0], y, b[2], y + 28),
                  bold=True, italic=True, max_size=23, key="traits")
        y += 34
    y = _box_block(d, pt.get("text", ""), (b[0], y, b[2], b[3] + extra_bottom),
                   start=text_start, key="text")
    if pt.get("flavor") and y + 34 < b[3] + extra_bottom:
        y = _box_block(d, pt.get("flavor", ""),
                       (b[0], y + 6, b[2], b[3] + extra_bottom + 16),
                       fill=(84, 66, 50), italic=True, start=20, key="flavor")
    if victory and c.get("victory"):
        _box_text(d, "Victory {}.".format(c["victory"]),
                  (b[0], min(y + 6, b[3]), b[2], min(y + 34, b[3] + 30)),
                  bold=True, max_size=22, key="victory")
    return y


def s_investigator_front(c, pt, dest, art_path=None, placement=None):
    letter = CLASS_LETTER.get(c.get("class"), "N")
    # no underlay: when there's no art the frame's own class-coloured background
    # (e.g. Guardian blue) shows through the portrait window — never a filler box
    img, d = _se_frame_compose("AHLCG-Investigator-" + letter, "Investigator",
                               "TransparentPortrait-portrait-clip",
                               art_path, placement, landscape=True)
    _box_text(d, c["name"], se_reg("Investigator", "Name"), title=True, grow=1.15,
              max_w_factor=1.0, key="name")
    if c.get("subtitle"):
        _box_text(d, c["subtitle"],
                  se_reg("Investigator", "SubtitleText", letter), italic=True,
                  max_size=26, max_w_factor=1.0, key="subtitle")
    for key, stat in (("Willpower", "wil"), ("Intellect", "int"),
                      ("Combat", "com"), ("Agility", "agi")):
        _box_text(d, str(c.get(stat, "-")), se_reg("Investigator", key),
                  stat=True, grow=1.0)
    _se_body(d, c, pt, "Investigator", text_start=20, extra_bottom=0)
    # health (red heart) + sanity (blue brain) chits from the official stat kit
    # — the plugin's own SanityBase is corrupt, so these are the clean source
    for kind, key, val in (("health_heart", "Stamina", c.get("health")),
                           ("sanity_brain", "Sanity", c.get("sanity"))):
        box = se_reg("Investigator", key)
        cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
        chit, numbered = _vital_chit(kind, val)
        if chit is not None:
            _paste_icon_fit(img, chit, (cx - 46, cy - 50, cx + 46, cy + 50))
            if not numbered:
                _box_text(d, str(val), box, fill=(255, 255, 255), stat=True, grow=0.9)
        else:
            _box_text(d, str(val), box, fill=(240, 240, 240), stat=True, grow=0.9)
    _box_text(d, _wm(art_path), se_reg("Investigator", "Artist"),
              fill=(70, 58, 46), max_size=18, align="left")
    _box_text(d, "THE STILL HOUR", se_reg("Investigator", "Copyright"),
              fill=(70, 58, 46), max_size=18, align="right")
    img.save(dest)


def s_investigator_back(c, pt, dest, art_path=None):
    letter = CLASS_LETTER.get(c.get("class"), "N")
    img, d = _se_frame_compose("AHLCG-InvestigatorBack-" + letter,
                               "InvestigatorBack", "Portrait-portrait-clip",
                               art_path, None, landscape=True)
    _box_text(d, c["name"], se_reg("InvestigatorBack", "Name"),
              title=True, grow=1.1, max_w_factor=1.0, key="name")
    if c.get("subtitle"):
        _box_text(d, c["subtitle"],
                  se_reg("InvestigatorBack", "SubtitleText", letter), italic=True,
                  max_w_factor=1.0, key="subtitle")
    b = se_reg("InvestigatorBack", "Body")
    portrait = se_reg("InvestigatorBack", "Portrait-portrait-clip")
    if b and portrait:
        _flow_around(d, pt.get("back_text", ""), b, portrait, start=22)
    else:
        _box_block(d, pt.get("back_text", ""), b, start=22, key="text")
    img.save(dest)


def s_enemy(c, pt, dest, art_path=None, placement=None):
    tpl = "AHLCG-WeaknessEnemy" if c.get("weakness") else "AHLCG-Enemy"
    img, d = _se_frame_compose(tpl, "Enemy", "Portrait-portrait-clip",
                               art_path, placement)
    _box_text(d, c["name"], se_reg("Enemy", "Name"), title=True, grow=1.15, key="name")
    if c.get("subtitle"):
        _box_text(d, c["subtitle"], se_reg("Enemy", "SubtitleText"),
                  italic=True, max_size=26, max_w_factor=1.0, key="subtitle")
    for key, val in (("Attack", pt.get("fight")), ("Health", pt.get("health")),
                     ("Evade", pt.get("evade"))):
        blank = val in (None, "", "None")     # Bolton has no em dash
        _box_text(d, "—" if blank else str(val),
                  se_reg("Enemy", key), stat=not blank, bold=blank, grow=1.0,
                  fill=(238, 232, 216))
    _box_text(d, "ENEMY", se_reg("Enemy", "Label"), bold=True, max_size=15,
              fill=(74, 60, 46))
    _se_body(d, c, pt, "Enemy", extra_bottom=0, text_start=22, victory=False)
    # Victory centred just above the damage/horror row (above the centre chevron)
    if c.get("victory"):
        dmg = se_reg("Enemy", "Damage1")
        hor = se_reg("Enemy", "Horror1")
        if dmg and hor:
            _box_text(d, "Victory {}.".format(c["victory"]),
                      (dmg[0] - 66, dmg[1] - 42, hor[2] + 66, dmg[1] - 6),
                      bold=True, max_size=21, key="victory")
    for kind_key, count, ov in (("Damage", pt.get("damage"), "AHLCG-Damage"),
                                ("Horror", pt.get("horror"), "AHLCG-Horror")):
        for i in range(pip_count(count)):
            _paste_region(img, _se_img("overlays", ov),
                          se_reg("Enemy", "{}{}".format(kind_key, i + 1)))
    _box_text(d, _wm(art_path), se_reg("Enemy", "Artist"),
              fill=(225, 218, 202), grow=1.0)
    img.save(dest)


def s_treachery(c, pt, dest, art_path=None, placement=None):
    weak = bool(c.get("weakness"))
    kind = "WeaknessTreachery" if weak else "Treachery"
    tpl = "AHLCG-" + kind
    img, d = _se_frame_compose(tpl, kind, "Portrait-portrait-clip",
                               art_path, placement)
    name_reg = se_reg(kind, "Name") or se_reg("Treachery", "Name")
    _box_text(d, c["name"], name_reg, title=True, grow=1.15, key="name")
    if weak:
        _box_text(d, "Weakness", se_reg(kind, "Subtype"), italic=True,
                  max_size=20)
    _box_text(d, "TREACHERY", se_reg(kind, "Label") or se_reg("Treachery", "Label"),
              bold=True, max_size=15, fill=(74, 60, 46))
    _se_body(d, c, pt, kind if se_reg(kind, "Body") else "Treachery")
    _box_text(d, _wm(art_path),
              se_reg(kind, "Artist") or se_reg("Treachery", "Artist"),
              fill=(225, 218, 202), grow=1.0)
    img.save(dest)


def _scenario_body(d, kind, c, pt, traits=False, top=None):
    """Rules/flavor block for a scenario-side card, inside its Body region."""
    b = se_reg(kind, "Body")
    if not b:
        return
    y = top if top is not None else b[1]
    b = (b[0], y, b[2], b[3])
    if traits and c.get("traits"):
        _box_text(d, c["traits"], (b[0], y, b[2], y + 28),
                  bold=True, italic=True, max_size=22, key="traits")
        y += 34
    y = _box_block(d, pt.get("text", ""), (b[0], y, b[2], b[3]), start=24, key="text")
    if pt.get("flavor") and y + 30 < b[3]:
        _box_block(d, pt.get("flavor", ""), (b[0], y + 6, b[2], b[3]),
                   fill=(84, 66, 50), italic=True, start=20, key="flavor")


def s_location(c, pt, dest, art_path=None, placement=None):
    """A location, calibrated to the official layout (ref: Abyssal Trench / Sea
    Floor): name, art, a stat band of shroud (left) / "LOCATION" label (centre) /
    per-investigator clues (right), trait + rules + flavour, and a bottom row of
    coloured connection symbols. Shroud is print-only (not a TTS data field)."""
    back = bool(c.get("revealed"))
    kind = "LocationBack" if back else "Location"
    img, d = _se_frame_compose("AHLCG-" + kind, kind, "Portrait-portrait-clip",
                               art_path, placement)
    _box_text(d, c["name"], se_reg(kind, "Name"), title=True, grow=1.15, key="name")
    # a location may have a subtitle banner under the title (e.g. "Feeding
    # Grounds") — distinct from its trait line
    if c.get("subtitle"):
        _box_text(d, c["subtitle"], se_reg(kind, "SubtitleText"),
                  italic=True, max_size=22, key="subtitle")
    # the "LOCATION" type label in the centre of the stat band
    _box_text(d, "LOCATION", se_reg(kind, "Label"), bold=True, max_size=17,
              fill=(74, 60, 46))
    if not back:
        # The frame already PRINTS both wells - the black shroud disc and the
        # tan clue magnifier are part of AHLCG-Location.png. Drawing our own
        # disc on top stacked a second, slightly-off circle over the real one,
        # which is exactly what made them read as pasted on. Only the numeral
        # goes in, the way the plugin itself does it.
        if c.get("shroud") not in (None, ""):
            sh = se_reg("Location", "Shroud")
            dia = sh[2] - sh[0]
            _box_text(d, str(c["shroud"]), sh, stat=True, grow=1.0,
                      max_size=int(dia * 0.52), fill=SHROUD_NUM)
        if c.get("clues") not in (None, ""):
            base = se_reg("Location", "Clues")
            per_inv = bool(c.get("clues_per_investigator"))
            cx = (base[0] + base[2]) // 2
            cy = (base[1] + base[3]) // 2
            dia = base[2] - base[0]
            if per_inv:
                # number left of centre + a small per-investigator hat to its
                # upper-right, both inside the disc (ref: Rainy London Streets)
                nx = cx - int(dia * 0.14)
                _box_text(d, str(c["clues"]),
                          (nx - dia, cy - dia, nx + dia, cy + dia),
                          stat=True, grow=1.0, max_size=int(dia * 0.56),
                          fill=CLUE_INK)
                hat = _tint_icon(_se_img("icons", "AHLCG-PerInvestigator"),
                                 CLUE_INK)
                hcx, hcy = cx + int(dia * 0.24), cy - int(dia * 0.02)
                hw, hh = int(dia * 0.22), int(dia * 0.18)
                _paste_icon_fit(img, hat, (hcx - hw, hcy - hh,
                                           hcx + hw, hcy + hh))
            else:
                _box_text(d, str(c["clues"]), base, stat=True, grow=1.0,
                          max_size=int(dia * 0.60), fill=CLUE_INK)
        if c.get("victory"):
            _box_text(d, "Victory {}.".format(c["victory"]),
                      se_reg("Location", "Victory"), bold=True, max_size=20, key="victory")
    # top-left corner: the location's OWN symbol, a disc in the location's colour
    # (this is how the map identifies each location; ref: Rainy London Streets)
    if c.get("icons"):
        bi = se_reg(kind, "BaseIcon")
        if bi:
            odia = int(min(bi[2] - bi[0], bi[3] - bi[1]) * 0.82)
            _paste_disc(img, _conn_disc(c["icons"], parse_color(c.get("color")),
                                        odia), bi)
    # bottom row: the symbols of the locations this one connects to, each in the
    # connected location's colour (official uses colour to match the map)
    conns = c.get("connections") or []
    if isinstance(conns, str):
        conns = [x for x in conns.split("|") if x]
    for i, con in enumerate(conns[:6]):
        sym = con.get("symbol") if isinstance(con, dict) else con
        col = (parse_color(con.get("color")) if isinstance(con, dict)
               else parse_color(c.get("color")))
        box = se_reg("Location", "Connection{}Icon".format(i + 1))
        if box and sym:
            # fill the well ring (ref: Scarlet Keys disc ≈ 0.085 of card width)
            disc_box = _expand_box(box, 1.0)
            _paste_disc(img, _conn_disc(sym, col, disc_box[2] - disc_box[0]),
                        box)
    # body: trait line, rules, flavour — below the stat band
    b = se_reg(kind, "Body")
    y = b[1]
    if c.get("traits"):
        _box_text(d, c["traits"], (b[0], y, b[2], y + 26),
                  bold=True, italic=True, max_size=20, key="traits")
        y += 30
    y = _box_block(d, pt.get("text", ""), (b[0], y, b[2], b[3]), start=22, key="text")
    if pt.get("flavor") and y + 24 < b[3]:
        _box_block(d, pt.get("flavor", ""), (b[0], y + 4, b[2], b[3]),
                   fill=(84, 66, 50), italic=True, start=19, key="flavor")
    _box_text(d, _wm(art_path), se_reg(kind, "Copyright"),
              fill=(120, 100, 80), max_size=14)
    img.save(dest)



def _scenario_footer(d, kind, c, art_path=None):
    """Illustrator (left) / (c) (centre) / card number (right), in the frame's
    tiny footer band - the official credit line."""
    a = se_reg(kind, "Artist")
    if a:
        _box_text(d, _wm(art_path), a, fill=(110, 92, 72),
                  max_size=13, align="left")
    cp = se_reg(kind, "Copyright")
    if cp:
        _box_text(d, ("\u00a9 " + WATERMARK) if art_path else "", cp, fill=(110, 92, 72), max_size=13)
    num = c.get("number")
    if num:
        en = se_reg(kind, "EncounterNumber")
        if en:
            _box_text(d, str(num), en, fill=(110, 92, 72), max_size=13,
                      align="right")


def s_agenda(c, pt, dest, art_path=None, placement=None):
    """Agenda (the doom clock) - landscape, art LEFT + text RIGHT, "Agenda N"
    header top-right, doom on the frame, credit footer."""
    img, d = _se_frame_compose("AHLCG-Agenda", "Agenda", "Portrait-portrait-clip",
                               art_path, placement, landscape=True)
    hdr = ("Agenda " + str(c.get("index", ""))).strip()
    _box_text(d, hdr, se_reg("Agenda", "ScenarioIndex"), bold=True, max_size=15,
              fill=(74, 60, 46), align="right")
    _box_text(d, c["name"], se_reg("Agenda", "Name"), title=True, grow=1.15, key="name")
    if c.get("doom") not in (None, ""):
        _box_text(d, str(c["doom"]), se_reg("Agenda", "Doom"),
                  stat=True, grow=1.0, fill=(238, 232, 216))
    _scenario_body(d, "Agenda", c, pt)
    _scenario_footer(d, "Agenda", c, art_path)
    img.save(dest)


def s_act(c, pt, dest, art_path=None, placement=None):
    """Act (the objective clock) - landscape, art RIGHT + text LEFT, "Act N"
    header top-left, clue threshold on the frame, credit footer."""
    img, d = _se_frame_compose("AHLCG-Act", "Act", "Portrait-portrait-clip",
                               art_path, placement, landscape=True)
    hdr = ("Act " + str(c.get("index", ""))).strip()
    _box_text(d, hdr, se_reg("Act", "ScenarioIndex"), bold=True, max_size=15,
              fill=(74, 60, 46), align="left")
    _box_text(d, c["name"], se_reg("Act", "Name"), title=True, grow=1.15, key="name")
    if c.get("clues") not in (None, ""):
        _box_text(d, str(c["clues"]), se_reg("Act", "Clues"),
                  stat=True, grow=1.0, fill=(238, 232, 216))
    _scenario_body(d, "Act", c, pt)
    _scenario_footer(d, "Act", c, art_path)
    img.save(dest)


# real chaos-bag token symbols (SE plugin overlays) for the reference card
CHAOS_OVERLAY = {"skull": "AHLCG-ChaosSkull", "cultist": "AHLCG-ChaosCultist",
                 "tablet": "AHLCG-ChaosTablet",
                 "elderthing": "AHLCG-ChaosElderThing"}


def s_scenario_ref(c, pt, dest, art_path=None, placement=None):
    """Scenario reference — on the authentic scenario-reference (Chaos) template:
    title, difficulty (EASY/STANDARD front, HARD/EXPERT back), and rows of the
    real chaos-bag token symbols with their modifier text."""
    img, d = _se_frame_compose("AHLCG-Chaos", "Chaos",
                               "Encounter-portrait-clip", None, None)
    nreg = se_reg("Chaos", "Name")
    # the Name region is tall; keep the title in its upper part and capped so it
    # doesn't swallow the difficulty line below it
    _box_text(d, c["name"], (nreg[0], nreg[1], nreg[2], nreg[1] + 74),
              title=True, grow=1.0, max_size=46, key="name")
    diff = c.get("difficulty") or (
        "HARD / EXPERT" if c.get("revealed") else "EASY / STANDARD")
    _box_text(d, diff, se_reg("Chaos", "Difficulty"), bold=True, max_size=20,
              fill=(74, 60, 46))
    body = se_reg("Chaos", "Body")
    icon = se_reg("Chaos", "BodyIcon")
    icx = (icon[0] + icon[2]) // 2          # token-column centre x
    isize = 80
    tw = body[2] - body[0]
    y = body[1]
    tokens = c.get("tokens") or []
    if tokens:
        for t in tokens:
            tok = str(t.get("token", "")).lower().replace(" ", "")
            text = str(t.get("text", ""))
            # size the text to the row, then measure its height so the token and
            # the text share one horizontal centreline
            size = 27
            for size in range(27, 19, -1):
                lines = wrap_runs(d, text, size, tw)
                if len(lines) * int(size * 1.22) <= isize + 40:
                    break
            lh = int(size * 1.22)
            th = len(lines) * lh
            rowh = max(isize, th)
            cy = y + rowh // 2                     # shared centreline
            draw_wrapped(d, text, body[0], cy - th // 2, size, tw, PSD_INK,
                         leading=1.22)
            ov = CHAOS_OVERLAY.get(tok)
            if ov and _se_img("overlays", ov):
                _paste_icon_fit(img, _se_img("overlays", ov),
                                (icx - isize // 2, cy - isize // 2,
                                 icx + isize // 2, cy + isize // 2))
            y += rowh + 22
    else:
        _box_block(d, pt.get("text", ""), (body[0], y, body[2], body[3]),
                   start=27, key="text")
    img.save(dest)


def s_story(c, pt, dest, art_path=None, placement=None):
    """Story card — name + narrative body."""
    img, d = _se_frame_compose("AHLCG-Story", "Story", "Portrait-portrait-clip",
                               art_path, placement)
    _box_text(d, c["name"], se_reg("Story", "Name"), title=True, grow=1.15, key="name")
    _scenario_body(d, "Story", c, pt, traits=True)
    img.save(dest)




def s_campaign_log(c, pt, dest, art_path=None, placement=None):
    """The campaign log / notes asset — a fillable sheet that travels with the
    campaign box: who is playing, each investigator with their XP/Years, and the
    running campaign notes. Rendered on the parchment scenario stock; every
    field is editable in the Studio like any card."""
    img, d = _se_frame_compose("AHLCG-Chaos", "Chaos",
                               "Encounter-portrait-clip", None, None)
    nreg = se_reg("Chaos", "Name")
    _box_text(d, c.get("name", "Campaign Log"),
              (nreg[0], nreg[1], nreg[2], nreg[1] + 74),
              title=True, grow=1.0, max_size=44, key="name")
    _box_text(d, c.get("subtitle", "") or pt.get("campaign", ""),
              se_reg("Chaos", "Difficulty"), bold=True, max_size=20,
              fill=(74, 60, 46), key="subtitle")
    b = se_reg("Chaos", "Body")
    x0, x1 = b[0] - 96, b[2] + 24
    y = b[1] - 6
    ink = (58, 46, 36)
    rule = (150, 132, 104)

    def field(label, value, ly):
        _box_text(d, label, (x0, ly, x0 + 150, ly + 26), bold=True,
                  max_size=20, align="left", fill=ink)
        d.line([(x0 + 158, ly + 24), (x1, ly + 24)], fill=rule, width=2)
        if value:
            _box_text(d, str(value), (x0 + 164, ly, x1, ly + 24),
                      max_size=20, align="left", fill=ink)
        return ly + 42

    y = field("Player", pt.get("player", ""), y)
    y = field("Campaign", c.get("campaign_name", "The Still Hour"), y)
    y += 6
    for i in range(1, 4):
        inv = pt.get("investigator{}".format(i), "")
        xp = pt.get("xp{}".format(i), "")
        _box_text(d, "Investigator {}".format(i), (x0, y, x0 + 150, y + 26),
                  bold=True, max_size=20, align="left", fill=ink)
        d.line([(x0 + 158, y + 24), (x1 - 150, y + 24)], fill=rule, width=2)
        if inv:
            _box_text(d, str(inv), (x0 + 164, y, x1 - 156, y + 24),
                      max_size=20, align="left", fill=ink)
        _box_text(d, "XP", (x1 - 140, y, x1 - 100, y + 26), bold=True,
                  max_size=20, align="left", fill=ink)
        d.line([(x1 - 96, y + 24), (x1, y + 24)], fill=rule, width=2)
        if xp not in ("", None):
            _box_text(d, str(xp), (x1 - 92, y, x1, y + 24), max_size=20,
                      align="left", fill=ink)
        y += 42
    y += 10
    _box_text(d, "Campaign notes", (x0, y, x0 + 260, y + 26), bold=True,
              max_size=20, align="left", fill=ink)
    y += 32
    notes = pt.get("text", "") or pt.get("notes", "")
    if notes:
        y = _box_block(d, notes, (x0, y, x1, b[3] + 40), start=21,
                       min_size=15, fill=ink, key="text")
    else:
        for _ in range(9):
            if y + 30 > b[3] + 40:
                break
            d.line([(x0, y + 22), (x1, y + 22)], fill=rule, width=2)
            y += 34
    _box_text(d, _wm(art_path), se_reg("Chaos", "Copyright"),
              fill=(120, 100, 80), max_size=14)
    img.save(dest)



SCENARIO_RENDERERS = {"Location": s_location, "Agenda": s_agenda,
                      "CampaignLog": s_campaign_log,
                      "Act": s_act, "Scenario": s_scenario_ref,
                      "Story": s_story}


def content_regions(card_type):
    """logical field -> face-coordinate box, for click-to-edit in the app."""
    if not has_se_frames():
        return {}
    def r(kind, key, letter=""):
        b = se_reg(kind, key, letter)
        return list(b) if b else None
    out = {}
    if card_type == "Investigator":
        out = {"name": r("Investigator", "Name"),
               "text": r("Investigator", "Body"),
               "wil": r("Investigator", "Willpower"),
               "int": r("Investigator", "Intellect"),
               "com": r("Investigator", "Combat"),
               "agi": r("Investigator", "Agility"),
               "health": r("Investigator", "Stamina"),
               "sanity": r("Investigator", "Sanity")}
    elif card_type == "Enemy":
        out = {"name": r("Enemy", "Name"), "text": r("Enemy", "Body"),
               "fight": r("Enemy", "Attack"), "health": r("Enemy", "Health"),
               "evade": r("Enemy", "Evade"),
               "damage": r("Enemy", "Damage1"), "horror": r("Enemy", "Horror1")}
    elif card_type == "Treachery":
        out = {"name": r("Treachery", "Name"), "text": r("Treachery", "Body")}
    elif card_type in ("Asset", "Event", "Skill"):
        out = {"name": r(card_type, "Name", "N"), "text": r(card_type, "Body")}
        if card_type in ("Asset", "Event"):
            out["cost"] = r(card_type, "Cost")
        if card_type == "Asset":
            out["health"] = r(card_type, "Stamina")
            out["sanity"] = r(card_type, "Sanity")
    elif card_type == "Location":
        out = {"name": r("Location", "Name"), "text": r("Location", "Body"),
               "shroud": r("Location", "Shroud"), "clues": r("Location", "Clues")}
    elif card_type == "Agenda":
        out = {"name": r("Agenda", "Name"), "text": r("Agenda", "Body"),
               "doom": r("Agenda", "Doom")}
    elif card_type == "Act":
        out = {"name": r("Act", "Name"), "text": r("Act", "Body"),
               "clues": r("Act", "Clues")}
    elif card_type in ("Scenario", "Story"):
        out = {"name": r(card_type, "Name"), "text": r(card_type, "Body")}
    return {k: v for k, v in out.items() if v}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="render only these card ids")
    ap.add_argument("--no-template", action="store_true",
                    help="force the drawn (non-template) placeholder look")
    args = ap.parse_args()
    use_tpl = (not args.no_template) and T.has_template("investigator_front")
    # EVERY campaign's specs — the authored Still Hour set plus any
    # <campaign>_*_spec.json written by the app (hand-made or imported cards),
    # so a campaign built from scratch renders exactly like the authored one
    cards, seen = [], set()
    for sp in sorted(glob.glob(os.path.join(HERE, "*_spec.json"))):
        try:
            for c in json.load(open(sp, encoding="utf-8")):
                if c.get("id") and c["id"] not in seen:
                    seen.add(c["id"])
                    cards.append(c)
        except (ValueError, OSError):
            continue
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
    global FONT_OVERRIDE, FIELD_STYLE
    card_overrides = load_card_overrides()
    font_default = font_overrides.get("_default", {})
    fields_default = font_default.get("fields", {})
    for c in cards:
        FONT_OVERRIDE = dict(font_default, **font_overrides.get(c["id"], {}))
        # per-area typography: card field styles layered over the global default
        fields_card = font_overrides.get(c["id"], {}).get("fields", {})
        FIELD_STYLE = {k: dict(fields_default.get(k, {}), **fields_card.get(k, {}))
                       for k in set(fields_default) | set(fields_card)}
        pt = print_text.get(c["id"], {})
        c, pt = apply_card_overrides(c, pt, card_overrides.get(c["id"]))
        if not pt.get("text"):
            missing_text.append(c["id"])
        art = art_index.get(c["id"])
        place = placements.get(c["id"])
        composed += 1 if art else 0
        dest = os.path.join(FACES_DIR, c["id"] + ".png")
        back_dest = os.path.join(FACES_DIR, c["id"] + "-back.png")
        if c["type"] == "Investigator":
            if has_se_frames():
                s_investigator_front(c, pt, dest, art_path=art, placement=place)
                s_investigator_back(c, pt, back_dest, art_path=art)
            elif has_psd("character_card_front"):
                p_investigator_front(c, pt, dest, art_path=art, placement=place)
                (t_investigator_back if use_tpl else render_investigator_back)(
                    c, pt, back_dest, **({"art_path": art} if use_tpl else {}))
            elif use_tpl:
                t_investigator_front(c, pt, dest, art_path=art, placement=place)
                t_investigator_back(c, pt, back_dest, art_path=art)
            else:
                render_investigator_front(c, pt, dest, art_path=art, placement=place)
                render_investigator_back(c, pt, back_dest)
        elif c["type"] == "Enemy":
            (s_enemy if has_se_frames() else
             p_enemy if has_psd("scenario_enemy") else
             (t_enemy if use_tpl else render_enemy))(c, pt, dest, art_path=art, placement=place)
        elif c["type"] == "Treachery":
            (s_treachery if has_se_frames() else
             p_treachery if has_psd("scenario_treachery") else
             (t_treachery if use_tpl else render_treachery))(c, pt, dest, art_path=art, placement=place)
        elif c["type"] in ("Asset", "Event", "Skill") and has_se_frames():
            s_player_card(c["type"], c, pt, dest, art_path=art, placement=place)
        elif c["type"] in SCENARIO_RENDERERS and has_se_frames():
            SCENARIO_RENDERERS[c["type"]](c, pt, dest, art_path=art, placement=place)
        else:
            render_player_card(c, pt, dest, art_path=art, placement=place)
    n = len([f for f in os.listdir(FACES_DIR) if f.endswith(".png")])
    print("rendered {} face(s) ({} with chosen art composited) -> {}".format(
        n, composed, os.path.relpath(FACES_DIR, ROOT)))
    if missing_text:
        print("cards with NO rules text in the print layer: " + ", ".join(missing_text))


if __name__ == "__main__":
    main()
