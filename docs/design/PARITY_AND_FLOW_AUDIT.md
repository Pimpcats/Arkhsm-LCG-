# Parity and flow audit (2026-10-06)

Designer-facing; no campaign content: boxes are named by role (Prologue box, Square box,
district box, finale box), cards by kind. Question: is The Still Hour scripted and does it
play like an official SCED campaign, and can a first-time player get stuck or find missing
pages or text? Status values (as in DECKBUILDING_REVIEW.md): **Fixed**, **Accepted**,
**Watch**, **Rejected**; **Different on purpose** where the campaign deliberately differs.

## What was run

| Audit | Method | Scope |
|---|---|---|
| Parity | SCED 4.9.2's own scripts and the 38 official campaign and scenario packages its Download menu serves (13,808 objects, 162 distinct scripts), a read-only probe suite on the real table | scripting inventory, box anatomy, Place mechanics, load path, capability matrix |
| Stuck states | static reading plus 15 headless suites and fuzzing against the real SCED table | every state of the Control token and the log, every Place / Recall / Clear Board / Reset Loop order |
| Entire run | the play engine on the real 4.9.2 table: 459 games over all boxes, parts and 1-4 investigators, owner-flow (104 checks), button sweep (576 clicks over 302 buttons), update flow, official-box comparison (75 Place/Recall pairs) | errors, gaps, notes, abnormal endings |
| Pages and text | the shipped guide PDF, log pages, card faces (OCR of 183 faces), object text, against the sources | missing, stale, clipped or misleading text; navigation |
| Card pool | 1,796 official player cards and 3,795 fan cards against the five investigators | brokenness and balance (docs/design/DECKBUILDING_REVIEW.md) |

Limits (all four): none of this ran in real Tabletop Simulator. The emulator cannot load
images, reach native faults, or settle physics; it keeps a saved GUID when it is free, which
is believed to match TTS. Passing here is not playtest approval and not art approval.

## How an official campaign is scripted, and where this one differs

- **Load.** The Download menu fetches `<SOURCE_REPO><filename>.json` and spawns it
  (`spawnObjectJSON`). This campaign loads from a Saved Object (the primary path) or from its
  own Download Box, which fetches the build from GitHub. Different on purpose.
- **Campaign box.** SCED's MemoryBag (one script on all 234 memory bags in the 38 packages).
  Same script, same layout here (guide, log, boxes), plus the Control token, the Player Cards
  bag and the Static token. Built.
- **Scenario box.** The same MemoryBag: Place takes objects out by GUID, Recall puts back.
  Here the box never empties (it is laid out again every loop), so Place works on a native copy
  with SCED's own `takeObject` step. Different on purpose.
- **Scripted box contents.** Median 1 scripted object per official box (a Set Up helper in 42%,
  a difficulty tile in 70%, a reference card in 92%). Here the Control token carries the
  scripting; the boxes hold cards only. Place also does Loop Setup (see G5).
- **Textures.** Official boxes use sprite sheets (median 9 textures per box, 44% are 10x7).
  Each box here now loads at most 4. Fixed.
- **Mythos area.** SCED's agenda/act advance buttons, doom counter, scenario reference
  reading and chaos-bag token table work with these cards (probe suite P1-P9). The Hour counter
  is the Control token's; SCED's own doom reset runs on each Hour change. Built.
- **Where this campaign is ahead:** Control-driven chaos bag that keeps campaign changes;
  interlude and purchase panel; derived and hidden-name log fields; log round trip through
  SCED's exporter; a headless test harness.

## Place, Recall, Clear Board, Reset Loop (stuck-state audit, entire run)

