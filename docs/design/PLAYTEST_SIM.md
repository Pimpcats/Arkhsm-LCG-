# The Still Hour — play engine (simulated playtests)

Designer-facing; spoilers throughout. This is simulation on an emulated table,
not a playtest: it measures what the cards and rules do when a competent AI
party plays them, and says nothing about fun, clarity or pacing at a real
table.

## What it is

`tools/play_engine` plays every scenario of the campaign many times on the
same emulated table the harness uses (`tests/sced_real`): the owner's SCED
4.8.0 save booted in the TTS emulator with SCED's real scripts, and the
campaign's Saved Object (`dist/saved_object_the_still_hour.json`) loaded and
Placed the way the owner does it. It is the successor of the abstract models
`pipeline/simulate.py` and `pipeline/simulate_tempo.py`.

- **The table holds the game.** Boxes are Placed with their own buttons;
  locations, encounter decks, the Hours, act decks and set-aside cards are the
  real objects they lay out. SCED spawns clues when a location is revealed
  (the engine flips the card, as a player does) and the engine moves those
  clue tokens to the playmats. Encounter cards are drawn with the playmat's
  own *Draw encounter card* button (SCED reshuffles the discard pile itself);
  enemies are moved to their location or to the engaged investigator's threat
  area; treacheries go to SCED's encounter discard spot. Chaos tokens are
  drawn from SCED's real bag (Standard, filled by the Control token's
  difficulty button) through SCED's own draw; revealed [static] tokens raise
  Dissonance through the Control token as at the table. The Control token
  keeps the Hour, Dissonance, the band's [static] tokens, the Appointed's
  stage and position (its Hunt and Hold Back buttons move and push it back),
  Memory, Years and aging; Knowledge and Victory are ticked on the campaign
  log. The Hours deck on the table is turned and set aside to follow the
  Hour, and rewinds put the cards back.
- **The rules layer** (`lua/rules.lua`, `lua/flow.lua`) runs the Rules
  Reference round (mythos, investigation, enemy, upkeep; the mythos phase is
  skipped in round 1), skill tests, the player actions, attacks of
  opportunity, engagement, hunters, damage and horror with soak, defeat, and
  the campaign rules: district crossings costing Hours (first move per round
  along a district connection, free for the rest of that round), Hour
  "When reached" effects (the Control's share applied by the Control, the
  rest by the engine), Dissonance bands, Sleepwalking Echoes, the Appointed's
  Approach, Knowledge, Victory, Years and the finale's contest.
- **The effects table** (`lua/effects.lua`) encodes all 97 scenario cards the
  boxes lay out (Hours, acts, locations, encounter cards, Named enemies,
  story cards, the scenario reference card), read from the effective card
  text (`tools/play_engine/cards.py`: the owner's overrides over the print
  layer). Numbers (shroud, fight, health, clue thresholds, token modifiers)
  are read from that data, never copied into the engine. `tests/test_play_engine.py`
  fails if a scenario card has no entry.
- **The party** (`lua/players.lua`, `lua/ai.lua`): the five investigators
  with their abilities, elder signs, signature cards and weaknesses, and
  30-card level-0 decks built from SCED's own *All Player Cards* bag in the
  save under each investigator's printed deckbuilding options
  (`tools/play_engine/decks.py`), plus one random basic weakness per game.
  The AI scores every legal action (objective progress, clue efficiency,
  threats and attacks of opportunity, Hold Back, the Hour cost of crossings,
  Dissonance, danger at a location) and takes the best. It counts the chaos
  bag like a careful player, commits cards and resources up to target odds,
  gathers clues where they are cheapest (clues are portable), crosses a
  district connection together when one crossing has been paid, never makes
  a crossing that would reach Hour IX, and avoids paying Dissonance as a cost
  more than twice a loop (leaning on the loop costs a Year).

## Running it

    python3 tools/play_engine/run.py --scenario district_church --runs 30 --players 3
    python3 tools/play_engine/run.py --scenario all --runs 30 --players 3 --jobs 4
    python3 tools/play_engine/run.py --suite --jobs 3        # the full balance suite (about 45 minutes; --runs-other 15)
    python3 tools/play_engine/run.py --scenario prologue --trace   # one game, play by play
    python3 tools/play_engine/run.py --scenario loop_multi --render .cache/play_engine/render/multi
    python3 tools/play_engine/run.py --report                # rebuild report.md / metrics.json

