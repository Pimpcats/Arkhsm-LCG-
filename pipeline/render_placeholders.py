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

Rules text is laid out inside each frame's visible parchment (_flow_body), and
every face is print-audited as it is saved (_finish): text the frame hides,
text pasted over, text blocks touching and text off the card are reported.
`--check` renders into a temporary folder and exits 1 on any finding
(tests/test_render_print_audit.py).
"""
import argparse
import re
import glob
import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from cardforge.glyphs import FONT_PATH, MARKUP, glyphify  # noqa: E402
import template_render as T  # noqa: E402  (official-frame template mode)

FACES_DIR = os.path.join(ROOT, "art", "faces")

# Furniture-only mode: compose the frame + text + discs on a TRANSPARENT art
# window instead of a face with art baked in. The live editor overlays this on
# top of the real, draggable art so the art reads *behind* the frame furniture
# exactly as the finished card does. Set by the --furniture CLI flag; the normal
# render path is completely unaffected when it is False.
FURNITURE = False

# Blank mode: the card with NO illustration — background (class colour /
# parchment) + frame + text, art window empty. The editor uses it as the
# backdrop behind the live draggable art, so the class background always shows
# and there is never a baked-in illustration to double with the live art.
BLANK = False


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from campaign_config import CFG  # noqa: E402  (which campaign: build.json)
ILLUSTRATIONS_DIR = CFG.path("illustrations")


def load_art_index():
    """id -> chosen illustration path. Committed art (assets/illustrations/,
    written by pipeline/import_art.py) is the base; a local pick in CardForge's
    out/<campaign>/index.json overrides it card by card."""
    index = {}
    if os.path.isdir(ILLUSTRATIONS_DIR):
        for f in sorted(os.listdir(ILLUSTRATIONS_DIR)):
            stem, ext = os.path.splitext(f)
            if ext.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                index[stem] = os.path.relpath(os.path.join(ILLUSTRATIONS_DIR, f), ROOT)
    path = os.path.join(CFG.path("out_dir"), "index.json")
    if os.path.exists(path):
        index.update(json.load(open(path, encoding="utf-8")))
    return index


PLACEMENTS_PATH = os.path.join(CFG.path("out_dir"), "placements.json")


def overrides_path(campaign=None):
    """Where a campaign's hand edits live. Every campaign keeps its own, so
    deleting one can never take another's work with it — and so the compiler,
    which reads the campaign's own folder, sees exactly what the editor wrote."""
    return os.path.join(ROOT, "campaigns", campaign or CFG.id,
                        "card_overrides.json")


CARD_OVERRIDES_PATH = overrides_path()      # the default campaign's file

# owner-editable fields, routed to the spec dict vs the print layer
OV_SPEC_KEYS = ("name", "subtitle", "traits", "cost", "level", "victory",
                "wil", "int", "com", "agi", "slot", "health", "sanity",
                "shroud", "clues", "doom", "back_shroud")
OV_PT_KEYS = ("text", "flavor", "back_text", "back_flavor", "fight", "evade",
              "damage", "horror", "player", "investigator1", "xp1",
              "investigator2", "xp2", "investigator3", "xp3", "unrevealed_flavor",
              "unrevealed_text")
# fields that are only ever str()-formatted onto the card (an "X" cost or "—"
# is legal, so these aren't forced to int)…
OV_NUMERIC_KEYS = ("cost", "level", "victory", "wil", "int", "com", "agi",
                   "health", "sanity", "fight", "evade",
                   "shroud", "clues", "doom", "back_shroud")
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
                "clues_per_investigator", "unrevealed")
OV_COUNT_KEYS = ("quantity", "memoryCost", "wildIcons",
                 "wilIcons", "intIcons", "comIcons", "agiIcons")
# index is what prints ("Agenda 1"), number is the encounter number ("1/9") —
# both are free text on real cards, so neither is forced to an int
OV_PROP_KEYS = ("class", "deck", "difficulty", "encounter", "uses",
                "elderSign", "signatures", "campaign_name", "index", "number",
                "take", "no_threshold")

# card id -> (encounter set id, "a/total") — filled in main() (encounter_sets.py)
ENC_MARKS = {}

# owner watermark, printed in the official footer text/format on every card
WATERMARK = "Pimpcats ACE"


def _wm(art_path):
    """The watermark prints only on illustrated cards; blank templates stay
    clean (an empty string makes _box_text a no-op)."""
    return WATERMARK if art_path else ""
MAX_PIPS = 5                       # the plugin frames carry Damage1..5/Horror1..5


def _soak_val(v):
    """An asset's health/sanity soak prints only when it's a real positive
    number — a plain item has None (or 0) and shows no chit at all."""
    try:
        return int(v) > 0
    except (TypeError, ValueError):
        return False


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
    # committed placements (campaigns/<campaign>/art_placements.json) are the
    # base; the Studio's local drag edits (out/, gitignored) win per card
    merged = {}
    committed = os.path.join(ROOT, "campaigns", CFG.id, "art_placements.json")
    for path in (committed, PLACEMENTS_PATH):
        if os.path.exists(path):
            merged.update({k: v for k, v in json.load(open(path, encoding="utf-8")).items()
                           if not k.startswith("_")})
    return merged


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
    pixels = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
    px = [p for p in pixels if p[3] > 200]
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
        # keep the alpha channel: a PNG cut-out (transparent background) must
        # composite over the frame's own background — the class colour on an
        # investigator, the parchment on an asset — instead of being flattened
        # onto a dark rectangle. A photo with no alpha still fills the window.
        art = Image.open(os.path.join(ROOT, art_path)).convert("RGBA")
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
    # clip to the window on a transparent layer, then composite with the art's
    # own alpha so transparent areas reveal whatever the frame draws behind
    layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    layer.alpha_composite(art, (-round(px), -round(py)))
    img.paste(layer, (box[0], box[1]), layer)
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
TITLE_FOLD_KEYS = {chr(k) for k in TITLE_FOLD}
# Bolton is the official cards' big stat-numeral face (enemy fight/health/
# evade, investigator skill values, health/sanity chits)
STAT_FONT_CANDIDATES = ["BoltonBold.ttf", "Bolton.ttf"]
TITLE_FONT = os.path.join(FONTS_DIR, "Teutonic.ttf")

