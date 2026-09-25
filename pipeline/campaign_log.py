#!/usr/bin/env python3
"""campaign_log.py — the interactive campaign log (SCED CampaignLog token).

One layout drives both halves of the log, so the printed sheet and the
clickable overlay can never drift apart:

  * render_pages()  draws each log page onto the plugin's own campaign-guide
    page (assets/frames/se/guide/AHLCG-GuideLetterEmpty.jpg — the same stock
    FFG's printed logs sit on, as the last pages of a campaign guide):
    labels, checkboxes, counter rings and write-in lines.
  * lua_layout()    emits the same fields as normalized (u, v) coordinates for
    src/tts/campaign_log.lua, which places a TTS checkbox / counter / input on
    each one at runtime (sized from the token's real bounds).

Field content follows docs/design/THE_STILL_HOUR_log_sheet.md (loop counter,
Act, investigators with Years/bracket/drift/Recollections/fate, banked Memory,
the Knowledge Track, the Named, threads, the dead and the kept, the finale
record). Page count: 3 (a token with 3 States, like SCED's multi-page logs).

Run: python3 pipeline/campaign_log.py   -> art/faces/sthr-log-page{1,2,3}.png
"""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

PAGE_W, PAGE_H = 1275, 1650          # GuideLetter template = US Letter @150dpi
PAGE_TEMPLATE = os.path.join(ROOT, "assets", "frames", "se", "guide",
                             "AHLCG-GuideLetterEmpty.jpg")
PAGE_IDS = ["sthr-log-page1", "sthr-log-page2", "sthr-log-page3"]
LOG_ID = "STHR-LOG"                  # GMNotes id stem: STHR-LOG1 / 2 / 3

INK = (36, 30, 26)
SOFT = (96, 80, 64)
TEAL = (45, 91, 88)                  # the plugin's guide header teal (#2d5b58)
RULE = (128, 108, 86)

# The five investigators (ids used by CampaignState.years / brackets).
INVESTIGATORS = [
    ("sthrelias", "Elias Warde"), ("sthrayako", "Dr. Ayako Sōma"),
    ("sthrcass", "Cass Lindqvist"), ("sthrseraphine", "Seraphine Vale"),
    ("sthrbirdie", "\"Birdie\" Okonkwo"),
]

# The Knowledge Track, in log-sheet order. Ids match src/StillHour/Knowledge.ttslua.
FACTS = [
    ("you-are-unstuck", "You Are Unstuck", "Prologue", "prologue",
     "Act I begins; Memory carries across resets."),
    ("the-lamp-was-never-lit", "The Lamp Was Never Lit", "Lighthouse", "surface",
     "Lit lamp keeps Echoes Sleepwalking one band longer."),
    ("the-keepers-ninth-death", "The Keeper's Ninth Death", "Lighthouse", "deep",
     "Elias elder-sign also heals horror; enables Break Through."),
    ("the-thirteenth-toll", "The Thirteenth Toll", "Church", "surface",
     "Removes the Church's extra Dissonance at Hour III."),
    ("the-hour-was-wrong", "The Hour Was Wrong", "Church", "deep",
     "Removes Hour IV from the Occultation."),
    ("the-road-remembers", "The Road Remembers", "Sunken Road", "surface",
     "Free Lighthouse travel once per loop."),
    ("who-walks-beside-you", "Who Walks Beside You", "Sunken Road", "deep",
     "Echoes -1 Fight vs. you; softens Take Its Place."),
    ("the-sheriff-is-already-dead", "The Sheriff Is Already Dead", "Square", "surface",
     "Read the top Occultation card once per loop."),
    ("the-vote-that-never-ends", "The Vote That Never Ends", "Square", "deep",
     "Seraphine thread; required for Close the Door."),
    ("the-wheel-still-turns", "The Wheel Still Turns", "Fairground", "surface",
     "Reorder the top 2 encounter cards once per loop."),
    ("the-ticket-takers-bargain", "The Ticket-Taker's Bargain", "Fairground", "deep",
     "Unlocks Let It In; flags the epilogue."),
    ("what-the-almanac-hid", "What the Almanac Hid", "Almanac", "surface",
     "Remove a [static] at Hour VI."),
    ("the-appointeds-name", "The Appointed's Name", "Almanac", "deep",
     "Appointed arrives exhausted; required for the finale."),
    ("the-way-the-night-breaks", "The Way the Night Breaks", "assembled", "assembled",
     "Name + Vote + one other deep fact: the finale may be attempted."),
]

