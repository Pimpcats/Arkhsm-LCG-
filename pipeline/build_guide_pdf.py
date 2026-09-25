#!/usr/bin/env python3
"""build_guide_pdf.py — typeset the campaign guide as the SCED CampaignGuide PDF.

Source: docs/design/THE_STILL_HOUR_player_guide.md, the player-facing guide
laid out like an official one (intro boxes, numbered setup, "Do not read
until..." dividers, resolution boxes in ```resolution fences). The design
reference it is drawn from is THE_STILL_HOUR_campaign_guide_v0_5.md. Look: the Strange Eons Arkham plugin's own
campaign-guide component (GuideLetter.js / AHLCG-GuideLetter.settings), laid
out the way it lays a guide page out:

  * pages      AHLCG-GuideLetterTitle (first page: the Arkham banner, the
               campaign name in its Name region, "Campaign Guide" in its Label
               region) and AHLCG-GuideLetterEmpty (every other page; mirrored
               on even pages, as drawGuideTemplateLetter does), 1275x1650 px =
               US Letter at 150 dpi
  * columns    BodyLeft/BodyRight{Title,Empty} regions; page number in the
               PageOdd/PageEven disc
  * headers    <section>/<header> styles: title family, 16.3 / 14 pt, #415a55
  * boxes      read-aloud text in the plugin's story box (AHLCG-BoxSA*),
               endings/resolutions in its resolution box (AHLCG-BoxRes*),
               notes in its interlude box (AHLCG-BoxInt*): top image, the
               1-px line stretched, the top mirrored as the bottom
  * type       Arkhamic (title family), Crimson Pro (body, the cards'
               body face), the Arkham
               icon font for [wil]/[int]/[com]/[agi]/[action] markup
The campaign log pages (pipeline/campaign_log.py) close the guide, like the
log printed at the back of an official guide.

Designer-facing asides (doc cross-references, change-order tags, design
notes' meta remarks) are stripped; rules text is kept verbatim.

Output is byte-stable (reportlab invariant mode), so the hosted URL's
content hash only changes when the guide does.

Run: python3 pipeline/build_guide_pdf.py [--out dist/guide/...pdf]
Needs: reportlab
"""
import argparse
import hashlib
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, "docs", "design", "THE_STILL_HOUR_player_guide.md")
OUT = os.path.join(ROOT, "dist", "guide", "the_still_hour_campaign_guide.pdf")
GUIDE_DIR = os.path.join(ROOT, "assets", "frames", "se", "guide")
FONTS = os.path.join(ROOT, "assets", "fonts")
FACES = os.path.join(ROOT, "art", "faces")
LOG_PAGES = ["sthr-log-page1", "sthr-log-page2", "sthr-log-page3"]

PX = 72.0 / 150.0           # template pixels -> PDF points
PAGE_W, PAGE_H = 1275 * PX, 1650 * PX

# AHLCG-GuideLetter.settings regions (x, y, w, h in template px)
R_NAME = (392, 276, 490, 46)
R_LABEL = (447, 316, 382, 37)
R_LEFT_TITLE = (82, 417, 537, 1173)
R_RIGHT_TITLE = (653, 417, 537, 1173)
R_LEFT = (82, 80, 537, 1520)
R_RIGHT = (653, 80, 537, 1520)
R_PAGE_ODD = (621, 1600, 30, 32)
R_PAGE_EVEN = (623, 1600, 30, 32)

TEAL = "#415a55"            # GuideSection / GuideHeader / GuideBoxBullet colour
RES_RED = "#63251d"         # ResHeader-style
INK = "#000000"

ICONS = {"[wil]": "A", "[int]": "B", "[com]": "C", "[agi]": "D",
         "[action]": "E", "[free]": "F", "[fast]": "F", "[reaction]": "G",
         "[skull]": "M", "[cultist]": "N", "[tablet]": "R", "[elder]": "Q",
         "[autofail]": "O", "[elderthing]": "H", "[unique]": "S",
         "[perinv]": "T", "[wild]": "U"}