# Per-card manual font override (Studio card editor): campaigns/still_hour/
# font_overrides.json {card_id: {"title": file, "body": file}} — files are
# names inside assets/fonts/. Set per card by the render loop (serial).
FONT_OVERRIDE = {}
FONT_OVERRIDES_PATH = os.path.join(ROOT, "campaigns", CFG.id,
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
# Body text: Arno Pro is what FFG prints; it is Adobe-licensed, so it is used
# only when the owner drops their own copies in. Otherwise Crimson Pro (OFL,
# an Aldine oldstyle cut from the same Garamond lineage as Arno/Minion, static
# instances committed in assets/fonts) is the default, and Nimbus Roman (a
# Times clone) is the last committed fallback.
BODY_FONTS = {
    (False, False): ["ArnoProRegular.otf", "ArnoPro-Regular.otf",
                     "CrimsonPro-Regular.ttf", "NimbusRomNo9L-Reg.otf",
                     "MinionProMedium.ttf", "Minion_Pro_Medium.ttf"],
    (True, False): ["ArnoProBold.otf", "ArnoPro-Bold.otf",
                    "CrimsonPro-Bold.ttf", "NimbusRomNo9L-Med.otf",
                    "MinionProBold.ttf"],
    (False, True): ["ArnoProItalic.otf", "ArnoPro-Italic.otf",
                    "CrimsonPro-Italic.ttf", "NimbusRomNo9L-RegIta.otf",
                    "MinionProItalic.ttf"],
    (True, True): ["ArnoProBoldItalic.otf", "ArnoPro-BoldItalic.otf",
                   "CrimsonPro-BoldItalic.ttf", "NimbusRomNo9L-MedIta.otf",
                   "MinionProBoldItalic.ttf"],
}
# Printed Arkham rules text is ~7.5 pt: ~31 px on a 750x1050 face (300 dpi).
# Every body/flavor block starts there and only shrinks when it must fit.
BODY_PX = 31
FLAVOR_PX = 28


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


# a hair of breathing space after an inline icon before the word it precedes,
# and a real gap between rules paragraphs so short abilities don't run together
GLYPH_PAD_FRAC = 0.16
PARA_GAP_FRAC = 0.45


# Ability triggers print bold with an en dash on the real cards
# ("Revelation – ...", "Forced – When ...", "Objective – ...").
TRIGGER_LEAD = re.compile(
    r"^((?:Revelation|Forced|Objective|Prey|Spawn|Haunted|Setup|Surge"
    r"|Hold Back|When reached)(?: \([^)]*\))?)\s*[—–-]\s*|^(When reached):\s*")


TRIGGER_BREAK = re.compile(
    r"(?<=[.!?])\s+(?=(?:Revelation|Forced|Objective|Prey|Spawn|Haunted)\s*[—–-])")


ARROW = "\u2192"


def _arrow_font(size):
    """Nimbus carries the resolution arrow (→) that Crimson Pro lacks."""
    try:
        return ImageFont.truetype(os.path.join(FONTS_DIR, "NimbusRomNo9L-Reg.otf"), size)
    except OSError:
        return _font(size)


def _smart_quotes(text):
    """Printed cards use curly quotes and apostrophes."""
    text = re.sub(r'(^|[\s(\[\u2014\u2013-])"', "\\1\u201c", text)
    text = text.replace('"', "\u201d")
    text = re.sub(r"(^|[\s(\[\u2014\u2013-])'", "\\1\u2018", text)
    return text.replace("'", "\u2019")


def _abilities(text):
    """Each ability on its own paragraph, as printed (curly quotes)."""
    return _smart_quotes(TRIGGER_BREAK.sub("\n", text or ""))


def _trigger_lead(paragraph):
    """(paragraph with an en-dashed trigger, number of leading bold words)."""
    m = TRIGGER_LEAD.match(paragraph)
    if not m:
        return paragraph, 0
    key = m.group(1) or m.group(2)
    rest = paragraph[m.end():]
    return key + " \u2013 " + rest, len(key.split(" ")) + 1


def _para_lines(draw, text, size, max_width, italic=False, bold=False,
                font_file=None, y0=0, narrow=None, leading=1.25):
    """Wrap [markup] text into a list of paragraphs, each a list of lines of
    (is_glyph, chunk) runs. Paragraph structure is preserved so callers can put
    a gap between abilities.

    `narrow` = (y, width): a line drawn from `y0` that would reach below y wraps
    at `width` instead (text flowing beside an act's clue circle)."""
    lh_ = int(size * leading)
    pgap_ = int(lh_ * PARA_GAP_FRAC)
    ycur = [y0]

    def width_now():
        if narrow and ycur[0] + lh_ > narrow[0]:
            return narrow[1]
        return max_width
    tfont = _font(size, italic=italic, bold=bold, font_file=font_file)
    kfont = _font(size, italic=italic, bold=True, font_file=font_file)
    gfont = _font(size, glyph=True)
    gpad = int(size * GLYPH_PAD_FRAC)
    paras = []
    for pn, paragraph in enumerate(_abilities(text).split("\n")):
        if pn:
            ycur[0] += pgap_
        paragraph, nkey = _trigger_lead(paragraph)
        words = []
        for is_glyph, chunk in glyphify(paragraph):
            if is_glyph:
                words.append((True, chunk))
            else:
                words.extend((False, w) for w in chunk.split(" ") if w != "")
        # the leading trigger ("Revelation –") prints bold: run kind None
        for i in range(min(nkey, len(words))):
            if words[i][0] is False:
                words[i] = (None, words[i][1])
        # a word with a glyph the body face lacks ("(→R1)") draws in the
        # fallback face: run kind ARROW
        words = [(ARROW, w) if k is False and ARROW in w else (k, w)
                 for k, w in words]
        afont = _arrow_font(size)
        lines, line, width = [], [], 0.0
        for is_glyph, w in words:
            font = (afont if is_glyph == ARROW else gfont if is_glyph
                    else kfont if is_glyph is None else tfont)
            glyph = is_glyph is True
            piece = w if glyph else (w + " ")
            plen = draw.textlength(piece, font=font) + (gpad if glyph else 0)
            if line and width + plen > width_now():
                lines.append(line)
                ycur[0] += lh_
                line, width = [], 0.0
            line.append((is_glyph, piece))
            width += plen
        lines.append(line or [(False, "")])
        ycur[0] += lh_
        paras.append(lines)
    return paras


def wrap_runs(draw, text, size, max_width, italic=False, bold=False,
              font_file=None):
    """Wrap [markup] text into lines of (is_glyph, chunk) runs (paragraphs
    flattened)."""
    lines = []
    for para in _para_lines(draw, text, size, max_width, italic=italic,
                            bold=bold, font_file=font_file):
        lines.extend(para)
    return lines


def _wrapped_height(text, size, nlines, leading):
    """Total drawn height of `nlines` lines plus the gap between paragraphs, so
    the fit search reserves room for the same spacing draw_wrapped lays down."""
    lh = int(size * leading)
    pgap = int(lh * PARA_GAP_FRAC)
    return nlines * lh + max(0, _abilities(text).count("\n")) * pgap


class _audit_role:
    """Mark the text drawn inside as `role` for the print audit ("body" text
    must sit on visible parchment clear of the frame)."""

    def __init__(self, role):
        self.role = role

    def __enter__(self):
        self.prev = AUDIT.get("role")
        AUDIT["role"] = self.role

    def __exit__(self, *exc):
        AUDIT["role"] = self.prev


def draw_wrapped(draw, text, x, y, size, max_width, fill, italic=False,
                 leading=1.25, bold=False, font_file=None, narrow=None):
    with _audit_role("body"):
        return _draw_wrapped(draw, text, x, y, size, max_width, fill,
                             italic=italic, leading=leading, bold=bold,
                             font_file=font_file, narrow=narrow)


def _draw_wrapped(draw, text, x, y, size, max_width, fill, italic=False,
                  leading=1.25, bold=False, font_file=None, narrow=None):
    tfont = _font(size, italic=italic, bold=bold, font_file=font_file)
    kfont = _font(size, italic=italic, bold=True, font_file=font_file)
    gfont = _font(size, glyph=True)
    # centre the inline icons (action/reaction/elder sign...) vertically on the
    # text line they sit in, the way the official cards do, instead of hanging
    # them from the line top
    tasc, _ = tfont.getmetrics()
    gmid = int(tasc * 0.60)
    gpad = int(size * GLYPH_PAD_FRAC)
    lh = int(size * leading)
    pgap = int(lh * PARA_GAP_FRAC)
    for pi, lines in enumerate(_para_lines(draw, text, size, max_width,
                                           italic=italic, bold=bold,
                                           font_file=font_file, y0=y,
                                           narrow=narrow, leading=leading)):
        if pi:
            y += pgap
        for line in lines:
            cx = x
            for is_glyph, piece in line:
                if is_glyph == ARROW:
                    af = _arrow_font(size)
                    # same baseline as the body face around it
                    draw.text((cx, y + tasc), piece, font=af, fill=fill,
                              anchor="ls")
                    cx += draw.textlength(piece, font=af)
                elif is_glyph:
                    draw.text((cx, y + gmid), piece, font=gfont, fill=fill, anchor="lm")
                    cx += draw.textlength(piece, font=gfont) + gpad
                else:
                    f = kfont if is_glyph is None else tfont
                    draw.text((cx, y), piece, font=f, fill=fill)
                    cx += draw.textlength(piece, font=f)
            y += lh
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
    draw.text((10, h - 22), WATERMARK + " · " + CFG.upper_name, font=_font(12), fill=DIM)
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


def _nudge(box, st):
    """Translate a text region by the owner's saved (dx, dy) offset — the result
    of dragging the text box in the editor. Offsets are in face pixels (the same
    space content_regions reports), so a pure translation keeps size and wrap."""
    if not st:
        return box
    dx = int(st.get("dx", 0) or 0)
    dy = int(st.get("dy", 0) or 0)
    if not (dx or dy):
        return box
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def _box_text(d, text, box, fill=PSD_INK, title=False, bold=False, italic=False,
              grow=1.5, min_size=13, max_w_factor=None, max_size=None,
              align="center", stat=False, key=None, pos_key=None):
    """Center text on a region bbox, auto-sized. Region bboxes come from the
    template's example text, so start from the box height and shrink to fit.
    Titles must stay inside their region (they sit between the art and the
    border); body/stat text is allowed a little overflow past the example.

    `key` names the editable area (name/subtitle/traits/…); if the owner has set
    a per-area typography override it applies here (font file, size scale,
    bold/italic)."""
    if not text:
        return
    if key in ("victory", "traits"):
        # these print inside the rules box: the audit holds them to the
        # visible parchment like the rules themselves
        with _audit_role("body"):
            return _box_text_at(d, text, box, fill, title, bold, italic, grow,
                                min_size, max_w_factor, max_size, align, stat,
                                key, pos_key)
    return _box_text_at(d, text, box, fill, title, bold, italic, grow,
                        min_size, max_w_factor, max_size, align, stat, key,
                        pos_key)


def _box_text_at(d, text, box, fill, title, bold, italic, grow, min_size,
                 max_w_factor, max_size, align, stat, key, pos_key):
    if stat and key is None:
        key = "stats"
    st = _field_style(key)
    # typography comes from `key` (stats share one style); position comes from
    # `pos_key` when given, so each stat numeral can be nudged on its own
    box = _nudge(box, _field_style(pos_key) if pos_key else st)
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
        # the display title fonts (Arkhamic/Teutonic) lack macron vowels: set
        # the base letter and draw the macron over it (below), so "Sōma" on
        # the title matches the rules text instead of reading "Soma"
        macrons = [i for i, ch in enumerate(text) if ch in TITLE_FOLD_KEYS]
        text = text.translate(TITLE_FOLD)
    else:
        macrons = []
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
    y = (box[1] + box[3]) / 2 - (bb[1] + bb[3]) / 2
    d.text((x, y), text, font=f, fill=fill)
    for i in macrons:
        x0 = x + d.textlength(text[:i], font=f)
        cw = d.textlength(text[i], font=f)
        top = y + f.getbbox(text[i])[1]
        th = max(2, int(round(size * 0.07)))
        gap = max(2, int(round(size * 0.08)))
        d.rectangle((x0 + cw * 0.18, top - gap - th, x0 + cw * 0.82, top - gap), fill=fill)


# text that did not fit its box even at the smallest size: (card id, area, size)
OVERFLOWS = []
CURRENT_CARD = [None]


# ------------------------------------------------------------ print audit --
# Every piece of text drawn on a card face is recorded with its exact ink mask
# and the colours under it, so the finished face can be checked for text the
# frame or later furniture hides — the defects a "did it fit its box" check
# can't see, because the boxes themselves (plugin regions) run under ornament:
#   contrast  ink sitting on frame ornament / border / dark art of its own tone
#   covered   an icon, chit or set symbol pasted over the text afterwards
#   collision two separate pieces of text touching (rules into the credit line)
#   clipped   ink running off the card edge
# Problems land in PRINT_ISSUES as (card id, problem, text, box); main() prints
# them and `--check` exits non-zero (tests/test_render_print_audit.py).
PRINT_ISSUES = []
AUDIT = {"on": True}
AUDIT_CONTRAST = 72        # min |luma(ink) - luma(ground)| for a legible pixel
AUDIT_BAD_FRAC = 0.22      # share of a piece's ink that may fail before it counts
AUDIT_COLLIDE_PX = 10      # ink pixels shared by two pieces = a collision
AUDIT_GAP = 4              # px of air kept between different text blocks
_AUDIT_RECS = {}           # id(canvas) -> [record]
_CANVAS_FRAMES = {}        # id(canvas) -> (template name, frame at face size)
_SAFE_MASKS = {}           # (template, size, margin, light) -> (opaque, safe)
AUDIT_MARGIN = 5           # dark ink keeps this many px off any frame ornament
AUDIT_LIGHT = 140          # ...on frame pixels at least this light (parchment)
AUDIT_EDGE_PX = 6          # ink pixels past that margin = text on the frame


def _ink_luma(color):
    if color is None:
        return 0.0
    if isinstance(color, int):
        return float(color)
    r, g, b = color[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


class _AuditDraw(ImageDraw.ImageDraw):
    """ImageDraw that records each text draw on an RGB card canvas for the
    print audit (no effect on what is drawn)."""

    def text(self, xy, text, *args, **kwargs):
        rec = None
        if AUDIT["on"] and CURRENT_CARD[0] and isinstance(text, str) \
                and text.strip():
            try:
                rec = _audit_record(self, xy, text, args, kwargs)
            except Exception:  # noqa: BLE001 - the audit never breaks a render
                rec = None
        out = super().text(xy, text, *args, **kwargs)
        if rec is not None:
            # what the ink looks like as drawn: anything pasted over it later
            # shows up as a change at the save
            W, H = self._image.size
            x0, y0, x1, y1 = rec["box"]
            rec["clip"] = (max(0, x0), max(0, y0), min(W, x1), min(H, y1))
            if rec["clip"][2] > rec["clip"][0] and rec["clip"][3] > rec["clip"][1]:
                rec["snap"] = self._image.crop(rec["clip"])
        return out


def _Draw(img):
    return _AuditDraw(img)


def _audit_record(d, xy, text, args, kwargs):
    img = getattr(d, "_image", None)
    if img is None or img.mode != "RGB":
        return
    fill = kwargs.get("fill", args[0] if args else None)
    font = kwargs.get("font", args[1] if len(args) > 1 else None)
    anchor = kwargs.get("anchor", args[2] if len(args) > 2 else None)
    if font is None:
        return
    bb = d.textbbox(xy, text, font=font, anchor=anchor)
    x0, y0 = int(bb[0]) - 1, int(bb[1]) - 1
    x1, y1 = int(bb[2]) + 2, int(bb[3]) + 2
    if x1 <= x0 or y1 <= y0:
        return
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.ImageDraw(m).text((xy[0] - x0, xy[1] - y0), text, fill=255,
                                font=font, anchor=anchor)
    core = m.point(lambda v: 255 if v > 235 else 0)
    if not core.getbbox():
        return
    W, H = img.size
    clipped = x0 + 1 < 0 or y0 + 1 < 0 or x1 - 2 > W or y1 - 2 > H
    cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    n = sum(core.histogram()[255:])
    low = 0
    if cx1 > cx0 and cy1 > cy0:
        ground = img.crop((cx0, cy0, cx1, cy1)).convert("L")
        sub = core.crop((cx0 - x0, cy0 - y0, cx1 - x0, cy1 - y0))
        fl = _ink_luma(fill)
        bad = ground.point(lambda v: 255 if abs(v - fl) < AUDIT_CONTRAST else 0)
        low = sum(Image.composite(bad, Image.new("L", bad.size, 0),
                                  sub).histogram()[255:])
    role = AUDIT.get("role") or "field"
    rec = {"text": text, "box": (x0, y0, x1, y1), "core": core, "n": n,
           "fill": fill, "low": low, "clipped": clipped, "role": role}
    recs = _AUDIT_RECS.setdefault(id(img), [])
    for o in recs:
        # rules against a different block (credit line, Victory, a label)
        # must also keep a few px of air, not just avoid touching
        g = AUDIT_GAP if o["role"] != role else 0
        ix0, iy0 = max(x0, o["box"][0] - g), max(y0, o["box"][1] - g)
        ix1, iy1 = min(x1, o["box"][2] + g), min(y1, o["box"][3] + g)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        a = core.crop((ix0 - x0, iy0 - y0, ix1 - x0, iy1 - y0))
        b = o["core"].crop((ix0 - o["box"][0], iy0 - o["box"][1],
                            ix1 - o["box"][0], iy1 - o["box"][1]))
        if g:
            b = b.filter(ImageFilter.MaxFilter(2 * g + 1))
        shared = sum(Image.composite(a, Image.new("L", a.size, 0),
                                     b).histogram()[255:])
        if shared > AUDIT_COLLIDE_PX:
            PRINT_ISSUES.append((CURRENT_CARD[0], "collision",
                                 "{!r} / {!r}".format(text.strip(),
                                                      o["text"].strip()),
                                 (ix0, iy0, ix1, iy1)))
    recs.append(rec)
    return rec


def _register_frame(img, name, frame):
    """Remember which frame (RGBA, at face size) the canvas `img` was built
    on: body text is laid out in that frame's visible parchment, and the
    print audit checks against it. Where pasted art covers an opaque frame,
    pass the frame with that window cleared."""
    _CANVAS_FRAMES[id(img)] = (name, frame)


def _safe_mask(name, frame, margin=None, light_min=120):
    """(opaque, safe) masks of a frame at face size. `safe` is the visible
    parchment — light, opaque frame pixels, specks closed — shrunk by
    `margin` (default AUDIT_MARGIN), so dark text outside it sits on (or
    touches) a border, arch, ornament, icon well or banner edge."""
    margin = AUDIT_MARGIN if margin is None else margin
    key = (name, frame.size, margin, light_min)
    if key not in _SAFE_MASKS:
        a = frame.getchannel("A").point(lambda v: 255 if v > 200 else 0)
        light = frame.convert("L").point(lambda v: 255 if v > light_min else 0)
        m = ImageChops.multiply(light, a)
        m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        safe = m.filter(ImageFilter.MinFilter(2 * margin + 1)) if margin else m
        _SAFE_MASKS[key] = (a, safe)
    return _SAFE_MASKS[key]


def _finish(img, dest):
    """Save a card face, auditing the text drawn on it first."""
    recs = _AUDIT_RECS.pop(id(img), [])
    frame = _CANVAS_FRAMES.pop(id(img), None)
    masks = (_safe_mask(frame[0], frame[1], AUDIT_MARGIN, AUDIT_LIGHT)
             if frame and frame[1].size == img.size else None)
    if AUDIT["on"] and img.mode == "RGB":
        W, H = img.size
        for r in recs:
            snippet = r["text"].strip()
            if r["clipped"]:
                PRINT_ISSUES.append((CURRENT_CARD[0], "clipped", snippet, r["box"]))
            if r["n"] and r["low"] > AUDIT_BAD_FRAC * r["n"]:
                PRINT_ISSUES.append((CURRENT_CARD[0], "contrast", snippet, r["box"]))
                continue
            if masks and r["role"] == "body" and _ink_luma(r["fill"]) < 110:
                # dark ink must sit on visible parchment, clear of the frame
                x0, y0, x1, y1 = r["box"]
                cx0, cy0 = max(0, x0), max(0, y0)
                cx1, cy1 = min(W, x1), min(H, y1)
                if cx1 > cx0 and cy1 > cy0:
                    sub = r["core"].crop((cx0 - x0, cy0 - y0, cx1 - x0, cy1 - y0))
                    opaque = masks[0].crop((cx0, cy0, cx1, cy1))
                    unsafe = masks[1].crop((cx0, cy0, cx1, cy1)).point(
                        lambda v: 0 if v else 255)
                    hit = ImageChops.multiply(ImageChops.multiply(sub, opaque),
                                              unsafe)
                    if sum(hit.histogram()[255:]) > AUDIT_EDGE_PX:
                        PRINT_ISSUES.append((CURRENT_CARD[0], "frame", snippet,
                                             r["box"]))
                        continue
            # covered: something pasted over the ink after it was drawn
            snap = r.get("snap")
            if snap is None or not r["n"]:
                continue
            cx0, cy0, cx1, cy1 = r["clip"]
            x0, y0 = r["box"][:2]
            diff = ImageChops.difference(img.crop(r["clip"]), snap).convert("L")
            off = diff.point(lambda v: 255 if v > 24 else 0)
            sub = r["core"].crop((cx0 - x0, cy0 - y0, cx1 - x0, cy1 - y0))
            moved = sum(ImageChops.multiply(off, sub).histogram()[255:])
            # (a dark icon over dark ink changes the ground around it instead)
            area = off.size[0] * off.size[1]
            if moved > AUDIT_BAD_FRAC * r["n"] or \
                    sum(off.histogram()[255:]) > 0.35 * area:
                PRINT_ISSUES.append((CURRENT_CARD[0], "covered", snippet, r["box"]))
    img.save(dest)


def audit_report(issues=None):
    """Human-readable lines, one per card, for the print-audit findings."""
    by = {}
    for cid, kind, text, box in (PRINT_ISSUES if issues is None else issues):
        by.setdefault(cid, []).append("{} {!r}@{},{}".format(
            kind, text[:28], box[0], box[1]))
    return ["{}: {}".format(cid, "; ".join(v[:6]) + (" (+{})".format(len(v) - 6)
                                                    if len(v) > 6 else ""))
            for cid, v in sorted(by.items())]


def _box_block(d, text, box, fill=PSD_INK, start=30, min_size=15,
               italic=False, leading=1.24, bold=False, key=None):
    """Wrapped [markup] text fitted into a box (shrinks until it fits).

    `key` names the editable area; a per-area typography override (font/size/
    bold/italic) applies here just like on single-line fields."""
    if not text:
        return box[1]
    st = _field_style(key)
    box = _nudge(box, st)
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
    fits = False
    for size in range(start, min_size - 1, -1):
        n = len(wrap_runs(d, text, size, bw, italic=italic, bold=bold,
                          font_file=font_file))
        if _wrapped_height(text, size, n, leading) <= box[3] - box[1]:
            fits = True
            break
    if not fits:
        OVERFLOWS.append((CURRENT_CARD[0], key or "text", size))
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
        gpad = int(size * GLYPH_PAD_FRAC)
        pgap = int(lh * PARA_GAP_FRAC)
        y = top
        placed = []
        fits = True
        paras = text.split("\n")
        for pi, para in enumerate(paras):
            if pi:
                y += pgap   # breathing room between abilities
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
                pl = d.textlength(piece, font=font) + (gpad if is_g else 0)
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
            if y + lh > bottom and pi != len(paras) - 1:
                fits = False
        return placed, y, fits

    placed, endy = None, top
    size = start
    for size in range(start, min_size - 1, -1):
        placed, endy, fits = layout(size)
        if fits:
            break
    if not fits:
        OVERFLOWS.append((CURRENT_CARD[0], "text", size))
    # centre inline icons vertically on the text line, like the official cards
    tasc, _ = _font(size, italic=italic).getmetrics()
    gmid = int(tasc * 0.60)
    gpad = int(size * GLYPH_PAD_FRAC)
    with _audit_role("body"):
        _draw_placed(d, placed, gmid, gpad, fill)
    return endy


def _draw_placed(d, placed, gmid, gpad, fill):
    for ly, lx, line in placed:
        cx = lx
        for is_g, piece, font in line:
            if is_g:
                d.text((cx, ly + gmid), piece, font=font, fill=fill, anchor="lm")
                cx += d.textlength(piece, font=font) + gpad
            else:
                d.text((cx, ly), piece, font=font, fill=fill)
                cx += d.textlength(piece, font=font)


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
               fill=(84, 66, 50), italic=True, start=FLAVOR_PX, key="flavor")
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
    _box_block(d, pt.get("text", ""), (40, e2[1], 693, e1[3] + 70), start=BODY_PX, key="text")
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
    _box_block(d, pt.get("text", ""), (52, e2[1], 681, 878), start=BODY_PX, key="text")
    p = R["Plot Text"]
    _box_block(d, pt.get("flavor", ""), (p[0], p[1], p[2], 992),
               fill=(84, 66, 50), italic=True, start=FLAVOR_PX, key="flavor")
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
    if v is not None and 1 <= v <= 9:
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
# the shroud/clue text regions sit above the template's printed discs, so the
# numeral reads high; drop it to sit centred in the disc
DISC_NUM_DY = 12


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


LEVEL_PIP_PATH = os.path.join(ROOT, "assets", "xp", "level_pip.png")


def _level_pip():
    """The official white XP pip (source-extracted, assets/xp/level_pip.png),
    cached. None if the asset isn't present."""
    if "level_pip" not in _SE_CACHE:
        _SE_CACHE["level_pip"] = (Image.open(LEVEL_PIP_PATH).convert("RGBA")
                                  if os.path.exists(LEVEL_PIP_PATH) else None)
    return _SE_CACHE["level_pip"]


# the five printed XP notches on the cost disc, measured off the frame as
# fractions of the Cost box (width w, from box centre-x and box top). The arc is
# wide and deep: outer notches high on the sides, centre notch lowest.
_NOTCH_XO = (-0.488, -0.294, 0.0, 0.294, 0.488)   # x offset from centre / w
_NOTCH_YF = (0.750, 0.955, 1.025, 0.955, 0.750)   # y below box top / w
# the skill "cup" prints a tighter, shallower notch arc than the cost disc
_SKILL_NOTCH_XO = (-0.370, -0.245, 0.0, 0.245, 0.370)
_SKILL_NOTCH_YF = (0.153, 0.265, 0.353, 0.265, 0.153)


def _notch_centers(box, xo=_NOTCH_XO, yf=_NOTCH_YF):
    """The five printed XP-notch centres, derived from the region box so they
    track it if the frame moves."""
    w = box[2] - box[0]
    cx = (box[0] + box[2]) / 2.0
    return [(cx + xo[i] * w, box[1] + yf[i] * w) for i in range(5)]


def _fill_level_notches(img, box, level, centers=None, width_frac=0.135):
    """Stamp the official white pip into the first `level` printed notches — the
    empty notch meter is part of the frame, so filling it this way matches a
    printed card. `centers` overrides the default cost-disc arc (e.g. for the
    skill cup)."""
    n = pip_count(level)
    pip = _level_pip()
    if n <= 0 or pip is None:
        return
    tw = max(1, int((box[2] - box[0]) * width_frac))
    th = max(1, round(pip.height * tw / pip.width))
    p = pip.resize((tw, th), Image.LANCZOS)
    for x, y in (centers or _notch_centers(box))[:n]:
        img.paste(p, (int(round(x - tw / 2)), int(round(y - th / 2))), p)


def s_player_card(kind, c, pt, dest, art_path=None, placement=None):
    """Asset / Event / Skill on the plugin's authentic per-class frame."""
    letter = "W" if c.get("weakness") else CLASS_LETTER.get(c.get("class"), "N")
    frame = _se_img("templates", "AHLCG-{}-{}".format(kind, letter)) \
        or _se_img("templates", "AHLCG-{}-N".format(kind))
    W, H = 375 * SE_SCALE, 525 * SE_SCALE
    frame2 = frame.resize((W, H), Image.LANCZOS)
    clip = se_reg(kind, "Portrait-portrait-clip")
    if BLANK:
        # no art: parchment background + frame, so the editor shows the empty
        # window behind the live art
        img = Image.new("RGB", (W, H), frame_underlay(frame))
        img.paste(frame2, (0, 0), frame2)
    elif FURNITURE:
        # furniture-only: frame (player frames are windowed) on a transparent
        # window; the text/icons drawn below land on top of it
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.paste(frame2, (0, 0), frame2)
    else:
        img = Image.new("RGB", (W, H), frame_underlay(frame))
        if art_path:
            paste_cover(img, art_path, clip, placement)
        img.paste(frame2, (0, 0), frame2)
    d = _Draw(img)
    _register_frame(img, "{}-{}".format(kind, letter), frame2)

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
                  fill=(238, 232, 216), title=True, grow=0.95, pos_key="cost")
    # XP level: fill the frame's printed notch meter with the official white pip,
    # left-to-right, on the exact measured notch centres
    if c.get("level"):
        if kind in ("Asset", "Event"):
            _fill_level_notches(img, se_reg(kind, "Cost"), c["level"])
        elif kind == "Skill":
            cup = se_reg("Skill", "Level")
            cen = _notch_centers(cup, _SKILL_NOTCH_XO, _SKILL_NOTCH_YF)
            _fill_level_notches(img, cup, c["level"], centers=cen, width_frac=0.10)

    _box_text(d, c["name"], se_reg(kind, "Name", letter), title=True, grow=1.15, key="name")
    if c.get("subtitle"):
        # the subtitle sits on a slim band just under the title; cap its size and
        # width so it can't grow to title height and bleed up over the name (only
        # Asset frames carry a subtitle band — Events/Skills return no region)
        sub_box = (se_reg(kind, "SubtitleText", letter)
                   or se_reg(kind, "Subtitle", letter))
        if sub_box:
            _box_text(d, c["subtitle"], sub_box, italic=True,
                      max_size=22, max_w_factor=1.0, key="subtitle")

    # body: traits line, rules, flavor — stacked inside the Body region
    b = se_reg(kind, "Body")
    if kind == "Skill":
        # the plugin's Skill body region runs under the frame's left border
        b = (b[0] + 26, b[1], b[2] - 8, b[3])
    y = b[1]
    if c.get("traits"):
        _box_text(d, c["traits"], (b[0], y, b[2], y + 30),
                  bold=True, italic=True, max_size=24, key="traits")
        y += 36
    # rules + flavour flow through the frame's visible parchment, which ends
    # at the frame's lower ornament (an Event's box curves in at its corners);
    # they step around the slot icon and soak chits pasted below
    obstacles = []
    if kind == "Asset" and c.get("slot") in SLOT_OVERLAY:
        obstacles.append(_grow(se_reg(kind, "Slot"), 6))
    if kind == "Asset":
        for region, fld, val in (("Stamina", "health", c.get("health")),
                                 ("Sanity", "sanity", c.get("sanity"))):
            if _soak_val(val):
                reg = _nudge(se_reg(kind, region), _field_style(fld))
                cx, cy = (reg[0] + reg[2]) // 2, (reg[1] + reg[3]) // 2
                obstacles.append((cx - 52, cy - 54, cx + 52, cy + 54))
    foot = se_reg(kind, "Artist") or (0, H - 30, 0, H)
    # (a Skill's parchment runs further right than its plugin region; the
    # layout keeps the margin to the frame either way)
    bx1 = b[2] + 40 if kind == "Skill" else b[2]
    y = _flow_body(d, (b[0], y, bx1, foot[1] - 10), pt.get("text", ""),
                   pt.get("flavor", ""), obstacles=obstacles)
    if c.get("victory"):
        _box_text(d, "Victory {}.".format(c["victory"]),
                  (b[0], y + 2, b[2], y + 30), bold=True, max_size=22, key="victory")

    if kind == "Asset" and c.get("slot") in SLOT_OVERLAY:
        _paste_region(img, _se_img("overlays", "AHLCG-" + SLOT_OVERLAY[c["slot"]]),
                      se_reg(kind, "Slot"))
    if kind == "Asset":
        # health/sanity are the soak an ally or device absorbs — draw them as the
        # official red-heart / blue-brain chits (the same kit investigators use),
        # numeral baked on, exactly like Guard Dog. A plain item has no soak, so
        # nothing is drawn at all.
        for ck, region, fld, val in (
                ("health_heart", "Stamina", "health", c.get("health")),
                ("sanity_brain", "Sanity", "sanity", c.get("sanity"))):
            if not _soak_val(val):
                continue
            reg = _nudge(se_reg(kind, region), _field_style(fld))
            cx = (reg[0] + reg[2]) // 2
            cy = (reg[1] + reg[3]) // 2
            chit, numbered = _vital_chit(ck, val)
            if chit is not None:
                _paste_icon_fit(img, chit, (cx - 44, cy - 46, cx + 44, cy + 46))
            else:
                # only reachable if a chit file is missing from the kit
                _box_text(d, str(int(val)), reg, fill=(250, 244, 238),
                          stat=True, grow=0.9, pos_key=fld)

    if kind == "Asset" and c.get("encounter_set"):
        # a story asset: its scenario's set symbol (top right); its set
        # number prints in the footer
        _encounter_mark(img, d, "AssetStory", c)
    _card_footer(img, d, kind, c, art_path)
    _finish(img, dest)


