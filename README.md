# Arkhsm-LCG — THE STILL HOUR

An original loop-horror campaign for **Arkham Horror: The Card Game**, built as a
module for **SCED** (Super Complete Edition, Tabletop Simulator). The town of
Ambergrove repeats the same span of hours; five investigators remember. You get
stronger by *remembering*, and using what you remember is what gets you noticed.

The design is frozen (see the six design docs referenced by
`SCED_BUILD_BRIEF.md`). This repo is the **build**: card content as data plus the
custom Lua for the campaign's novel systems.

## Layout

```
pipeline/
  build_cards.py            card generator: spec -> SCED Card objects
  stillhour_cards_spec.json full player-card spec (5 investigators, 15 sig/weakness, 10 Recollections)
  lua_smoketest.lua         offline test harness for the Lua modules (48 assertions)
src/StillHour/
  Constants.ttslua          thresholds/bands derived from investigator count
  CampaignState.ttslua      the single owned state store (Memory/Dissonance/Hourglass/Years/Knowledge/flags)
  Dissonance.ttslua         [static] token + band-driven chaos-bag reconciliation
  LoopFlags.ttslua          once-per-loop + per-loop test-type bookkeeping
  Hourglass.ttslua          the Occultation clock (advance/rewind, "when reached" Hours)
  Aging.ttslua              age brackets + stat drift
dist/
  the_still_hour.json       generated 30-card player-card bag
  stillhour_starter.json    generated Elias vertical slice
docs/
  BUILD_STATUS.md           priority ladder (P0–P8) + flagged design-doc conflicts
  INTEGRATION.md            how to wire this into an argonui/SCED fork
```

## Quickstart

```bash
python3 pipeline/build_cards.py            # -> dist/the_still_hour.json (30 cards)
python3 pipeline/bundle_mod.py             # -> dist/the_still_hour_mod.json (LOADABLE TTS SAVE)
lua5.4  pipeline/lua_smoketest.lua         # Lua system tests (54 assertions)
lua5.4  pipeline/verify_bundle.lua         # load the mod bundle in a stubbed TTS env
python3 pipeline/simulate.py               # balance simulation report + assertions
```

**To play/test in Tabletop Simulator:** build the two commands above, then load
`dist/the_still_hour_mod.json` — see **`docs/LOADING.md`**. It spawns the card
bag + a scripted Control token; click **Run Tests** for an in-engine pass.

## Testing & simulation

Two complementary layers, plus an in-engine harness:

- **`pipeline/lua_smoketest.lua`** — offline functional tests of the Lua modules
  (state persistence, bands, loop flags, clock, aging, CO-001 spend). 54 asserts.
- **`pipeline/simulate.py`** — Monte-Carlo *balance* model: chaos-bag success
  curve (reproduces 25/56/75), Memory economy vs the official-XP benchmark
  (~40–50/investigator), Dissonance pacing (cautious vs greedy), and the aging
  spread. Validates the math the design docs cite. `--trials/--loops/--quiet`.
- **`tests/tts_console_harness.lua`** — runs the *same* assertions inside
  Tabletop Simulator against the real bundled modules, with a live
  loop→reset→interlude walkthrough. Attach to an object and click its button, or
  `>execute runStillHourTests()` from the console (see the file header).

The simulator validates probabilities/economy/pacing; it cannot validate fun or
catch rules-interaction surprises — those still need real play in TTS.

## Status

P1–P7 are implemented and tested offline (99-assertion suite): the card pipeline,
the campaign state manager, the `[static]`/Dissonance bands, loop bookkeeping, the
Appointed (P5, staged Approach), the Occultation clock + location fact-toggles
(P6), and aging drift + the interlude (P7). Remaining: P8 download-box packaging,
the real in-TTS load test, and per-system board wiring (see `docs/BUILD_STATUS.md`).
`docs/INTEGRATION.md` covers folding this into an SCED fork.