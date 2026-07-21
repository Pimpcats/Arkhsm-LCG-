# Scenario-card fidelity audit — vs. the official reference (The Drowned City)

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

| Element | Official shows | We render | Fix asset |
|---|---|---|---|
| **Connection symbols** | the location's own symbol (e.g. ◆) + a row of the symbols it connects to, along the bottom | **nothing** | plugin `AHLCG-LocDiamond/Circle/Square/Triangle/Cross/Heart/Moon/Star/Hourglass/Quote` (+Alt) → regions `BaseIcon`, `Connection1Icon`…`Connection6Icon` |
| **Shroud** | shroud value on the shroud icon/base | a plain number | plugin `AHLCG-LocationBase`; region `Shroud` (+ `ShroudPerInvIcon`) |
| **Clues** | value **per investigator** with the per-investigator marker | a plain number, no per-inv marker | plugin `AHLCG-PerInvestigator`; regions `Clues`/`CluesPerInv`/`CluesPerInvIcon` |
| **Front vs back text** | unrevealed = flavor only; revealed = full rules + clues + victory | we put full rules on the front | data model: split front/back text |
| **Victory** | on the revealed back, bottom | field exists, not shown on back yet | region `Victory` |

New data fields a location needs (to drive the above): `icons` (own symbol),
`connections[]` (symbols it links to), `clues_per_investigator` (bool),
`revealed`/back text. All hand-editable.

## Agenda / Act

Real: agenda `{doomThreshold}`, act minimal; both carry a scenario/encounter
index.

| Element | Official shows | We render | Fix |
|---|---|---|---|
| **Doom / clue threshold** | number beside the doom pip / clue+per-inv icon | plain number | regions `Doom`/`DoomPerInvIcon`, `Clues`/`CluesPerInvIcon` |
| **Agenda "a" / Act "1" index** | the big stage number in the corner | not shown | region `ScenarioIndex` **[need ref]** for exact glyph |
| **Encounter-set icon** | the set's symbol | not shown | our campaign has no set icon yet — design choice |

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
