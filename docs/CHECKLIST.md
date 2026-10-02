# THE STILL HOUR — Master Checklist
*Updated 2026-10-02. Spoiler-free. ✅ done · 🔶 partly done / needs your action · ⬜ not started.*

Current counts and test results: `campaigns/still_hour/assistant/production.json`.

## The campaign

- ✅ Rules modules, campaign state, loop bookkeeping, clock, aging and
  interlude built and tested offline (Lua rules suite, Control token bundle
  check)
- ✅ Every scenario authored and locked (scenario audit: 0 errors); the
  campaign box compiles with all scenario boxes
- ✅ Rules-wording passes against the Rules Reference applied to the guide
  and every card
- ✅ Balance and pacing modelled and measured with computer-played games
  (designer-facing, spoilers: docs/design/FINISHING_BALANCE.md; docs/BALANCE.md
  is historical). The results do not yet meet every difficulty target
- ✅ Campaign guide typeset as a PDF on the plugin's guide pages; interactive
  campaign log; investigator minicards; campaign and scenario boxes with
  Place / Recall
- ✅ Generated objects byte-aligned with real SCED objects
  (docs/art_reference/sced_objects/)
- ✅ One file to load: `dist/saved_object_the_still_hour.json`
  (docs/LOADING.md). Card images are hosted on GitHub, pinned to a commit
- 🔶 Real-TTS relay run on the current build — needs you (local PowerShell,
  docs/TTS_RELAY.md). The last real run passed on an older build
- ⬜ First playtest (Prologue and Loop 1)
- ✅ One-page play aid for the table: docs/QUICK_REFERENCE.md (read it when
  you sit down to play; it explains the campaign's systems)

## Art

- ✅ Art complete: every illustration approved and composited into the card
  faces
- 🔶 Box art: the campaign box and scenario boxes share one texture (not urgent)

## CardForge Studio (the app)

- ✅ Workflow tabs (Setup · Illustrate · Cards · Campaign / scenarios · Play in
  TTS · Advanced) with numbered self-checking steps
- ✅ In-place card editor for every card type: click text or stats on the card,
  steppers and pips, upload an image with fit sliders
- ✅ Official font stack ships in the repo; default-font panel and per-card
  overrides; upload your own font
- ✅ Deck backs on every export
- ✅ Cloud art is the default path; local backends (A1111 / ComfyUI) optional,
  settings in `rig.local.json` (never committed)
- ✅ Selftests: `cardforge/selftest.py` passes (re-run 2026-10-02);
  `cardforge/studio_selftest.py` passed when last run. Both run in a temporary
  copy, so they never touch your files
- 🔶 Strange Eons path (pixel-perfect benchmark): optional, one-time setup

## Your to-dos (nobody else can)

- 🔶 Start the TTS relay on your PC and let it test the current build
- ⬜ Load the campaign in TTS and play the Prologue and Loop 1
- ✅ Campaign log names stay hidden until earned (decided and built)

## Parked

- ⬜ SCED download box: optional; the Saved Object is the load path
- ⬜ Plugging Claude directly into the app (later goal)
