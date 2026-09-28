# THE STILL HOUR — Master Checklist
*Updated 2026-09-27. Spoiler-free. ✅ done · 🔶 partly done / needs your action · ⬜ not started.*

Current counts and test results: `campaigns/still_hour/assistant/production.json`.

## The campaign

- ✅ Rules modules, campaign state, loop bookkeeping, clock, aging and
  interlude built and tested offline (Lua rules suite, Control token bundle
  check)
- ✅ Every scenario authored and locked (scenario audit: 0 errors); the
  campaign box compiles with all scenario boxes
- ✅ Rules-wording passes against the Rules Reference applied to the guide
  and every card
- ✅ Balance and pacing modelled (docs/BALANCE.md, designer-facing)
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

## Art

- ✅ Illustrations approved and composited into the card faces
- 🔶 Six illustrations still to generate: the "remaining" request of the
  ChatGPT art pack (docs/CHATGPT_ART_PACK.md). Their cards show a blank art
  window until then
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
- ✅ Selftests: `cardforge/selftest.py` and `cardforge/studio_selftest.py` all
  green; both run in a temporary copy, so they never touch your files
- 🔶 Strange Eons path (pixel-perfect benchmark): optional, one-time setup

## Your to-dos (nobody else can)

- 🔶 Start the TTS relay on your PC and let it test the current build
- 🔶 Generate the six remaining illustrations in ChatGPT (the assistant
  prepares the request and imports the results)
- ⬜ Load the campaign in TTS and play the Prologue and Loop 1
- ⬜ Decide: hide Knowledge entry names on the campaign log until earned, or
  keep the visible checklist

## Parked

- ⬜ SCED download box: optional; the Saved Object is the load path
- ⬜ Plugging Claude directly into the app (later goal)
