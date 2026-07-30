# Loading THE STILL HOUR into Tabletop Simulator

The build produces a self-contained, loadable TTS artifact:

- **`dist/the_still_hour_mod.json`** — a TTS save containing the 30-card
  player-card bag **and** a scripted **Control** token that carries the entire
  StillHour Lua (state manager, Dissonance/`[static]`, Hourglass, Aging, loop
  flags) bundled inline, with an in-engine test harness.

This is the *vertical slice* proving the spine end-to-end — it is **not** the
full SCED mod (no base-game content). It runs standalone in vanilla TTS; to fold
into a real SCED fork, see `docs/INTEGRATION.md`.

## Build it

```bash
python3 pipeline/build_cards.py     # dist/the_still_hour.json (the card bag)
python3 pipeline/bundle_mod.py      # dist/the_still_hour_mod.json (the loadable save)
```

`bundle_mod.py` inlines `src/StillHour/*.ttslua` behind a local `require` (a
hand-rolled luabundle) and appends `src/tts/control.lua` as the entry script, so
everything lives in one object's `LuaScript`.

## Load it

**As a save game:**
1. Copy `dist/the_still_hour_mod.json` into your TTS saves folder:
   `Documents/My Games/Tabletop Simulator/Saves/`
2. In TTS: **Games → Save & Load →** pick **THE STILL HOUR**.

Two objects spawn: the card bag (left) and the Control token (right).

## Use it

- Press the **`` ` ``** (backtick/tilde) key to open the console for script output.
- On the Control token, click **Run Tests** — you should see
  `RESULT: 23 passed, 0 failed` and a green broadcast. This confirms the bundled
  Lua behaves in-engine (real TTS `JSON` round-trip and all).
- **Advance Hour / +1 Dissonance / Reset Loop / Status** drive the systems live so
  you can watch Memory/Knowledge/Years persist and Dissonance drop to the scar
  across a reset. State auto-persists via `onSave`/`onLoad` (reload the save and
  the Control token restores its state).
- Drag the investigators/cards out of the bag to inspect them (placeholder art
  for now — real art comes from the CardForge / art pipeline).

## Verify the bundle offline (no TTS)

```bash
lua5.4 pipeline/verify_bundle.lua   # loads the bundle in a stubbed TTS env, runs the harness + play buttons
```

## Distributing it (P8 — the download box)

For sharing rather than a local file, package it the SCED way:

```bash
python3 pipeline/build_cards.py && python3 pipeline/bundle_mod.py
python3 pipeline/package_download.py    # -> dist/downloads/
```

- `dist/downloads/the_still_hour.json` — the **release asset**: one campaign box
  holding the card bags + Control token. Upload it as a GitHub release asset at a
  URL the mod's `SOURCE_REPO` resolves (`{SOURCE_REPO}/the_still_hour.json`).
- `dist/downloads/the_still_hour_box.json` — the **placeholder box**: add this
  object to the SCED game; its GMNotes is `{"filename":"the_still_hour"}` and its
  Lua calls `GlobalApi.placeholderDownload("the_still_hour")` to fetch and spawn
  the release asset in place of the box.

Verify `GlobalApi.placeholderDownload`'s exact name/signature in your SCED fork
before shipping; the box prints a clear message (instead of erroring) if it's
called outside the mod.

## Regenerating after changes

Edit `src/StillHour/*.ttslua` or `src/tts/control.lua`, then re-run
`python3 pipeline/bundle_mod.py`. Never edit `dist/stillhour_bundle.lua` or the
save's `LuaScript` by hand — they are generated.