def _has_art_window(frame, clip):
    """True when the frame's art window is see-through (art goes UNDER it).
    Judged inside the clip rect: some opaque frames (Rogue, Mystic) carry a few
    transparent pixels elsewhere, and a whole-frame test pasted their art under
    a solid window, hiding it behind the class emblem."""
    alpha = frame.getchannel("A")
    if not clip:
        return alpha.getextrema()[0] < 250
    hist = alpha.crop(tuple(int(v) for v in clip)).histogram()
    return sum(hist[:250]) > 0.1 * sum(hist)


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
    windowed = _has_art_window(frame2, clip)
    # the frame as text layout / the print audit see it: on an opaque frame
    # the art is pasted OVER the clip rect, so that window is not frame
    if windowed or not clip:
        lay_name, lay_frame = tpl_name, frame2
    else:
        lay_name, lay_frame = tpl_name + "#" + clip_key, frame2.copy()
        lay_frame.paste((0, 0, 0, 0), tuple(int(v) for v in clip))

    def done(img):
        _register_frame(img, lay_name, lay_frame)
        return img, _Draw(img)
    if BLANK:
        # the card with no art: keep the background the frame provides so the
        # editor can show the class colour behind the live art
        if windowed:
            img = Image.new("RGB", (W, H), underlay or frame_underlay(frame))
            img.paste(frame2, (0, 0), frame2)
        else:
            img = frame2.convert("RGB")
            if underlay and clip:
                ImageDraw.Draw(img).rectangle(list(clip), fill=underlay)
        return done(img)
    if FURNITURE:
        # The frame (plus the text/discs the caller draws next) on a TRANSPARENT
        # art window, so the live editor can lay real art behind it. A windowed
        # frame already has its window cut; an opaque frame is solid, so punch a
        # hole at the art clip rect — that is exactly where the finished card
        # pastes the art over the frame.
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.paste(frame2, (0, 0), frame2)
        if not windowed and clip:
            img.paste(Image.new("RGBA", (clip[2] - clip[0], clip[3] - clip[1]),
                                (0, 0, 0, 0)), (clip[0], clip[1]))
        return done(img)
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
    return done(img)


