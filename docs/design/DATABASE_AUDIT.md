# Card database audit (2026-10-06)

Designer-facing; ids, counts and structure only, no rules text. "Database" here
is everything the build ships as data: the card objects, decks and boxes in
`dist/` (what Tabletop Simulator loads) and the four layers they are built
from (spec, print text, the owner's overrides, the build code).

Method. Two audits, both against the owner's real SCED 4.9.2 save and the 38
official campaign and scenario boxes its Download menu serves (11,483 official
card entries, 3,851 distinct ids; the Download menu's 199 items are cached in
`.cache/official/tts_menu/` and their cards listed in
`library/save_4.9.2/`):

1. **Structure** against TTS and SCED. Re-runnable: `python3
   tools/audit_database.py` (about 2 s, exits 1 on any ERROR; `--online` also
   checks every hosted URL; tests in `tests/test_database_audit.py`).
2. **Content**: every id, quantity, text, number and flag compared across the
   specs, print text, overrides, art manifests, engine, Lua, guide, starter decks
   and `dist/`; a typo scan against a 20,356-word official corpus; OCR of every
   shipped face.

Status values (as in DECKBUILDING_REVIEW.md): **Fixed**, **Accepted**, **Watch**,
**Rejected**. Everything marked Fixed is in the rebuilt `dist/` that ships with this
audit (`tests/test_dist_fresh.py` fails whenever `dist/` falls behind the specs or the
rules code).

## Structure

Verdict: no structural defect was found that explains a native Tabletop
Simulator stop by itself. Decks, ids, grids, `ml` memory lists, URLs (all 101
hosted files exist, match their `?v=` hash, are byte-identical in the pinned
commit and answered HTTP 200), tags, transforms and Lua syntax are clean. What
remains is "unlike every official box" (below).

| # | Finding | Status |
|---|---|---|
| S1 | `CustomUIAssets` font bundle on 203 of 208 cards (official: 4 of 11,483, helpers with XML UI; nothing of ours uses it) | Fixed |
| S2 | The shipped scenario-box script and Control are older than `src/` (one-frame `spawnObjectData` Place; no quest cards in the Control) | Fixed: `dist/` rebuilt; `tests/test_dist_fresh.py` now fails when `dist/` is behind the specs or the rules code |
| S3 | Texture budget per Place: The First Hour 43 textures / 29 deck ids, The Square 57 / 41 (official median 9 / 7, max 27 / 21); every card its own 1x1 sheet | Fixed: sprite sheets, 4 textures per box (SPRITE_SHEETS.md) |
| S4 | All 199 JPEGs progressive | Fixed: baseline |
| S5 | `BackIsHidden` false on 127 of 137 deck entries (official exports: true everywhere) | Fixed |
| S6 | Card scale 1.15 on 221 of 227 cards and decks (official: 1.0; investigators 1.15) | Fixed: 1.0, investigators 1.15 |
| S7 | Five story assets with `cost` as the string "–" (official: always an integer; SCED's AttachmentHelper compares it to a number) | Fixed |
| S8 | Lexicon `uses` token `secret` (official: always `resource`; SCED's TokenManager raises on an unknown token if it ever spawns one; with `resource` and a count of 0 SCED spawns a counter) | Fixed (spec) |
| S9 | Download box could not work: `GlobalApi` is not a global in an object's script, and SCED's menu reads only its own release | Fixed: the box fetches the campaign from the address in its GMNotes and spawns it (`src/tts/download_box.lua`); tests in the mock TTS |
| S10 | The Place script (see PLACE_BUTTON_AUDIT.md) | Fixed |
| S11 | Campaign log and guide lacked `CameraZoom_ignore` / `CleanUpHelper_ignore` (SCED's Clean Up Helper trashes every unlocked, untagged object lying in the play area) | Fixed: the guide, log, Control token and static token carry the ignore tags (90% of official logs and 55% of official guides do); the Control and the box stay locked
| S12 | The last Hour has no `doomThreshold` (96% of official agendas have one) | Accepted: it has no doom threshold by design |
| S13 | 25 of 202 GUIDs repeated, always as copies of one card | Fixed: each repeat of a card in a deck gets its own GUID (`compile_campaign.build_deck`). The official data shares one GUID per copy group, but Place now keeps the GUIDs a box holds and SCED keys state (which locations already spawned their clues) on them; the entire-run audit found engine games invalid on the repeats. Test: every GUID in a scenario box is unique |
| S14 | The Control script is 217 KB (the largest script in any official box 95 KB) | Watch |
| S15 | Minicard images 0.651 aspect (not 5:7) | Accepted: follows the official minicard export |
| S16 | `dist/cards/sthr-campaign-log.jpg` is referenced by nothing | Accepted: kept as the record of the log's face |
| S17 | The investigator minicards took deck ids from a hash into 99000-99899, and Seraphine's equalled a sprite sheet's id (the Fairground's): two images under one id (audit rule A10; found on the first audit of the real rebuild) | Fixed: one id per investigator from 99800 up, sheets stay below it (asserted in `pack_sheets`) |
| S18 | The Place test's structure box showed one image where its per-card twin shows many, under the same deck ids | Fixed: its own ids (`place_test.new_deck_ids`); test |
| S19 | The audit treated the Place test as a second campaign (cross-file comparisons, repeated cards) and compared where a card's picture sits between boxes that pack their own sheets | Fixed (tool): the Place test is a diagnostic file; a card two boxes share has a CardID in each box's sheets (info); copies are compared by content; a CardID repeated inside one box is still an error |
| S20 | `tests/test_publish_hosted.py` deleted the repository's `dist/cards/sheets` (its stale-sheet cleanup was not redirected with `OUT`) | Fixed |

## Content

| # | Finding | Status |
|---|---|---|
| C1 | `dist/` was the pre-redesign build: 10 new quest cards absent (and without art), 19 changed cards stale, eight faces matching the specs badly (OCR), the shipped guide PDF without the quest cards | Fixed: `dist/` rebuilt from the current specs. Quest-card art: Watch (ten faces render with placeholder art until art is generated) |
| C2 | The Hard / Expert side of the scenario reference card ignored its override (`back_tokens` read by no renderer) and shipped stale text in the image and the metadata, in the published build too | Fixed: consumed by `apply_card_overrides`; the stale lower layer frozen to the effective text; `tests/test_content_lints.py` fails on any override key no renderer reads |
| C3 | The Bell of Ambergrove shipped 3 charge tokens and printed 4 | Fixed (spec 4); lint: printed "Uses (N" equals `uses[0].count` |
| C4 | `build_art_manifest.py` exited 1 (the ten quest scenes were only in the hand-edited manifests) | Fixed: scenes in the generator. The committed manifests keep their seeds (they belong to the approved art), so they are not regenerated |
| C5 | Metadata deviating from SCED's model: four signature events without `level`; (S7, S8 above) | Fixed (spec/build); lint |
| C6 | The campaign log's solo scar cap was 3 (the Control uses 4, the printed label says 4/4/6/8) | Fixed |
| C7 | `production.json` and sibling docs state numbers that no longer match (133 effective cards: 143; guide pages 24: 25; "art complete"; pytest counts; the hosted commit) | Fixed with this rebuild (production.json regenerated) |
| C8 | Three data layers hold stale values the top layer overrides (99 spec fields on 61 cards; 43 print-text entries overridden; 317 no-op override values; two unused patch files) | Watch: the effective cards are tested; only the scenario reference card was frozen. Freezing every field is a separate clean-up |
| C9 | Two cards named "The Square" (Prologue and loop hub); a card titled like an official Dunwich scenario; id-naming outliers (`sthr<name>` for investigators) | Accepted |
| C10 | The quest cards are linked to code by name only; "(Investigator) deck only" text absent from signature and quest cards; `sthr-questdone-*` print "Bonded" without the official `bonded` key | Watch |
| C11 | Two bonded quest cards print their rules at 20-21 px (official 31): wording tightened to 22 px, flavour left off | Watch: judge legibility in TTS |
| C12 | Wording nits: "(limit once per loop)" lowercase on two cards, British "parlours", "flavour" in two designer docs, the loop mark "Torn" and the choice "torn out" share a word | Accepted |
| C13 | Stale comments and a dead trait test in the play engine (`Time` trait in flow.lua; "per loop" in players.lua; 6x memory cap in CampaignState) | Watch: no effect on the build; AI heuristics for two treacheries never fire |
| C14 | Signature, quest and unlocked cards carried `level: 0` (official signature cards carry none, so level-0 effects such as Scrounge for Supplies could fetch them) | Fixed: 20 cards without `level`; they render identically (a level-0 card prints no pip); lints require no level on these and a level on every other player card |
| C15 | No contents, bookmarks or navigation in the guide; four of nine "Do not read until..." guards shared a page with text read before them; the later interlude stories sat beside the first | Fixed: printed contents with page numbers, PDF bookmarks, a right-click Guide menu on the Control token, guarded text and each later story on pages of their own (`tests/test_guide_layout.py`, `tests/test_guide_menu.py`) |
| C16 | Log: three hidden-name labels overflowed the page and four showed bracket tokens; Victory locations were named in the clear; standing rules of earlier choices had to be found in the district pages; two hit-area overlaps and a field below the text frame | Fixed (log layout tests: no overlap, nothing outside the frame, labels fit) |
| C17 | Flavour text left off 23 faces and rules at 22-24 px on four (official body 31) | Accepted as a design choice; the print audit pins the list and a 22 px floor, so a new drop fails until it is added on purpose |
| C18 | The last Hour printed an empty doom disc | Fixed: a dash, as an act's circle prints |
| C19 | Scenario manifest lacked the loop's fourth ending and spelled one entry differently from the guide | Fixed |
| C20 | Four copies of each Recollection for up to eight wanted (four investigators, two copies each) | Fixed: eight |

## Verified clean (counts)

- **Identity:** 143 spec ids, no duplicates across the four spec files; every id in
  overrides (142), print text (54), the feed (72), connection patch (22), art
  placements (17) and the board (102) resolves to a card; art manifests: 148 entries
  = 143 cards + 5 investigator backs; no id, deck id, CardID or GUID collides with the
  official data (1,158 deck ids, 6,032 card ids, 6,316 GUIDs).
- **Shipped objects:** 19 Decks, 203 Card and 5 CardCustom objects; every `DeckIDs`
  equals its cards' CardIDs in order; every `ml` key is a direct child; the Saved
  Object's box is JSON-equal to the download asset.
- **Quantities:** the three starter decks are 30 legal level-0 cards each (type splits
  13/13/4, 12/10/8, 13/12/5); investigators' skills sum 12-13, health plus sanity
  13-14; requirements equal the signature ids; the ten Recollection prices equal the
  Control's table.
- **Scenarios:** 8 of 8 scenario audits clean (acts, agendas, locations, encounter decks,
  set-aside, connections symmetric and connected, shroud and clues equal the effective
  cards, thresholds equal printed costs); 14 Knowledge facts in the Control equal the
  log; difficulty chaos bags equal the guide.
- **Lua:** all scripts compile on Lua 5.2 and 5.4; no `io`/`os`/`require`; no Card or
  Deck carries a script.
