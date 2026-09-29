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
    python3 tools/play_engine/run.py --suite --jobs 4        # the full balance suite (about 20 minutes)
    python3 tools/play_engine/run.py --scenario prologue --trace   # one game, play by play
    python3 tools/play_engine/run.py --scenario loop_multi --render .cache/play_engine/render/multi
    python3 tools/play_engine/run.py --report                # rebuild report.md / metrics.json

Scenarios: `prologue`; `district_<square|church|road|lighthouse|fairground|almanac>`
(Part I, the Square plus that district; the Lighthouse also places the Sunken
Road); the same with `_p2` (Part II, the deep act); `loop_multi` (the Square,
the Drowned Church and the Almanac House); `finale` (declared at the Sealed
Study) and `finale_h9` (the same state, begun when Hour IX is reached). Parties: solo Cass;
Elias and Ayako; Elias, Ayako and Cass; the four with Seraphine. Outputs stay
in `.cache/play_engine/` (gitignored): `games/*.jsonl` (one JSON per game with
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

## Headline results (suite of 2026-09-29, Standard, 3 players, 30 runs)

| scenario | objective | Hours to spare | rounds | defeat games | Dissonance max |
|---|---|---|---|---|---|
| prologue | 100% | 7.7 (done Hour 1.3) | 1.1 | 0% | 1.2 |
| Square I / II | 100% / 100% | 5.7 / 5.7 | 5.6 / 5.8 | 30% / 43% | 4.0 / 7.9 |
| Drowned Church I / II | 90% / 100% | 4.9 / 5.3 | 5.0 / 4.5 | 17% / 37% | 4.2 / 6.9 |
| Sunken Road I / II | 87% / 97% | 2.7 / 5.2 | 4.8 / 4.7 | 27% / 47% | 5.3 / 6.6 |
| Lighthouse I / II | 37% / 57% | 1.7 / 2.1 | 4.0 / 4.4 | 0% / 17% | 5.2 / 7.8 |
| Fairground I / II | 87% / 100% | 4.8 / 5.0 | 4.6 / 4.6 | 50% / 47% | 4.7 / 6.9 |
| Almanac House I / II | 93% / 100% | 5.2 / 5.5 | 5.4 / 5.1 | 17% / 23% | 4.3 / 8.3 |
| loop_multi | 1.93 objectives/loop | – | 5.3 | 40% | 7.3 |
| finale / finale_h9 | contest 0% / 0% | – | 6.0 / 7.8 | 57% / 70% | 13 / 15.7 |

Solo (Cass) district loops lose all investigators in 30–80% of games; four
players play like three. Full per-count tables, Hour sources, spawns by card,
damage/horror sources, Memory/Years and the comparison with
`simulate_tempo.py --race` are in `.cache/play_engine/report.md`.

Findings (proposals only; nothing in the campaign was changed):

- **The Prologue ends in round 1.** Six shroud-1 clues in the Square pay the
  act before any mythos phase. What-ifs: act contributed only at the Steps
  (3 per investigator) 93%, round 3.2; "not before Hour IV" 100%, round 2.9.
- **The finale contest is out of reach** (mean 7.5 of 12: deep entries 4,
  Study visits 3, Hold Back 0.4, the Uninvited 0.1). Contest 3 per
  investigator: 10%; Appointed and Uninvited spawned at the Reading Room:
  3% (93% defeats); both: 30%. Begun at Hour IX it is worse (40% reset).
  Needs a lower threshold plus nearer sources or softer Arrived attacks.
- **Lighthouse and Road are the slow districts** (tempo model 99%/98%;
  engine 37%/87%). Lighthouse crossings cost 2.9 Hours a loop and Light the
  Lamp needs the Lamp carrier's own clues; letting any investigator spend
  raises it only to 57%. A cheaper Road–Lighthouse crossing or a lower
  Lamp threshold is the lever.
- **The Wheel** is the Fairground's main defeat source (6.6 horror a game).
- **Hour IV often closes the harvested Square**, the hub, leaving
  crossings as the only route.
- Doom supplies about 4 Hours a loop, the Lost Hour 1.4–2.1, Elder Thing
  tokens 0.5–1.4; Hold Back is rarely worth an action in district loops.
- No impossible spawns, no reshuffles, no placement overlaps and no Lua
  errors in the suite. The district act row covers SCED's "Investigators
  playing" panel (cosmetic).

## Assumptions and limits

- One AI party, greedy but competent; real players differ (they talk and plan
  across rounds). Treat differences between
  scenarios as signal, absolute rates as rough.
- Campaign states are representative, not played through: each scenario
  restores a fixed Control blob and log (table above).
- Player cards are engine data, not physical cards; damage, horror and
  resources are tracked by the engine. Level-0 decks only; no Recollections
  beyond Foreknowledge, Muscle Memory and I've Done This Before.
- Standard difficulty only.
- Approximated: choices on Hour IV, Wrong Turn and Town Hall (AI picks);
  the Appointed's engagement (Control position plus engine engagement); the
  order of "last Hour" act effects; Lucky Compass and Nobody Believes Her
  partially; the walker's ring choices. Not encoded (not in the decks or
  rarely drawn): Old Book of Lore, Stubborn Detective, Silver Twilight
  Acolyte, Leo De Luca, Opportunist, Medical Texts, Marked Deck, the
  Ambergrove Lamp action.
- What-if runs (`--what-if file.json`: card/act overrides, contest per
  investigator, finale spawn location) change the engine's reading only;
  results land in `.cache/play_engine/whatif/<tag>/`.
