# Integrating StillHour into the SCED fork

This module is written as **source** to drop into an `argonui/SCED` fork and
bundle with the repo's tooling (luabundle). Do **not** hand-edit the 11 MB save
JSON — work in source and rebuild (`SCED_BUILD_BRIEF.md` §1, §6).

## 1. Where the files go

```
SCED-fork/
  src/
    StillHour/                <- copy this repo's src/StillHour/ here
      Constants.ttslua
      CampaignState.ttslua
      Dissonance.ttslua
      LoopFlags.ttslua
      Hourglass.ttslua
      Aging.ttslua
```

`require` paths use the bundle-root-relative form `require("StillHour/X")`.
Confirm your fork's luabundle root (SCED bundles from `src/`); if it differs,
adjust the `require` prefixes to match (they must all share one prefix).

## 2. The state host object (P2 persistence)

`CampaignState` is a pure module holding an in-memory `state` table. It needs one
**owner object** in the scene (a token/tile) whose lifecycle hooks persist it:

```lua
-- LuaScript on the "Still Hour — Campaign State" token
local CampaignState = require("StillHour/CampaignState")

function onSave()
  return CampaignState.serialize()          -- uses TTS global JSON.encode
end

function onLoad(saved)
  CampaignState.deserialize(saved)          -- empty/nil -> fresh state
  -- Optionally: CampaignState.setInvestigatorCount(#getSeatedPlayers())
end
```

Because SCED's campaign save/import-export carries `LuaScriptState`, this one
object's state survives **node travel and resets** — the make-or-break property
in `SCED_BUILD_BRIEF.md` §5. Every other module reads/writes through this
manager; no card stores loop state itself.

If SCED exposes a campaign-state registry (verify the save/import-export API in
your fork), register this object with it so it is included in campaign exports.

## 3. Chaos-bag adapter (P3)

`Dissonance` never touches the bag directly. Provide a thin adapter over SCED's
existing chaos-bag / bless-curse manager implementing at minimum:

```lua
local bag = {
  setBaselineStatic = function(n)
    -- ensure exactly n baseline [static] tokens are in the bag
    -- (add/remove [static] via the bag manager's API, not by mutating the bag)
  end,
}
```

Then call `Dissonance.raise(n, bag)` / `Dissonance.reduce(n, bag)` /
`Dissonance.onStaticRevealed(bag)` from wherever Dissonance changes, and
`Dissonance.syncBag(bag)` at loop setup. Band → baseline count is
Calm 0 / Glitch 1 / Noticed 2 (`Constants.STATIC_BY_BAND`).

The `[static]` token itself: modifier **−3**, and on reveal call
`Dissonance.onStaticRevealed(bag)` (raises Dissonance by 1, which may itself
cross a band and reconcile the bag, or trigger the Latecomer/reset — the return
table reports `latecomerArriving` / `reachedReset`).

## 4. Cards → manager (P4/P6/P7)

- **Once per loop** (`I Get Out`, `I Remember the Ending`, `Rehearsed Escape`,
  `Cassandra's Notebook`, `The Hour I Learned Your Name`): call
  `LoopFlags.use("<cardId>:<playerColor>")` — returns false if already used this
  loop (persists across nodes, clears on reset).
- **Muscle Memory**: `LoopFlags.muscleMemoryUpgraded(testType)`; record every
  test with `LoopFlags.recordTest(testType)`.
- **Hourglass**: `Hourglass.advance(n, ctx)` / `Hourglass.rewind(n, ctx)`.
  Pass a `ctx` with the board callbacks you have (see the module header); all are
  optional and default to no-ops, so a partial board still advances the clock.
- **Aging**: at the interlude call `Aging.applyInterlude(id, cond, lockedChoice)`
  per investigator; apply the returned `drift` to the physical investigator sheet
  (skills floor at 1). `cond.endedInDanger` must be computed from the loop-end
  Dissonance **before** `CampaignState.reset()` drops it to the scar.

## 5. Loop flow ordering

```
setup each loop:   CampaignState.startLoop()   -- enforces Memory soft cap
                   Dissonance.syncBag(bag)     -- baseline [static] for the band
... play (advance Hourglass, raise/reduce Dissonance, set flags) ...
reset:             CampaignState.reset()       -- scar, Hour I, clear flags, snapshot tests
interlude:         (bank on-card Memory) CampaignState.bankMemory(x)
                   Aging.applyInterlude(...) per investigator
                   (buy Recollections) CampaignState.spendMemory(memoryCost)
```

## 6. Card data & deckbuilding

- Regenerate card objects with `python3 pipeline/build_cards.py`
  (`dist/the_still_hour.json`). Each card is a standard SCED `Card` with
  `GMNotes` metadata only — printed rules text lives on the **art**.
- Deckbuilding recognises the five investigators' signatures via the
  `signatures` field. Recollection access is granted by each investigator's
  deckbuilding line; Recollection cards carry the `Recollection` trait and a
  `memoryCost` in GMNotes for the interlude buy UI (the Memory price, distinct
  from the resource `cost`).
- Art is the last stage (`ART_PIPELINE_BRIEF.md` / `CARDFORGE_BRIEF.md`): the
  spec's `placehold.co` FaceURLs are swapped for hosted sheet URLs before the
  final build. Placeholders load today so the slice is testable now.

## 7. Distribution (P8)

Ship `dist/the_still_hour.json` as a GitHub release asset and add a
`Custom_Model` placeholder box with `GMNotes={"filename":"the_still_hour"}` whose
Lua calls `GlobalApi.placeholderDownload("the_still_hour")` — the pattern SCED
already uses (`SCED_BUILD_BRIEF.md` §1). Verify `placeholderDownload`'s signature
in your fork before wiring the box.
