# THE STILL HOUR — Content decisions (scenario content pass)

*CONTAINS SPOILERS. Assistant/designer reference only — not an owner handout.*

The scenario boxes were completed from the design docs (design v0.1, cards
v0.2, aging v0.3, encounter v0.4, campaign guide v0.5, log sheet, CO-001,
CO-002; change orders override older docs). Where the docs were ambiguous or
contradictory, the reading most consistent with the latest change order was
used and is recorded here. Nothing below adds a mechanic the docs do not
state; items the docs leave undefined are flagged for the owner instead of
being invented.

Content lives in the editor's own data (card overrides, the imported spec and
the scenario board), poured in through the Studio import from
`campaigns/still_hour/scenario_content_feed.json`. Readiness is measured by
`pipeline/scenario_content.py` against `scenario_manifest.json` and enforced by
`tests/test_scenario_content.py`; a scenario is locked only when it reports
zero errors.

## Structure

**D1 — The Square box is the loop hub.** The guide builds one board per loop:
start at The Square, the Occultation in order, the shared spine, the node sets
of the districts you visit, the Appointed set aside (guide §2 setup). The
Lighthouse is only reachable through the Sunken Road (guide §3), so district
boxes cannot each be a self-contained scenario, and eight copies of the clock
and spine on the table would be wrong. The guide calls the Square district "the
hub of the night" and "always the loop's start location" (§6.4), so its box
carries the loop's shared components once: the hub location, Hours I–IX, the
shared spine + The Crossing + the Square node set, the set-aside Appointed set,
the Square's Named enemy and the interlude beats. Every other district box holds
its locations, two objective acts, node set, Named enemy (if any) and the
reference card. The manifest keeps each district's `#spine` / `appointed`
requirement and names the box that supplies it (`shared_from`); the audit checks
it there. Each loop: Place the Square box, then Place each district's box the
first time you enter it that loop and shuffle its node-set cards in.

**D2 — Two Square cards.** The Prologue's map (a row of three) and the
Ambergrove map (a hub with five neighbours: Nave, Milestones, Town Hall Steps,
Ticket Booth, Reading Room) are different maps; one card cannot print seven
connections. `sthr-loc-square` stays the Prologue's Square (unchanged);
`sthr-loc-hubsquare` is the loop's Square with the same stats (shroud 1, 2
clues — the only Square values the guide gives, §5) and flavour. Its text
carries the map rule "travel along a connection costs 1 Hour (a Skip)" (§3),
worded as travel between districts.

**D3 — The finale box is played on the loop board.** Guide §9: the finale is
declared at the Sealed Study (or at Hour IX) during a loop that knows "The Way
the Night Breaks". The box holds the finale act, the six resolution cards, the
"Before the Finale" beat and the reference; the locations, clock, spine and
Appointed are the ones already in play (shared from the hub).

**D4 — The Crossing is shuffled in; the Whispers wait for Act II.** Guide §2
lists the deck as spine + node sets + Whispers (Act II) with the Appointed set
aside, and encounter §7 says the boss set is set aside. But CO-002 (latest)
names The Crossing as one of the cards that advances the Approach, which a
Revelation can only do if it is drawn, and it gates only the Whispers by Act.
So The Crossing is in the loop encounter deck every loop (not the Prologue,
which has no Appointed); the Appointed, its Approach reference card and the two
Whispers are set aside in the hub box.

**D5 — Spine size.** Encounter §7 says the shared spine is "26 cards", but the
per-card quantities it lists (§2 5, §3 6, §4 8, §6 5) total **24**. The explicit
per-card quantities are used; 26 looks like the Whispers counted in by mistake.

**D6 — Node-set Echoes are copies of the §3 cards.** "The Congregation Kneels
(Drowned Choir Echo, from encounter v0.4 §3)" and "Those Who Walk (Waiting
Congregation Echo)" name existing cards, so the Church and Road node sets add
one more copy of The Drowned Choir / The Waiting Congregation rather than new
cards. They had been placed in the Named stack; they are ordinary node-set
enemies and moved to the encounter deck. The Church's Named slot now holds The
Bell-Ringer Beneath (encounter §5b); the Road fields no Named enemy.

**D7 — The Hours are agendas with doom 1.** The Hourglass advances about one
Hour a round on its own (guide §2, encounter §8), so Hours I–VIII carry a doom
threshold of 1 (SCED `doomThreshold`); Skips advance it further. Hour IX ends
the loop and has no threshold.

## Objectives (acts)

Each district has two acts: the surface objective (1a) and the deep objective
(2a, "Act II only, once the log shows <surface fact>"), with wording taken from
guide §6 and the effect summary from §7. The prologue has one act carrying the
guide §5 objective, and the scripted ending is the story card "The First Reset".

**D8 — Clue values are per investigator; objective thresholds are fixed.** The
location data (already per investigator) is kept. The guide's objective counts
("discover 6 clues") are printed as fixed totals: with fixed location clues the
Almanac House surface objective would be impossible (Reading Room 2 + Press 3 = 5
with the Study sealed). *Flag:* at one investigator it still is (5 clues for a
threshold of 6); the guide tunes for three.