Scenarios: `prologue`; `district_<square|church|road|lighthouse|fairground|almanac>`
(Part I, the Square plus that district; the Lighthouse also places the Sunken
Road); the same with `_p2` (Part II, the deep act); `loop_multi` (the Square,
the Drowned Church and the Almanac House); `finale` (declared at the Sealed
Study; the suite plays it at 1-4 investigators) and `finale_h9` (the same state, begun when Hour IX is reached). Parties: solo Cass;
Elias and Ayako; Elias, Ayako and Cass; the four with Seraphine. Outputs stay
in `.cache/play_engine/` (gitignored); the engine plays dist/'s Saved Object with the Control's and
the log's scripts rebuilt from `src/` (`.cache/play_engine/payload/`), so rules code changes need no publish.
Outputs: `games/*.jsonl` (one JSON per game with
every metric), `report.md`, `metrics.json`, `coverage.json`. Needs `lua5.2` and
the save at `/home/user/sce480/Arkham SCE 4.8.0.json` (or `--save` /
`$SCED_SAVE`).

## Representative campaign states

| scenario | loop / scar | Part | Knowledge recorded | banked Memory | Years |
|---|---|---|---|---|---|
| prologue | Prologue, Dissonance 0 | – | – | 0 | 0 |
| district_* | loop 1, scar 0 | I | You Are Unstuck | 2 (after interlude spending) | 0 |
| district_*_p2 | loop 4, scar 3 | II | the district's surface entry and two others (the Almanac House also The Vote That Never Ends) | 5 | 6 (Weathered) |
| loop_multi | loop 2, scar 1 | I | You Are Unstuck | 3 | 1 |
| finale | loop 7, scar 6 | II | all six surface entries; deep: the Vote, the Name, the Hour Was Wrong, the Ninth Death; The Way the Night Breaks | 14 | 11 (Elder) |

The finale is declared at the Sealed Study as soon as the whole party stands
there (Square and Almanac House placed); the log records *the name is kept
unspoken*, *the drowned heard the true hour*, *the vote still stands*, *the
ninth line was left blank* and *the town was warned*.

## Tuning round (2026-09-30)

The first suite (2026-09-29) found a Prologue that ended in round 1, an
unreachable finale, a slow Lighthouse, a lethal Wheel, Hour IV closing the
hub and a deadly solo game. The tuning round changed these cards and rules
(card ids for re-rendering: `sthr-act-firsthour`, `sthr-act-walkbackward`,
`sthr-loc-wheel`, `sthr-hour-4`, `sthr-act-lasthour`, `sthr-act-almanachid`,
`sthr-act-hourwaswrong`, `sthr-act-appointedname`, `sthr-bellringer`):

| lever | before | after |
|---|---|---|
| The First Hour (Prologue act) | an investigator at the Almanac Steps; the group spends 2 [perinv] | investigators **at the Almanac Steps** spend **3 [perinv]** |
| The Turning–The Winding Stair | a district connection (1 Hour) | not a district connection: never costs an Hour (guide: Districts and travel, map, Lighthouse box) |
| The Road Remembers (Walk It Backward back) | once per loop, the Turning–the Winding Stair costs no Hour | once per loop, **the Square–the Milestones** costs no Hour (log token text too) |
| The Wheel | 1 horror per Hour advanced | **Forced – At the end of the round:** 1 horror |
| Hour IV | fewest-clue revealed location | fewest-clue revealed location **other than the Square** |
| Contest the Crossing | 4 [perinv] (12 at 3p); +1 per Hold Back, deep entry, Uninvited, and each investigator's first Study visit | **5 (6 with four investigators)**; Study visits no longer count; the spoken name gives 1 (was 2) |
| The Bell-Ringer Beneath's Hour III attack | the nearest investigator, even at another location | the nearest investigator **at its location or a connecting location** (Victory 2 kept) |
| What the Almanac Hid | 2 [perinv] | **3 [perinv]** |
| The Hour Was Wrong / The Appointed's Name | 1 [perinv] | **2 [perinv]** |
| Solo (Difficulty and Player Count) | reset 9, Noticed 6, Glitch 3, scar cap 3 | the two-investigator bands (reset 12, Noticed 8, Glitch 4, scar cap 4) and **+3 maximum health and sanity** (the Control token applies both) |