# ------------------------------------------------- shaped body layout --
# Rules text is laid out line by line inside the frame's VISIBLE parchment:
# each line gets the clear run of parchment (through the box's middle) across the rows it
# occupies (minus LAYOUT_MARGIN), so text follows an enemy's arched text
# circle, stops above an asset's bottom ornament, and steps around an act's
# clue circle, a slot icon or a Victory line — the frame itself is the
# measure, not a rectangle that runs under the ornament.
LAYOUT_MARGIN = 10          # px of clear parchment kept between ink and frame
LAYOUT_LIGHT = 150          # parchment for layout is at least this light (the
                            # audit tolerates down to 120: shaded edges)
BODY_LEADING = 1.15         # official cards set rules tight (~1.15)
BODY_PARA_GAP = 0.33        # gap between abilities, as a share of a line
FLAVOR_INK = (84, 66, 50)
FLAVOR_KEEP_PX = 24         # below this, a dense card drops its flavour text
FLAVOR_DROPPED = []         # card ids whose flavour did not fit
BODY_SIZES = {}             # card id -> [rules px of each body block drawn]


def _canvas_frame(d):
    img = getattr(d, "_image", None)
    return _CANVAS_FRAMES.get(id(img)) if img is not None else None


def _span_fn(d, box, obstacles=()):
    """span(y, h) -> (x_left, x_right) of the clear run of visible parchment
    through the middle of `box`, over rows y..y+h, or None."""
    fr = _canvas_frame(d)
    mask = _safe_mask(fr[0], fr[1], LAYOUT_MARGIN, LAYOUT_LIGHT)[1] if fr else None
    x0, x1 = int(box[0]), int(box[2])
    cache = {}

    def span(y, h):
        key = (int(y), int(h))
        if key in cache:
            return cache[key]
        y, h = key
        w = x1 - x0
        if mask is not None and h > 0 and w > 0:
            band = mask.crop((x0, y, x1, y + h))
            ok = [v == 255 for v in band.resize((w, 1), Image.BOX).tobytes()]
        else:
            ok = [True] * max(0, w)
        for ob in obstacles:
            if ob[1] < y + h and ob[3] > y:
                for x in range(max(x0, int(ob[0])), min(x1, int(ob[2]))):
                    ok[x - x0] = False
        # the clear run through the box's centre: text never jumps to a
        # far side of the box because an ornament rises in its middle
        mid = w // 2
        res = None
        if 0 <= mid < len(ok) and ok[mid]:
            a = mid
            while a > 0 and ok[a - 1]:
                a -= 1
            e = mid
            while e < len(ok) and ok[e]:
                e += 1
            res = (x0 + a, x0 + e)
        cache[key] = res
        return res
    return span


def _words(paragraph):
    """[(kind, word, glued)] for one paragraph: kind False = body face, None =
    bold trigger lead, True = glyph, ARROW = fallback face for the arrow;
    `glued` = no space before it (a glyph's "." or "+1" before a glyph), so a
    line never breaks there and strands the punctuation."""
    paragraph, nkey = _trigger_lead(paragraph)
    words = []
    prev_tail_space = True
    for is_glyph, chunk in glyphify(paragraph):
        if is_glyph:
            words.append((True, chunk, bool(words) and not prev_tail_space))
            prev_tail_space = False
        else:
            parts = chunk.split(" ")
            for i, w in enumerate(parts):
                if w != "":
                    words.append((False, w, i == 0 and bool(words)
                                  and not prev_tail_space))
            prev_tail_space = chunk.endswith(" ") or not chunk
    for i in range(min(nkey, len(words))):
        if words[i][0] is False:
            words[i] = (None,) + words[i][1:]
    return [(ARROW,) + t[1:] if t[0] is False and ARROW in t[1] else t
            for t in words]


def _fonts(size, italic=False, bold=False, font_file=None):
    return {False: _font(size, italic=italic, bold=bold, font_file=font_file),
            None: _font(size, italic=italic, bold=True, font_file=font_file),
            True: _font(size, glyph=True), ARROW: _arrow_font(size)}


def _shape(d, text, size, top, bottom, span, italic=False, bold=False,
           font_file=None, leading=BODY_LEADING, min_w=0):
    """Lay `text` out from y=top, every line in span(); -> (lines, next_y,
    fits) with lines = [(y, x, runs)]."""
    fonts = _fonts(size, italic, bold, font_file)
    lh = int(size * leading)
    pgap = int(lh * BODY_PARA_GAP)
    gpad = int(size * GLYPH_PAD_FRAC)
    asc, desc = fonts[False].getmetrics()
    ink_top = int(size * 0.18)                  # cap height starts about here
    ink_h = max(1, int(asc + desc * 0.7) - ink_top)
    state = {"y": top, "fits": True, "x": None}

    def place():
        y = state["y"]
        s = span(y + ink_top, ink_h)
        if s is None or s[1] - s[0] < min_w or y + ink_top + ink_h > bottom:
            state["fits"] = False
            return s if s and s[1] > s[0] else (span(top, 1) or (0, 1))
        # keep the left edge aligned: where the parchment only widens by a few
        # px (texture at a torn edge) stay on the previous line's edge rather
        # than wobble; a real step in the frame (the enemy arch) still shows
        px = state["x"]
        if px is None:
            # first line: look a few lines ahead and start on the edge they
            # will need if it is only a few px in
            for k in (1, 2, 3):
                nxt = span(y + k * lh + ink_top, ink_h)
                if nxt and s[0] < nxt[0] <= s[0] + 12 and s[1] - nxt[0] >= min_w:
                    px = max(px or 0, nxt[0])
        if px is not None and s[0] < px <= s[0] + 12 and s[1] - px >= min_w:
            s = (px, s[1])
        state["x"] = s[0]
        return s
    out = []
    for pn, paragraph in enumerate(_abilities(text).split("\n")):
        if pn:
            state["y"] += pgap
        s = place()
        line, width = [], 0.0
        toks = _words(paragraph)
        lens = []
        for kind, w, _g in toks:
            glyph = kind is True
            piece = w if glyph else w + " "
            lens.append((piece, d.textlength(piece, font=fonts[kind])
                         + (gpad if glyph else 0)))
        for i, (kind, w, glued) in enumerate(toks):
            piece, plen = lens[i]
            if not glued:
                # break before a word only together with what is glued to it
                group = plen
                j = i + 1
                while j < len(toks) and toks[j][2]:
                    group += lens[j][1]
                    j += 1
                if line and width + group > s[1] - s[0]:
                    out.append((state["y"], s[0], line))
                    state["y"] += lh
                    s = place()
                    line, width = [], 0.0
            line.append((kind, piece))
            width += plen
        out.append((state["y"], s[0], line or [(False, "")]))
        state["y"] += lh
    return out, state["y"], state["fits"]


