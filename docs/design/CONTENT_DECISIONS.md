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

**D8 — Clue values are per investigator; thresholds are fixed unless that
fails a table size.** The location data (already per investigator) is kept and
the guide's objective counts are printed as fixed totals, except where a fixed
total cannot be met: the Almanac House surface objective needed 6 clues from the
Reading Room and Press (the Study is sealed) — only 5 exist at one investigator.
It is now **2 per investigator** (exactly the guide's 6 at three players), on the
act and on the Press. Every objective was checked at 1, 2, 3 and 4 investigators
(each act's clue sources are named in the manifest's `needs`;
`objective_feasibility` in pipeline/scenario_content.py; a test runs every table
size). All the others hold with the guide's numbers: Prologue 5 of 7 per
investigator, Lighthouse 4 of 5, Church 6 of 7 (crypt sealed), Square 5 of 7,
Fairground 2 of 7, Road 1 at each of three; deep objectives take the objective
location's own clues; the finale contest has a repeatable source (Hold Back).

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
- New cards take explicit deck ids 95100–95123.

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
because each connection well is drawn in the target's colour.

**D13 — Every loop location has a unique SCED connection key.** SCED's own
matcher (argonui/SCED `src/playarea/PlayArea.ttslua`, `buildLocListByIcon` /
`buildConnection`) splits `icons` and `connections` on non-letters
(`gmatch("%a+")`) and links every card carrying a matching token — any
letters-only string works, as official cards' `FromDowntown` shows. So the
GMNotes key is the symbol plus its colour spelled in letters
(`build_cards.location_key`, e.g. Star + #1a605e → `StarBkgagpo`; hex digits
0–f → a–p), which is unique per printed symbol+colour. All 20 loop locations
can be on the table at once and SCED draws exactly the printed lines: the audit
fails on any shared key or unmatched/one-way line, and a test replays SCED's
matcher over the whole loop map and compares it with the printed connections.
The printed repeats above therefore never produce a wrong line.

The Lighthouse's entrance is the Winding Stair, joined to the Turning (the far
end of the Sunken Road; the Milestones end touches the Square).

## Accepted inherited content (A1–A4)

These are existing edits and data, accepted as part of the campaign. The
manifest records the Lantern Room's value as `accepted`, so the audit raises no
note for it; the others are not measured against a guide value.

- **A1 — Lantern Room shroud 4** (the guide says 3): the owner's own editor edit.
  Its calm side (D14) prints the guide's 3.
- **A2 — Victory 1 on five locations** (Keeper's Quarters, Flooded Crypt, Records
  Office, Ticket Booth, Sealed Study): kept. Read with the campaign's Victory rule
  (encounter §5b): the location goes to the victory display when its clues are
  gone, and the first time each name is claimed it banks its Victory as Memory,
  once per campaign, gated by the log's Victory list exactly like the Named.
- **A3 — Winding Stair climb test** ("[action] Test [agi] (2) to climb. If you
  fail, take 1 damage."): kept (markup fixed to [agi]).
- **A4 — Chaos-token effects** on "The Still Hour" reference card: kept as
  authored; the same card is placed in every box (the bag's contents are driven
  by the Dissonance bands, its symbol effects by this card).

## Resolved gaps

**D14 — The Lantern Room's calm side** (guide §6.1 "flips to its calmer back";
`Locations.ttslua` `flipFact = "the-lamp-was-never-lit"`, the only fact-flip
with a physical side — the Town Hall Steps' flip is printed on its front). The
card now has a real second face, rendered as its back: shroud 3 (the guide's
value, calmer than the front's 4), same clues and connections, and "[action]
Light the lamp (no test)" with the lit-lamp edit from §6.1, plus The Dark That
Waits treating investigators there as not at the Lantern Room (its node
treachery's harsher branch). Calmer = the lesson is kept: you know how to light
it, and the dark there no longer bites harder. The act tells players to place it
calm side up in every later loop.

**D15 — "Hold" an Echo.** Defined on the act as a Hold Back analogue: "[action]
Hold: test [wil] or [com] (X), where X is its fight; if you succeed, exhaust it".
Same skills as Hold Back (CO-002); an Echo has no Approach stage to push, so the
push-back is exhausting it, and the difficulty uses its printed fight as evade
uses its printed evade.

**D16 — R1 softened.** If "Who Walks Beside You" is known, the ones who walk the
Sunken Road (the earlier loopers, guide §6.3) share the anchor's weight: the
Ancient walks out at dawn, +3 Years, free and not kept. The cost stays age (the
§9 design note: every win costs age or someone kept behind).

**D17 — "Let It In, On Your Terms" is R1b.** The Bargain fact unlocks it (§6.5)
and design v0.1 §2 describes it as "a Faustian resolution unlocked only by high
Memory + specific facts". Condition: contest reached, the Bargain known, banked
Memory 12 or more (the same bar R5 uses for "remembering enough"). It is checked
after R1 and before R2 and may be declined (a bargain is offered, not forced).
Cost: banked Memory drops to 0 and each investigator present ages +2 Years; the
epilogue tone follows the "bargain heard" log flag. The finale act lists the
order R1, R1b, R2–R6; the manifest's `resolutions` carry it; the log sheet's
finale record gains the box.

**D18 — Finale contest.** "Reaching the Study" is worth 1 contest progress the
first time each investigator is at the Sealed Study during the finale (the
declaring investigator counts at once), so it contributes at most n of the 4n
target; Hold Back and spent deep facts are 1 each as the guide states.
**Hour IX edge case:** if the finale opens because the Hourglass reached Hour IX,
set the Hourglass back to Hour V instead of resetting (no Hour resolves) — the
finale is otherwise unwinnable by definition, and Hour V is the finale start the
balance simulation models (`simulate.py` `simulate_finale_staged`, start_hour 5).

**D19 — Unused scaffold cards removed.** `sthr-scenario-lighthouse` (an early
reference card with different token text) and `sthr-agenda-hour1` (superseded by
`sthr-hour-1`) were in no scenario box or bag and referenced only by the Studio
selftest's frame/aspect checks, which now use live cards. `sthr-campaign-log` is
kept: the compiler builds the Campaign Log token from it. A test fails on any
Still Hour card that is in no box, no bag and is not the log.

**D20 — Illustration briefs for every card.** `pipeline/build_art_manifest.py`
now derives the job list from all four Still Hour specs and writes both
`pipeline/art_manifest.json` and `campaigns/still_hour/manifest.json`: 126 faces,
119 illustrated, 7 text-only (5 investigator backs, the chaos-token reference
card — its template has no art window — and the campaign log form). Scenes are
subject-only, 1920s inland town under a starless sky, no named characters on
scenario cards (the location/act/story profiles exclude characters); the calm
Lantern Room side shares its card's illustration. A test fails on any card that
is neither briefed nor explicitly text-only.

## Still outside this pass

- **Setup instructions** for each box live in the campaign guide; the Campaign
  Guide PDF object is being handled with the table objects.
