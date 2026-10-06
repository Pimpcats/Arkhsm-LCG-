# Place button audit (rewritten 2026-10-06, updated after the rebuild)

Designer-facing; no campaign content. Question: why does Tabletop Simulator
stop when the owner presses Place on a scenario box (The First Hour), and is
the box built the way SCED builds its own?

Evidence: SCED 4.9.2 itself (the owner's save, Global Lua bundled in it), all
199 items its Download menu serves (cached in `.cache/official/tts_menu/`; the
38 official ones are the comparison set), and an emulator run on that real
table. Method tags: MEASURED (computed from files), READ (code), EMULATED
(tests/sced_real), INFERRED. Status values: **Fixed**, **Accepted**, **Watch**,
**Rejected** (as in DECKBUILDING_REVIEW.md).

## What is established

1. **The cause of the native crash is not known.** The emulator cannot reach
   texture loading, memory or native faults, so nothing here demonstrates it. It
   rules out Lua: on the real 4.9.2 table, SCED's handlers raise no error or
   warning for our boxes (8 boxes, old and new script, 16 runs) and fire the
   same events, in the same counts, as for official boxes (EMULATED).
2. **The owner's earlier build had the first version of the Place script.**
   `dist/saved_object_the_still_hour.json` (built 2026-10-05 20:25) predates the
   staged-spawn commit 52cb886; its scenario script was byte-identical to
   `git show 52cb886^:src/tts/loop_box.lua`. The crash was seen with that
   script. `dist/` has since been rebuilt (see the status column below); the new
   build has not run on the owner's table.
3. **No card of ours has been displayed in Tabletop Simulator yet.** The
   campaign box's own Place (minicards, log, guide, boxes) works; The First Hour
   is the first Place that spawns Card and Deck objects with custom images.
   Anything wrong with how our cards are built meets TTS here first.

## How the official boxes place (READ, MEASURED)

- **Download menu.** `placeholder_download` fetches
  `SOURCE_REPO .. filename .. ".json"` (SCED-downloads release), and
  `contentDownloadCallback` calls `spawnObjectJSON` on the text, then adds
  `{filename}` to GMNotes and the `Reloadable` tag and calls `onObjectSpawn`.
  It spawns in the first free spot of the upper table. Nothing else.
  Our Saved Object has the same data (a deep diff of `dist/downloads/
  the_still_hour.json` against the Saved Object's object is empty) and the same
  tag and GMNotes, so the ingestion path is not a difference.
- **Campaign box Place.** One script (hash 3cf6bab4, SCED's MemoryBag) on all
  234 memory bags in the 38 files. `buttonClick_place` is synchronous, in the
  click frame: one `self.getData()` (names only), then per remembered object
  `getObjectFromGUID` (already on the table with the same name: MOVE it, so a
  second press re-lays instead of duplicating) else
  `self.takeObject({guid, position, rotation, smooth = false})` and `setLock`.
  The object keeps its GUID; the box empties; Recall is `putObject`.
  State: `LuaScriptState {"ml": {guid: {pos, rot, lock}}}`.
- **Scenario box Place.** The same script on the scenario box (a bag inside the
  campaign box), with the same `ml` format. Official scenario boxes hold
  (min / median / p90 / max over 145 boxes): 1 / 12 / 21 / 57 top-level
  objects, 1 / 72 / 105 / 288 nested objects, 17 / 87 / 149 / 378 KB, **0 / 9 /
  14 / 27 card-sheet textures**, **0 / 7 / 13 / 21 CustomDeck ids**; a median of
  1 scripted object; nesting depth median 3. Sheets: 44% are 10x7, 12.6% 1x1.
  50% of nested objects share a GUID with another (the official data reuses
  GUIDs heavily; TTS hands the taken-out object a new GUID if one is in use).
- **What SCED's Global does when objects spawn or leave a container** (READ,
  EMULATED): cheap tag and metadata checks, no loops. The heavy parts are the
  play area's per-card token spawn and the Token Arranger's 32-token burst when
  a scenario reference card lands, identical for official boxes.

## Ours against the official, ranked for a native crash (INFERRED)

Rule: exists at the failing step but not at the working campaign Place, lies
outside the official range, and is on a native TTS path.

| # | Difference | Official | The Still Hour (published) | Status |
|---|---|---|---|---|
| 1 | Card textures and CustomDeck ids per box, one frame | median 9 / max 27 textures; median 7 / max 21 ids | The First Hour **43 / 29**, The Square **57 / 41**, others 12-20 (every card is its own 1x1 sheet; 128 of 128) | **Fixed**: sprite sheets, at most 4 textures per box (docs/design/SPRITE_SHEETS.md) |
| 2 | Per-card `CustomUIAssets` font bundle | 4 of 11,483 cards (a helper with XML UI) | 203 of 208 cards, unused (no XML UI, no object-UI code) | **Fixed** (`pipeline/build_cards.py`, in `dist/`) |
| 3 | The old Place rewrites everything in the click frame | `takeObject` of stored data, GUIDs kept | `self.getData()`, `JSON.decode(JSON.encode())` of every object, a random 6-hex GUID and two new tags on every nested object including each card in a deck, then `spawnObjectData` | **Fixed** in `src/tts/loop_box.lua` (a native copy of the box, SCED's own `takeObject` on it) |
| 4 | Follow-up work 2 s after Place (board sync, chaos bag) while textures load | none | Control `shApiSyncBoard` | **Fixed**: the sync runs in announced stages, a few frames apart |
| 5 | Image encoding and host | Steam CDN | `raw.githubusercontent.com`, 200 of 200 progressive JPEGs | **Fixed**: baseline JPEGs and sheets; the host stays (Accepted) |
| 6 | Tag `StillHourBox:<guid>` (colon) | tags are letters, digits, underscore | colon, added at run time to every nested object | **Fixed**: `StillHourBox_<id>`, baked into the data |
| 7 | Windows cache path length (unverified) | | 115-134 characters per URL | Accepted (sheet URLs are shorter and far fewer) |
| 8 | Object count, JSON size, nesting, deck size, scripts on contained objects, GMNotes and tag vocabulary, chaos-token keys, Deck/CustomDeck consistency, id collisions, SCED's Lua reaction | | all smaller than or equal to the official median, or identical | Rejected as causes (MEASURED, EMULATED) |

Because items 1-3 first appear at the same step they cannot be separated from
this data. The new build therefore removes all of them (scale 1.0 and
`BackIsHidden` like the official exports too), and the owner has a bisection
that needs only button presses (below).

## The new Place (src/tts/loop_box.lua)

A Still Hour box is laid out again every loop, after its decks were drawn,
shuffled and discarded, so SCED's bag (it empties, and Recall returns only what
kept its GUID) cannot be used as is. The box never empties:

1. `self.clone` makes a native copy of the whole box (copy and paste), parked
   above it and frozen.
2. On the copy it does what SCED's Place does: `takeObject({guid, position,
   rotation, smooth = false})` for every remembered object, `setLock`, one
   object every 6 frames, each announced in chat and in the Lua log before it
   runs. If the copy renumbered what it holds, it takes by position in the bag
   instead (highest first).
3. The empty copy is destroyed and the board sync runs in announced stages.
4. A second press while placing, or while the box's objects are on the table, is
   refused (SCED would move them), and so is a press while another box's cards
   lie where this one lays out (Clear Board first). Recall and the Control
   token's Clear Board clear by tag, stop a Place that is still running, and
   take the tokens resting on the cards with them (Reset Loop does not clear the
   board). Before anything is taken, SCED's Token Spawn Tracker (which remembers
   by GUID which locations already spawned their clues) forgets the GUIDs about
   to be laid out, because the objects keep their GUIDs from loop to loop; the
   Control token drops what it remembered by GUID about a removed card for the
   same reason, and reads a CLOSED label off the card instead of remembering it.
5. A working copy left on the table by a save taken during a Place destroys
   itself when it loads (unless the box it was copied from is still laying out).
   Each step of a Place is guarded: an error in one object is logged and the
   next object comes out, so a box is never left "placing".
6. After a Place the Control token says, once, in one sentence naming the box as
   printed on it, when the box is out of context (the Prologue box after the
   Prologue, the last box before its time, a district nothing on the table
   connects to the Square yet). It never says why.
7. Neither the chat nor `Player.log` carries a card's title: the log names each
   object by kind and GUID ("taking 3/10 object <guid>", then "took ... as
   <guid>"), so a log pasted into a message spoils nothing. (An entry's `name`
   in `getObjects()` is the object's display name, a card's title; an earlier
   version of the trace read it.)

Nothing is rebuilt from data in Lua: no `spawnObjectData`, no JSON round trip,
no new GUIDs. The tags (`StillHourLoop`, `StillHourBox_<box id>`) are in the
build data on every object and every card inside a deck.

## If it still stops: the bisection (owner, button presses only)

Load a fresh table each time; after a stop, send the last 60 lines of
`%USERPROFILE%\AppData\LocalLow\Berserk Games\Tabletop Simulator\Player.log`.
The log ends on the step that was running ("taking 3/8 ..." etc.).

1. Place on **The Lighthouse**, **The Sunken Road** and **The Last Hour** (the
   smallest boxes).
2. Place on **The First Hour**, then **The Square**.
3. Built: the `Place test` Saved Object (`dist/saved_object_place_test.json`,
   steps in `docs/PLACE_TEST.md`): one card; the First Hour's structure on one
   shared image; the First Hour on sprite sheets (the build); the First Hour
   with one image per card (the old build); and the sprite-sheet First Hour laid
   out by SCED's own unmodified Place script. The first that stops names the
   cause (a card, structure, texture count, or the script itself).

## Other findings of this audit

- `src/tts/download_box.lua` (the Download placeholder) could not work as
  written: `GlobalApi.placeholderDownload` is a module SCED's own scripts
  require; the placeholder's script does not, so the call was nil, and the URL
  SCED builds is Chr1Z93's release, which has no file of ours. Status: **Fixed**:
  the box fetches the campaign from the address in its GMNotes (GitHub's `main`
  by default) and spawns it, as SCED's own downloader does; the Saved Object
  stays the primary load path.
- `All Encounter Cards` (SCED) reacts to every spawned Deck or Bag with a
  delayed `getData()`, but only when its card index is populated, which it is
  not in 4.9.2's save; ids `sthr-*` would not match anyway. Accepted.