def _draw_line(d, x, y, runs, size, fill, italic=False, bold=False,
               font_file=None):
    fonts = _fonts(size, italic, bold, font_file)
    tasc, _ = fonts[False].getmetrics()
    gmid = int(tasc * 0.60)
    gpad = int(size * GLYPH_PAD_FRAC)
    cx = x
    for kind, piece in runs:
        f = fonts[kind]
        if kind == ARROW:
            d.text((cx, y + tasc), piece, font=f, fill=fill, anchor="ls")
            cx += d.textlength(piece, font=f)
        elif kind is True:
            d.text((cx, y + gmid), piece, font=f, fill=fill, anchor="lm")
            cx += d.textlength(piece, font=f) + gpad
        else:
            d.text((cx, y), piece, font=f, fill=fill)
            cx += d.textlength(piece, font=f)


def _flow_body(d, box, text, flavor="", start=BODY_PX, min_size=14,
               obstacles=(), story_first=False, drop_flavor=True, key="text",
               fill=PSD_INK, min_w_frac=0.42):
    """Rules (+ flavour) in the visible parchment of `box`, at the largest
    size where everything fits. Official cards drop the flavour of a dense
    card rather than shrink its rules, so below FLAVOR_KEEP_PX the flavour
    goes. `story_first`: agenda/act fronts, story in italics above the rules
    at one shared size (never dropped). Returns the y below the last line."""
    text, flavor = text or "", flavor or ""
    if not (text or flavor):
        return box[1]
    st = _field_style(key)
    box = _nudge(box, st)
    font_file = (st or {}).get("font") or None
    if st and st.get("size"):
        start = max(min_size, int(round(start * float(st["size"]))))
    span = _span_fn(d, box, obstacles)
    min_w = int((box[2] - box[0]) * min_w_frac)

    def attempt(size, with_flavor):
        fs = size if story_first else min(size, FLAVOR_PX)
        seq = [(flavor, True), (text, False)] if story_first \
            else [(text, False), (flavor, True)]
        y, ok, parts = box[1], True, []
        for t, it in seq:
            if not t or (it and not with_flavor):
                continue
            if parts:
                y += int(size * (0.30 if story_first else 0.42))
            sz = fs if it else size
            lines, y, f = _shape(d, t, sz, y, box[3], span, italic=it,
                                 font_file=font_file, min_w=min_w)
            ok = ok and f
            parts.append((lines, sz, it))
        return ok, parts, y

    def best(with_flavor):
        for size in range(start, min_size - 1, -1):
            ok, parts, y = attempt(size, with_flavor)
            if ok:
                return size, parts, y
        return None, None, None
    size, parts, y = best(True)
    if flavor and text and drop_flavor and not story_first \
            and (size is None or size < FLAVOR_KEEP_PX):
        s2, p2, y2 = best(False)
        if s2 is not None and (size is None or s2 > size):
            FLAVOR_DROPPED.append(CURRENT_CARD[0])
            size, parts, y = s2, p2, y2
    if size is None:
        OVERFLOWS.append((CURRENT_CARD[0], key, min_size))
        size = min_size
        _, parts, y = attempt(size, True)
    BODY_SIZES.setdefault(CURRENT_CARD[0], []).append(size)
    with _audit_role("body"):
        for lines, sz, it in parts:
            for ly, lx, runs in lines:
                _draw_line(d, lx, ly, runs, sz, FLAVOR_INK if it else fill,
                           italic=it, font_file=font_file)
    return y


def _grow(box, px):
    return (box[0] - px, box[1] - px, box[2] + px, box[3] + px)


def _se_body(d, c, pt, kind, letter="", extra_bottom=26, text_start=BODY_PX,
             victory=True, box=None, obstacles=()):
    """Traits + rules + flavor (+ Victory) in the Body region, the rules and
    flavour flowed through the frame's visible parchment (_flow_body). Pass
    victory=False when the card places its Victory line at a fixed spot (enemies
    print it centred just above the damage/horror row, not after the text)."""
    b = box or se_reg(kind, "Body", letter)
    y = b[1]
    if c.get("traits"):
        traits = c["traits"] + ("  Elite." if c.get("elite")
                                and "Elite" not in c["traits"] else "")
        _box_text(d, traits, (b[0], y, b[2], y + 36),
                  bold=True, italic=True, max_size=BODY_PX, key="traits")
        y += 40
    y = _flow_body(d, (b[0], y, b[2], b[3] + extra_bottom), pt.get("text", ""),
                   pt.get("flavor", ""), start=text_start, obstacles=obstacles)
    if victory and c.get("victory"):
        _box_text(d, "Victory {}.".format(c["victory"]),
                  (b[0], y + 2, b[2], y + 30), bold=True, max_size=22,
                  key="victory")
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
                  stat=True, grow=1.0, pos_key=stat)
    # the text box ends above the health/sanity chits (their tops sit about
    # 62 px above their centres) and keeps a margin inside the parchment's
    # right edge, so no line runs under a chit or off the border
    VITAL_GAP = 14
    VITAL_RISE = 12
    b = se_reg("Investigator", "Body")
    st_ = se_reg("Investigator", "Stamina")
    chit_top = (st_[1] + st_[3]) // 2 - VITAL_RISE - 62
    _se_body(d, c, pt, "Investigator", extra_bottom=0,
             box=(b[0], b[1], b[2], min(b[3], chit_top - 8)))
    # health (red heart) + sanity (blue brain) chits from the official stat kit
    # — the plugin's own SanityBase is corrupt, so these are the clean source.
    # Push them apart (health left, sanity right) so the two big chits get a
    # small gap between them instead of hugging, and lift them a touch off the
    # bottom border, like the reference cards.
    for kind, key, fld, val, off in (
            ("health_heart", "Stamina", "health", c.get("health"), -VITAL_GAP),
            ("sanity_brain", "Sanity", "sanity", c.get("sanity"), VITAL_GAP)):
        reg = _nudge(se_reg("Investigator", key), _field_style(fld))
        cx = (reg[0] + reg[2]) // 2 + off
        cy = (reg[1] + reg[3]) // 2 - VITAL_RISE
        hw, hh = (reg[2] - reg[0]) // 2, (reg[3] - reg[1]) // 2
        box = (cx - hw, cy - hh, cx + hw, cy + hh)   # numeral follows the chit
        chit, numbered = _vital_chit(kind, val)
        if chit is not None:
            _paste_icon_fit(img, chit, (cx - 58, cy - 62, cx + 58, cy + 62))
        else:
            # only reachable if a chit file is missing from the kit
            _box_text(d, str(val), box, fill=(240, 240, 240), stat=True, grow=0.9)
    _card_footer(img, d, "Investigator", c, art_path)
    _finish(img, dest)


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
    # the frame's brass cartridge hangs below the portrait: keep text clear of it
    ob = (portrait[0], portrait[1], portrait[2], portrait[3] + 118)
    paras = [(line, "label") for line in pt.get("back_text", "").split("\n") if line.strip()]
    if pt.get("back_flavor"):
        paras.append((pt["back_flavor"], "story"))
    # inset from the parchment's torn right edge and darkened lower-left
    # corner, which the plugin's Body region runs onto
    _flow_rich(d, paras, (b[0] + 8, b[1], b[2] - 22, b[3] - 30), ob, start=BODY_PX)
    _finish(img, dest)


def _flow_rich(d, paras, box, obstacle, start=22, min_size=13, leading=1.24, gap=18):
    """Investigator-back text, official layout: each deckbuilding line opens
    with its label in bold ("Deck Size:"), then the story paragraph in italics.
    Beside the portrait (and the cartridge under it) lines start right of it;
    below, they run full width. Shrinks everything together until it fits."""
    left, top, right, bottom = box
    ob_r, ob_b = obstacle[2] + gap, obstacle[3]

    def avail(y, lh):
        lx = ob_r if y + lh > obstacle[1] and y < ob_b else left
        return lx, right - lx

    def words_of(text, kind):
        out = []
        if kind == "label" and ":" in text:
            head, tail = text.split(":", 1)
            out += [("b", w) for w in (head + ":").split(" ") if w]
            text = tail
        style = "i" if kind == "story" else "r"
        out += [(style, w) for w in text.split(" ") if w]
        return out

    def layout(size):
        fonts = {"r": _font(size), "b": _font(size, bold=True), "i": _font(size, italic=True)}
        lh = int(size * leading)
        pgap = int(lh * PARA_GAP_FRAC)
        y, placed, fits = top, [], True
        for pi, (text, kind) in enumerate(paras):
            if pi:
                y += pgap * (3 if kind == "story" else 1)
            if kind == "story":
                # the story runs full width under the portrait, as printed
                y = max(y, ob_b + 4)
            lx, aw = avail(y, lh)
            line, lw = [], 0.0
            for st, w in words_of(text, kind):
                piece = w + " "
                pl = d.textlength(piece, font=fonts[st])
                if line and lw + pl > aw:
                    placed.append((y, lx, line, kind))
                    y += lh
                    lx, aw = avail(y, lh)
                    line, lw = [], 0.0
                line.append((piece, fonts[st]))
                lw += pl
            placed.append((y, lx, line, kind))
            y += lh
            if y > bottom:
                fits = False
        return placed, fits

    for size in range(start, min_size - 1, -1):
        placed, fits = layout(size)
        if fits:
            break
    if not fits:
        OVERFLOWS.append((CURRENT_CARD[0], "back_text", size))
    with _audit_role("body"):
        for ly, lx, line, kind in placed:
            cx = lx
            fill = (84, 66, 50) if kind == "story" else PSD_INK
            for piece, font in line:
                d.text((cx, ly), piece, font=font, fill=fill)
                cx += d.textlength(piece, font=font)


# ------------------------------------------------------------ footers --
# One credit line for every card type, laid out as official cards print it:
# "Illus. <artist>" at the left, "© <publisher>" in the copyright slot, then
# at the right the encounter-set number ("4/18", scenario cards only), the
# collection symbol and the card's collector number. Bold, in light type on a
# dark strip or over art (dark type where the frame's footer is parchment,
# as on story cards), sized together so nothing collides.
FOOT_LIGHT = (238, 234, 226)
FOOT_DARK = (52, 40, 30)
FOOT_STROKE = (22, 18, 14)
FOOT_PX = 18
COLLECTION_NUMBERS = {}     # card id -> collector number (main(): campaign order)


def collection_symbol():
    """The campaign's collection symbol (build.json "collection_symbol", else
    its default encounter symbol): printed beside every collector number."""
    syms = CFG.get("encounter_symbols") or {}
    return CFG.get("collection_symbol") or syms.get("_default")


