# The Still Hour — play engine (simulated playtests)

> **Historical — superseded by [FINISHING_BALANCE.md](FINISHING_BALANCE.md)** for every
> measured win rate and calibration table below. The description of how the
> play engine works still applies.

> Current source: 2026-10-02 finishing corrections. See
> [correction ledger](FINISHING_CORRECTIONS.md) and
> [current campaign audit](CURRENT_CAMPAIGN_AUDIT.md) and
> [finishing measurements](FINISHING_BALANCE.md).

Everything below the dated update is a historical design or measurement record.
Old clue costs, doom thresholds, economy caps, deck budgets and success rates
are superseded wherever they disagree with effective card overrides, the current
guide and the corrected engine. Do not use an old headline as release approval.


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
| district_*_n3 | loop 3, scar 2 (night 3) | I | You Are Unstuck | 4 | 3 |
| district_*_p2_n5 / _n6 / _n7 | loops 5 / 6 / 7, scar 4 / 5 / 6 (nights 5-7) | II | as district_*_p2 | 7 / 9 / 11 | 7 / 9 / 10 |
| finale | loop 7, scar 6 | II | the Square's, the Church's and the Almanac House's surface entries; deep: the Vote, the Name; The Way the Night Breaks | 12 | 10 (Elder) |

Investigators play level-0 decks on nights 1-2 and upgraded decks after
(`decks.py` `UPGRADES`, bought in order while the night's XP lasts:
night 2 4 XP, 3 8, 4 12, 5 16, 6 20, 7 24, finale 26 per investigator,
about two-thirds of the Memory earned; level 1-5 cards from SCED's own
player cards, legal for each investigator).

The finale is declared at the Sealed Study as soon as the whole party stands
there (Square and Almanac House placed); the log records *the name is kept
unspoken* and *the vote still stands*. Before 2026-10 the finale state held
all six surface and four deep entries (the old unlock rule).

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
`sthr-wearssheriff`, `sthr-appointed`, `sthr-crossing` and every act except Who Walks Beside You;
see BALANCE.md):

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
| The Crossing (`sthr-crossing`) | advance the Approach, raise Dissonance by 1 | advance the Approach, **place 1 doom on the current Hour** |
| Hold Back (`sthr-appointed`) | rewind the Hourglass by 1 Hour (not in the finale) | at most **3 times each loop** (the Control counts; a reset gives them back) |
| Solo | +3 maximum health and sanity | +3 and a **second wind**: once a loop (and once in the finale) a defeat is replaced by removing all damage and horror, for 1 Year |
| Two investigators (new) | – | **+2 maximum health and sanity** each (the Control applies it) |

The Control token applies the bands, the contest target, the finale's Hold
Back, the 3-rewind Hold Back limit and the solo and two-investigator maxima,
and reminds the table when the Hour turns (the solo second wind is a table
rule; the engine applies it); doom on
the Hours is on the table (the engine tracks it). `simulate.py` and
`simulate_tempo.py` model the new clock (half an Hour a round, crossings and
small costs as doom).

### Results (final suite, Standard; 30 runs at 3p, 15 at 1p/4p)

Minutes use 14 a round at 3p (first-time group), 10 solo, 17 at four. The
Square alone and the three-district loop were also played on a second seed
set (seed 5000, 30 games; the Square at 4p on a third, 15): both columns are
given where they were.

| 3 investigators | rounds (min) | objective, spare Hours/rounds | any defeat | wiped | Dissonance max / resets |
|---|---|---|---|---|---|
| Prologue | 5.9 (83) | 97% | 0% | 0% | 7.8 / 0% |
| Square I (two seed sets) | 11.5 / 11.6 (161 / 162) | 97 / 100%, 5.9H/7.9R · 6.0H/7.7R | 17 / 20% | 7 / 0% | 7.0 / 0%; 7.3 / 0% |
| Square II | 11.7 (164) | 100%, 4.7H/6.5R | 50% | 13% | 11.9 / 3% |
| Church I / II | 10.7 / 11.0 | 100 / 100%, 4.5/5.7 · 3.8/5.2 | 43 / 27% | 0 / 0% | 9.2 / 0%; 11.4 / 3% |
| Road I / II | 11.4 / 10.6 | 100 / 100%, 5.0/6.8 · 7.3/8.2 | 37 / 27% | 0 / 0% | 8.6 / 0%; 10.1 / 0% |
| Lighthouse I / II | 10.7 / 10.7 | 80 / 100%, 4.4/5.7 · 4.6/5.7 | 47 / 30% | 10 / 0% | 8.9 / 0%; 10.2 / 0% |
| Fairground I / II | 9.8 / 10.6 | 80 / 97%, 4.5/5.5 · 4.4/5.3 | 30 / 30% | 0 / 3% | 8.2 / 0%; 9.3 / 0% |
| Almanac I / II | 11.6 / 10.4 | 100 / 97%, 4.3/6.1 · 4.2/4.9 | 57 / 13% | 3 / 0% | 12.0 / 3%; 8.0 / 0% |
| Square + Church + Almanac (two seed sets) | 11.0 / 10.6 (154 / 148) | 2+ objectives 60 / 40% (50% of 60) | 40 / 30% | 0 / 3% | 11.8 / 3%; 11.4 / 3% |
| Finale (declared at the Study) | 7.8 (109) | contest 53% | 57% | 3% | 10.9 / 0% |
| Finale begun at Hour IX | 13.2 (184) | contest 63% | 83% | 33% | 15.2 / 3% |