The Control token applies the new contest target (`Constants.contestTarget
= 5`, 6 at four investigators), the solo bands and the solo maxima (shown on the investigator card
and read by `shApiInvestigators`); its Hour IV reminder names the Square.
The engine was also improved (these lift or lower rates without any card
change): clues for a contributed objective count only when their carrier
will be there; a secondary objective is paid for only when the current one
stays covered; crossings for the current objective are taken early and
together; the lead's Hour IV choice spares the party's routes and objective
locations; investigators Hold Back when the Arrived Appointed engages them
and end their turn instead of taking a lethal attack of opportunity; in the
finale they Hold Back at long odds once the deep entries are spent and do
not investigate. The Part II and finale states now raise Cass's willpower
at Weathered (with intellect she could not Hold Back at all).

## Results after tuning (final suite, Standard; 30 runs at 3p, 15 at 1p/4p)

| scenario (3p) | objective before → after | Hours to spare | defeat games | party wiped |
|---|---|---|---|---|
| Prologue | 100% (round 1.1) → **100%**, round 2.9 (93% in a second run) | 7.7 → 4.5 | 0% → 0% | 0% |
| Square I / II | 100 / 100% → 100 / 97% | 5.7 / 5.7 → 5.5 / 5.3 | 30 / 43% → 33 / 47% | 0 / 3% |
| Drowned Church I / II | 90 / 100% → 100 / 100% | 4.9 / 5.3 → 5.0 / 4.6 | 17 / 37% → 13 / 40% | 0 / 3% |
| Sunken Road I / II | 87 / 97% → 90 / 100% | 2.7 / 5.2 → 3.5 / 5.3 | 27 / 47% → 37 / 30% | 0 / 0% |
| Lighthouse I / II | 37 / 57% → **70 / 63%** | 1.7 / 2.1 → 2.6 / 2.2 | 0 / 17% → 13 / 47% | 0 / 3% |
| Fairground I / II | 87 / 100% → 97 / 97% | 4.8 / 5.0 → 3.9 / 3.8 | 50 / 47% → 33 / 20% | 0 / 0% |
| Almanac House I / II | 93 / 100% → 97 / 97% | 5.2 / 5.5 → 4.1 / 4.2 | 17 / 23% → 27 / 10% | 0 / 0% |
| Square + Church + Almanac | 2+ objectives 77% → **47%** (0/1/2/3: 0/53/43/3%) | – | 40% → 30% | 0% |
| Finale (declared at the Study) | contest 0% → **53%** (62% over 60 runs) | – | 57% → 33% | 17% → 3% |
| Finale begun at Hour IX | 0% → 43% (33% end by Dissonance reset) | – | 70% → 60% | 27% → 3% |

Finale contest at other counts (30 runs; two seed sets agree within ±10):
1 investigator 60%, 2 investigators 60%, 4 investigators 48% over 60 runs
with the 4p target of 6 (76% with 5; before: out of reach, 16 to find). Sources at 3p per finale: deep entries spent 3.9, Hold Back 0.6, the
Uninvited 0.0; 21 of the 23 failures in 60 runs at 3p end at Hour IX one short (4 of 5).

Solo (Cass, 15 runs a district): party wiped 7–27% in Part I (mean 16%, was
30–70%) and 0–20% in Part II (mean 14%, was 10–80%), Dissonance resets 0%
(22% in Part II with the old bands once solo survived longer). Four
investigators: 53–100% objectives, defeat games 20–53%, no wipes but one.

The Wheel now deals 3.6 horror a game (was 6.6) and defeated 0.03
investigators a game (was 0.37). Hour IV no longer closes the Square; the
hub then stays open to the Appointed too, which the engine offsets by
Holding Back when caught (Appointed attacks a game in the Almanac House
loop: 0.17 before, 0.63 with the Square open under the old policy, 0.23 now).