| # | Finding | Status |
|---|---|---|
| N-1 / QA-01 | The new Place keeps the GUIDs a box holds; SCED's Token Spawn Tracker remembers by GUID which locations already spawned clues, so from loop 2 on no clues spawned (in the emulator; real TTS may renumber) | Fixed: Place makes the tracker forget those GUIDs before laying out; regression suite lays a box out three times and counts clues |
| N-2 | The Control's GUID-keyed location memos (flipped, sealed, labelled) said "done" for a new card with an old GUID, so a CLOSED label was never re-applied and Sync Board did not repair it | Fixed: the memos of a removed card are dropped (Board.onDestroy, Clear Board, Recall) |
| N-3 | The "already laid out" message named Reset Loop (which does not clear the board) | Fixed: names Clear Board; guide and loading notes describe the refusal |
| N-4 | Recall or Clear Board pressed during a Place left a half layout and a refused next Place | Fixed: both stop a running Place first |
| N-5 / QA-04 | Recall left the clue tokens of the cards it removed | Fixed: Recall takes the tokens resting on a card with it, by Clear Board's rule |
| N-6 / QA-06 | A save taken during a Place left a working copy, a second Place-able box | Fixed: a working copy destroys itself on load |
| N-7 | Prologue or finale box could be placed in an ordinary loop, a district without its prerequisite, with no word | Fixed (announce only) |
| QA-03 | Copies of one card shared one GUID inside box decks (the official norm, but Place now keeps GUIDs and SCED keys state on them) | Fixed: each repeat gets its own GUID (compile step); every GUID in a box is unique |
| QA-05 | After an update an old box's layout is not recognised by a new box (older tag) | Fixed: a Place refuses when another box's objects occupy its spots; update note in LOADING.md |
| QA-07 | One error inside a Place step could leave the box "placing" | Fixed: each step guarded |
| G12 | Prologue box and Square box share the Mythos spots; both placed stack decks | Fixed: Place refuses ("Clear Board first") |
| QA-10..12 | Emulator noise (double count in Clear Board's message, SCED's own destroyed-object warnings) | Accepted |
| QA-11 | Two location cards land on SCED table pieces (tour tile, lead investigator marker) | Accepted (official boxes do this far more) |

## Control token and campaign log flow

