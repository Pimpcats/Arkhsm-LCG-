# Campaign feed — pour a written campaign into the editor

## Two ways to use it

**Add to the campaign you have open** — open `5 · Scenarios` and hit
*Import campaign JSON…*. Cards whose ids already exist become edits; new ids
become new cards.

**Start a brand-new campaign** — click **+ New** beside the campaign selector
in the header, name it, then import into it. The new campaign gets its own
folder under `campaigns/<id>/`, its own cards, its own scenario board and its
own output, and inherits the locked house style. Nothing touches your other
campaigns.


`6 · Scenarios → Import campaign JSON…` (or `POST /api/campaign_import` with
`{data: <json>}`). The feed pre-fills exactly the data the manual editor
edits — nothing is locked afterwards; every imported value can still be
changed by hand, card by card. That is the manual-first contract: an AI- or
hand-written campaign is just a faster way to fill the same forms.

## What happens on import

- **Known card id** → the fields become that card's editor overrides
  (same as typing them into the card editor).
- **Unknown card id** → a new card is created in
  `pipeline/stillhour_imported_spec.json` and joins the catalog, renderer,
  exports and the Scenarios board like any authored card.
- **assignments** → merged into the deck-builder board
  (`campaigns/still_hour/scenario_assignments.json`).
- Every face re-renders; the import reports `created / updated / skipped`.

## Schema

```json
{
  "campaign": "still_hour",
  "cards": [
    {
      "id": "sthr-my-location",
      "type": "Location",
      "name": "The Tide Shrine",
      "traits": "Ambergrove. Coastal.",
      "shroud": 3, "clues": 2, "clues_per_investigator": true,
      "icons": "heart", "color": "#2c5a9a",
      "connections": [{"symbol": "star", "color": "#25807a"}],
      "text": "[action] Pray: Test [wil] (3). On success, discover 1 clue.",
      "flavor": "The sea remembers what the town forgot.",
      "victory": 1
    },
    {
      "id": "sthr-my-enemy", "type": "Enemy", "class": "Mythos",
      "name": "The Harbor Thing", "traits": "Monster.", "elite": true,
      "fight": 3, "health": 4, "evade": 2, "damage": 2, "horror": 1,
      "text": "Hunter.", "victory": 2
    },
    {
      "id": "sthr-my-scenario", "type": "Scenario", "name": "The Harbor",
      "difficulty": "EASY / STANDARD",
      "tokens": [
        {"token": "skull", "text": "-X. X is the number of Sunken locations."},
        {"token": "cultist", "text": "-2."}
      ]
    },
    { "id": "sthr-loc-lanternroom", "shroud": 5 }
  ],
  "assignments": {
    "district_lighthouse": {
      "locations": ["sthr-my-location"],
      "named": ["sthr-my-enemy"],
      "reference": ["sthr-my-scenario"]
    }
  }
}
```

### Card fields by type

Everything is optional except `id` (and `type`+`name` for new cards). The feed
can set exactly what the card editor can set — no more, no less — so anything
here can also just be typed in by hand under **Card content → Card properties**.

- **all types** — `name subtitle traits text flavor victory class`
- **Asset/Event/Skill** — `cost level slot health sanity wil int com agi
  memoryCost`; Asset also `uses permanent`; Skill also `wildIcons`
- **Investigator** — `wil int com agi health sanity back_text back_flavor
  deck elderSign signatures`
- **Enemy** — `fight health evade damage horror elite unique weakness
  encounter quantity`
- **Treachery/Story** — `weakness encounter quantity`
- **Location** — `shroud clues clues_per_investigator icons color
  connections[{symbol,color}]` (symbols: circle square triangle diamond moon
  star heart hourglass cross quote slash doubleslash spade clover t;
  colors: named or #hex)
- **Scenario** — `difficulty number tokens[{token,text}]`
  (tokens: skull cultist tablet elderthing)
- **Agenda/Act** — `doom clues index number` — `index` is what prints
  ("Agenda 1"), `number` is the encounter number ("1/9")
- **CampaignLog** — `campaign_name player investigator1..3 xp1..3`
- Rules text takes the same `[markup]` as the editor: `[action] [fast]
  [reaction] [wil] [int] [com] [agi] [wild] [perinv] [unique] [skull]
  [cultist] [tablet] [elderthing] [elder] [autofail] [codex]`.

### The location map

`5 · Scenarios → 🗺 map` on a scenario box opens the black bordered slot grid
you see when a scenario is laid out in TTS.

**The grid is 5 columns × 5 rows** — the slots the playmat shows in TTS. The
step and origin are measured off the real scenario box
(`docs/art_reference/sced_objects/scenario_box_memory_bag.json`): columns 6.60
apart from x −30.24, rows 7.65 apart from z 11.46. The 5 × 5 extent comes from
the playmat itself; the exact coordinates of the outer column and row are
extrapolated from that step, not measured. Exporting the playmat object would
settle them — a TTS playmat carries its snap points.

- **Arrange** — drag location cards between slots, then *Save layout*. Those
  exact coordinates are what the campaign box scripts.
- **Connect** — either click one location and then the one it connects to, or
  grab the coloured connector nub on a card and drop it on its neighbour. Both
  cards immediately print the other's symbol; a location with no symbol yet is
  given a free symbol and colour. Repeat on the same pair to unlink.
- **Table preview** — the whole scenario drawn to scale from above: locations
  where you put them, plus the encounter / agenda / act / named / reference /
  set-aside furniture they have to fit around. Anything that overlaps is
  outlined in red. This is the layout the campaign box will spawn, so you can
  see whether it works before sending anything to TTS.

Connections are stored on the cards themselves (`icons` + `connections`), so
the map, the printed card and the compiled object can never disagree.

### How connections reach TTS

**SCED draws the lines itself, from the cards.** Put two connected locations on
the playmat and it links them; drag one anywhere and the line stretches to
follow; take one off the mat and the line goes. It works off symbol matching,
not positions: each location's GMNotes carry `icons` (its own symbol) and
`connections` (the symbols it connects to), and the mod pairs one card's
`connections` entries against the other cards' `icons`.

So nothing about the lines needs to be compiled into the box — and the box
could not carry them anyway. The memory bag's `onLoad` reads exactly two keys
out of a box's saved state and discards the rest:

```lua
memoryList  = loadedData.ml          -- guid -> {pos, rot, lock}
setupButton = loadedData.setupButton
```

Anything else in that state is decoded and discarded, so the compiled box
writes `ml` and nothing else. Placement is a GUID lookup: Place walks
`memoryList` calling `setRotation` / `setPositionSmooth` / `setLock`.

What TTS *does* read is the card's own metadata. A real location carries:

```json
"locationFront": {"icons": "Diamond", "connections": "Tee|Plus|Circle|Square"}
```

Compiled locations carry exactly that shape, so SCED draws our maps' lines the
way it draws its own — that is the whole hook-up, and there is nothing further
to wire.

The lines on our map and table preview mirror that behaviour: edge to edge,
stretching to wherever you put the cards, and gone the moment a location leaves
the board. One thing ours add — each half of a line is coloured with the symbol
at the *far* end, so following a colour off a card leads you to the location
whose symbol that is. SCED's own lines are plain white.

### Scenario board stacks

`locations act_deck agenda_deck encounter named reference setup_aside` —
per scenario id from `campaigns/still_hour/scenario_manifest.json`
(prologue, district_lighthouse, district_church, district_road,
district_square, district_fairground, district_almanac, finale).