Targets not met (3p): the Prologue ends mostly in round 3 but succeeds
93–100% (4 [perinv] gave 80%, round 3.4); the Drowned Church and the Almanac
House keep 4–5 Hours to spare (3 [perinv] on Why Thirteen? drops the
three-district loop to 27% two-objective loops, below the 45–60% band, so
only the Almanac House was raised); the Lighthouse is at 70% (Part II 63%);
Part II deep objectives still finish with 4–5 Hours to spare except the
Lighthouse; the finale sits at the top of the band at 3p (53–62%; a contest
of 6 falls to about 20–25% at 3p, so the step is coarse). The Drowned
Church's Part II loop defeated someone in 70% of one seed set and 40% of
another (55% pooled); with the Bell-Ringer's shorter reach it is 40–43%. Memory and Years: Knowledge-driven Memory per loop is unchanged
(Lighthouse 2.5 → 4.6 banked a game); Years per investigator per loop stay
1.1–1.4 (finale 2.3 → 1.5); the tempo model's first-time finale unlock at 3p
moves from loop 6 to loop 7 (5 for a finale-first party).

## Twelve-round loops (2026-09-30)

The owner wants each loop to take about three hours at three investigators,
like an official scenario: about 12 rounds (the Prologue 6-8). The loop was
lengthened and everything that scales with it re-tuned. Changes (card ids to
re-render: `sthr-hour-1` to `sthr-hour-8`, `sthr-loc-hubsquare`,
`sthr-thirteen`, `sthr-bridgeremembers`, `sthr-wheelsturn`,
`sthr-milecounter`, `sthr-losthour`, `sthr-yearinanight`, `sthr-forgotten`,
`sthr-wrongturn`, `sthr-longwayround`, `sthr-scn-stillhour`, `sthr-loc-wheel`,
`sthr-wearssheriff`, `sthr-appointed`, every act but The Ninth Death's and
Who Walks Beside You's text is re-costed; see BALANCE.md):

| lever | before | after |
|---|---|---|
| Hours | doom threshold 1 | Hour I **3**, Hours II–VIII **2** (an Hour every second Mythos phase) |
| District crossings, Thirteen, The Bridge Remembers, The Wheel's Turn, The Mile-Counter, the Elder Thing token | advance the Hourglass by 1 Hour | **place 1 doom on the current Hour** (checked in the Mythos phase) |
| Lost Hour | 1 Hour (2 from Hour VI) | a 1-Hour Skip at any Hour |
| The Hour turns (new rule) | – | each time the Hourglass advances, each investigator heals 1 horror |
| Dissonance | reset 6 × investigators (18), bands 6 / 12 | reset **8 ×** investigators (24), bands 8 / 16; scar cap 2 × investigators (6 at 3p); solo 16 / 10 / 5 |
| Tokens (Standard side) | Tablet from Sensed; Cultist on any fail | Tablet horror from **Emerging**; Cultist raises Dissonance on a fail **by 2 or more** |
| A Year in a Night / What You've Forgotten | horror per point failed, Year on any fail / remove 2 Memory | 1 horror, a Year only on a fail by 2+ / remove 1 Memory |
| The Wheel | 1 horror at the end of the round | 1 horror after the Hourglass advances |
| What Wears the Sheriff | Hunter | keeps the Records Office |
| The First Hour | 3 [perinv] at the Steps | **Hour V or later**, 4 [perinv] |
| Surface acts | 5 / 2 / 3 / 1 / 1 [perinv] (Square / Church / Almanac / Wheel / Lamp) | 5 / 5 / 5 / 3 / 3; Walk It Backward 2 clues at each step |
| Deep acts | 2 [perinv] (Vote, Crypt, Name, Bargain), 1 (Ninth Death) | 5 [perinv]; Ninth Death 3 (the district's clues pay; manifest updated) |
| Finale | contest 5 (6 at four), Hold Back rewinds | contest **7 (6 solo)**; a finale begun before Hour V skips to Hour V; Hold Back does not rewind during the finale |
| Knowledge pays Memory | surface 1, deep 3 per investigator | surface 0, deep **2** |

The Control token applies the bands, the contest target, the finale's Hold
Back and the solo maxima, and reminds the table when the Hour turns; doom on
the Hours is on the table (the engine tracks it). `simulate.py` and
`simulate_tempo.py` model the new clock (half an Hour a round, crossings and
small costs as doom).

### Results (final suite, Standard; 30 runs at 3p, 15 at 1p/4p)

Minutes use 14 a round at 3p (first-time group), 10 solo, 17 at four.

| 3 investigators | rounds (min) | objective, spare Hours/rounds | any defeat | wiped | Dissonance max / resets |
|---|---|---|---|---|---|
| Prologue | 5.9 (83) | 97% | 0% | 0% | 7.8 / 0% |
| Square I / II | 16.1 / 11.7 (226 / 163) | 100 / 93%, 6.3H/12.5R / 4.9H/6.3R | 53 / 50% | 17 / 0% | 13.6 / 13%; 13.8 / 10% |
| Church I / II | 11.5 / 10.7 | 100 / 93%, 4.7/6.7 · 4.1/5.2 | 33 / 30% | 0 / 0% | 10.6 / 3%; 12.0 / 3% |
| Road I / II | 11.5 / 10.9 | 97 / 100%, 4.8/6.8 · 7.1/8.6 | 43 / 37% | 3 / 0% | 8.6 / 0%; 11.0 / 0% |
| Lighthouse I / II | 10.7 / 11.2 | 87 / 100%, 4.5/5.5 · 4.3/5.9 | 43 / 50% | 3 / 7% | 10.2 / 0%; 11.8 / 3% |
| Fairground I / II | 10.5 / 11.0 | 87 / 97%, 4.9/6.6 · 4.3/5.4 | 23 / 40% | 0 / 7% | 9.3 / 0%; 11.3 / 0% |
| Almanac I / II | 11.2 / 11.0 | 100 / 100%, 4.9/6.3 · 4.3/5.5 | 30 / 27% | 0 / 3% | 11.8 / 3%; 9.2 / 0% |
| Square + Church + Almanac | 11.9 (167) | 2+ objectives 73% (62% over three suites) | 53% | 3% | 14.2 / 3% |
| Finale (declared at the Study) | 7.7 (108) | contest 63% | 67% | 7% | 11.3 / 0% |
| Finale begun at Hour IX | 13.1 (184) | contest 73% | 70% | 23% | 16.7 / 3% |

Finale contest by count: 1 investigator 67%, 2 53%, 3 63%, 4 67%; per 3p
finale: deep entries 4.0, Hold Back ~2.7. Deck reshuffles 0.4-1.0 a loop
(2.0 when the Square is played alone). Solo loops run 11-15 rounds (about
two hours); four investigators 9-13 (2.5-3.5 hours). Memory: `simulate_tempo.py
--memory` puts the campaign total per investigator before the finale loop at
34-45 at three investigators (was 44-56 with the old Knowledge payments);
first-time finale unlock at 3p loop 5-6 (4-8). Years per investigator per loop
1.3-1.9 (1.1-1.4 before): more encounter draws and defeats in longer loops.

Missed or loose: districts stay a little generous (87-100%, 4-5 Hours to
spare where 2-4 was asked; raising more acts drops the three-district loop
below 45%); the three-district loop gives two objectives in 50-73% (three
suites); the Square alone runs 15-16 rounds with 13% resets and 17% wipes;
solo wipes average about 30% in Part I (Fairground 53%, Road 47%) and 12% in
Part II; the two-investigator finale wipes 40%; the finale begun at Hour IX
wipes 23%; Years per loop rose.

## Assumptions and limits

- One AI party, greedy but competent; real players differ (they talk and plan
  across rounds). Treat differences between
  scenarios as signal, absolute rates as rough.
- Campaign states are representative, not played through: each scenario
  restores a fixed Control blob and log (table above).
- Player cards are engine data, not physical cards; damage, horror and
  resources are tracked by the engine. Level-0 decks only; no Recollections
  beyond Foreknowledge, Muscle Memory and I've Done This Before.
- Standard difficulty only. Doom on the Hours is tracked by the engine (the table's tokens are not moved).
- Approximated: choices on Hour IV, Wrong Turn and Town Hall (AI picks);
  the Appointed's engagement (Control position plus engine engagement); the
  order of "last Hour" act effects; Lucky Compass and Nobody Believes Her
  partially; the walker's ring choices. Not encoded (not in the decks or
  rarely drawn): Old Book of Lore, Stubborn Detective, Silver Twilight
  Acolyte, Leo De Luca, Opportunist, Medical Texts, Marked Deck, the
  Ambergrove Lamp action.
- What-if runs (`--what-if file.json`: card/act overrides, scenario patches,
  contest target, finale spawn locations, a two-action deep entry, the old
  Lighthouse crossing) change the engine's reading only; results land in
  `.cache/play_engine/whatif/<tag>/`.
- The finale is sensitive to the party: an investigator who cannot Hold Back
  (willpower and combat 2) cannot reach it alone; the four-investigator
  party with Seraphine reaches it most.