# ------------------------------------------------------------ source text --
def clean(md):
    """Strip designer-facing asides; keep every rule and story beat."""
    s = md.replace("\r", "")
    s = re.sub(r"\s*\*\(This refines[^)]*\)\*", "", s)
    s = re.sub(r"\s*Consistent with [^*\n]*", "", s)
    s = re.sub(r"^### v0\.\d+ · ", "### ", s, flags=re.M)
    s = re.sub(r"\s*[—,;]?\s*`[^`\n]*v0\.\d[^`\n]*`", "", s)
    s = re.sub(r",?\s*\bCO-00\d\b", "", s)
    s = re.sub(r",?\s*from\s*\)", ")", s)
    s = re.sub(r"\s*\(\s*[,;]?\s*\)", "", s)
    s = s.replace("`memoryCost`", "listed Memory cost")
    s = s.replace("**Design note.**", "**Note.**")
    s = s.replace(" — the finale you asked for", "")
    s = re.sub(r"^\*All values provisional[^\n]*\n?", "", s, flags=re.M)
    s = re.sub(r"(?<!`)`(?!`)", "", s)          # inline code marks, not ``` fences
    s = s.replace("⅓", "one-third of the")
    return s


def inline(text, size=None):
    """Markdown emphasis + icon markup -> reportlab paragraph markup."""
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    for tok, letter in ICONS.items():
        t = t.replace(tok, '<font name="AHIcons">{}</font>'.format(letter))
    t = t.replace("[static]", "<b>[static]</b>")
    return t


def title_case(s):
    small = {"a", "an", "and", "of", "the", "to", "in", "on", "at", "by", "for"}
    roman = re.compile(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)$")
    out = []
    for i, w in enumerate(s.split(" ")):
        core = w.strip("—()\"'.,:")
        if not core or not core.isupper():
            out.append(w)
        elif roman.match(core):
            out.append(w)
        elif (i > 0 and core.lower() in small and out
              and not re.match(r"^(?:\d+(?:\.\d+)*\.?|—|.*[:—])$", out[-1])):
            out.append(w.lower())
        else:
            out.append(w[:1] + w[1:].lower() if w[:1].isalpha() else
                       w[:2] + w[2:].lower())
    return " ".join(out)


