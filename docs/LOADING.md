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

## End of every session: save your game (Tabletop Simulator)

Your progress lives in the **Control** token and the **campaign log** on your
table, and TTS only writes them to disk when you save. Before you quit:
top menu **Games → Save & Load**, then **Create**, type a name (for example
`Still Hour`) and click **Save**, or hover over your existing save and choose
**Overwrite**. Next time, load that save instead of starting from SCED.

## Updating to a newer build

**Before a campaign starts:** copy the new `saved_object_the_still_hour.json`
over the old one (step 2 of the one-time setup) and spawn it on a fresh table.

**In the middle of a campaign** (moving a campaign in progress onto a newer
build without losing progress). The Control token keeps a copy of the campaign
state inside the campaign log, so a new Control token picks up where the old one
stopped. Keep the campaign log you have; you only swap the other pieces.
Between sessions or between loops is the easiest moment, but mid-loop works:
cards already on the table stay as they are.

1. **In Tabletop Simulator:** load your campaign save and save it once more
   under a new name (for example `Still Hour before update`), as described
   above. This is your way back if anything goes wrong.
2. **On your PC, in Windows File Explorer:** copy the new
   `saved_object_the_still_hour.json` into
   `Documents\My Games\Tabletop Simulator\Saves\Saved Objects\`, and choose
   **Replace** when Windows asks.
3. **In Tabletop Simulator:** with your campaign table loaded, right-click the
   old **Control** token and choose **Delete**. Leave the **campaign log** where
   it is. It holds your progress. Do not delete or replace it.
4. **In Tabletop Simulator:** **Objects → Saved Objects → The Still Hour.** A
   new campaign box appears. **Do not press Place on it.** That would lay out a
   second campaign log, and with two logs on the table the Control cannot tell
   which one holds your progress.
5. **In Tabletop Simulator:** right-click the new box and choose **Search**.
   Drag the new **Control** token out onto the table. When it lands it reads
   the campaign log and says *"Still Hour campaign state restored from the
   campaign log."* Check that its Memory, Dissonance, Hour and loop count match
   what you had.
6. **In Tabletop Simulator:** delete the old scenario boxes and drag the new
   ones out of the box the same way. Where you put them does not matter: each
   box remembers where its cards go. Swap the campaign guide too (your progress
   is not in it). If the update notes mention other pieces (for example a
   changed player card), take those from the new box now.
7. **In Tabletop Simulator:** delete the new campaign box with what is left in
   it (including its spare campaign log), then save your game (as described
   above).

If step 5 shows a brand-new campaign (Prologue, Memory 0), there was more than
one campaign log on the table, or the log was deleted. Load the save from step 1
and start again.

---

## For the build (developer notes)

| File | What it is |
|---|---|
| `dist/saved_object_the_still_hour.json` | **The package the owner loads** (the campaign box as a Saved Object). |
| `dist/downloads/the_still_hour.json`, `the_still_hour_box.json` | The same box as a single object plus a download-box stub, for SCED's download mechanism. **Optional and not a load path:** the stub only works once the release file is hosted where SCED's downloader looks, which this build does not do. Use the Saved Object. |
| `dist/the_still_hour_mod.json`, `dist/the_still_hour_table.json` | Component builds the TTS relay spawns for automated in-game tests (it also spawns and tests the Saved Object itself). Not for play. |
| `dist/the_still_hour_campaign.json` | The scenario boxes in one campaign box (a build step and CardForge's spawn button). Not for play. |

Rebuild everything (cards, hosted images, guide PDF, boxes, package):

```bash
python3 pipeline/publish_hosted.py      # renders, pins image URLs, rebuilds dist/
python3 -m pytest -q tests              # offline checks
lua5.4 pipeline/lua_smoketest.lua       # rules engine
lua5.4 pipeline/verify_bundle.lua       # the Control token in a stubbed TTS
```

`publish_hosted.py` commits the card images and pins every image URL to that
commit, so **never squash- or rebase-merge a publish commit** (the pinned URLs
would stop resolving and every face in TTS would go blank). The individual
build scripts refuse to write placeholder or `file:///` image URLs into
`dist/`; `--local` makes a private test build that must not be committed.

`bundle_mod.py` inlines `src/StillHour/*.ttslua` behind a local `require` and
appends `src/tts/control.lua` as the entry script. Scenario boxes carry
`src/tts/loop_box.lua` (Place lays out a fresh copy every loop; the box never
empties); the campaign box carries SCED's own `src/tts/memory_bag.lua`. Never
edit generated files in `dist/` by hand.

In-game verification runs through the TTS relay: `docs/TTS_RELAY.md`.