def collection_numbers(cards):
    """{card id: n}: investigators, then player cards, then the scenario
    cards set by set in encounter-number order, as an official box is
    numbered. Only the campaign's own specs are numbered."""
    own, order = set(), {}
    for sp in (CFG.path("specs") or []):
        try:
            for c in json.load(open(sp, encoding="utf-8")):
                if c.get("id") and c["id"] not in order:
                    order[c["id"]] = len(order)
                    own.add(c["id"])
        except (ValueError, OSError):
            continue
    set_rank = {}
    for cid, (sid, _num) in ENC_MARKS.items():
        set_rank.setdefault(sid, len(set_rank))

    def first(num):
        try:
            return int(str(num).split("/")[0].replace("–", "-").split("-")[0])
        except ValueError:
            return 0

    def key(c):
        cid = c["id"]
        if c.get("type") == "Investigator":
            return (0, 0, 0, order[cid])
        if cid in ENC_MARKS:
            sid, num = ENC_MARKS[cid]
            return (2, set_rank[sid], first(num), order[cid])
        if c.get("type") in ("Asset", "Event", "Skill") \
                and not c.get("encounter_set"):
            return (1, 0, 0, order[cid])
        return (3, 0, 0, order[cid])
    mine = sorted((c for c in cards if c.get("id") in own), key=key)
    return {c["id"]: i + 1 for i, c in enumerate(mine)}


def _foot_box_text(img, d, text, x, band, size, align="left"):
    """Draw one footer item at x (left edge, or right edge for align right)
    in the band; the colour follows what is under it. -> (x0, x1)."""
    f = _font(size, bold=True)
    w = d.textlength(text, font=f)
    x0 = x - w if align == "right" else x
    probe = img.crop((int(x0), int(band[1]), int(x0 + w) + 1, int(band[3])))
    lum = ImageStat.Stat(probe.convert("L")).mean[0] if probe.size[0] else 0
    light = lum < 140
    bb = f.getbbox(text)
    y = (band[1] + band[3]) / 2 - (bb[1] + bb[3]) / 2
    if light:
        d.text((x0, y), text, font=f, fill=FOOT_LIGHT, stroke_width=1,
               stroke_fill=FOOT_STROKE)
    else:
        d.text((x0, y), text, font=f, fill=FOOT_DARK)
    return x0, x0 + w


