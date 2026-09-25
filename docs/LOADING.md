# Loading THE STILL HOUR into Tabletop Simulator

Everything you need is one file: **`dist/saved_object_the_still_hour.json`**,
the campaign box as a TTS *Saved Object*. It holds the scenario boxes, the
Control token, the player cards, the campaign guide, the campaign log, the
investigator minicards and the `[static]` chaos token. Card images load from
GitHub, so the build works on any PC.

## One-time: put the file where TTS finds it (your PC, File Explorer)

1. Download `dist/saved_object_the_still_hour.json` from the repository
   (or pull the repo).
2. Copy it into
   `Documents\My Games\Tabletop Simulator\Saves\Saved Objects\`
   (create the `Saved Objects` folder if it is missing).

## Each campaign: set the table (Tabletop Simulator)

1. Load the **SCED** mod (Arkham Horror LCG Super Complete Edition) on a fresh
   table.
2. **Objects → Saved Objects →** click **The Still Hour**. The campaign box
   appears in the box area at the top of the table.
3. Press **Place** on the campaign box. It lays out the scenario boxes, the
   campaign guide, the campaign log, the minicards, the player-card bag, the
   **Control** token and the `[static]` token.
4. Open the **campaign guide** and follow it from *Campaign Setup*. The guide
   tells you when to press each button on the Control token and each box's
   **Place**.

The Control token does the campaign's bookkeeping: Hour, Dissonance and the
`[static]` tokens in the chaos bag, Memory, the loop count, aging and the
between-loops purchases. Its difficulty buttons fill SCED's chaos bag for the
difficulty you choose. Ticking a Knowledge fact on the campaign log tells the
Control token too.

## Updating to a newer build

Before a campaign starts: copy the new `saved_object_the_still_hour.json` over
the old one and spawn it on a fresh table.

In the middle of a campaign: your progress lives in the Control token and the
campaign log on your table. Save your game, then ask the assistant which pieces
to swap; it will tell you how to keep that state.

---

## For the build (developer notes)

| File | What it is |
|---|---|
| `dist/saved_object_the_still_hour.json` | **The package the owner loads** (the campaign box as a Saved Object). |
| `dist/downloads/the_still_hour.json` | The same box as a single object, for SCED's download mechanism. |
| `dist/the_still_hour_mod.json`, `dist/the_still_hour_campaign.json`, `dist/the_still_hour_table.json` | Component builds the TTS relay spawns for automated in-game tests. Not for play. |

Rebuild everything (cards, hosted images, guide PDF, boxes, package):

```bash
python3 pipeline/publish_hosted.py      # renders, pins image URLs, rebuilds dist/
python3 -m pytest -q tests              # offline checks
lua5.4 pipeline/lua_smoketest.lua       # rules engine
lua5.4 pipeline/verify_bundle.lua       # the Control token in a stubbed TTS
```

`bundle_mod.py` inlines `src/StillHour/*.ttslua` behind a local `require` and
appends `src/tts/control.lua` as the entry script. Scenario boxes carry
`src/tts/loop_box.lua` (Place lays out a fresh copy every loop; the box never
empties); the campaign box carries SCED's own `src/tts/memory_bag.lua`. Never
edit generated files in `dist/` by hand.

In-game verification runs through the TTS relay: `docs/TTS_RELAY.md`.