# Victory — the Named (ids = the encounter cards' ids; CampaignState.victoryLog keys)
NAMED = [
    ("sthr-bellringer", "The Bell-Ringer Beneath", "Church", 2),
    ("sthr-wearssheriff", "What Wears the Sheriff", "Square", 3),
    ("sthr-onewhorides", "The One Who Rides Forever", "Fairground", 2),
]

# Choices (guide: "What You Saw" and each district's deep resolution). Each is
# a pair of mutually exclusive options; keys are the log fields <key>_a/_b.
CHOICES = [
    ("prologue", "What You Saw", ("The town was warned",), ("Kept the night to yourselves",)),
    ("ninth", "The Ninth Line", ("Signed the ninth line",), ("Left it blank",)),
    ("page", "The Drowned Page", ("Page reached the Press",), ("The drowned heard the hour",)),
    ("ring", "The Walker's Ring", ("You carry the ring",), ("The walkers keep it",)),
    ("vote", "The Ledger", ("The vote was torn out",), ("The vote still stands",)),
    ("ticket", "The Ticket", ("You hold the ticket",), ("You refused the ticket",)),
    ("name", "The Name", ("You have spoken the name",), ("Kept unspoken",)),
]

BRACKETS = [("prime", "Prime", 0, 4), ("weathered", "Weathered", 5, 9),
            ("elder", "Elder", 10, 14), ("ancient", "Ancient", 15, 99)]

CB = 26          # checkbox square (px)
RING = 58        # counter ring diameter (px)