def _card_footer(img, d, kind, c, art_path=None, numbers=True):
    """The official credit line for one face (see the section note)."""
    cp = se_reg(kind, "Copyright")
    art = se_reg(kind, "Artist")
    en = se_reg(kind, "EncounterNumber")
    cn = se_reg(kind, "CollectionNumber")
    if not cp:
        return
    band = (0, cp[1] - 4, 0, cp[3] + 4)
    left = art[0] if art and abs(art[1] - cp[1]) <= 8 else cp[0]
    right = cn[2] if cn else (en[2] if en else cp[2])
    illus = ("Illus. " + WATERMARK) if art_path else ""
    copy = ("© " + WATERMARK) if art_path else ""
    enc = str(c.get("number") or "") if numbers and c.get("encounter_set") else ""
    coll = str(COLLECTION_NUMBERS.get(c.get("id"), "")) if numbers else ""
    icon = None
    if coll and collection_symbol():
        import encounter_sets
        path = encounter_sets.icon_path(collection_symbol())
        if path:
            icon = Image.open(path).convert("RGBA")
    ih = band[3] - band[1] + 2
    for size in range(FOOT_PX, 11, -1):
        f = _font(size, bold=True)
        tl = lambda t: d.textlength(t, font=f) if t else 0   # noqa: E731
        x = right - tl(coll)
        icon_x = x - (ih + 6) if icon is not None else x
        enc_x1 = icon_x - (16 if (coll or icon is not None) else 0)
        enc_x0 = enc_x1 - tl(enc)
        ill_x1 = left + tl(illus)
        # © centred on its own slot, kept clear of its neighbours
        cw = tl(copy)
        cx0 = (cp[0] + cp[2]) / 2 - cw / 2
        lo = ill_x1 + (18 if illus else 0)
        hi = (enc_x0 if enc else icon_x if (coll or icon is not None) else right) - 18
        cx0 = max(lo, min(cx0, hi - cw))
        if cx0 >= lo - 0.5 and cx0 + cw <= hi + 0.5 and enc_x0 >= ill_x1 + 12:
            break
    if illus:
        _foot_box_text(img, d, illus, left, band, size)
    if copy:
        _foot_box_text(img, d, copy, cx0, band, size)
    if enc:
        _foot_box_text(img, d, enc, enc_x1, band, size, align="right")
    color = None
    if coll:
        _foot_box_text(img, d, coll, right, band, size, align="right")
        probe = img.crop((int(icon_x), int(band[1]), int(icon_x + ih), int(band[3])))
        color = FOOT_LIGHT if ImageStat.Stat(probe.convert("L")).mean[0] < 140 \
            else FOOT_DARK
    if icon is not None and color is not None:
        tint = Image.new("RGBA", icon.size, color + (255,))
        tint.putalpha(icon.getchannel("A"))
        cy = (band[1] + band[3]) // 2
        _paste_icon_fit(img, tint, (int(icon_x), cy - ih // 2,
                                    int(icon_x) + ih, cy + ih // 2))


def _encounter_mark(img, d, kind, c, number=True):
    """The encounter-set symbol in the frame's set slot, as official scenario
    cards print it (pipeline/encounter_sets.py decides it; no drawing, no
    symbol). The encounter number ("4/18") prints in the footer
    (_card_footer); `number` is kept for callers."""
    sid = c.get("encounter_set")
    if sid:
        import encounter_sets
        path = encounter_sets.icon_path(sid)
        box = se_reg(kind, "Encounter-portrait-clip")
        if path and box:
            icon = Image.open(path).convert("RGBA")
            w, h = box[2] - box[0], box[3] - box[1]
            pad = int(min(w, h) * 0.12)
            if kind in ("Location", "LocationBack"):
                # the location frame prints no disc for the symbol: a small
                # parchment one, as official locations show, so it reads on art
                g = int(min(w, h) * 0.10)
                d.ellipse([box[0] - g, box[1] - g, box[2] + g, box[3] + g],
                          fill=(236, 226, 204), outline=(74, 60, 46), width=max(2, g // 2))
                pad = int(min(w, h) * 0.16)
            _paste_icon_fit(img, icon, (box[0] + pad, box[1] + pad, box[2] - pad, box[3] - pad))


def s_enemy(c, pt, dest, art_path=None, placement=None):
    tpl = "AHLCG-WeaknessEnemy" if c.get("weakness") else "AHLCG-Enemy"
    img, d = _se_frame_compose(tpl, "Enemy", "Portrait-portrait-clip",
                               art_path, placement)
    nb = se_reg("Enemy", "Name")
    if c.get("subtitle"):
        # no subtitle banner in the frame kit: name and subtitle share the title
        # banner (as on official unique enemies), clear of the stat row
        _box_text(d, c["name"], (nb[0], nb[1] - 4, nb[2], nb[1] + 38), title=True, grow=1.0, key="name")
        _box_text(d, c["subtitle"], (nb[0] + 30, nb[1] + 38, nb[2] - 30, nb[3] + 2),
                  italic=True, max_size=20, max_w_factor=1.0, key="subtitle")
    else:
        _box_text(d, c["name"], nb, title=True, grow=1.15, key="name")
    for key, fld, val in (("Attack", "fight", pt.get("fight")),
                          ("Health", "health", pt.get("health")),
                          ("Evade", "evade", pt.get("evade"))):
        blank = val in (None, "", "None")     # Bolton has no em dash
        _box_text(d, "—" if blank else str(val),
                  se_reg("Enemy", key), stat=not blank, bold=blank, grow=1.0,
                  fill=(238, 232, 216), pos_key=fld)
    _box_text(d, "ENEMY", se_reg("Enemy", "Label"), bold=True, max_size=15,
              fill=(74, 60, 46))
    # the text circle ends at the encounter-set ring at its foot; Victory
    # prints centred on the last line above that ring, as on official enemies
    b = se_reg("Enemy", "Body")
    ring = se_reg("Enemy", "ReturnEncounter-portrait-clip") or (0, b[3], 0, b[3])
    vic = None
    bottom = ring[1] - 4
    if c.get("victory"):
        vic = (b[0] + 150, ring[1] - 34, b[2] - 150, ring[1] - 6)
        bottom = vic[1] - 2
    _se_body(d, c, pt, "Enemy", extra_bottom=0, victory=False,
             box=(b[0], b[1], b[2], bottom))
    if vic:
        _box_text(d, "Victory {}.".format(c["victory"]), vic,
                  bold=True, max_size=22, key="victory")
    for kind_key, count, ov in (("Damage", pt.get("damage"), "AHLCG-Damage"),
                                ("Horror", pt.get("horror"), "AHLCG-Horror")):
        for i in range(pip_count(count)):
            _paste_region(img, _se_img("overlays", ov),
                          se_reg("Enemy", "{}{}".format(kind_key, i + 1)))
    _encounter_mark(img, d, "Enemy", c)
    _card_footer(img, d, "Enemy", c, art_path)
    _finish(img, dest)


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
    bk = kind if se_reg(kind, "Body") else "Treachery"
    b = se_reg(bk, "Body")
    foot = se_reg(kind, "Artist")
    # the parchment ends at the frame's lower ornament (the layout finds it);
    # never below the credit line
    _se_body(d, c, pt, bk, extra_bottom=0,
             box=(b[0], b[1], b[2], foot[1] - 12))
    _encounter_mark(img, d, kind, c)
    _card_footer(img, d, kind, c, art_path)
    _finish(img, dest)


def _scenario_body(d, kind, c, pt, traits=False, top=None, obstacles=()):
    """Rules/flavor block for a scenario-side card, flowed through the visible
    parchment of its Body region (_flow_body): an act's clue circle and the
    frame's torn edges shape the lines. Agenda/act fronts print the story in
    italics first and the rules below it, both at one size."""
    b = se_reg(kind, "Body")
    if not b:
        return
    y = top if top is not None else b[1]
    if traits and c.get("traits"):
        _box_text(d, c["traits"], (b[0], y, b[2], y + 36),
                  bold=True, italic=True, max_size=BODY_PX, key="traits")
        y += 40
    story_first = kind in ("Agenda", "Act")
    return _flow_body(d, (b[0], y, b[2], b[3]), pt.get("text", ""),
                      pt.get("flavor", ""), story_first=story_first,
                      drop_flavor=not story_first, obstacles=obstacles,
                      min_w_frac=0.30 if kind == "Act" else 0.42)


def s_location(c, pt, dest, art_path=None, placement=None):
    """A location, calibrated to the official layout (ref: Abyssal Trench / Sea
    Floor): name, art, a stat band of shroud (left) / "LOCATION" label (centre) /
    per-investigator clues (right), trait + rules + flavour, and a bottom row of
    coloured connection symbols. Shroud is print-only (not a TTS data field)."""
    back = bool(c.get("revealed"))
    kind = "LocationBack" if back else "Location"
    # the plugin names the unrevealed side's art window BackPortrait
    clip = "BackPortrait-portrait-clip" if back else "Portrait-portrait-clip"
    img, d = _se_frame_compose("AHLCG-" + kind, kind, clip, art_path, placement)
    nb = se_reg(kind, "Name")
    if c.get("subtitle"):
        # a location may carry a subtitle (distinct from its trait line). The
        # frame kit has no subtitle ribbon — its SubtitleText region falls on
        # the banner's tip and the art — so, as on official unique enemies,
        # name and subtitle share the light title banner
        # (the banner's light field ends at the double rule, ~y 60)
        _box_text(d, c["name"], (nb[0], nb[1] - 8, nb[2], nb[1] + 32),
                  title=True, grow=1.0, key="name")
        _box_text(d, c["subtitle"], (nb[0] + 40, nb[1] + 32, nb[2] - 40, nb[1] + 51),
                  italic=True, max_size=19, max_w_factor=1.0, key="subtitle")
    else:
        _box_text(d, c["name"], nb, title=True, grow=1.15, key="name")
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
            shn = (sh[0], sh[1] + DISC_NUM_DY, sh[2], sh[3] + DISC_NUM_DY)
            _box_text(d, str(c["shroud"]), shn, stat=True, grow=1.0,
                      max_size=int(dia * 0.52), fill=SHROUD_NUM, pos_key="shroud")
        if c.get("clues") not in (None, ""):
            base = se_reg("Location", "Clues")
            # a 0-clue location prints a plain 0 (no per-investigator mark)
            per_inv = bool(c.get("clues_per_investigator")) and str(c["clues"]) != "0"
            cx = (base[0] + base[2]) // 2
            cy = (base[1] + base[3]) // 2
            dia = base[2] - base[0]
            if per_inv:
                # number left of centre + a small per-investigator hat to its
                # upper-right, both inside the disc (ref: Rainy London Streets)
                nx = cx - int(dia * 0.14)
                _box_text(d, str(c["clues"]),
                          (nx - dia, cy - dia + DISC_NUM_DY, nx + dia, cy + dia + DISC_NUM_DY),
                          stat=True, grow=1.0, max_size=int(dia * 0.56),
                          fill=CLUE_INK, pos_key="clues")
                hat = _tint_icon(_se_img("icons", "AHLCG-PerInvestigator"),
                                 CLUE_INK)
                hcx, hcy = cx + int(dia * 0.24), cy - int(dia * 0.02)
                hw, hh = int(dia * 0.22), int(dia * 0.18)
                _paste_icon_fit(img, hat, (hcx - hw, hcy - hh,
                                           hcx + hw, hcy + hh))
            else:
                basen = (base[0], base[1] + DISC_NUM_DY, base[2], base[3] + DISC_NUM_DY)
                _box_text(d, str(c["clues"]), basen, stat=True, grow=1.0,
                          max_size=int(dia * 0.60), fill=CLUE_INK, pos_key="clues")
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
        _box_text(d, c["traits"], (b[0], y, b[2], y + 36),
                  bold=True, italic=True, max_size=BODY_PX, key="traits")
        y += 40
    obstacles = []
    if not back and c.get("victory"):
        # the rules step around the Victory line in the box's lower right
        vr = se_reg("Location", "Victory")
        vw = d.textlength("Victory {}.".format(c["victory"]), font=_font(20, bold=True))
        vcx, vcy = (vr[0] + vr[2]) / 2, (vr[1] + vr[3]) / 2
        obstacles.append((vcx - vw / 2 - 14, vcy - 22, vcx + vw / 2 + 14, vcy + 22))
    _flow_body(d, (b[0], y, b[2], b[3] + 30), pt.get("text", ""),
               pt.get("flavor", ""), obstacles=obstacles)
    _encounter_mark(img, d, kind, c)
    _card_footer(img, d, kind, c, art_path, numbers=not back)
    _finish(img, dest)



def _a_index(c):
    """'1a' from an index of 1 (official agenda/act fronts print the a side)."""
    idx = str(c.get("index", "")).strip()
    if idx and idx[-1:] not in ("a", "b"):
        idx += "a"
    return idx


def _hdr_box(kind):
    """The 'Act 1a' / 'Agenda 1a' line, centred above the set symbol as on
    official cards (the plugin's region is the left-aligned example text)."""
    r = se_reg(kind, "ScenarioIndex")
    clip = se_reg(kind, "Encounter-portrait-clip")
    cx = (clip[0] + clip[2]) // 2 if clip else (r[0] + r[2]) // 2
    half = max(r[2] - r[0], 220) // 2
    return (cx - half, r[1] - 6, cx + half, r[3] + 10)


def s_agenda(c, pt, dest, art_path=None, placement=None):
    """Agenda (the doom clock) - landscape, art LEFT + text RIGHT, "Agenda N"
    header top-right, doom on the frame, credit footer."""
    img, d = _se_frame_compose("AHLCG-Agenda", "Agenda", "Portrait-portrait-clip",
                               art_path, placement, landscape=True)
    hdr = ("Agenda " + _a_index(c)).strip()
    _box_text(d, hdr, _hdr_box("Agenda"), bold=True, max_size=28, fill=(58, 44, 32))
    _box_text(d, c["name"], se_reg("Agenda", "Name"), title=True, grow=1.0, max_size=46, key="name")
    if c.get("doom") not in (None, ""):
        db = se_reg("Agenda", "Doom")
        # sized to sit inside the doom circle, not spill over its rim
        _box_text(d, str(c["doom"]), db, stat=True, grow=1.0,
                  max_size=int((db[3] - db[1]) * 0.60),
                  fill=(238, 232, 216), pos_key="doom")
    _scenario_body(d, "Agenda", c, pt)
    _card_footer(img, d, "Agenda", c, art_path)
    _encounter_mark(img, d, "Agenda", c)
    _finish(img, dest)


def s_act(c, pt, dest, art_path=None, placement=None):
    """Act (the objective clock) - landscape, art RIGHT + text LEFT, "Act N"
    header top-left, clue threshold on the frame, credit footer."""
    img, d = _se_frame_compose("AHLCG-Act", "Act", "Portrait-portrait-clip",
                               art_path, placement, landscape=True)
    hdr = ("Act " + _a_index(c)).strip()
    _box_text(d, hdr, _hdr_box("Act"), bold=True, max_size=28, fill=(58, 44, 32))
    _box_text(d, c["name"], se_reg("Act", "Name"), title=True, grow=1.0, max_size=46, key="name")
    if c.get("take") or c.get("no_threshold"):
        # an objective with no clue threshold (a take-and-deliver act, or a
        # clue cost paid on the act's [action]): the circle prints a dash, as
        # official ones do
        cb = se_reg("Act", "Clues")
        cx, cy = (cb[0] + cb[2]) // 2, (cb[1] + cb[3]) // 2
        half = max(6, (cb[2] - cb[0]) // 5)
        d.line([(cx - half, cy), (cx + half, cy)], fill=(238, 232, 216),
               width=max(3, half // 3))
    elif c.get("clues") not in (None, ""):
        cb = se_reg("Act", "Clues")
        if c.get("clues_per_investigator") and cb:
            # a per-investigator threshold: numeral left of centre and the
            # plugin's own per-investigator mark beside it, as on locations
            w = cb[2] - cb[0]
            _box_text(d, str(c["clues"]), (cb[0] - w // 6, cb[1], cb[2] - w // 6, cb[3]),
                      stat=True, grow=1.0, max_size=int((cb[3] - cb[1]) * 0.5),
                      fill=(238, 232, 216), pos_key="clues")
            hat = _tint_icon(_se_img("icons", "AHLCG-PerInvestigator"), (238, 232, 216))
            cx, cy = cb[2] - int(w * 0.30), (cb[1] + cb[3]) // 2 - (cb[3] - cb[1]) // 8
            hw, hh = int(w * 0.15), int(w * 0.12)
            _paste_icon_fit(img, hat, (cx - hw, cy - hh, cx + hw, cy + hh))
        else:
            # sized to sit inside the clue circle, not spill over its rim
            _box_text(d, str(c["clues"]), cb, stat=True, grow=1.0,
                      max_size=int((cb[3] - cb[1]) * 0.56),
                      fill=(238, 232, 216), pos_key="clues")
    _scenario_body(d, "Act", c, pt)
    _card_footer(img, d, "Act", c, art_path)
    _encounter_mark(img, d, "Act", c)
    _finish(img, dest)


def _b_index(kind, c):
    """'Agenda 3b' / 'Act 2b': the b side of the front's index."""
    idx = str(c.get("index", "")).strip()
    if idx[-1:] in ("a", "b"):
        idx = idx[:-1]
    return "{} {}b".format(kind, idx).strip()


def s_scenario_back(kind, c, pt, dest):
    """Agenda/act b side on the plugin's own back frame: 'Agenda 1b' over the
    set circle, the name printed sideways up the left column, the story in
    indented italics and the rules below it, one fitted size for both."""
    frame = _se_img("templates", "AHLCG-{}Back".format(kind))
    W, H = 525 * SE_SCALE, 375 * SE_SCALE
    frame2 = frame.resize((W, H), Image.LANCZOS)
    img = frame2.convert("RGB")
    d = _Draw(img)
    _register_frame(img, kind + "Back", frame2)
    bi = se_reg(kind + "Back", "BackScenarioIndex")
    _box_text(d, _b_index(kind, c), (bi[0] - 10, bi[1] - 4, bi[2] + 10, bi[3] + 6),
              bold=True, max_size=24, fill=(58, 44, 32))
    # the name, reading bottom to top in the tall left column
    nb = se_reg(kind + "Back", "Name")
    if nb:
        nw, nh = int(nb[3] - nb[1]), int(nb[2] - nb[0])
        strip = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
        _box_text(ImageDraw.Draw(strip), c["name"], (0, 0, nw, nh), title=True,
                  grow=1.0, max_size=int(nh * 0.9))
        strip = strip.rotate(90, expand=True)
        img.paste(strip, (int(nb[0]), int(nb[1])), strip)
    story = pt.get("back_flavor", "")
    rules = pt.get("back_text", "")
    sb = se_reg(kind + "Back", "Story")
    bb = se_reg(kind + "Back", "Body")
    top, bottom = bb[1] + 14, bb[3] - 14
    size = BODY_PX
    for size in range(BODY_PX, 14, -1):
        h = 0
        if story:
            h += _wrapped_height(story, size, len(wrap_runs(
                d, story, size, sb[2] - sb[0], italic=True)), 1.24) + 18
        if rules:
            h += _wrapped_height(rules, size, len(wrap_runs(
                d, rules, size, bb[2] - bb[0])), 1.24)
        if h <= bottom - top:
            break
    y = top
    if story:
        y = draw_wrapped(d, story, sb[0], y, size, sb[2] - sb[0],
                         (84, 66, 50), italic=True, leading=1.24) + 18
    if rules:
        draw_wrapped(d, rules, bb[0], y, size, bb[2] - bb[0], PSD_INK,
                     leading=1.24)
    _encounter_mark(img, d, kind + "Back", c, number=False)
    _finish(img, dest)


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
            elif tok == "static":
                # the campaign's own [static] token face (render_token.py)
                from render_token import render_static_token
                tpath = os.path.join(FACES_DIR, (CFG.static_token or {}).get("id", CFG.prefix + "-static-token") + ".png")
                if not os.path.exists(tpath):
                    render_static_token(tpath)
                icon = Image.open(tpath).convert("RGBA")
                m = Image.new("L", icon.size, 0)
                ImageDraw.Draw(m).ellipse([0, 0, icon.size[0] - 1, icon.size[1] - 1], fill=255)
                icon.putalpha(m)
                _paste_icon_fit(img, icon, (icx - isize // 2 + 6, cy - isize // 2 + 6,
                                            icx + isize // 2 - 6, cy + isize // 2 - 6))
            y += rowh + 22
    else:
        _box_block(d, pt.get("text", ""), (body[0], y, body[2], body[3]),
                   start=BODY_PX, key="text")
    _encounter_mark(img, d, "Chaos", c)
    _card_footer(img, d, "Chaos", c, art_path)
    _finish(img, dest)


def s_story(c, pt, dest, art_path=None, placement=None):
    """Story card — name + narrative body."""
    img, d = _se_frame_compose("AHLCG-Story", "Story", "Portrait-portrait-clip",
                               art_path, placement)
    _box_text(d, c["name"], se_reg("Story", "Name"), title=True, grow=1.15, key="name")
    _scenario_body(d, "Story", c, pt, traits=True)
    _encounter_mark(img, d, "Story", c)
    _card_footer(img, d, "Story", c, art_path)
    _finish(img, dest)




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
    y = field("Campaign", c.get("campaign_name", CFG.name), y)
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
    _finish(img, dest)



def minicard_id(card_id):
    """SCED's minicard id convention: the investigator's id + "-m"
    (docs/art_reference/sced_objects/minicard.json: "10001-m")."""
    return card_id + "-m"


def s_minicard(c, dest, back_dest, art_path=None, placement=None):
    """Investigator minicard, exactly as the plugin's MiniInvestigator.js
    paints it: the AHLCG-MiniInvestigator template, the investigator portrait
    over the whole Portrait clip region (0,0,244,375), the artist line in its
    Artist region; the back is the same portrait in greyscale. With no
    portrait yet, the investigator's name is set on the template so the mini
    is identifiable on the table (placeholder only — the plugin has no name
    field, the portrait is the identity)."""
    tpl = _se_img("templates", "AHLCG-MiniInvestigator")
    if tpl is None:
        return False
    W, H = 244 * SE_SCALE, 375 * SE_SCALE
    base = tpl.resize((W, H), Image.LANCZOS).convert("RGB")
    reg = se_reg("MiniInvestigator", "Portrait-portrait-clip") or (0, 0, W, H)
    artist = se_reg("MiniInvestigator", "Artist")
    for grey, out in ((False, dest), (True, back_dest)):
        img = base.copy()
        if art_path and paste_cover(img, art_path, reg, placement):
            if grey:
                img = img.convert("L").convert("RGB")
            d = _Draw(img)
            if artist and not grey:
                _box_text(d, _wm(art_path), artist, fill=(230, 226, 214),
                          max_size=16, min_size=10)
        else:
            d = _Draw(img)
            name = c.get("name", "")
            _box_text(d, name, (18, H - 150, W - 18, H - 90), title=True,
                      fill=(150, 150, 150) if grey else (236, 230, 212),
                      grow=1.0, max_size=46, min_size=18)
            if c.get("class") and not grey:
                _box_text(d, c["class"], (18, H - 84, W - 18, H - 52),
                          italic=True, fill=(196, 188, 170), max_size=26)
        _finish(img, out)
    return True


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
    # so every printed field is editable ON the card: split the Body into a
    # traits strip (top) / rules (middle) / flavour strip (bottom), and add the
    # subtitle plate where the frame prints one
    body = out.get("text")
    if body:
        top, bot = body[1], body[3]
        h = bot - top
        th = min(46, int(h * 0.20))
        fh = min(58, int(h * 0.24))
        if h > th + fh + 70:
            out["traits"] = [body[0], top, body[2], top + th]
            out["flavor"] = [body[0], bot - fh, body[2], bot]
            out["text"] = [body[0], top + th, body[2], bot - fh]
    if card_type in ("Investigator", "Asset", "Event"):
        letter = "N" if card_type in ("Asset", "Event") else ""
        sub = r(card_type, "SubtitleText", letter) or r(card_type, "Subtitle", letter)
        if sub:
            out["subtitle"] = sub
    # the XP pip band — click it like a stat (left +1 to 5, right -1 to 1) to set
    # the card's level; sits over the lower cost disc / skill cup
    if card_type in ("Asset", "Event"):
        cb = se_reg(card_type, "Cost")
        if cb:
            w = cb[2] - cb[0]
            cx = (cb[0] + cb[2]) / 2
            out["level"] = [int(cx - w * 0.56), int(cb[1] + w * 0.70),
                            int(cx + w * 0.56), int(cb[3] + w * 0.25)]
    elif card_type == "Skill":
        cup = se_reg("Skill", "Level")
        if cup:
            out["level"] = list(cup)
    return {k: v for k, v in out.items() if v}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="render only these card ids")
    ap.add_argument("--campaign", help="campaign id (campaigns/<id>/build.json); default $CAMPAIGN or still_hour")
    ap.add_argument("--no-template", action="store_true",
                    help="force the drawn (non-template) placeholder look")
    ap.add_argument("--furniture", action="store_true",
                    help="render frame+text+discs on a transparent art window "
                         "(<id>-furniture.png) for the live editor overlay")
    ap.add_argument("--blank", action="store_true",
                    help="render the card with NO art (<id>-blank.png): the "
                         "editor backdrop showing the class background")
    ap.add_argument("--check", action="store_true",
                    help="print audit only: render the faces into a temporary "
                         "folder (art/faces untouched) and exit 1 if any text "
                         "is hidden by the frame, covered, colliding or clipped")
    args = ap.parse_args()
    global FURNITURE, BLANK, FACES_DIR
    if args.check:
        import tempfile
        FACES_DIR = tempfile.mkdtemp(prefix="print_audit_")
    FURNITURE = bool(args.furniture)
    BLANK = bool(args.blank)
    use_tpl = (not args.no_template) and T.has_template("investigator_front")
    # EVERY campaign's specs — the authored Still Hour set plus any
    # <campaign>_*_spec.json written by the app (hand-made or imported cards),
    # so a campaign built from scratch renders exactly like the authored one
    cards, seen = [], set()
    # (a campaign with "render_all_pipeline_specs": false renders its own specs only)
    spec_files = (sorted(glob.glob(os.path.join(HERE, "*_spec.json")))
                  if CFG.get("render_all_pipeline_specs", True) else CFG.path("specs"))
    for sp in spec_files:
        try:
            for c in json.load(open(sp, encoding="utf-8")):
                if c.get("id") and c["id"] not in seen:
                    seen.add(c["id"])
                    cards.append(c)
        except (ValueError, OSError):
            continue
    all_cards = list(cards)
    if args.only:
        cards = [c for c in cards if c["id"] in set(args.only)]
    print_text = {k: v for k, v in
                  json.load(open(CFG.path("print_text"), encoding="utf-8")).items()
                  if not k.startswith("_")}
    art_index = load_art_index()
    placements = load_placements()
    os.makedirs(FACES_DIR, exist_ok=True)
    missing_text = []
    composed = 0
    font_overrides = load_font_overrides()
    global FONT_OVERRIDE, FIELD_STYLE
    card_overrides = load_card_overrides()
    global ENC_MARKS
    try:
        import encounter_sets
        ENC_MARKS = encounter_sets.load()
    except Exception as e:  # noqa: BLE001 - a campaign without sets prints none
        print("encounter symbols skipped: {}".format(e))
        ENC_MARKS = {}
    # collector numbers come from the whole campaign, even for an --only run
    COLLECTION_NUMBERS.clear()
    COLLECTION_NUMBERS.update(collection_numbers(
        [dict(c, encounter_set=ENC_MARKS[c["id"]][0]) if c["id"] in ENC_MARKS
         else c for c in all_cards]))
    font_default = font_overrides.get("_default", {})
    fields_default = font_default.get("fields", {})
    for c in cards:
        CURRENT_CARD[0] = c.get("id")
        _AUDIT_RECS.clear()
        _CANVAS_FRAMES.clear()
        FONT_OVERRIDE = dict(font_default, **font_overrides.get(c["id"], {}))
        # per-area typography: card field styles layered over the global default
        fields_card = font_overrides.get(c["id"], {}).get("fields", {})
        FIELD_STYLE = {k: dict(fields_default.get(k, {}), **fields_card.get(k, {}))
                       for k in set(fields_default) | set(fields_card)}
        pt = print_text.get(c["id"], {})
        c, pt = apply_card_overrides(c, pt, card_overrides.get(c["id"]))
        if c["id"] in ENC_MARKS:
            sid, num = ENC_MARKS[c["id"]]
            c = dict(c, encounter_set=sid)
            if "number" not in (card_overrides.get(c["id"]) or {}):
                c["number"] = num
        if not pt.get("text"):
            missing_text.append(c["id"])
        art = art_index.get(c["id"])
        place = placements.get(c["id"])
        composed += 1 if art else 0
        # furniture/blank faces go to their own filenames so they never clobber
        # the real, art-baked faces (or backs) the compiler and gallery read
        suffix = "-furniture" if FURNITURE else "-blank" if BLANK else ""
        dest = os.path.join(FACES_DIR, c["id"] + suffix + ".png")
        back_dest = os.path.join(FACES_DIR, c["id"] + suffix + "-back.png")
        if c["type"] == "Investigator":
            if has_se_frames():
                s_investigator_front(c, pt, dest, art_path=art, placement=place)
                s_investigator_back(c, pt, back_dest, art_path=art)
                if not (FURNITURE or BLANK):
                    mid = minicard_id(c["id"])
                    s_minicard(c, os.path.join(FACES_DIR, mid + ".png"),
                               os.path.join(FACES_DIR, mid + "-back.png"),
                               art_path=art_index.get(mid) or art,
                               placement=placements.get(mid))
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
            if c["type"] in ("Agenda", "Act") and (pt.get("back_text")
                                                   or pt.get("back_flavor")):
                # the printed b side: its own landscape back (UniqueBack), so
                # the card zooms and flips like an official agenda/act
                s_scenario_back(c["type"], c, pt, back_dest)
            if c["type"] == "Scenario" and c.get("back_tokens"):
                # the reference card's Hard / Expert side, like an official one
                s_scenario_ref(dict(c, tokens=c["back_tokens"], difficulty="HARD / EXPERT"),
                               pt, back_dest)
            if c["type"] == "Location" and c.get("unrevealed"):
                # the unrevealed side, as the card's back: name, traits, its
                # own symbol, connections, its own rules (if any) and a line
                # of flavour; no shroud or clues (SCED spawns them when the
                # location is revealed)
                s_location(dict(c, revealed=True),
                           dict(pt, text=pt.get("unrevealed_text", ""),
                                flavor=pt.get("unrevealed_flavor", "")),
                           back_dest, art_path=art, placement=place)
            elif c["type"] == "Location" and (pt.get("back_text")
                                            or c.get("back_shroud") not in (None, "")):
                # a location a Knowledge fact flips (src/StillHour/Locations.ttslua
                # flipFact) prints its flipped side as the card's back: same
                # frame, its own shroud/rules/flavour
                bc = dict(c, shroud=c.get("back_shroud", c.get("shroud")))
                bpt = dict(pt, text=pt.get("back_text", ""),
                           flavor=pt.get("back_flavor", ""))
                SCENARIO_RENDERERS["Location"](bc, bpt, back_dest, art_path=art,
                                               placement=place)
        else:
            render_player_card(c, pt, dest, art_path=art, placement=place)
    CURRENT_CARD[0] = None
    if not (FURNITURE or BLANK or args.only or args.check):
        # table presence: the campaign-log pages and the box texture
        import campaign_log
        import table_presence
        campaign_log.render_pages(FACES_DIR)
        table_presence.render_box_texture(
            os.path.join(FACES_DIR, table_presence.BOX_TEXTURE_ID + ".png"))
    n = len([f for f in os.listdir(FACES_DIR) if f.endswith(".png")])
    print("rendered {} face(s) ({} with chosen art composited) -> {}".format(
        n, composed, os.path.relpath(FACES_DIR, ROOT)))
    if missing_text:
        print("cards with NO rules text in the print layer: " + ", ".join(missing_text))
    if OVERFLOWS:
        print("TEXT OVERFLOW (did not fit at the smallest size): " + ", ".join(
            "{} [{}@{}px]".format(*o) for o in OVERFLOWS))
    if FLAVOR_DROPPED:
        print("flavour left off (rules too dense to keep it at {}px+): {}".format(
            FLAVOR_KEEP_PX, ", ".join(sorted(set(FLAVOR_DROPPED)))))
    small = sorted((v[0], k) for k, v in BODY_SIZES.items() if v and v[0] < 25)
    if small:
        print("rules set below 25px (official 31): " + ", ".join(
            "{} {}px".format(k, v) for v, k in small))
    if PRINT_ISSUES:
        lines = audit_report()
        print("PRINT AUDIT: text hidden by the frame / covered / colliding / "
              "clipped on {} face(s):".format(len(lines)))
        for line in lines:
            print("  " + line)
    else:
        print("print audit: no hidden, covered, colliding or clipped text")
    if args.check:
        import shutil
        shutil.rmtree(FACES_DIR, ignore_errors=True)
        if PRINT_ISSUES or OVERFLOWS:
            sys.exit(1)


if __name__ == "__main__":
    main()