**D9 — Deep-objective clue counts** are the objective location's own clue value
where the guide gives none (Records Office 3, Sealed Study 3), matching the text
already printed on those locations.

**D10 — The First Reset bonus.** "A small bonus Memory if you finished the
objective: +1" is read as +1 banked Memory to the shared pool.

**D11 — The Sheriff fact.** "Draw the top Occultation card once per loop (the
records let you read the night ahead)" is kept as the existing wording "look at
the top card" — drawing an Hour would advance the clock, which the parenthesis
rules out.

**D12 — The Way the Night Breaks** is recorded on the Almanac deep act as soon
as its three inputs are known (guide §6.6), and the finale act requires it.

## Renames and fixes (CO-002 and markup)

- Hour VII and the Sealed Study still said "The Latecomer's Name"; renamed to
  "The Appointed's Name" (CO-002 rename map), and Hour VII uses the encounter
  §1 wording "it arrives exhausted".
- Hour VI printed the Static token as a skull glyph (`[skull] Static`); the
  Static token is its own token (encounter §0), so the glyph was removed.
- The Winding Stair's inherited print text used `[agility]`, which is not card
  markup and printed literally; now `[agi]` (same text).
- `sthr-appointed-approach` shared deck id 95041 with The Appointed's Whisper,
  so in one deck the two faces would overwrite each other; moved to 95046.
- New cards take explicit deck ids 95100–95122.

## SCED metadata (pipeline/build_cards.py)

Aligned with the vendored ground-truth objects: agendas carry `doomThreshold`;
agendas and acts are `SidewaysCard: true`, `HideWhenFaceDown: false`; the
reference card's GMNotes type is `ScenarioReference` with `tokens.front`
`{Skull|Cultist|Tablet|Elder Thing: {description, modifier}}` (an X value is
-999, as on the real card); agendas, acts, references and stories with no traits
omit the key. Duplicate copies in a deck are repeated card ids on the board, as
real SCED decks repeat CardID/GUID.

## The map

Grid slots (5 × 5 playmat) are unique across the whole loop map so any
combination of boxes can be placed together; the Prologue has its own row.

Symbols: 15 printable symbols, 20 loop locations. The hub and every symbol the
hub or the always-present Square district lists are unique on the whole map.
Changed to achieve that: Lantern Room diamond → quote, Winding Stair circle →
cross, Keeper's Quarters moon → clover, Sealed Study spade → doubleslash (with a
colour of its own). Five symbols are necessarily printed in two districts, each
in a different colour: clover (Keeper's Quarters / Vestry), doubleslash (Low
Bridge / Sealed Study), quote (Lantern Room / Hall of Mirrors), spade (Flooded
Crypt / Wheel), triangle (Belfry / Press). Printed cards stay unambiguous
because each connection well is drawn in the target's colour; SCED's automatic
lines match by symbol only, so if both districts of a pair are on the table in
the same loop it can draw an extra line between them. *Flag:* a future fix is
unique SCED icon keys per location (SCED accepts arbitrary icon strings, e.g.
`FromDowntown`), which needs a key field in the card data.

The Lighthouse's entrance is the Winding Stair, joined to the Turning (the far
end of the Sunken Road; the Milestones end touches the Square).

## Inherited content kept, flagged for the owner

- **Lantern Room shroud 4** — the guide says 3; the override came in with an
  editor stat-click change. Kept as an existing edit; the audit reports it.
- **Victory 1 on five locations** (Keeper's Quarters, Flooded Crypt, Records
  Office, Ticket Booth, Sealed Study) — the design only defines Victory for Named
  enemies (Memory, once per campaign). Kept as existing data; its meaning is
  undefined by the rules.
- **Winding Stair climb test** — "[action] Test [agi] (2) to climb. If you fail,
  take 1 damage." is not in the design; kept (markup fixed).
- **Chaos-token effects** on "The Still Hour" reference card are not in the
  design docs (the bag is driven by Dissonance bands). Kept as authored; the same
  reference card is placed in every box. The older, unassigned scaffolding cards
  `sthr-scenario-lighthouse` and `sthr-agenda-hour1` are left in the pool.

## Undefined in the docs (not invented)

- **The Lantern Room's "calmer back"** (guide §6.1) has no stated effect. The
  act says the location flips; there is no second face to print. The
  Lighthouse is otherwise complete, so it is locked with this flag.
- **"Hold" an Echo** (Sunken Road deep objective) — Hold Back is defined only for
  the Appointed. Printed as written.
- **R1 "Softened if Who Walks Beside You is known"** — no softened text exists.
  Printed as written.
- **"Let It In, On Your Terms"** — the Bargain fact "unlocks" it (§6.5, design
  v0.1), but the §9 resolution table (R1–R6) has no such row. No resolution card
  was invented; the Bargain act records the epilogue flag only.
- **Finale contest "reaching the Study"** has no stated value, and a finale
  triggered at Hour IX has no Hours left "before Hour IX". Printed as written.
- **Setup instructions** for each box live in the campaign guide; the compiled
  Campaign Guide PDF object still has no URL (pre-existing to-do).