# ------------------------------------------------------------------ layout --
class Page:
    """Collects drawing ops (labels, furniture) and interactive fields."""

    def __init__(self, n, title):
        self.n, self.title = n, title
        self.ops, self.fields = [], []

    def text(self, x, y, s, size=24, style="body", fill=INK, anchor="ls"):
        self.ops.append(("text", x, y, s, size, style, fill, anchor))

    def header(self, y, s):
        self.text(PAGE_W // 2, y, s, size=40, style="title", fill=TEAL, anchor="ms")
        self.ops.append(("rule", 150, y + 12, PAGE_W - 150))

    def checkbox(self, key, x, y, label=None, size=22, style="body", group=None):
        """Box with its top-left at (x, y - CB + 4); label to its right.
        Returns the x just past the label."""
        top = y - CB + 4
        self.ops.append(("box", x, top))
        self.fields.append({"k": key, "t": "cb", "x": x, "y": top,
                            "w": CB, "h": CB, **({"g": group} if group else {})})
        nx = x + CB + 8
        if label:
            self.text(nx, y, label, size=size, style=style)
            nx += measure(label, size, style) + 22
        return nx

    def counter(self, key, cx, cy, lo=0, hi=99, derived=None):
        self.ops.append(("ring", cx, cy, derived is not None))
        f = {"k": key, "t": "dv" if derived else "ct", "x": cx - RING // 2,
             "y": cy - RING // 2, "w": RING, "h": RING}
        if derived:
            f["d"] = derived
        else:
            f.update({"min": lo, "max": hi})
        self.fields.append(f)

    def line(self, key, x0, x1, y, rows=1, row_h=34):
        """Write-in line(s); the input box sits on top of them."""
        for r in range(rows):
            self.ops.append(("line", x0, y + r * row_h, x1))
        top = y - row_h + 6
        self.fields.append({"k": key, "t": "tx", "x": x0, "y": top,
                            "w": x1 - x0, "h": row_h * rows, "rows": rows})


def _pages():
    p1 = Page(1, "Campaign Log")
    p1.text(PAGE_W // 2, 128, "The Still Hour — Campaign Log", size=62,
            style="title", fill=TEAL, anchor="ms")
    p1.text(PAGE_W // 2, 166, "Fill in at each interlude. Everything on this "
            "sheet persists across resets.", size=22, style="italic", fill=SOFT,
            anchor="ms")
    y = 222
    p1.text(90, y, "Campaign started:", size=24, style="bold")
    p1.line("started", 300, 470, y)
    p1.text(500, y, "Difficulty:", size=24, style="bold")
    x = p1.checkbox("diff_easy", 630, y, "Easy", group="diff")
    x = p1.checkbox("diff_standard", x, y, "Standard", group="diff")
    x = p1.checkbox("diff_hard", x, y, "Hard", group="diff")
    p1.checkbox("diff_expert", x, y, "Expert", group="diff")

    p1.header(290, "Loop Counter")
    y = 348
    p1.text(90, y, "Completed loops", size=24, style="bold")
    p1.counter("loops", 320, y - 9, 0, 99)
    p1.text(420, y, "Dissonance scar next loop (= loops, max 6):", size=22,
            style="italic", fill=SOFT)
    p1.counter("scar", 895, y - 9, derived="scar")
    p1.text(960, y, "Investigators:", size=24, style="bold")
    p1.counter("investigators", 1162, y - 9, 1, 4)
    y = 410
    p1.text(90, y, "Current Act:", size=24, style="bold")
    x = p1.checkbox("act1", 250, y, "I — Learning the Rules", group="act")
    x = p1.checkbox("act2", x, y, "II — The Shape of the Hour", group="act")
    p1.checkbox("act3", x, y, "The Last Hour available", group="act")

    p1.header(468, "Investigators")
    panels = [(80, 500), (660, 500), (80, 894), (660, 894)]
    for i, (px, py) in enumerate(panels, start=1):
        _investigator_panel(p1, i, px, py)

    p1.header(1314, "Banked Memory")
    y = 1368
    p1.text(90, y, "Banked Memory", size=24, style="bold")
    p1.counter("banked", 300, y - 9, 0, 99)
    p1.text(345, y, "(soft cap 6 × investigators — reduce at each loop start)",
            size=20, style="italic", fill=SOFT)
    p1.text(900, y, "Spent this interlude", size=24, style="bold")
    p1.counter("spent", 1150, y - 9, 0, 99)
    y = 1424
    p1.text(90, y, "Spent on:", size=24, style="bold")
    p1.line("spent_on", 210, 1190, y)
    p1.text(90, 1474, "Campaign notes", size=24, style="bold")
    p1.line("notes1", 90, 1190, 1512, rows=2, row_h=34)

    p2 = Page(2, "Campaign Log — continued")
    p2.text(PAGE_W // 2, 116, "The Knowledge Track", size=52, style="title",
            fill=TEAL, anchor="ms")
    p2.text(PAGE_W // 2, 150, "Check when unlocked. Each edits the night "
            "permanently.", size=22, style="italic", fill=SOFT, anchor="ms")
    y = 206
    for fid, name, district, layer, summary in FACTS:
        p2.checkbox("k:" + fid, 88, y)
        p2.text(128, y, name, size=24, style="bold")
        p2.text(128, y + 22, district if layer != "assembled"
                else "assembled", size=17, style="italic", fill=SOFT)
        p2.text(510, y - 2, summary, size=20, style="body")
        if layer == "deep":
            p2.text(1178, y - 2, "deep", size=16, style="italic", fill=SOFT,
                    anchor="rs")
        y += 52
    y += 6
    p2.text(90, y, "Surface facts held:", size=24, style="bold")
    p2.counter("surface_held", 330, y - 9, derived="surface")
    p2.text(370, y, "/ 6 — Act II opens at 3+", size=22, style="italic", fill=SOFT)
    p2.text(720, y, "Deep facts held:", size=24, style="bold")
    p2.counter("deep_held", 925, y - 9, derived="deep")
    p2.text(965, y, "/ 6", size=22, style="italic", fill=SOFT)

    p2.header(y + 70, "Victory — The Named")
    y += 140
    p2.text(760, y - 34, "defeated", size=18, style="italic", fill=SOFT)
    p2.text(900, y - 34, "Memory banked", size=18, style="italic", fill=SOFT)
    for eid, name, where, vic in NAMED:
        p2.text(90, y, name, size=24, style="bold")
        p2.text(470, y, "({}, Victory {})".format(where, vic), size=20,
                style="italic", fill=SOFT)
        p2.checkbox("v:" + eid, 780, y)
        p2.checkbox("vb:" + eid, 940, y)
        y += 46

    p2.header(y + 26, "Threads & Choices")
    y += 84
    p2.text(90, y, "Seraphine — \"Who Opened the Door\":", size=22, style="bold")
    x = p2.checkbox("sera_unheard", 520, y, "unheard", group="sera")
    x = p2.checkbox("sera_suspected", x, y, "suspected", group="sera")
    p2.checkbox("sera_known", x, y, "known (Vote + Name)", group="sera")
    y += 46
    p2.text(90, y, "The Ticket-Taker's Bargain:", size=22, style="bold")
    x = p2.checkbox("bargain_never", 520, y, "never heard", group="bargain")
    p2.checkbox("bargain_heard", x, y, "heard (epilogue flag)", group="bargain")
    y += 46
    p2.text(90, y, "Districts fully cracked (surface + deep):", size=22, style="bold")
    y += 42
    x = 110
    for key, label in (("lighthouse", "Lighthouse"), ("church", "Church"),
                       ("road", "Sunken Road"), ("square", "Square"),
                       ("fairground", "Fairground"), ("almanac", "Almanac")):
        x = p2.checkbox("cracked_" + key, x, y, label)

    p3 = Page(3, "Campaign Log — continued")
    p3.text(PAGE_W // 2, 116, "The Dead & the Kept", size=52, style="title",
            fill=TEAL, anchor="ms")
    y = 186
    p3.text(90, y, "Investigator", size=20, style="italic", fill=SOFT)
    p3.text(560, y, "Fate", size=20, style="italic", fill=SOFT)
    p3.text(1070, y, "Loop", size=20, style="italic", fill=SOFT)
    y = 240
    for i in range(1, 5):
        p3.line("dead{}_name".format(i), 90, 520, y)
        x = p3.checkbox("dead{}_died".format(i), 560, y, "died", group="dead%d" % i)
        x = p3.checkbox("dead{}_aged".format(i), x, y, "aged out", group="dead%d" % i)
        p3.checkbox("dead{}_kept".format(i), x, y, "kept as anchor", group="dead%d" % i)
        p3.line("dead{}_loop".format(i), 1070, 1185, y)
        y += 58

    p3.header(y + 30, "Choices")
    y += 88
    p3.text(90, y, "Prologue ended:", size=22, style="bold")
    x = p3.checkbox("pro_r1", 330, y, "R1", group="pro")
    x = p3.checkbox("pro_r2", x, y, "R2", group="pro")
    x = p3.checkbox("pro_nr", x, y, "No Resolution", group="pro")
    p3.text(840, y, "Torn loops", size=22, style="bold")
    p3.counter("torn", 1000, y - 9, 0, 99)
    p3.text(1040, y, "Taken", size=22, style="bold")
    p3.counter("taken", 1150, y - 9, 0, 99)
    y += 50
    for key, label, a, b in CHOICES:
        p3.text(90, y, label, size=22, style="bold")
        x = p3.checkbox(key + "_a", 400, y, a[0], size=21, group="ch_" + key)
        x = p3.checkbox(key + "_b", max(x, 780), y, b[0], size=21, group="ch_" + key)
        y += 44
    p3.text(90, y, "Signed the ninth line:", size=22, style="bold")
    p3.line("ninth_signer", 330, 760, y)
    y -= 8

    p3.header(y + 50, "Finale Record")
    y += 108
    p3.text(90, y, "Attempted on loop:", size=24, style="bold")
    p3.line("finale_loop", 300, 400, y)
    p3.text(440, y, "Contest reached:", size=24, style="bold")
    x = p3.checkbox("contest_yes", 630, y, "yes", group="contest")
    p3.checkbox("contest_no", x, y, "no", group="contest")
    p3.text(880, y, "Banked Memory:", size=24, style="bold")
    p3.counter("finale_memory", 1130, y - 9, 0, 99)
    y += 54
    p3.text(90, y, "Resolution reached:", size=24, style="bold")
    for row in ((("r1", "R1 Take Its Place"), ("r1b", "R1b Let It In"),
                 ("r2", "R2 Close the Door")),
                (("r3", "R3 Break Through"), ("r4", "R4 Seal by Force")),
                (("r5", "R5 Next Time (continue)"), ("r6", "R6 The Loop Wins (end)"))):
        y += 44
        x = 110
        for key, label in row:
            x = p3.checkbox(key, x, y, label, group="res")
    y += 54
    p3.text(90, y, "Anchor left behind:", size=24, style="bold")
    p3.line("anchor", 320, 1185, y)
    y += 50
    p3.text(90, y, "Years paid at the end:", size=24, style="bold")
    p3.line("aged3", 350, 1185, y)

    p3.header(y + 62, "Campaign Notes")
    rows = max(2, (1560 - (y + 132)) // 36 + 1)
    p3.line("notes3", 90, 1190, y + 132, rows=rows, row_h=36)
    return [p1, p2, p3]


def _investigator_panel(p, i, px, py):
    w = 540
    p.ops.append(("panel", px, py, px + w, py + PANEL_H))
    x0, x1 = px + 20, px + w - 20
    p.text(x0, py + 40, "Investigator {}".format(i), size=30, style="title", fill=TEAL)
    y = py + 80
    p.text(x0, y, "Name", size=22, style="bold")
    p.line("inv{}_name".format(i), x0 + 70, x1, y)
    y += 42
    p.text(x0, y, "Class", size=22, style="bold")
    p.line("inv{}_class".format(i), x0 + 70, x0 + 230, y)
    p.text(x0 + 250, y, "Player", size=22, style="bold")
    p.line("inv{}_player".format(i), x0 + 330, x1, y)
    y += 54
    p.text(x0, y, "Years", size=22, style="bold")
    p.counter("inv{}_years".format(i), x0 + 100, y - 8, 0, 99)
    bx = x0 + 142
    for key, label, lo, hi in BRACKETS:
        p.ops.append(("box", bx, y - CB + 4))
        p.fields.append({"k": "inv{}_{}".format(i, key), "t": "dv",
                         "d": "bracket:{}:{}:{}".format(i, lo, hi),
                         "x": bx, "y": y - CB + 4, "w": CB, "h": CB})
        p.text(bx + CB + 4, y, label, size=16, style="body")
        bx += CB + 12 + measure(label, 16, "body")
    p.text(x0 + 142, y + 22, "Prime 0–4 · Weathered 5–9 · Elder 10–14 · Ancient 15+",
           size=15, style="italic", fill=SOFT)
    y += 60
    p.text(x0, y, "Drift", size=22, style="bold")
    x = p.checkbox("inv{}_dcom".format(i), x0 + 70, y, "−1 [com]", size=20)
    x = p.checkbox("inv{}_dagi".format(i), x, y, "−1 [agi]", size=20)
    x = p.checkbox("inv{}_dwil".format(i), x, y, "+1 [wil]", size=20)
    p.checkbox("inv{}_dint".format(i), x, y, "+1 [int]", size=20)
    y += 42
    p.text(x0, y, "Recollections", size=22, style="bold")
    p.line("inv{}_recollections".format(i), x0 + 150, x1, y, rows=2, row_h=32)
    y += 32 + 50
    x = p.checkbox("inv{}_agedout".format(i), x0, y, "Aged out", size=20)
    x = p.checkbox("inv{}_anchor".format(i), x, y, "Anchor", size=20)
    x = p.checkbox("inv{}_dead".format(i), x, y, "Dead — loop", size=20)
    p.line("inv{}_deadloop".format(i), x - 14, x1, y)


PANEL_H = 374


# ---------------------------------------------------------------- render --
_FONT_CACHE = {}


def _font(size, style):
    import render_placeholders as rp
    key = (size, style)
    if key not in _FONT_CACHE:
        if style == "glyph":
            _FONT_CACHE[key] = rp._font(size, glyph=True)
        else:
            _FONT_CACHE[key] = rp._font(size, title=style == "title",
                                        bold=style == "bold",
                                        italic=style == "italic")
    return _FONT_CACHE[key]


def _runs(s):
    from cardforge.glyphs import glyphify
    return glyphify(s)


def measure(s, size, style):
    img = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    w = 0
    for is_glyph, chunk in _runs(s):
        f = _font(size + 4, "glyph") if is_glyph else _font(size, style)
        w += img.textlength(chunk, font=f)
    return int(w)


def _draw_text(d, x, y, s, size, style, fill, anchor):
    if style == "title":
        import render_placeholders as rp
        s = s.translate(rp.TITLE_FOLD)
    w = measure(s, size, style)
    if anchor[0] == "m":
        x -= w / 2
    elif anchor[0] == "r":
        x -= w
    for is_glyph, chunk in _runs(s):
        f = _font(size + 4, "glyph") if is_glyph else _font(size, style)
        d.text((x, y), chunk, font=f, fill=fill, anchor="ls")
        x += d.textlength(chunk, font=f)


def render_page(page, dest):
    img = Image.open(PAGE_TEMPLATE).convert("RGB")
    if img.size != (PAGE_W, PAGE_H):
        img = img.resize((PAGE_W, PAGE_H), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    for op in page.ops:
        kind = op[0]
        if kind == "text":
            _, x, y, s, size, style, fill, anchor = op
            _draw_text(d, x, y, s, size, style, fill, anchor)
        elif kind == "rule":
            _, x0, y, x1 = op
            d.line([(x0, y), (x1, y)], fill=RULE, width=1)
            d.line([(x0 + 60, y + 5), (x1 - 60, y + 5)], fill=RULE, width=1)
        elif kind == "box":
            _, x, y = op
            d.rectangle([x, y, x + CB, y + CB], outline=INK, width=2)
        elif kind == "ring":
            _, cx, cy, derived = op
            r = RING // 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=INK,
                      width=1 if derived else 2)
            if derived:
                d.ellipse([cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5],
                          outline=RULE, width=1)
        elif kind == "line":
            _, x0, y, x1 = op
            d.line([(x0, y), (x1, y)], fill=RULE, width=2)
        elif kind == "panel":
            _, x0, y0, x1, y1 = op
            d.rounded_rectangle([x0, y0, x1, y1], radius=14, outline=TEAL, width=2)
    img.save(dest)
    return dest


def render_pages(out_dir=None):
    out_dir = out_dir or os.path.join(ROOT, "art", "faces")
    os.makedirs(out_dir, exist_ok=True)
    return [render_page(p, os.path.join(out_dir, PAGE_IDS[i] + ".png"))
            for i, p in enumerate(_pages())]


# ------------------------------------------------------------------- lua --
def layout():
    """Every page's fields, normalized to the page (u, v in 0..1; w/h too)."""
    out = []
    for p in _pages():
        fields = []
        for f in p.fields:
            g = dict(f)
            x, y, w, h = g.pop("x"), g.pop("y"), g.pop("w"), g.pop("h")
            g["u"] = round((x + w / 2) / PAGE_W, 5)
            g["v"] = round((y + h / 2) / PAGE_H, 5)
            g["w"] = round(w / PAGE_W, 5)
            g["h"] = round(h / PAGE_H, 5)
            fields.append(g)
        out.append({"page": p.n, "title": p.title, "fields": fields})
    return out


def _lua(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list):
        return "{ " + ", ".join(_lua(x) for x in v) + " }"
    if isinstance(v, dict):
        return "{ " + ", ".join("{} = {}".format(k, _lua(x)) for k, x in v.items()) + " }"
    raise TypeError(v)


def lua_script(page):
    """The token's LuaScript for one page: generated data + the library."""
    lay = layout()
    pg = lay[page - 1]
    lib = open(os.path.join(ROOT, "src", "tts", "campaign_log.lua"),
               encoding="utf-8").read()
    head = [
        "-- THE STILL HOUR — campaign log, page {} of {}. GENERATED by".format(page, len(lay)),
        "-- pipeline/campaign_log.py from the log layout; edit that, not this.",
        "PAGE = {}".format(page),
        "PAGE_COUNT = {}".format(len(lay)),
        "FIELDS = {",
    ]
    for f in pg["fields"]:
        head.append("  " + _lua(f) + ",")
    head.append("}")
    head.append("INVESTIGATORS = {")
    for iid, name in INVESTIGATORS:
        head.append("  {{ id = {}, name = {} }},".format(_lua(iid), _lua(name)))
    head.append("}")
    head.append("FACT_LAYER = {")
    for fid, _n, _d, layer, _s in FACTS:
        head.append("  [{}] = {},".format(_lua(fid), _lua(layer)))
    head.append("}")
    return "\n".join(head) + "\n\n" + lib


def main():
    paths = render_pages()
    print(json.dumps({"pages": [os.path.relpath(p, ROOT) for p in paths],
                      "fields": [len(p["fields"]) for p in layout()]}))


if __name__ == "__main__":
    main()