No game in the suite, or in the 60 extra Square games at 3p and 4p, reached
the engine's 30-round cap (before the Hold Back limit, 3 of 30 Square games at
3p and 1 of 15 at 4p did: a party holding the Appointed back every round kept
the night at Hour VIII). The Square at 4p: 10.6-11.1 rounds, 0 resets, 0
wipes over 60 games.

Solo (1 investigator, 15 games each): Part I wipes Square 0%, Church 7%, Road
0%, Lighthouse 13%, Fairground 7%, Almanac 7% (6% average; 30%, 27-53%
before), Part II 0%; loops 12.6-15.0 rounds. The second wind is used in most
solo loops; solo now loses about as often as a larger party is wiped.

Finale by count: contest 1 investigator 67% (wiped 20%), 2 67% (13%; 40%
before, 63% contest over 30 games of each seed set), 3 53% (3%), 4 60% (0%).

Years per investigator per loop at 3p (district and three-district loops,
450 games): 1.46 (Part I 1.51, Part II 1.38; 1.58 before this pass). At that
rate an investigator reaches Elder (10 Years) after about 7 loops and ages
out (18) after about 12, against a first-time finale unlock around loop 5-6
(`simulate_tempo.py`). Memory: 34-45 per investigator before the finale loop
(unchanged). Deck reshuffles 0.2-1.2 a loop (1.2-1.7 in the Square alone).

Missed or loose: districts stay a little generous (80-100%, 4-6 Hours to
spare where 2-4 was asked); the three-district loop's two-objective rate
swings by seed set (40-60%); the Hour IX finale wipes 33%; solo defeats are
now rarer than party defeats.

## Engine corrections and the finale retune (2026-09-30, evening)

**Every engine result above this section was measured with two engine bugs
and is superseded by the tables below.** Both made the game look kinder than
its cards are:

- **One enemy per enemy phase.** `R.enemyPhase` copied `G.enemies` with
  `{ table.unpack and table.unpack(t) or unpack(t) }`; an and/or expression
  keeps one value, so only the first enemy in play hunted and attacked in
  each enemy phase. Every other enemy only ever hit through attacks of
  opportunity. Fixed (`copyList`); `tests/test_play_engine.py` fails on the
  idiom.
- **The finale started an Hour late.** A finale begun before Hour V clicked
  the Hour a fixed number of times; with Hour IV removed (The Hour Was Wrong,
  in the finale state) the Control steps over it and the Skip ended on
  Hour VI. It now advances until Hour V is current (test: the Skip ends on
  Hour V). The guide's instruction had the same trap and now says to click
  until the Control token shows Hour V.
- The AI now fights or evades any engaged enemy (the most dangerous or the
  easiest to remove scores best), not only the first one to engage.

The two bugs pulled in opposite directions in the finale (an Hour of time
missing, most enemy attacks missing): 3 investigators, normal start,
contest 55% (120 games) with both bugs, 87% with only the Hour fixed, 47.5%
with both fixed (120 games; 50% of finales wiped the party).

## The owner's curve by night, XP decks and the unlock rule (2026-10-01)

**Supersedes every result above.** The owner asked for a win-rate curve at
three investigators **by night**, never above 80%: Prologue and night 1
**80%**, nights 2-3 **70%**, nights 4-5 **60%**, nights 6-7 **50%**, finale
**40%**. Changes:

- **XP decks.** Later nights play upgraded decks (`decks.py` `UPGRADES`,
  tiers n2-n7 and fin: 4, 8, 12, 16, 20, 24, 26 XP), from that night's state
  (scenarios `district_*_n3`, `_p2`, `_p2_n5`, `_p2_n6`, `_p2_n7`; table in
  Representative campaign states).