def parse(md):
    """Markdown -> a flat list of (kind, payload) blocks."""
    lines = clean(md).split("\n")
    blocks, i = [], 0
    while i < len(lines):
        ln = lines[i]
        st = ln.strip()
        if not st or st == "---":
            i += 1
            continue
        if st.startswith("```resolution"):
            # a resolution box: header line, then ordinary markdown inside
            head = st[len("```resolution"):].strip()
            inner = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                inner.append(lines[i])
                i += 1
            blocks.append(("res", (head, parse("\n".join(inner)))))
            i += 1
            continue
        if st.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(("map", code))
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", st)
        if m:
            blocks.append(("h%d" % len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        if st.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            # a bare ">" line is a paragraph break inside the same box
            paras, cur = [], []
            for q in quote:
                if q:
                    cur.append(q)
                elif cur:
                    paras.append(" ".join(cur))
                    cur = []
            if cur:
                paras.append(" ".join(cur))
            blocks.append(("quote", "\n\n".join(paras)))
            continue
        if st.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.match(r"^:?-+:?$", c) for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", ln)
        if m:
            items = []
            while i < len(lines):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if not m:
                    if lines[i].strip() and lines[i].startswith("  ") and items:
                        items[-1] = (items[-1][0], items[-1][1], items[-1][2] + " " + lines[i].strip())
                        i += 1
                        continue
                    break
                items.append((len(m.group(1)) // 2, m.group(2), m.group(3)))
                i += 1
            blocks.append(("list", items))
            continue
        para = [st]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^\s*(#|>|\||```|[-*]\s|\d+\.\s|---)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        blocks.append(("p", " ".join(para)))
    return blocks


# ------------------------------------------------------------------ fonts --
def register_fonts(tmp):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    pdfmetrics.registerFont(TTFont("Arkhamic", os.path.join(FONTS, "Arkhamic_v2.2.ttf")))
    pdfmetrics.registerFont(TTFont("AHIcons", os.path.join(FONTS, "ArkhamFontWithCodex.ttf")))
    pdfmetrics.registerFont(TTFont("Bolton", os.path.join(FONTS, "BoltonBold.ttf")))
    # Crimson Pro (OFL, committed static TTFs) is the cards' body face too
    body = {"Body": "CrimsonPro-Regular", "Body-Italic": "CrimsonPro-Italic",
            "Body-Bold": "CrimsonPro-Bold", "Body-BoldItalic": "CrimsonPro-BoldItalic"}
    try:
        for name, stem in body.items():
            pdfmetrics.registerFont(TTFont(name, os.path.join(FONTS, stem + ".ttf")))
        fam = ("Body", "Body-Bold", "Body-Italic", "Body-BoldItalic")
    except Exception as e:
        print("note: body font falls back to Times ({})".format(e), file=sys.stderr)
        fam = ("Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic")
    addMapping(fam[0], 0, 0, fam[0])
    addMapping(fam[0], 1, 0, fam[1])
    addMapping(fam[0], 0, 1, fam[2])
    addMapping(fam[0], 1, 1, fam[3])
    return fam[0]


# ----------------------------------------------------------------- layout --
def build(out=OUT, source=SOURCE, log_pages=True):
    from reportlab import rl_config
    rl_config.invariant = 1
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable,
                                    Frame, KeepTogether, NextPageTemplate,
                                    PageBreak, PageTemplate, Paragraph, Spacer,
                                    Table, TableStyle)
    from reportlab.lib.utils import ImageReader
    from PIL import Image

    # a fixed scratch dir: reportlab names image XObjects from their source
    # path, so a random temp dir would make every build differ
    tmp = os.path.join(tempfile.gettempdir(), "sthr_guide_build")
    os.makedirs(tmp, exist_ok=True)
    body = register_fonts(tmp)

    def frame_px(r, ident):
        x, y, w, h = r
        return Frame(x * PX, PAGE_H - (y + h) * PX, w * PX, h * PX, id=ident,
                     leftPadding=4, rightPadding=4, topPadding=0, bottomPadding=0)

    tpl_title = os.path.join(GUIDE_DIR, "AHLCG-GuideLetterTitle.jpg")
    tpl_empty = os.path.join(GUIDE_DIR, "AHLCG-GuideLetterEmpty.jpg")
    mirrored = os.path.join(tmp, "empty_mirror.jpg")
    Image.open(tpl_empty).transpose(Image.FLIP_LEFT_RIGHT).save(mirrored, quality=90)
    campaign = "The Still Hour"

    def page_bg(c, doc, title=False):
        n = doc.page
        if title:
            c.drawImage(tpl_title, 0, 0, PAGE_W, PAGE_H)
            c.setFillColor(colors.white)
            for (x, y, w, h), text, size in ((R_NAME, campaign, 20.0),
                                             (R_LABEL, "Campaign Guide", 16.0)):
                c.setFont("Arkhamic", size)
                c.drawCentredString((x + w / 2) * PX, PAGE_H - (y + h * 0.78) * PX, text)
            return
        c.drawImage(mirrored if n % 2 == 0 else tpl_empty, 0, 0, PAGE_W, PAGE_H)
        x, y, w, h = R_PAGE_EVEN if n % 2 == 0 else R_PAGE_ODD
        c.setFillColor(colors.black)
        c.setFont("Bolton", 12)
        c.drawCentredString((x + w / 2) * PX, PAGE_H - (y + h * 0.72) * PX, str(n))

    def log_bg(c, doc):
        i = min(doc._log_i, len(doc._log_pages) - 1)
        doc._log_i += 1
        c.drawImage(doc._log_pages[i], 0, 0, PAGE_W, PAGE_H)

    doc = BaseDocTemplate(out, pagesize=(PAGE_W, PAGE_H), title="The Still Hour — Campaign Guide",
                          author="The Still Hour (fan campaign)", subject="Campaign Guide",
                          creator="pipeline/build_guide_pdf.py")
    doc.addPageTemplates([
        PageTemplate("title", [frame_px(R_LEFT_TITLE, "tl"), frame_px(R_RIGHT_TITLE, "tr")],
                     onPage=lambda c, d: page_bg(c, d, True)),
        PageTemplate("body", [frame_px(R_LEFT, "l"), frame_px(R_RIGHT, "r")],
                     onPage=lambda c, d: page_bg(c, d)),
        PageTemplate("log", [Frame(0, 0, PAGE_W, PAGE_H, id="log")], onPage=log_bg),
    ])

    S = {
        "p": ParagraphStyle("p", fontName=body, fontSize=9.4, leading=11.6,
                            alignment=TA_JUSTIFY, spaceAfter=4.5, textColor=INK),
        "intro": ParagraphStyle("intro", fontName=body, fontSize=10, leading=12.6,
                                alignment=TA_CENTER, spaceAfter=6, textColor=INK),
        "section": ParagraphStyle("section", fontName="Arkhamic", fontSize=16.3,
                                  leading=19, textColor=TEAL, spaceBefore=8,
                                  spaceAfter=5, alignment=TA_CENTER),
        "header": ParagraphStyle("header", fontName="Arkhamic", fontSize=14,
                                 leading=16.5, textColor=TEAL, spaceBefore=7,
                                 spaceAfter=3),
        "sub": ParagraphStyle("sub", fontName="Arkhamic", fontSize=12,
                              leading=14, textColor=TEAL, spaceBefore=5, spaceAfter=2),
        "quote": ParagraphStyle("quote", fontName=body, fontSize=9.4, leading=11.6,
                                alignment=TA_JUSTIFY, textColor=INK),
        "cell": ParagraphStyle("cell", fontName=body, fontSize=7.9, leading=9.3),
        "cellh": ParagraphStyle("cellh", fontName="Arkhamic", fontSize=9.5,
                                leading=11, textColor=TEAL),
        "reshead": ParagraphStyle("reshead", fontName="Arkhamic", fontSize=12,
                                  leading=14, textColor=RES_RED, spaceAfter=2),
        "noread": ParagraphStyle("noread", fontName=body, fontSize=10.2,
                                 leading=12.6, alignment=TA_CENTER,
                                 textColor=RES_RED, spaceBefore=8, spaceAfter=8),
    }

    class GuideBox(Flowable):
        """Content framed in one of the plugin's guide boxes (top image, the
        1-px line image stretched, top mirrored as bottom)."""

        def __init__(self, kind, flowables, pad=(16, 13)):
            super().__init__()
            self.kind, self.content, self.pad = kind, flowables, pad
            top = {"sa": "AHLCG-BoxSA", "res": "AHLCG-BoxRes",
                   "int": "AHLCG-BoxInt"}[kind]
            line = {"sa": "AHLCG-BoxSALine", "res": "AHLCG-BoxResLine",
                    "int": "AHLCG-BoxIntLine"}[kind]
            self.top = ImageReader(os.path.join(GUIDE_DIR, top + ".png"))
            self.bot = ImageReader(Image.open(os.path.join(GUIDE_DIR, top + ".png"))
                                   .transpose(Image.FLIP_TOP_BOTTOM))
            self.line = ImageReader(os.path.join(GUIDE_DIR, line + ".png"))
            tw, th = self.top.getSize()
            self.ar = th / float(tw)

        def wrap(self, aw, ah):
            self.width = aw
            px, py = self.pad
            self.sizes = [f.wrap(aw - 2 * px, ah) for f in self.content]
            self.inner = sum(h for _, h in self.sizes) + sum(
                f.getSpaceAfter() for f in self.content[:-1])
            self.height = self.inner + 2 * py
            return aw, self.height

        def split(self, aw, ah):
            return []

        def draw(self):
            c = self.canv
            w, h = self.width, self.height
            cap = w * self.ar
            for img, y0, y1 in ((self.top, h / 2.0, h), (self.bot, 0, h / 2.0)):
                c.saveState()
                p = c.beginPath()
                p.rect(0, y0, w, y1 - y0)
                c.clipPath(p, stroke=0, fill=0)
                c.drawImage(img, 0, (h - cap) if img is self.top else 0, w, cap,
                            mask="auto")
                c.restoreState()
            if h > 2 * cap:
                c.drawImage(self.line, 0, cap, w, h - 2 * cap, mask="auto")
            px, py = self.pad
            y = h - py
            for f, (_, fh) in zip(self.content, self.sizes):
                y -= fh
                f.drawOn(c, px, y)
                y -= f.getSpaceAfter()

    class MapFlowable(Flowable):
        """The district map drawn from the guide's ASCII diagram: names become
        plaques, '|' and '—' become connections."""

        def __init__(self, code):
            super().__init__()
            self.nodes, self.edges = self._parse(code)

        @staticmethod
        def _parse(code):
            rows = [ln for ln in code]
            nodes = []
            for r, ln in enumerate(rows):
                for m in re.finditer(r"[A-Z][A-Z' ]*[A-Z]", ln):
                    nodes.append({"name": m.group(0).strip(), "row": r,
                                  "col": (m.start() + m.end()) / 2.0,
                                  "span": (m.start(), m.end())})
            edges = set()
            for r, ln in enumerate(rows):
                for m in re.finditer(r"\|", ln):
                    above = [n for n in nodes if n["row"] < r and
                             n["span"][0] <= m.start() <= n["span"][1]]
                    below = [n for n in nodes if n["row"] > r and
                             n["span"][0] <= m.start() <= n["span"][1]]
                    if above and below:
                        a = max(above, key=lambda n: n["row"])
                        b = min(below, key=lambda n: n["row"])
                        edges.add((a["name"], b["name"]))
                same = sorted([n for n in nodes if n["row"] == r], key=lambda n: n["col"])
                for a, b in zip(same, same[1:]):
                    if "—" in ln[a["span"][1]:b["span"][0]]:
                        edges.add((a["name"], b["name"]))
            return nodes, sorted(edges)

        def wrap(self, aw, ah):
            self.width = aw
            rows = max(n["row"] for n in self.nodes) + 1
            self.height = rows * 13 + 10
            return aw, self.height

        def draw(self):
            c = self.canv
            cols = [n["col"] for n in self.nodes]
            lo, hi = min(cols), max(cols)
            rows = max(n["row"] for n in self.nodes) + 1
            pos = {}
            for n in self.nodes:
                x = 36 + (n["col"] - lo) / max(1.0, hi - lo) * (self.width - 72)
                y = self.height - 8 - n["row"] * (self.height - 16) / max(1, rows - 1)
                pos[n["name"]] = (x, y)
            c.setStrokeColor(colors.HexColor(TEAL))
            c.setLineWidth(1.2)
            for a, b in self.edges:
                c.line(*pos[a], *pos[b])
            for n in self.nodes:
                x, y = pos[n["name"]]
                label = title_case(n["name"])
                c.setFont("Arkhamic", 8.6)
                w = c.stringWidth(label, "Arkhamic", 8.6) + 8
                c.setFillColor(colors.HexColor("#e9e1cf"))
                c.setStrokeColor(colors.HexColor(TEAL))
                c.roundRect(x - w / 2, y - 6, w, 12, 3, stroke=1, fill=1)
                c.setFillColor(colors.HexColor("#1e2a28"))
                c.drawCentredString(x, y - 2.8, label)

    story = []
    blocks = parse(open(source, encoding="utf-8").read())
    first_h1 = True
    for kind, payload in blocks:
        if kind == "h1":
            if first_h1:
                first_h1 = False
                continue                    # the name is printed on the banner
            story.append(Paragraph(inline(title_case(payload)), S["section"]))
        elif kind == "h2":
            text = payload
            if re.search(r"PROLOGUE|THE DISTRICTS|FINALE", text):
                story.append(PageBreak())
            elif re.search(r"THE LOOP|BETWEEN LOOPS", text):
                story.append(CondPageBreak(3.2 * 72))
            else:
                story.append(CondPageBreak(1.6 * 72))
            story.append(Paragraph(inline(title_case(text)), S["section"]))
        elif kind == "h3":
            if not story:
                story.append(Paragraph("<i>" + inline(payload) + "</i>", S["intro"]))
            else:
                story.append(CondPageBreak(1.3 * 72))
                story.append(Paragraph(inline(title_case(payload)), S["header"]))
        elif kind == "h4":
            story.append(Paragraph(inline(title_case(payload)), S["sub"]))
        elif kind == "p":
            if payload.strip("*").startswith("Do not read"):
                story.append(Paragraph("<b>" + inline(payload.strip("*")) + "</b>",
                                       S["noread"]))
                continue
            style = S["intro"] if len(story) < 2 and payload.startswith("*") else S["p"]
            story.append(Paragraph(inline(payload), style))
        elif kind == "res":
            head, inner_blocks = payload
            inner = [Paragraph(inline(head), S["reshead"])]
            for ik, ip in inner_blocks:
                if ik == "quote":
                    inner.append(Paragraph("<i>" + inline(ip) + "</i>",
                                           ParagraphStyle("rs", parent=S["quote"],
                                                          spaceAfter=4)))
                elif ik == "list":
                    for depth, marker, text in ip:
                        # a choice's options sit one level in, under an en dash
                        inner.append(Paragraph(
                            inline(text),
                            ParagraphStyle("rli", parent=S["quote"],
                                           leftIndent=11 + depth * 11,
                                           bulletIndent=1 + depth * 11, spaceAfter=2),
                            bulletText="–" if depth else "•"))
                elif ik == "p":
                    inner.append(Paragraph(inline(ip), ParagraphStyle(
                        "rp", parent=S["quote"], spaceAfter=3)))
            story.append(GuideBox("res", inner))
            story.append(Spacer(1, 5))
        elif kind == "quote":
            text = payload
            if text.startswith("**Note.**"):
                story.append(GuideBox("int", [Paragraph(inline(text), S["quote"])], pad=(20, 12)))
            else:
                qs = ParagraphStyle("qp", parent=S["quote"], spaceAfter=5)
                story.append(GuideBox("sa", [Paragraph(inline(t), qs)
                                             for t in text.split("\n\n")]))
            story.append(Spacer(1, 5))
        elif kind == "list":
            for depth, marker, text in payload:
                bullet = marker if marker[0].isdigit() else "•"
                st = ParagraphStyle("li", parent=S["p"], leftIndent=12 + depth * 10,
                                    bulletIndent=2 + depth * 10, spaceAfter=2.5,
                                    bulletFontName=body if bullet != "•" else body,
                                    bulletColor=colors.HexColor(TEAL))
                story.append(Paragraph(inline(text), st, bulletText=bullet))
            story.append(Spacer(1, 3))
        elif kind == "table":
            head, rows = payload[0], payload[1:]
            if "Resolution" in head[-1] and "Condition" in head:
                for r in rows:
                    tag, cond, res = r[0], r[1], r[2]
                    name = re.match(r"\*\*(.+?)\*\*\s*(.*)$", res)
                    title, rest = (name.group(1).rstrip("."), name.group(2)) if name else (res, "")
                    inner = [Paragraph("{} — {}".format(tag, inline(title)), S["reshead"]),
                             Paragraph("<i>If:</i> " + inline(cond),
                                       ParagraphStyle("if", parent=S["quote"], spaceAfter=3))]
                    if rest:
                        inner.append(Paragraph(inline(rest), S["quote"]))
                    story.append(GuideBox("res", inner))
                    story.append(Spacer(1, 4))
                continue
            data = [[Paragraph(inline(h), S["cellh"]) for h in head]] + \
                   [[Paragraph(inline(c), S["cell"]) for c in r] for r in rows]
            aw = R_LEFT[2] * PX - 8
            widths = [aw * 0.36, aw * 0.24, aw * 0.40] if len(head) == 3 else \
                [aw / len(head)] * len(head)
            t = Table(data, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.9, colors.HexColor(TEAL)),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#b9ab94")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(t)
            story.append(Spacer(1, 6))
        elif kind == "map":
            story.append(KeepTogether([MapFlowable(payload), Spacer(1, 6)]))

    # after the title page, every page uses the plain template
    story.insert(0, NextPageTemplate("body"))

    doc._log_pages, doc._log_i = [], 0
    if log_pages:
        for pid in LOG_PAGES:
            src = os.path.join(FACES, pid + ".png")
            if os.path.exists(src):
                jpg = os.path.join(tmp, pid + ".jpg")
                Image.open(src).convert("RGB").save(jpg, "JPEG", quality=86)
                doc._log_pages.append(jpg)
    if doc._log_pages:
        story.append(NextPageTemplate("log"))
        story.append(PageBreak())
        for i in range(len(doc._log_pages)):
            story.append(Spacer(1, 1))
            if i < len(doc._log_pages) - 1:
                story.append(PageBreak())

    os.makedirs(os.path.dirname(out), exist_ok=True)
    doc.build(story)
    data = open(out, "rb").read()
    return {"out": os.path.relpath(out, ROOT), "pages": doc.page,
            "bytes": len(data), "sha1": hashlib.sha1(data).hexdigest()[:10]}


def main():
    if os.environ.get("PYTHONHASHSEED") != "0":
        # font subsetting walks sets; pin hash order so builds are byte-stable
        import subprocess
        env = dict(os.environ, PYTHONHASHSEED="0")
        sys.exit(subprocess.call([sys.executable] + sys.argv, env=env))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--no-log", action="store_true",
                    help="leave the campaign-log pages off the end")
    a = ap.parse_args()
    import json
    print(json.dumps(build(a.out, log_pages=not a.no_log)))


if __name__ == "__main__":
    main()
