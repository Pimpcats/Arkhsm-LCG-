# Real SCED objects (vendored examples)

Objects exported straight from the official Arkham SCE mod by the owner
(right-click → Save Object). They are the ground truth our generated objects
are aligned against — `pipeline/build_cards.py` cites them. Never edit; they
carry FFG content and stay in-repo only as schema reference for this free
fan project.

| File | What it establishes |
|---|---|
| `asset_ally_andy_van_nortwick.json` | Story-asset pattern: player-type card living outside deckbuilding. Tags `[Asset, PlayerCard]`, camelCase `*Icons`, `cycle` in GMNotes. |
| `asset_weapon_uses.json` (Becky) | `uses: [{count, type, token}]`, `slot: "Hand x2"`, signature = class Neutral. |
| `asset_signature_ally.json` (Randall Cho) | Class-carded signature asset (Guardian); multi-icon rows. |
| `skill_signature.json` (The Home Front) | Skills carry Tags `[PlayerCard]` only — no type tag. |
| `treachery_weakness.json` (In Harm's Way) | `weakness: true`; player-deck treachery; `uses` with count 0. |
| `enemy_signature_weakness.json` (Tommy Malloy) | Enemy-TYPE weakness in a player deck: Tags stay `[PlayerCard]`; no combat stats in GMNotes (they live on the art). |
| `investigator_front.json` (Tommy Muldoon) | Statline as `*Icons`, `elderSignEffect {description, modifier}`, `signatures [{id: count}]`, Tags `[Investigator, PlayerCard]`, SidewaysCard, unique back, `HideWhenFaceDown: false`. |
| `investigator_with_helper.json` (Nathaniel Cho) | Same + the CardWithHelper/side-button Lua pattern and `font_arkhamicons` CustomUIAsset. |
| `minicard.json` (Wilson Richards) | Minicards: Name `CardCustom`, Tags `[Minicard]`, id suffix `-m`, scale 0.6, unique artless back. |
| `enemy_regular_encounter.json` (Swarm of Rats) | Encounter deck cards: Tags `[ScenarioCard]`, class `Mythos`. |
| `enemy_elite_encounter.json` (Naomi O'Bannion) | Elite = a TRAIT ("… Elite."), `victory: 1` in GMNotes; still just `[ScenarioCard]`. |
| `treachery_encounter.json` (End of Negotiations) | Encounter treachery; subtypes (Blunder/Curse/Omen…) are traits, not schema. |
| `agenda_front.json` / `agenda_back.json` | Agendas: `doomThreshold`, class `Mythos`, Tags `[ScenarioCard]`, SidewaysCard true, UniqueBack true, `HideWhenFaceDown: false`. |
| `location_revealed.json` / `location_unrevealed.json` | `locationFront`/`locationBack` split: `icons`, pipe-separated `connections`, `uses [{countPerInvestigator, type: Clue}]`, per-side `victory`. Tags `[Location, ScenarioCard]`. |
| `act_location_double.json` | Double-sided act/location card from a scenario sheet deck (UniqueBack true). |
| `campaign_guide_pdf.json` | Campaign guide = `Custom_PDF` object (`PDFUrl`), Tags `[CampaignGuide]`. |
| `campaign_log_token.json` | Interactive campaign log = `Custom_Token` + CampaignLogLibrary Lua: checkbox/counter/textbox coords over the log image, 2-page `States`, auto-fill from playermats. |
| `scenario_box_memory_bag.json` (One Last Job) | Scenario box = `Custom_Model_Bag` book, GMNotes `{type: ScenarioBox}`; memory-bag Lua (`LuaScriptState.ml`: GUID → pos/rot) with Place/Recall. |

Also universal across every card: `ColorDiffuse` 0.7132…, `Hands: true`,
`HideWhenFaceDown: true` except investigators/agendas/acts, shared player back
URL, `BackIsHidden: true`.

`act_back.json` — a pure Act card: GMNotes `{id, cycle, type: Act, class:
Mythos}`, Tags `[ScenarioCard]`, sideways. `act_back_becomes_location.json` —
an act whose other side is a Location put into play (GMNotes switches to the
location shape).

## Still wanted (schema gaps)
- An act WITH a clue threshold in its GMNotes (the examples here have none) —
  to confirm the key name before the Hour/act content pass.
- A scenario reference card (chaos-token effects) — schema + frame.

`campaign_box_memory_bag.json` (The Drowned City) — the top of the hierarchy:
`Custom_Model_Bag`, GMNotes `{filename, id, type: CampaignBox}` (the
`filename` is the placeholder-download key — confirms our P8 box), Tags
`[CampaignBox, Reloadable]`. Contains: all ScenarioBoxes (each a memory bag
with Place/Recall that lays the scenario out), the CampaignLog token, the
CampaignGuide PDF, and campaign-level story decks (Tasks/Artifacts/Expedition
— the home of story assets like Andy Van Nortwick). Its own Place lays the
scenario books out in a row.
