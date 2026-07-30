"""template_render.py — compose cards ON the official reference frames.

The owner's reference cards (docs/art_reference -> assets/frames/templates,
normalized to TTS dimensions) are used as the card BASE. Every region with
baked-in content (portrait, name, stats, rules text) is covered by our art
paste or a sampled-color panel carrying our text; the ornate borders, textures
and colors between those regions are the real thing. FFG's copyright line is
left visible (fan-content attribution); the original illustrator credit is
covered because the illustration is replaced.

Region maps are hand-measured against the normalized templates. Fan content:
free, online only, per the owner's declared scope.
"""
import os

from PIL import Image, ImageDraw

TPL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "frames", "templates")

# sampled palette from the references
SCROLL = (38, 31, 25)          # dark name-scroll background
SCROLL_INK = (232, 222, 200)
PARCH = (228, 216, 192)        # body parchment
PARCH_DARK = (216, 202, 174)   # subtitle strip
INK = (36, 30, 26)
FLAVOR_INK = (86, 70, 54)
RED = (158, 36, 32)
BLUE = (46, 78, 140)
CLASS_COLORS = {
    "Guardian": (43, 80, 140), "Seeker": (196, 132, 47), "Rogue": (55, 122, 83),
    "Mystic": (94, 63, 128), "Survivor": (150, 55, 51), "Neutral": (94, 94, 102),
    "Mythos": (52, 44, 62),
}


VENDOR_BLANKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "vendor", "frames")

# When an SD-inpainted blank frame exists (vendor/frames/blank_<layout>.png,
# built by CardForge's "Rebuild blank frames"), it becomes the card base and
# the flat cover fills are skipped — text is typeset straight onto the real
# regenerated texture. Set per-render by open_template (renders are serial).
BLANK_MODE = False


def template_path(layout):
    return os.path.join(TPL_DIR, layout + ".png")


def blank_path(layout):
    return os.path.join(VENDOR_BLANKS, "blank_" + layout + ".png")


def has_template(layout):
    return os.path.exists(template_path(layout))


def open_template(layout):
    global BLANK_MODE
    if os.path.exists(blank_path(layout)):
        BLANK_MODE = True
        return Image.open(blank_path(layout)).convert("RGB")
    BLANK_MODE = False
    return Image.open(template_path(layout)).convert("RGB")


COVER_FILLS = None  # set after the palette below


def rrect(d, box, fill, radius=8, outline=None):
    # cover fills exist to hide the template's baked-in content; an inpainted
    # blank has none, so skip them and keep its texture (badges still draw)
    if BLANK_MODE and COVER_FILLS and fill in COVER_FILLS and outline is None:
        return
    d.rounded_rectangle(list(box), radius=radius, fill=fill, outline=outline)


def cover_illus_credit(img, d, w, h, landscape=False):
    """Cover the original illustrator credit (left half of the footer) with a
    fill sampled from the template so it blends; keep the (c) FFG side visible."""
    if landscape:
        # landscape investigator credit sits mid-footer
        fill = img.getpixel((int(w * 0.40), h - 6))
        d.rectangle([int(w * 0.50), h - 28, int(w * 0.76), h - 8], fill=fill)
    else:
        fill = img.getpixel((int(w * 0.30), h - 4))
        d.rectangle([8, h - 22, int(w * 0.42), h - 6], fill=fill)


def blank_art_window(d, box, label="place art"):
    d.rectangle(list(box), fill=(30, 27, 36))
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    d.text((cx - 30, cy - 8), label, fill=(120, 114, 128))


# region maps (normalized template coordinates)
INV_FRONT = {
    "class_disc": (8, 6, 62, 60),
    "name": (112, 8, 566, 48),
    "subtitle": (118, 52, 562, 78),
    "stats_strip": (566, 4, 750, 58),
    "stats": [(578, 10, 620, 52), (621, 10, 663, 52), (664, 10, 706, 52), (707, 10, 749, 52)],
    "art": (6, 82, 336, 502),
    "panel": (348, 92, 736, 500),
    "hs_y": 450,
}
INV_BACK = {
    "polaroid": (24, 30, 206, 244),
    "name": (300, 12, 700, 52),
    "subtitle": (330, 56, 660, 82),
    "panel": (228, 90, 738, 508),
    "panel_low": (26, 258, 738, 508),
}
TREACHERY = {
    "art": (13, 13, 406, 300),
    "keyhole": (186, 272, 233, 322),
    "type": (118, 318, 301, 346),
    "name": (58, 352, 361, 386),
    "weakness_bar": (88, 386, 332, 412),
    "panel": (30, 392, 389, 556),
    "panel_weak": (30, 410, 389, 556),
}
ENEMY = {
    "name": (78, 8, 341, 46),
    "fight": (116, 50, 170, 104),
    "health": (188, 44, 244, 110),
    "evade": (250, 50, 304, 104),
    "traits": (40, 110, 380, 140),
    "panel": (30, 140, 389, 332),
    "banner_strip": (110, 330, 309, 384),
    "art": (13, 388, 406, 578),
}

COVER_FILLS = {SCROLL, PARCH, PARCH_DARK}

# layout -> (region map, landscape) — drives inpaint mask generation
LAYOUT_REGIONS = {
    "investigator_front": (INV_FRONT, True),
    "investigator_back": (INV_BACK, True),
    "treachery": (TREACHERY, False),
    "treachery_weakness": (TREACHERY, False),
    "enemy": (ENEMY, False),
    "enemy_elite": (ENEMY, False),
}

# region fills for the local (no-GPU) blank fallback, keyed like the maps
_BLANK_FILL_BY_KEY = {
    "name": SCROLL, "type": SCROLL, "stats_strip": SCROLL,
    "subtitle": PARCH_DARK, "traits": PARCH_DARK,
    "weakness_bar": (86, 28, 26), "polaroid": (30, 27, 36),
    "class_disc": SCROLL, "fight": SCROLL, "health": SCROLL, "evade": SCROLL,
}


def inpaint_regions(layout, w, h):
    """(key, box) pairs an inpainted blank must regenerate: every mapped
    region except the art window (art paste covers it fully), plus the
    original illustrator credit in the footer."""
    regions, landscape = LAYOUT_REGIONS[layout]
    out = []
    for key, val in regions.items():
        if key in ("art", "stats", "hs_y"):
            continue
        out.append((key, val))
    if landscape:
        out.append(("credit", (int(w * 0.50), h - 28, int(w * 0.76), h - 8)))
    else:
        out.append(("credit", (8, h - 22, int(w * 0.42), h - 6)))
    return out


def make_local_blank(layout):
    """The no-GPU fallback blank: the template with its content regions
    covered by the sampled-palette fills (exactly what the renderer would
    draw). SD inpainting replaces this with regenerated real texture."""
    img = Image.open(template_path(layout)).convert("RGB")
    d = ImageDraw.Draw(img)
    for key, box in inpaint_regions(layout, img.width, img.height):
        if key == "credit":
            fill = img.getpixel((max(0, box[0] - 6), (box[1] + box[3]) // 2))
        else:
            fill = _BLANK_FILL_BY_KEY.get(key, PARCH)
        d.rounded_rectangle(list(box), radius=8, fill=fill)
    return img