- **Unlock rule.** The finale opens once the log records The Appointed's Name
  and The Vote That Never Ends (`Knowledge.canAssembleFinale`); with the old
  rule a first-time group needed a median of 10 nights.
- **Rules.** The Minute Hand ×1; an Echo that wakes is exhausted; when the
  Hour turns each investigator heals 1 damage and 1 horror; the Uninvited 1
  horror; finale contest **6, 5 solo, 7 at four**.
- **Act costs** ([perinv] unless noted; before → after): The First Hour Hour V
  4 → **Hour VI 7**; The Sheriff Is Already Dead 5 → **9**; The Thirteenth
  Toll 5 → **10**; What the Almanac Hid 5 → **9**; Light the Lamp 3 → **4**;
  The Wheel Still Turns 3 → **5**; Walk It Backward 2 a step → **3, 3, 4**
  clues; The Vote 5 → **8**; The Hour Was Wrong 5 → **7**; The Keeper's Ninth
  Death 3 → **6**; The Ticket-Taker's Bargain 5 → **8**; The Appointed's Name
  5 → **7**; Who Walks Beside You **7** (new cost). A failed Lamp, Wheel or
  Stand Firm test puts the spent clues on the location.

Results (engine, Standard, 3 investigators, 30 games a district, 60 for the
finale; the published cards, no what-ifs except the last three Part II
costs, measured as overrides before they were printed):

| night | target | won | Square / Church / Road / Lighthouse / Fairground / Almanac |
|---|---|---|---|
| Prologue | 80% | **80%** | – |
| 1 | 80% | **73%** | 73 / 57 / 73 / 77 / 83 / 77 |
| 3 | 70% | **71%** | 53 / 63 / 60 / 87 / 80 / 80 |
| 4 | 60% | **69%** | 67 / 73 / 57 / 60 / 77 / 80 |
| 5 | 60% | **63%** | 67 / 63 / 60 / 67 / 60 / 63 |
| 6 | 50% | **59%** | 60 / 60 / 60 / 60 / 63 / 53 |
| 7 | 50% | **40%** | 37 / 47 / 57 / 30 / 30 / 40 |
| Finale | 40% | **43%** | – |

Pairs: nights 4-5 66% (target 60), nights 6-7 49.5% (50). Square + Church +
Almanac in one night: one objective 77%, two 0% (with the Name-and-Vote
unlock that still reaches the finale in about 7-8 nights).

Finale by count (60 games each): 1 investigator 55% at contest 5 (23% at 6),
2: 38% at 6 (67% at 5), 3: 43% at 6 (28% with the 2-horror Uninvited), 4:
37% at 7 (70% at 6). One contest step moves the finale 25-35 points, so each
count takes the goal nearest 40%.

Method note: the engine builds its table from `dist/`'s Saved Object; five
sets that started before a publish played the old encounter deck and were
rerun. Engine results from different builds are not comparable game by game
(a changed deck changes every shuffle), only as rates.

Missed or loose: night 1 sits 7 under (the Church 57%); night 4 9 over;
the night-7 Lighthouse and Fairground 30%; one AI party and one upgrade path
per investigator. Simulation only; not a playtest.



## Official flow and final calibration (2026-10-01, late)

**Supersedes the curve section above.** After the official comparison
(docs/design/OFFICIAL_COMPARISON.md): enemies at official strength, 10
treacheries rewritten as skill tests (Rising Water lingers), campaign
chaos-bag changes, official XP (Victory per investigator, surface 1 / deep 3,
cap 10 per investigator). Recalibrated on the engine with two cost settings
per act (current and 2 lower), fitted per district and confirmed.

Final costs ([perinv] unless noted): The First Hour 7 from **Hour VII**; The
Sheriff Is Already Dead 9; The Thirteenth Toll **9**; What the Almanac Hid 9;
Light the Lamp 4; The Wheel Still Turns **4**; Walk It Backward 3, 3, 4
clues (4/4/4: 40% / 30%; 3/4/4: 43% / 57% on nights 1 / 3); The Vote 8; The
Hour Was Wrong 7; The Keeper's Ninth Death 6; The Ticket-Taker's Bargain
**7**; The Appointed's Name 7; Who Walks Beside You **8**. The Uninvited
**2 fight, 3 health** (finale 30% -> 38%). Finale contest 6, 5 solo, 7 at four.

