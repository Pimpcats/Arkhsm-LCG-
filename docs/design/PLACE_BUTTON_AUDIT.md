# Place button audit (rewritten 2026-10-06)

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
2. **The owner's published build still has the first version of the Place
   script.** `dist/saved_object_the_still_hour.json` (built 2026-10-05 20:25)
   predates the staged-spawn commit 52cb886 (20:32); its scenario script is
   byte-identical to `git show 52cb886^:src/tts/loop_box.lua`. The crash was
   seen with that script, and nothing newer has reached the owner's table yet.
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
| 1 | Card textures and CustomDeck ids per box, one frame | median 9 / max 27 textures; median 7 / max 21 ids | The First Hour **43 / 29**, The Square **57 / 41**, others 12-20 (every card is its own 1x1 sheet; 128 of 128) | Planned (in progress): pack the cards into sprite sheets, a handful of textures per box |
| 2 | Per-card `CustomUIAssets` font bundle | 4 of 11,483 cards (a helper with XML UI) | 203 of 208 cards, unused (no XML UI, no object-UI code) | Fixed in the build code (`pipeline/build_cards.py`); reaches `dist/` with the next rebuild |
| 3 | The old Place rewrites everything in the click frame | `takeObject` of stored data, GUIDs kept | `self.getData()`, `JSON.decode(JSON.encode())` of every object, a random 6-hex GUID and two new tags on every nested object including each card in a deck, then `spawnObjectData` | Fixed in `src/tts/loop_box.lua` (a native copy of the box, SCED's own `takeObject` on it); reaches `dist/` with the next rebuild |
| 4 | Follow-up work 2 s after Place (board sync, chaos bag) while textures load | none | Control `shApiSyncBoard` | Fixed on the branch (52cb886); not in the published build |
| 5 | Image encoding and host | Steam CDN | `raw.githubusercontent.com`, 200 of 200 progressive JPEGs | Planned with #1: baseline JPEG sheets; the host stays |
| 6 | Tag `StillHourBox:<guid>` (colon) | tags are letters, digits, underscore | colon, added at run time to every nested object | Fixed in the build code (`pipeline/table_presence.py`); reaches `dist/` with the next rebuild |
| 7 | Windows cache path length (unverified) | | 115-134 characters per URL | Accepted (sheet URLs are shorter and far fewer) |
| 8 | Object count, JSON size, nesting, deck size, scripts on contained objects, GMNotes and tag vocabulary, chaos-token keys, Deck/CustomDeck consistency, id collisions, SCED's Lua reaction | | all smaller than or equal to the official median, or identical | Rejected as causes (MEASURED, EMULATED) |

Because items 1-3 first appear at the same step they cannot be separated from
this data. The new build therefore removes all of them, and the owner has a
bisection that needs only button presses (below).

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
   refused (SCED would move them); Recall and the Control token's Reset Loop
   clear by tag.

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
3. Planned: a `Place test` Saved Object (dist/saved_object_place_test.json)
   holding the First Hour three ways: with no textures at all, with one image
   per card (the old build) and with sprite sheets; the first that stops names
   the cause (structure, texture count, or neither).

## Other findings of this audit

- `src/tts/download_box.lua` (the Download placeholder) cannot work as written:
  `GlobalApi.placeholderDownload` is a module SCED's own scripts require; the
  placeholder's script does not, so the call is nil, and the URL SCED builds is
  Chr1Z93's release, which has no file of ours. Status: Watch (the scripting-parity
  review will decide how the campaign is delivered).
- `All Encounter Cards` (SCED) reacts to every spawned Deck or Bag with a
  delayed `getData()`, but only when its card index is populated, which it is
  not in 4.9.2's save; ids `sthr-*` would not match anyway. Accepted.
