# Scenario Requirements Schema

The contract the CardForge scenario-builder fills in. When you feed a campaign
(a campaign guide + card lists) into the editor, it produces one
`campaigns/<name>/scenario_manifest.json` describing **what every scenario
requires** — every stack, every card slot, every field. The builder then shows
those stacks as fill-in decks (art + text + type), and the *finalize* step turns
the completed manifest into scripted, self-placing TTS objects.

This is the "what does a scenario need" checklist, drawn from the standard
Arkham LCG scenario anatomy (and validated against real SCED campaigns).

## Two tiers

- **Campaign pools** — things shared across scenarios (the investigator decks,
  the reusable encounter *sets*, campaign-wide clocks, the knowledge/log track).
  Authored once, referenced by many scenarios.
- **Scenarios** — each scenario references pools and adds its own locations,
  objectives, and setup. A "scenario" is any self-contained play unit; in a
  loop or open-map campaign a *district/node* is a scenario.

## Campaign pool block

```jsonc
{
  "campaign": {
    "id": "still_hour",
    "name": "The Still Hour",
    "investigators": ["sthr-elias", ...],          // player-side, already built
    "encounter_sets": {                             // reusable card bundles
      "set_id": {
        "name": "Static",
        "cards": [ {"id": "...", "type": "Treachery", "qty": 2}, ... ]
      }
    },
    "clocks": [                                     // agenda/act-style shared decks
      {"id": "occultation", "kind": "agenda-like",
       "stages": [{"name": "Hour I", "threshold": null, "text": "..."}]}
    ],
    "knowledge_track": [ {"fact": "...", "source": "...", "effect": "..."} ],
    "resolutions": [ {"id": "R1", "condition": "...", "log": "..."} ]
  }
}
```

## Scenario block — the required stacks

Each scenario lists the stacks it needs. A stack the editor renders as a
flip-through, add/subtract deck. `fill` = where the cards come from
(a pool ref, an explicit list, or `campaign_guide` to auto-select).

```jsonc
{
  "id": "district_lighthouse",
  "name": "The Lighthouse",
  "order": 2,
  "reference": {                                    // the scenario reference card
    "art": null, "setup": "...", "xp": null
  },
  "stacks": {
    "locations": {                                  // REQUIRED per scenario
      "template": "Location",
      "cards": [
        {"name": "The Lantern Room", "shroud": 3, "clues": 2,
         "connections": ["The Winding Stair"], "victory": null,
         "unrevealed_text": "...", "revealed_text": "...", "art": null}
      ]
    },
    "act_deck": {                                   // objectives (clue thresholds)
      "template": "Act",
      "cards": [{"name": "the ninth death", "clue_threshold": 2, "text": "..."}]
    },
    "agenda_deck": {                                // doom/clock — may ref a pool
      "template": "Agenda", "ref": "occultation"
    },
    "encounter": {                                  // what shuffles into the deck
      "fill": "sets",
      "sets": ["spine", "node_lighthouse"],         // pool refs + this node's set
      "aside": ["appointed"]                        // set-aside, not shuffled
    },
    "enemies_named": {                              // optional victory elites
      "template": "Enemy", "cards": []
    }
  },
  "setup": {
    "starting_location": "The Square",
    "chaos_bag": "Calm band",
    "notes": "..."
  },
  "grants": ["Knowledge: The Ninth Death"]          // log entries earned here
}
```

## Required-stack checklist (every scenario is measured against this)

| Stack | Template | Required? | Fields the builder must expose |
|---|---|---|---|
| Scenario reference | `Scenario` | 1 per scenario | name, setup text, XP, art |
| Locations | `Location` | ≥1 | name, shroud, clues (fixed/per-inv), connections, unrevealed + revealed text, victory, both-side art |
| Act deck | `Act` | if the scenario has objectives | stage name, clue threshold, text, art |
| Agenda deck | `Agenda` | if the scenario has a doom clock | stage name, doom threshold, text, art (or ref a shared clock) |
| Encounter | (sets) | ≥1 set | which encounter *sets* shuffle in, which are set aside, per-set quantities |
| Named enemies | `Enemy` | optional | standard enemy fields + `Named`/`Victory` |
| Setup | — | 1 | starting location(s), chaos-bag band, set-aside, out-of-play |
| Resolutions | — | ≥1 (campaign-level ok) | condition → campaign-log entry |