Results (3 investigators, Standard, XP decks, 30 games a district, 60 for
the finale):

| night | target | won | Square / Church / Road / Lighthouse / Fairground / Almanac |
|---|---|---|---|
| Prologue | 80% | **83%** | – |
| 1 | 80% | **76%** | 67 / 80 / 93 / 83 / 67 / 67 |
| 3 | 70% | **76%** | 73 / 80 / 77 / 73 / 73 / 80 |
| 4 | 60% | **71%** | 77 / 67 / 57 / 53 / 83 / 87 |
| 5 | 60% | **61%** | 57 / 60 / 63 / 50 / 63 / 70 |
| 6 | 50% | **48%** | 50 / 53 / 40 / 43 / 47 / 53 |
| 7 | 50% | **42%** | 33 / 40 / 37 / 43 / 57 / 40 |
| Finale | 40% | **38%** | 1p 42%, 2p 38%, 4p 27% (60 each) |

Pairs: nights 4-5 66% (60), nights 6-7 45% (50). Over the 80% cap: Road
night 1 (93%), Almanac II night 4 (87%), Fairground II night 4 (83%), the
Prologue (83%); the steps either side were much further off. Memory: about
5.6 per investigator on a Part II night (4.0 before the XP change).
Simulation only; not a playtest.

## Official clue scale, the night's goal and the party's order (2026-10-01, night)

**Supersedes the calibration sections above.** Locations now carry official
clue/shroud ranges and acts official clue costs (docs/design/OFFICIAL_COMPARISON.md,
third pass). A night counts as won only when every act of its goal is done:
the district's act and the Square's current act (`tools/play_engine/report.py`,
NIGHT). The party does the Square's act first (everyone starts there): on the
far districts that order won more (Lighthouse 50% -> 67%, Fairground 63% -> 90%
on night 1). Values chosen with single-act what-if sweeps, then confirmed.

Final costs ([perinv] unless noted): The First Hour 1 from **Hour VIII**; The
Sheriff Is Already Dead 3; Why Thirteen? 4 (take); What the Almanac Hid 4
(take); Light the Lamp 2 (and a test); The Wheel Still Turns 3; Walk It
Backward 3, 1, 1 clues (2, 1, 1 solo); The Vote 2 (take); The Hour Was Wrong 2
(take); The Keeper's Ninth Death 2 (take); Who Walks Beside You 3; The
Ticket-Taker's Bargain fare 5 (resources 3 for 1); The Appointed's Name 2
**while Arrived**. The Uninvited 4 health. Finale contest 6 (5 solo, 7 at four).

Results (3 investigators, Standard, XP decks, 30 games a cell, 60 for the
finale; about ±9 points at 30 games):

| night | target | won | Church / Road / Lighthouse / Fairground / Almanac |
|---|---|---|---|
| Prologue | 80% | **80%** | – |
| 1 | 80% | **79%** | 73 / 80 / 73 / 80 / 87 |
| 3 | 70% | **77%** | 77 / 73 / 77 / 73 / 87 |
| 4 | 60% | **59%** | 70 / 63 / 57 / 67 / 37 |
| 5 | 60% | **59%** | 70 / 63 / 57 / 63 / 40 |
| 6 | 50% | **57%** | 60 / 60 / 47 / 73 / 47 |
| 7 | 50% | **42%** | 53 / 50 / 20 / 47 / 40 |
| Finale | 40% | **37%** | – |

The Square alone (97-100%) is left out of the night averages: a loop is the
Square plus one or two districts (guide, "A first loop"). Off the curve: the
Almanac House's deep act (37-47%: "while Emerging or Arrived" measured 97%,
"while Arrived" about 40%; the clue cost does not move it, the one-Hour window
does), the Lighthouse on night 7 (20%; 47-57% on nights 4-6), the Almanac
House's surface act at 87% (within noise of the 80% cap). A three-district
night (Square, Church, Almanac): 2 or more of 3 acts in 80% of loops.
Simulation only; not a playtest.

## Assumptions and limits

- One AI party, greedy but competent; real players differ (they talk and plan
  across rounds). Treat differences between
  scenarios as signal, absolute rates as rough.
- Campaign states are representative, not played through: each scenario
  restores a fixed Control blob and log (table above).
- Player cards are engine data, not physical cards; damage, horror and
  resources are tracked by the engine. Level-0 decks on nights 1-2, then a
  fixed upgrade path per investigator (one path, not every combination a
  group might build); no Recollections beyond Foreknowledge, Muscle Memory
  and I've Done This Before.
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
