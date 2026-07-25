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

Everything is optional except `id` (and `type`+`name` for new cards).

- **all types** — `name subtitle traits text flavor victory class`
- **Asset/Event/Skill** — `cost level slot health sanity wil int com agi`
- **Investigator** — `wil int com agi health sanity back_text`
- **Enemy** — `fight health evade damage horror elite unique`
- **Treachery** — `weakness`
- **Location** — `shroud clues clues_per_investigator icons color
  connections[{symbol,color}]` (symbols: circle square triangle diamond moon
  star heart hourglass cross quote slash doubleslash spade clover t;
  colors: named or #hex)
- **Scenario** — `difficulty tokens[{token,text}]`
  (tokens: skull cultist tablet elderthing)
- **Agenda/Act** — `doom clues index number`
- Rules text takes the same `[markup]` as the editor: `[action] [fast]
  [reaction] [wil] [int] [com] [agi] [wild] [perinv] [unique] [skull]
  [cultist] [tablet] [elderthing] [elder] [autofail] [codex]`.

### Scenario board stacks

`locations act_deck agenda_deck encounter named reference setup_aside` —
per scenario id from `campaigns/still_hour/scenario_manifest.json`
(prologue, district_lighthouse, district_church, district_road,
district_square, district_fairground, district_almanac, finale).
