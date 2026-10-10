"""The guide PDF and the campaign log pages as a first-time player meets them.

Guarded text ("Do not read until...") must never share a page with text read earlier, the printed
contents must name the pages the sections really start on, and the log's fields must not overlap,
leave the page frame, or overflow their labels. (docs/design/DATABASE_AUDIT.md, TXT-05/06/11/12.)"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import campaign_log as L  # noqa: E402

try:
    import reportlab  # noqa: F401
    HAVE_REPORTLAB = True
except ImportError:
    HAVE_REPORTLAB = False

pymupdf = pytest.importorskip("pymupdf", reason="PyMuPDF reads the built PDF back")


@pytest.fixture(scope="module")
def guide(tmp_path_factory):
    if not HAVE_REPORTLAB:
        pytest.skip("reportlab not installed")
    import build_guide_pdf as G
    path = str(tmp_path_factory.mktemp("guide") / "g.pdf")
    info = G.build(path, log_pages=False)
    doc = pymupdf.open(path)
    pages = [doc[i].get_text("text") for i in range(len(doc))]
    return {"info": info, "doc": doc, "pages": pages, "toc": doc.get_toc()}


def test_text_after_a_guard_starts_on_the_next_page(guide):
    guards = [i for i, t in enumerate(guide["pages"]) if re.search(r"Do not read until", t)]
    assert len(guards) >= 8, "the guide lost its 'Do not read until' guards"
    for i in guards:
        after = guide["pages"][i].split("Do not read until", 1)[1]
        after = after.split("\n", 2)[-1]            # the rest of the guard line
        assert "Resolution" not in after, "page %d: a resolution shares the page with its guard" % (i + 1)


def _body(page):
    """The text of a page between its running header and its page number, clear of the edge tab."""
    r = page.rect
    return page.get_text("text", clip=pymupdf.Rect(42, 40, r.width - 42, r.height - 45)).lstrip()


def test_each_district_and_section_starts_a_page(guide):
    starts = {title: page for _lvl, title, page in guide["toc"]}
    # Difficulty and Player Count is still the rules part: it may follow Campaign Rules on its page
    for name in ("New Rules", "Campaign Rules", "Campaign Setup",
                 "The Ambergrove Map", "Prologue — The First Hour", "The Loop", "Between Loops",
                 "The Districts", "The Lighthouse", "The Drowned Church", "The Sunken Road", "The Square",
                 "The Fairground", "The Almanac House", "Finale — The Last Hour",
                 "Appendix — Starting Decks", "Appendix — Encounter Deck Contents"):
        text = _body(guide["doc"][starts[name] - 1])
        assert text.lower().startswith(name.lower()), "%s does not open its page" % name


def test_what_you_saw_starts_its_own_page(guide):
    page = next(p for p, t in zip(guide["doc"], guide["pages"]) if "Salt on your tongue. The same lanterns" in " ".join(t.split()))
    assert _body(page).startswith("What You Saw"), "What You Saw shares a page with the Prologue's endings"


def test_every_page_names_its_part_in_its_header_and_on_an_edge_tab(guide):
    """Rules, setup, the Prologue, the loop, each district, the finale and the appendices each say so in
    a running header (and on a coloured tab at the page's edge), from the page their heading starts on
    to the page before the next one starts."""
    import build_guide_pdf as G
    starts = sorted((page, title) for _lvl, title, page in guide["toc"] if title != "Campaign Log")
    log_start = next((page for _lvl, title, page in guide["toc"] if title == "Campaign Log"),
                     len(guide["pages"]) + 1)
    districts = ("The Lighthouse", "The Drowned Church", "The Sunken Road", "The Square",
                 "The Fairground", "The Almanac House")
    expected, label = {}, None
    for i, (page, title) in enumerate(starts):
        label = ("DISTRICT \u2014 " + title.upper()) if title in districts else \
            G.part_label(title.upper()) or label
        end = starts[i + 1][0] if i + 1 < len(starts) else log_start
        for n in range(page, end):
            expected[n] = label
    expected.pop(1, None)                        # the title page carries no header
    assert len(expected) >= 30
    squash = lambda t: re.sub(r"\s+", "", t)
    for n, label in expected.items():
        page = guide["doc"][n - 1]
        head = squash(" ".join(w[4] for w in page.get_text("words") if w[1] < 60))
        assert squash(label) in head, "page %d header should say %s, not %r" % (n, label, head)
        edge = [w for w in page.get_text("words")
                if (w[2] > page.rect.width - 40 if n % 2 else w[0] < 40) and 60 < w[1] < 400]
        tab = squash("".join(w[4] for w in edge))
        assert squash(label.split(" \u2014 ")[-1]) in tab or squash(label.split(" \u2014 ")[-1])[::-1] in tab, \
            "page %d: the edge tab should read %s, not %r" % (n, label, tab)


def test_printed_contents_name_the_real_pages(guide):
    first = guide["pages"][0]
    entries = {title: page for _lvl, title, page in guide["toc"]}
    assert len(entries) >= 15
    # "<title>\n<page>" pairs as the contents prints them
    for title, page in entries.items():
        if title == "Campaign Log":
            continue
        assert re.search(r"%s\s*\n\s*%d\s*\n" % (re.escape(title), page), first), \
            "contents: %s should read page %d" % (title, page)


def test_the_later_interlude_stories_wait_on_their_own_pages(guide):
    # each later story sits alone: the page that holds one holds no other story
    markers = ("The Shape of the Hour (when Part II begins)", "After the fourth and fifth loops",
               "Age stories. The first time any investigator", "Before the finale (once your log records")
    holders = [[m for m in markers if m in " ".join(t.split())] for t in guide["pages"]]
    assert sum(len(h) for h in holders) == len(markers), "a later story went missing from the guide"
    for found in holders:
        assert len(found) <= 1, "two later stories share a page: %s" % found


def test_the_static_token_is_a_word_not_markup(guide):
    # only the two sentences that name the Control token's "[static]" button may print it
    n = sum(t.count("[static]") for t in guide["pages"])
    assert n <= 2, "[static] prints %d times; say 'the Static token'" % n


# ------------------------------------------------------------------ log --
def _boxes(page):
    W, H = L.PAGE_W, L.PAGE_H
    for f in L.layout()[page - 1]["fields"]:
        yield f, ((f["u"] - f["w"] / 2) * W, (f["v"] - f["h"] / 2) * H,
                  (f["u"] + f["w"] / 2) * W, (f["v"] + f["h"] / 2) * H)


@pytest.mark.parametrize("page", [1, 2, 3])
def test_log_fields_do_not_overlap_or_leave_the_frame(page):
    boxes = list(_boxes(page))
    for i, (fa, a) in enumerate(boxes):
        assert a[3] <= 1600 and a[2] <= 1195 and a[0] >= 80, \
            "page %d: %s leaves the text frame %s" % (page, fa["k"], [round(v) for v in a])
        for fb, b in boxes[i + 1:]:
            ox, oy = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
            assert not (ox > 1 and oy > 1), "page %d: %s overlaps %s" % (page, fa["k"], fb["k"])


def test_hidden_name_labels_fit_their_fields():
    for page in (1, 2, 3):
        for f, (x0, y0, x1, y1) in _boxes(page):
            if f.get("t") != "rv":
                continue
            font_px = f["h"] * L.PAGE_H / 2.0
            est = len(f["rt"]) * 0.455 * font_px            # an average letter of a button label
            assert est <= (x1 - x0) * 1.08, "page %d: label of %s is wider than its field" % (page, f["k"])
            assert "[" not in f["rt"], "page %d: %s shows markup a button label cannot draw" % (page, f["k"])


def test_standing_rules_show_under_their_choice_once_ticked():
    fields = {f["k"]: f for f in L.layout()[2]["fields"]}
    for (choice, side), text in L.STANDING.items():
        f = fields["%s_%ss" % (choice, side)]
        assert f["t"] == "rv" and f["rw"] == "%s_%s" % (choice, side) and f["rt"].endswith(text)


def test_every_victory_name_stays_hidden_until_claimed():
    fields = {f["k"]: f for f in L.layout()[1]["fields"]}
    for eid, _name, _where, _vic in L.NAMED + L.VICTORY_ENEMIES + L.VICTORY_LOCATIONS:
        f = fields["vr:" + eid]
        assert f["t"] == "rv" and f["rw"] == "v:" + eid


# -------------------------------------------------------------- appendix --
def _deck_lists_in_the_guide():
    from collections import Counter
    import build_guide_pdf as G
    text = open(G.SOURCE, encoding="utf-8").read()
    appendix = text.split("## APPENDIX — STARTING DECKS", 1)[1].split("\n## ", 1)[0]
    decks = {}
    for m in re.finditer(r"^\*\*(.+?) \((\w+)\)\.\*\* \*(.+?)\.\* (.+)$", appendix, flags=re.M):
        cards = Counter()
        for entry in re.split(r", (?=\d )", m.group(4).rstrip(".")):
            qty, name = entry.split(" ", 1)
            cards[name.strip()] += int(qty)
        decks[m.group(1)] = cards
    return decks


def _deck_lists_in_the_document():
    from collections import Counter
    text = open(os.path.join(ROOT, "docs", "STARTER_DECKS.md"), encoding="utf-8").read()
    decks = {}
    for part in text.split("\n## ")[1:]:
        head, body = part.split("\n", 1)
        cards = Counter()
        for qty, name in re.findall(r"^\| (\d) \| (.+?) \| (?:Asset|Event|Skill) \|", body, flags=re.M):
            cards[name] += int(qty)
        decks[re.sub(r" \(\w+\)$", "", head.strip())] = cards
    return decks


def test_the_guides_starting_decks_are_the_starter_decks_document():
    guide, doc = _deck_lists_in_the_guide(), _deck_lists_in_the_document()
    assert len(guide) == 5 and set(guide) == set(doc), (sorted(guide), sorted(doc))
    for name in doc:
        assert guide[name] == doc[name], name
        assert sum(doc[name].values()) == 30, name
        assert max(doc[name].values()) <= 2, name


def test_no_guard_line_sits_alone_in_the_second_column(guide):
    """A "Do not read until..." line ends what is read before it, so it sits under that text in the first
    column, never alone at the top of the second (The Loop's page, 2026-10-10)."""
    for i, page in enumerate(guide["doc"]):
        blocks = page.get_text("blocks")
        half = page.rect.width / 2
        for b in blocks:
            if "Do not read until" in b[4] and b[0] >= half:
                above = [x for x in blocks if x[0] >= half and x[3] <= b[1] + 1 and x is not b
                         and x[1] > 30 and x[4].strip()]
                assert above, "page %d: the guard line sits alone at the top of the second column" % (i + 1)
