# Fonts — the official Arkham LCG text stack

Analysis of every font in this project: what it is, where the real cards use
it, license, and how the renderer picks it. The renderer's order of
preference is in `pipeline/render_placeholders.py` (`TITLE_FONT_CANDIDATES`,
`BODY_FONTS`); per-card manual overrides live in
`campaigns/still_hour/font_overrides.json` (set from the card editor's font
dropdowns).

| Font | Role on real cards | License | In git? |
|---|---|---|---|
| **Arkhamic** (`Arkhamic.ttf`) | Card titles / class headers / scenario names / **cost numbers** — the community's extension of Teutonic with extra Latin glyphs (github.com/javnik36/arkhamic, "officially" circulated via the Mythos Busters community). Full ASCII coverage (complete alphabet, digits, punctuation). | OFL 1.1 + GPLv3+FE — redistributable | **yes** (vendored from the element kit; Setup tab installer remains as a refresher) |
| **Teutonic** (`Teutonic.ttf`) | Same face as above, the original by Peter Wiegel — what FFG's titling is based on. Fallback when Arkhamic isn't installed. | OFL (see `Teutonic-OFL.txt`) | **yes** |
| **Bolton** (`Bolton.ttf`, `BoltonBold.ttf`) | The **big stat numerals** — enemy fight/health/evade, investigator skill values, health/sanity chit numbers, asset level. By Paul Lloyd (GreyWolf WebWorks), freeware; circulated with the community card-building kits. No em-dash glyph, so "—" stat blanks fall back to the body font. | freeware (Paul Lloyd) | **yes** |
| **Nimbus Roman No9 L** (`NimbusRomNo9L-Reg/RegIta/Med/MedIta.otf`) | **The default body font** — rules text, traits, flavor, keywords — the complete family (regular / italic / bold / bold-italic) from the element kit. Ships in-repo so every card renders one consistent serif with real bold + italic. | URW / freely redistributable (GhostScript AFPL, part of the standard free font set) | **yes** (vendored from the element kit) |
| **Arno Pro** (`ArnoPro*.otf`) | The body font on official FFG cards. Nimbus is the default now; to use Arno instead, drop your licensed copies here and pick it from the font dropdown. | **Adobe commercial** — do NOT commit | no (gitignored; drop your own copies here) |
| **Minion Pro** (`MinionPro*.ttf/otf`) | What the community PSD templates set their text in ("Keywords are set in Minion Pro Bold Italic") — visually close to Arno; used as body fallback. | **Adobe commercial** — do NOT commit | no (gitignored) |
| **Arkham icon font** (`ArkhamFontWithCodex.ttf`) | Every game symbol — stat icons, action/free/reaction, chaos tokens, Codex — mapped to letters A–V (`cardforge/glyphs.py`). Community-made, circulated on BGG/Discord. | fan-made, freely shared | **yes** |
| DejaVu (system) | Nothing on real cards — last-resort fallback so rendering never fails. | free | system |

Resolution order at render time, per text run:

1. the card's own manual override (editor dropdowns), if set
2. the campaign **default font** override (`_default` in `font_overrides.json`,
   set from the Cards tab's "Default fonts" panel), if set — applies to every
   card at once; a single card's own override beats it
3. the baked-in default stack — titles + cost: Arkhamic → Teutonic; stat
   numerals: Bolton Bold → Bolton → bold body; body: **Nimbus Roman No9 L**
   (all four styles, committed — the default for every card). Arno Pro / Minion
   Pro are listed after Nimbus, so they only take over if Nimbus is removed;
   to use Arno instead, pick it from the font dropdown (per-card or default).
4. icons: always the Arkham icon font via `[wil]`-style markup

**Bring your own font:** the "Upload font…" button (per-card editor *and* the
Default fonts panel) drops a `.ttf`/`.otf` straight into this folder, validates
it loads, and adds it to every font dropdown. Three roles are independently
overridable: **title** (titles + cost), **stat** (the big numerals), **body**
(rules/traits/flavor).

Missing pieces worth hunting (Mythos Busters Discord / your own licenses):
Arno Pro **Bold**, **Italic**, **Bold Italic** — used for keywords ("Forced —",
"Revelation —") and flavor text; until present those runs fall back to DejaVu
equivalents.