Anything the campaign guide specifies but a scenario leaves blank is what the
editor flags as "needs filling." Anything already built (player cards,
reusable sets) is pre-linked so you're never re-entering it.

## How "feed the campaign in" works

1. **Ingest** — point the editor at the campaign guide + card docs. It parses
   the scenario/district headers, location tables (shroud/clues), encounter-set
   lists, objectives, and resolutions into a `scenario_manifest.json`.
2. **Fill** — for each scenario the editor shows its required stacks as
   deck-builder decks. Pool cards arrive pre-linked; blanks are flagged. You
   flip through, set art + text + type, and add/subtract freely (or hit
   "select what the guide needs" to auto-populate).
3. **Finalize** — the completed manifest is assembled into SCED objects
   (scenario bags, encounter/act/agenda decks, location sets, campaign box,
   log/guide) and scripted to self-place in TTS, ready to play.

## Field-vs-print vs GMNotes (validated against a real SCED campaign)

Not every field the builder shows is exported the same way. From The Drowned
City (a real FFG SCED save):

- **Mechanics live in `GMNotes`** — a JSON string on each card, keyed by
  `type` (`Location`/`Agenda`/`Act`/`Enemy`/`Treachery`/`Asset`/`Story`/
  `ScenarioReference`). `type` + `Tags` are how TTS/SCED classify a card.
- **`shroud` is print-only** — it is *not* stored in GMNotes; it is baked into
  the location art. The builder still needs it as a value (to print on the
  card face), but it is not exported to GMNotes.
- **Clues** are stored as `locationFront/Back.uses[{countPerInvestigator, type:
  "Clue", token:"clue"}]` (or `clueThresholdPerInvestigator`).
- **Locations carry front (unrevealed) + back (revealed) separately**, each with
  its own `icons` (this card's connector symbol) and `connections` (pipe-
  delimited symbols it links to, e.g. `"Circle|Square|Diamond"`).
- **Agenda** stores `doomThreshold`; **Act** is minimal (thresholds are on the
  act text); **Enemy** stores `victory`; **Treachery** stores `weakness`.
- **Scenario reference** carries the **chaos-bag token modifiers** as
  `tokens.front` (easy/standard) and `tokens.back` (hard/expert), each a map of
  `{Skull|Cultist|Tablet|"Elder Thing"|…: {description, modifier}}`.

## Finalize → TTS assembly (the exporter contract)

The real structure the finalize step must emit:

- **Campaign box** = one `Custom_Model_Bag`, `Tags:["CampaignBox","Reloadable"]`,
  `GMNotes:{id,type:"CampaignBox"}`. (We already build this as `CB-STHR`.)
- **Each scenario** = its own nested `Custom_Model_Bag`, `GMNotes:{id:"SB…",
  type:"ScenarioBox"}`, containing its reference card, `Deck "Agenda Deck"`,
  `Bag "Act Decks"` (a bag so acts can **branch**), `Deck "Encounter Deck"`,
  location cards / location-set `Deck`s, a `Custom_Model_Bag "Set-aside"`, a
  difficulty `Custom_Tile`, and a `Notecard "Setup Notes"`.
- **Decks** carry `DeckIDs` (one int per card incl. duplicates) + a `CustomDeck`
  sprite-sheet map (`FaceURL/BackURL/NumWidth/NumHeight`). Reusable encounter
  sets can be `Custom_Model_Infinite_Bag`s.
- **Auto-placement is the SCED MemoryBag module.** Every bag runs a bundled
  `MemoryBag` `LuaScript`; its `LuaScriptState` is `{"ml": {GUID: {pos,rot,
  lock}}}` — one entry per contained object. A **Place** button moves each child
  to its recorded position (the scenario "sets itself up"); **Recall** pulls
  them back. So finalize = assign GUIDs, nest objects, author each bag's `ml`
  layout, attach the MemoryBag bundle.
- **Campaign log** = `Custom_Token`, `Tags:["CampaignLog"]`; **campaign guide**
  = `Custom_PDF`, `Tags:["CampaignGuide"]` — both at campaign level.

This is why the finalize step is "just" a compiler: the manifest already holds
every card's fields; the exporter maps type→template art, packs decks, and
writes the memory-bag layout so the scenario places itself on the table.