| # | Finding | Status |
|---|---|---|
| F-01 | Begin Next Loop without Reset Loop started a "next loop" at the old Hour and Dissonance and never counted the loop | Fixed: refused ("Click Reset Loop first") |
| F-02 | After Reset Loop, Interlude then Back led to a play panel headed "loop N+1" with no way to end that night | Fixed: the panel reads BETWEEN LOOPS and offers only what applies |
| F-03 | Replacing the Control after turning the log to another page restored a blank or stale campaign (the mirror sat in the shown page's memo only) | Fixed: the mirror follows the page turn; a Control that starts blank beside a log with entries says so |
| F-04 | The first chaos-bag-changing action after a load was taken as the baseline and swallowed | Fixed |
| F-05 | The sealed location stayed CLOSED when the second gating entry was recorded mid-loop and its box placed later | Fixed |
| F-06 | One accidental Reset Loop ended the loop with no way back | Fixed: a loop not over by the Control's count asks first (click again to confirm) |
| F-07 | Departed or aged-out investigators stay in the roster (a warning every interlude) | Watch (warn-then-proceed; the party size is set by hand) |
| F-08 | No campaign-end state | Fixed: a neutral banner when no investigator can continue; the guide's Age stories end the campaign |
| F-09 | Un-ticking a Victory box refunds nothing; a taken-back quest tally leaves it unlocked | Watch |
| F-10 | Finale could begin in the Prologue; unticking its entry mid-finale left it running | Fixed |
| F-11 | Two Campaign Logs on the table silently disabled mirroring | Fixed: one-sentence warning; no mirroring over a newer log |
| F-12 | Non-SCED tables lose a defeated investigator's on-card Memory at Bank | Accepted (the campaign is played on SCED) |
| G8 | The Control's Investigators counter was separate from SCED's | Fixed: it sets SCED's counter (one way) |
| G13 | A "Run Tests" button and a developer description on the Control | Fixed: removed (the relay still calls the function) |
| G14 | A Reloadable tag with nothing to reload | Fixed |
| G20 | The Control was unlocked after Place | Fixed |

## Text, pages and navigation

| # | Finding | Status |
|---|---|---|
| TXT-01 | Nothing said the log token has three pages or how to turn them | Fixed: guide Campaign Setup, LOADING.md |
| TXT-02 | The Place refusal named the wrong button | Fixed |
| TXT-03 | Wrong object named for the Player Cards bag | Fixed |
| TXT-04 | Docs the guide cited cannot be opened in Tabletop Simulator | Fixed: starting decks for all five investigators are an appendix of the guide |
| TXT-05 | No contents or bookmarks in a 25-page guide | Fixed: printed contents with page numbers, PDF bookmarks, and a right-click Guide menu on the Control token |
| TXT-06 | Four of nine "Do not read until..." guards shared a page with text read before them | Fixed: guarded text starts on a new page; every district, Between Loops and each later interlude story starts on its own page (the guide grew from 25 to about 38 pages) |
| TXT-07 | Half-empty pages; the chaos-bag table split across pages | Fixed (table kept whole); the empty halves are the new page breaks |
| TXT-08 | "[static]" printed as literal markup 16 times | Fixed: the words "Static token"; only the two lines that name the Control's button keep it |
| TXT-09 | Standing rules of earlier choices had to be found again in the district pages | Fixed: they show under their choice on the log once it is ticked |
| TXT-10 | The always-open rules name some Knowledge entries the log hides | Accepted: the entries' names are on the cards in play |
| TXT-11 | Three hidden-name labels overflowed the log; four showed bracket tokens | Fixed |
| TXT-12 | Log page 1: hit areas overlapped, write-in line below the text frame | Fixed (tests: no overlap, nothing outside the frame) |
| TXT-13 | Solo scar read-out 3 instead of 4 in the shipped build | Fixed (rebuild) |
| TXT-14 | Victory location names printed in the clear on the log | Fixed: hidden until claimed |
| TXT-15 | No log field for campaign chaos-bag changes | Fixed: the guide says Campaign notes |
| TXT-16 | Flavour left off 23 faces; rules at 22-24 px on four | Accepted as a design choice; the print audit now pins the list and a 22 px floor |
| TXT-17 | The last Hour printed an empty doom disc | Fixed: a dash |
| TXT-19, 20 | Stale developer text; button labels wider than their buttons | Fixed |
| TXT-21 | Manifest missing the loop's fourth ending; one name drifted | Fixed |
| TXT-22 | Four copies of each Recollection for up to eight wanted | Changed: two (a deck's limit); the bag listed 110 cards with eight copies of each, which read as a mistake. A third copy is a TTS copy, as the guide says |

## Scripting parity (capability gaps)

| # | Gap | Status |
|---|---|---|
| G1 | Place unverified in real TTS; the owner's dist file one generation behind | Rebuilt and pushed with this audit; the Place test (five boxes) and `Player.log` settle it |
| G2 | Place chat printed every card title | Fixed: kind and GUID only |
| G3 | Hour counter and agenda deck are double entry | Partly fixed: the Hour button runs SCED's own doom reset; moving the Hours deck stays by hand (guide) |
| G4 | Player cards unindexed, no pre-built decks | Partly fixed: starting decks in the guide for all five; community packs are loose bags too (Different on purpose) |
| G5 | Loop Setup was manual: shuffling each district's encounter set and the Whispers into the encounter deck, putting the Approach into play, setting the act decks | **Built (2026-10-10).** After each Place the Control token's board sync runs `setUpPlacedBox`: the encounter set (and the Fairground's Named in Part II) into the shared encounter deck, the Approach to the mythos mat, the Whispers from Part II, the act deck set from the log (removed, 1a current or 2a current) and a shuffle. Checked in `tests/sced_real/playthrough.lua` and the play engine; not yet in Tabletop Simulator |
| G6 | SCED's "Reset play areas" deletes investigators and decks | Fixed: warned in the guide |
| G7 | Act clue thresholds missing, SCED's clue-spend flow never runs | Watch (acts spend clues by their own text) |
| G9 | Per-loop investigator reset by hand | Watch (beyond official) |
| G10, G11 | Set-aside is a face-down deck; reference card in 2 of 8 boxes | Accepted |
| G15 | Docs contradicted the new Place | Fixed |
| G16 | No guide page jumps | Fixed: right-click the Control token |
| G17 | Resolution recording is double entry | Watch |
| G18 | One image per card | Fixed: sprite sheets |
| G19, G21 | Log memo and tags; difficulty prompt | Accepted |
| G22 | Control script 217 KB (largest official 85 KB) | Watch |
| G23 | Download menu listing, XML UI, localisation, notecards | Different on purpose |

## What only the owner's table can settle

Whether Place no longer stops the game (the Place test and `Player.log`); whether TTS keeps
saved GUIDs through a native copy (check: Place a box, flip its locations, Clear Board, Place
again, count clues); how landscape cells of a sprite sheet display; legibility of the smallest
rules text on a 585 x 819 cell; the first playtest.
