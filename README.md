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
python3 pipeline/build_cards.py --only sthr-elias sthr-lamp sthr-donebefore sthr-eighthgrave
lua5.4  pipeline/lua_smoketest.lua         # run the Lua system tests
```

## Status

Card pipeline (all player cards) and the campaign state manager core (P1–P4, plus
the P6 clock and P7 aging math) are implemented and tested offline. The Latecomer
enemy (P5), location fact-toggles (P6), and the interlude UI (P7) are next. See
`docs/BUILD_STATUS.md` for the full ladder and the flagged design-doc conflicts,
and `docs/INTEGRATION.md` for SCED wiring.