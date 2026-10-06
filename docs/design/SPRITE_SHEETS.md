# Sprite sheets (2026-10-06)

Designer-facing; no campaign content.

## Why

A scenario box's Place spawns its decks and cards, and Tabletop Simulator then
loads every image they name. SCED's own boxes need a handful: over the 145
official scenario boxes the median is 9 card-sheet textures and the largest 27,
because their cards are packed into sprite sheets (a TTS CustomDeck is a grid of
cards in one image). The Still Hour drew each card from its own image, so The
First Hour needed 43 textures and The Square 57 (more than any official box),
all requested in the frame its Place spawns them. The owner's game stopped at
that Place. The cause is not proven (docs/design/PLACE_BUTTON_AUDIT.md), and the
texture count was the largest difference from the official boxes, so the
release no longer has it.

## What the build does now

`pipeline/pack_sheets.py` (called by `pipeline/publish_hosted.py`) packs, per
box (each scenario box, the player-card bag, the investigators):

| | portrait cards | landscape cards (agendas, acts, investigators) |
|---|---|---|
| cell | 585 x 819 | 819 x 585 |
| most cells on a sheet | 7 x 5 (4095 x 4095 px) | 5 x 7 (4095 x 4095 px) |
| sheet | only as big as its cards need | the same |

- one sheet = one CustomDeck id (99100 upward, in sorted key order; the
  per-card ids 95010-98999 and every official id are clear of it); a card's
  CardID is the deck id times 100 plus its cell, row by row from the top left;
- every sheet has a face image and a back image of the same grid
  (`UniqueBack` true): a card's cell on the back sheet holds its own back (a
  location's other side, an investigator's deckbuilding back) or the shared
  player / encounter back;
- baseline JPEG, quality 88, hosted at
  `dist/cards/sheets/<key>-face.jpg` / `-back.jpg` like every other image
  (pinned to a commit, `?v=<hash>`);
- art_urls.json carries `"_sheets": {key: {box, deck, cols, rows, sideways,
  cells: [card ids], face, back}}`; `build_cards.build_card(card, box=...)` uses
  it. Without it (a local build, the Studio's live preview) every card keeps its
  own 1x1 deck as before. The per-card images stay in `dist/cards/` as the
  record of each final face.

Result (The Still Hour): 18 sheets, 39 MB; every scenario box loads 4 textures
(a face and a back sheet for its portrait cards, the same for its landscape
cards), the player cards 2, the investigators 2. The First Hour 43 -> 4, The
Square 57 -> 4.

## Checks

tests/test_sheets.py: the plan's geometry and ids, every cell holds its card and
its back (pixel check on synthetic faces), wrong-shaped faces are refused, a
compiled campaign draws every scenario card from its own box's sheets with the
right cell and at most 4 textures per box, deck ids clear of the per-card ids.
tests/test_publish_hosted.py: the sheet URLs, grids and cells reach
art_urls.json pinned to the commit, and stale sheets are removed.

## Watch

- Resolution: a face is 585 x 819 on a sheet against 750 x 1050 as a single
  image (78% of the linear resolution, about 40% more than an official sheet
  cell). Legibility of the smallest rules text is a thing to look at in TTS.
- Every box has its own copy of a card that several boxes hold (a Hour card, the
  scenario reference): same GUID, different CardID.
- Whether TTS shows a landscape cell of a SidewaysCard deck the way a landscape
  1x1 image was shown (the same orientation convention; the Godot renderer's
  calibration says the landscape image is turned onto the card).
