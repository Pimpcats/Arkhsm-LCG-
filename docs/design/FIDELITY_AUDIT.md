# Scenario-card fidelity audit — vs. the official reference (The Drowned City)

## THE HARD RULE

**Everything this app produces is checked against the official Arkham campaign
reference before it ships. Templates, proportions, fonts, iconography, element
placement — all of it must match the official cards.**

The *only* permitted deviation is genuinely **new custom content** — a card,
mechanic, or element that does not exist in official Arkham. Custom content
still uses the official *template* (frame, fonts, layout); only its content is
new. If something would change the shape/form of a standard card type, it is a
bug, not a style choice. Arkham's card templates rarely change between sets;
when they do it's a deliberate FFG update, and we track to the current one.

Enforcement: `cardforge/studio_selftest.py` asserts every rendered card type
matches the official **aspect ratio** (see below); this audit is the living
element checklist each type is measured against; and every new card type gets a
side-by-side against the official reference before it's called done.

### Verified card aspects (true printed card = our target)

Standard card 63.5×88.9mm → portrait **0.714**; rotated (agenda/act) →
landscape **1.400**. Our renders: portrait 750×1050 = 0.714 ✓, landscape
1050×750 = 1.400 ✓ — both match the real card (the supplied PSDs read 0.698 /
1.432, marginally off from true due to trim/bleed; we track the true card).
NOTE: newer sets (incl. The Drowned City) may use a **portrait agenda/act**
variant — the plugin ships it (`AgendaPortrait`); match per the reference.

---

Goal: our scenario cards must look **exactly** like official Arkham cards.
The *frames* are authentic (extracted from the maintained SE plugin), but we
are not yet populating several elements that official cards always show. Each
flag below is grounded in the real Drowned City card data (`GMNotes` from the
TTS save) and the plugin's own region map.

**Good news:** almost every missing element is an asset the plugin already
ships (connection symbols, per-investigator marker, location base). Those need
no external extraction — just wiring. Items marked **[need ref]** are the only
ones where a real official card image would let me match placement exactly
(the Steam card URLs are blocked from here, so I can't fetch them myself).

## Location — the biggest gap

Real location `GMNotes` (Miskatonic University): `icons:"Diamond"`,
`connections:"Tee|Plus|Circle|Square|FromRight"`, clues via
`uses[{countPerInvestigator:2, type:"Clue"}]`, `victory` on the back.

| Element | Official shows | We render | Status |
|---|---|---|---|
| **Connection symbols** | the location's own symbol (e.g. ◆) + a row of the symbols it connects to, along the bottom | **now rendered** — own symbol at `BaseIcon`, connected symbols at `Connection1..6` from the plugin's `AHLCG-Loc*` icons (16 symbols mapped) | ✅ **wired** (placement to fine-tune vs ref) |
| **Clues per investigator** | value + per-investigator marker | **now rendered** — number in the per-inv slot + `AHLCG-PerInvestigator` marker | ✅ **wired** (icon size/pos to fine-tune) |
| **Shroud** | shroud value | plain number in the shroud slot | ✅ number; icon baked in frame |
| **Front vs back text** | unrevealed = flavor only; revealed = full rules + clues + victory | we put full rules on the front | ⬜ data model: split front/back text |
| **Victory** | on the revealed back, bottom | field exists, not shown on back yet | ⬜ region `Victory` |

New editable location fields now driving the icons: `icons` (own symbol name),
`connections[]` (connected symbols, each optionally `{symbol,color}`),
`clues_per_investigator` (bool), and **`color`** (the location's colour). Symbol
names map to the plugin assets (Circle/Square/Triangle/Diamond/Moon/Star/Heart/
Hourglass/Cross/Quote/Slash/DoubleSlash/Spade/Clover/T).

**Colour**: the plugin ships gold-monochrome symbols; official locations tint
each location a colour and colour its connection symbols to match the map. We
now **tint** the own symbol to `color` and each connection to its target's
colour (named palette + hex). Exact colours to be matched from the reference
images. A connection-symbol + colour **picker** in the editor is the remaining
UI piece.

New data fields a location needs (to drive the above): `icons` (own symbol),
`connections[]` (symbols it links to), `clues_per_investigator` (bool),
`revealed`/back text. All hand-editable.

## Agenda / Act

Real: agenda `{doomThreshold}`, act minimal; both carry a scenario/encounter
index.

| Element | Official shows | We render | Fix |
|---|---|---|---|
| **Doom / clue threshold** | number beside the doom pip / clue+per-inv icon | plain number | regions `Doom`/`DoomPerInvIcon`, `Clues`/`CluesPerInvIcon` |
| **"Agenda #a" / "Act 1" header** | stage header across the top | **not shown** | region `ScenarioIndex` / header band |
| **Footer** | illustrator credit · © FFG · collection number · encounter-set symbol · card number | **not shown** | regions `Artist`/`Copyright`/`CollectionNumber`/`EncounterNumber` |
| **Body flow** | text flows down the card from the header | clustered top-right, big empty parchment | widen/retop the Body region to the frame's text area |
| **Orientation** | landscape (or portrait in newer sets) | landscape 1.400 ✓ (confirm vs Drowned City ref) | `AgendaPortrait` template available if needed |

## Scenario reference

Real `ScenarioReference` carries `tokens.front`/`tokens.back` = the chaos-bag
symbol modifiers per difficulty.

| Element | Official shows | We render | Fix |
|---|---|---|---|
| **Chaos-token modifiers** | rows of symbol → modifier/description, front (easy/std) + back (hard/exp) | nothing | regions `BodyName`/`BodyResolution`; needs a token-modifier data block **[need ref]** for exact layout |
| **Header band** | scenario name in the header | name centered, ok now | — |

## What is already correct

- The **frames** themselves (per class / per type) — authentic plugin art.
- **Titles** (Arkhamic), **stat numerals** (Bolton), **body** (Nimbus).
- Portrait/landscape orientation, art window placement, name/traits/rules flow.

## What would let me match EXACTLY

The elements above are mostly in-hand. To verify pixel-placement against the
real thing, a handful of **official card face images** as PNG uploads would be
ideal — one each of: a revealed **Location**, an **Agenda**, an **Act**, and a
**Scenario reference** card. With those I can calibrate icon positions and sizes
to the reference instead of trusting the region boxes alone.
