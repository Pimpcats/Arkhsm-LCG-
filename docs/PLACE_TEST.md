# If Place stops Tabletop Simulator: the Place test

Spoiler-free. Nothing here needs any file work beyond copying one file once.

**What it is.** `dist/saved_object_place_test.json` is a small Saved Object with
five boxes. Each lays out cards the same way the campaign's boxes do (or, for
the fifth, the way SCED's own boxes do), but loads a different amount of
images. Pressing them one by one on a fresh table shows which part of a Place
is the problem. It is not the campaign: no Control token, no campaign log,
nothing is saved.

## Steps

1. Copy `dist/saved_object_place_test.json` into
   `Documents\My Games\Tabletop Simulator\Saves\Saved Objects\` (as with the
   campaign file).
2. Load SCED on a fresh table. **Objects → Saved Objects →** *The Still Hour —
   Place test*. A box appears at the top of the table.
3. Press **Place** on it. Five small boxes appear in a column.
4. On each small box press **Place**, look at the table, then press **Recall**
   on that box before the next one. Do them in this order, stopping at the first
   one that stops Tabletop Simulator:
   1. **Test 1 — one card** (a single card)
   2. **Test 2 — structure, one image** (a whole scenario's cards, every image the same)
   3. **Test 3 — sprite sheets** (the same cards as the campaign's First Hour now)
   4. **Test 4 — image per card** (the same cards the way the first build loaded them)
5. If one of 1 to 4 stopped Tabletop Simulator, start again on a **fresh table**
   and press **Place** on **Test 5 — SCED's own Place**. It lays out the same
   cards as Test 3 with SCED's own, unmodified Place script (it empties the box;
   **Recall** puts everything back, as on every official box).
6. Tell the assistant which test was the first to stop Tabletop Simulator (or
   that none did, and whether Test 5 stopped it) and send the last 60 lines of
   `%USERPROFILE%\AppData\LocalLow\Berserk Games\Tabletop Simulator\Player.log`.
   The last line says which step was running.

## How to read the result

- All of 1 to 4 work: the campaign's own Place on **The First Hour** should too.
- Test 4 is the only one that stops: the images were the problem and the
  campaign no longer loads them that way.
- Test 1 stops: the problem is in the Place script's way of copying the box or
  in a single card; Test 5 tells which.
- Test 3 stops and Test 5 works: the campaign's Place script is the cause.
- Test 3 and Test 5 both stop: the script is not the cause; the cards or their
  sprite sheets are.

(What each box does: `pipeline/place_test.py`; why:
`docs/design/PLACE_BUTTON_AUDIT.md`.)
