"""Arkham glyph font support (assets/fonts/ArkhamFontWithCodex.ttf).

The font maps 22 Arkham symbols onto plain letters A-V (legend:
assets/fonts/character_chart.png). This module is the single source of truth
for that mapping and converts the design docs' `[wil]`-style markup — the exact
markup used throughout cards_v0.2 / encounter_v0.4 — into glyph letters for
rendering with the font (Pillow placeholder faces, Strange Eons text when the
plugin's own tags aren't used).

CONFIRMED mappings were read off the chart; UNCONFIRMED ones are best guesses
the owner should verify against the chart once (they render regardless — worst
case a wrong symbol shows until corrected here).
"""
import os

FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "fonts", "ArkhamFontWithCodex.ttf")

# design-doc markup -> font letter
MARKUP = {
    # skills (chart row 1: head/tome/fist/winged boot) — confirmed
    "[wil]": "A", "[int]": "B", "[com]": "C", "[agi]": "D",
    # triggers — E ">>>" action, F lightning fast/free, G curved-arrow reaction
    "[action]": "E", "[free]": "F", "[fast]": "F", "[reaction]": "G",
    # chaos tokens — M skull, N hooded cultist, R broken tablet,
    # Q star sigil (elder sign), O tentacle swirl (auto-fail)  — confirmed
    "[skull]": "M", "[cultist]": "N", "[tablet]": "R",
    "[elder]": "Q", "[autofail]": "O",
    # UNCONFIRMED (verify vs chart): H rune-in-square = elder thing?,
    # P insectile = elder thing alt?; using H for now.
    "[elderthing]": "H",
    # misc — S small star (unique), T fedora head (per-investigator),
    # U question mark (wild), V open book (the Codex)
    "[unique]": "S", "[perinv]": "T", "[wild]": "U", "[codex]": "V",
    # campaign-custom token: no glyph in this font — rendered as text
    "[static]": None,
}

# Chart letters believed to be class icons (UNCONFIRMED — owner to verify):
# I raven(?), J shield-and-star (Guardian?), K eye-in-triangle (Seeker or
# Mystic?), L globe (Seeker?). Not wired into MARKUP until confirmed.
UNCONFIRMED_CLASS_GLYPHS = {"I": "?", "J": "Guardian?", "K": "Seeker/Mystic?", "L": "Seeker?"}


def glyphify(text):
    """Split marked-up text into runs: [(is_glyph, chunk), ...].

    Glyph runs are font letters to draw with the Arkham font; text runs draw
    with a normal font. Unknown/unglyphable markup (e.g. [static]) stays as
    literal text so nothing is silently dropped.
    """
    runs = []
    buf = ""
    i = 0
    while i < len(text):
        if text[i] == "[":
            close = text.find("]", i)
            if close != -1:
                token = text[i:close + 1]
                letter = MARKUP.get(token)
                if letter:
                    if buf:
                        runs.append((False, buf))
                        buf = ""
                    runs.append((True, letter))
                    i = close + 1
                    continue
        buf += text[i]
        i += 1
    if buf:
        runs.append((False, buf))
    return runs


def statline_runs(wil, int_, com, agi):
    """An investigator's statline as glyphify-style runs: '3[wil] 2[int] ...'"""
    runs = []
    for value, token in ((wil, "[wil]"), (int_, "[int]"), (com, "[com]"), (agi, "[agi]")):
        runs.append((False, "{} ".format(value)))
        runs.append((True, MARKUP[token]))
        runs.append((False, "   "))
    return runs[:-1]
