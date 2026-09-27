# Location text — "What the town remembers"

Status: **pacing- and economy-checked in the simulator, not yet playtested**
(2026-09-27). Contains rules text: a design document, not player-facing.

## 1. Reference: what official campaigns do

Public ArkhamDB card data, core set plus Dunwich to Innsmouth (43 packs, 588
locations). Reproduce: `python3 pipeline/survey_official_locations.py`.

| Revealed-side text | Share |
|---|---|
| a **Forced** effect | 44% |
| an **[action]** ability | 36% |
| deals damage or horror | 24% |
| a **restriction** | 21% |
| a **[fast]** ability | 13% |
| **blank** | 2% (hubs, starts, the intro scenario) |

Median length about 30 words; 31% carry Victory. Most text is small, flat
friction; benefits are rare, costly and limited; the rest are hooks into that
scenario's story.

## 2. The Still Hour's own system

Locations speak the campaign's currencies: **Hours** (time), **Dissonance**
(being noticed), **Memory** (what you keep), **Years** (what it costs you),
**Static**. The system has four rules:

1. **One lever per district.** A benefit paid for in a campaign currency, never
   free:

   | District | Lever | Pays with | Gives |
   |---|---|---|---|
   | Sunken Road | The Turning | 2 Dissonance, an action | 1 Hour back (once per loop) |
   | Drowned Church | The Vestry | a clue, an action | 1 Dissonance lower (once per round) |
   | Fairground | The Hall of Mirrors | 1 Year, an action | 2 Memory on your card (once per loop) |
   | Square | The Records Office | 2 clues, an action | takes back 1 Year a card gave this loop (once per loop) |
   | Almanac House | The Press | a clue, an action | removes a temporary Static token (once per round) |
   | Lighthouse | The Keeper's Quarters | two actions | heal 1 damage and 1 horror |

2. **The levers feed each other (one economy).**
   - Time costs attention: the Turning's rewind raises Dissonance, and the
     Vestry lowers it.
   - Memory costs age: the Hall of Mirrors trades a Year for Memory, and the
     Records Office (always on the board) can take that Year back for clues.
   - Memory on cards is also what the Appointed and the Waiting Congregation
     hunt, and what several investigators' abilities run on.
   - The Press answers the Static that Almanac and Fairground treacheries add.

3. **Hazards go where the encounter deck does not already hurt, and Knowledge
   quiets them.** Encounter cards already punish the Lantern Room, the Low
   Bridge, the Hall of Mirrors, the Sealed Study and the Church. Location
   hazards sit elsewhere, and the district's recorded entry switches them off:
   - Well (1 horror): off once you know **The Sheriff Is Already Dead**.
   - Belfry (+1 Dissonance): off once you know **The Thirteenth Toll**.
   - Ticket Booth (lose 1 resource): off once **You hold the ticket** (a
     choice echo).
   - The Wheel's horror stays: the fastest objective keeps a cost for lingering.

   This is the balance arc: the scar makes each loop start with more
   Dissonance, and learning the town makes its places kinder.
4. **Hubs stay quiet** (the Nave, the Milestones, the Reading Room) and so does
   the Low Bridge, which The Bridge Remembers already covers. The Prologue
   teaches one mechanic per location, like The Gathering.

## 3. Every location, every scenario

| Scenario / district | Location | Text | Role |
|---|---|---|---|
| Prologue | The Square | Each investigator begins play here. | start |
| Prologue | The Long Pier | [action]: Test [wil] (2). If you succeed, place 1 Memory on your investigator card. Group limit once per game. | teaches Memory |
| Prologue | The Almanac Steps | Forced – After you enter the Almanac Steps: Raise Dissonance by 1. | teaches Dissonance |
| Square (every loop) | The Square | Each loop begins here… (travel rule) | hub, rule reminder |
| Square | The Town Hall Steps | side rule; other side: look at the next Hour | Knowledge payoff (unchanged) |
| Square | The Well | Forced – After you enter the Well: If your Campaign Log does not record The Sheriff Is Already Dead, take 1 horror. | hazard, Knowledge quiets |
| Square | The Records Office (V1) | [action] Spend 2 clues: An investigator at the Records Office who gained Years from a card effect during this loop loses 1 of those Years. Group limit once per loop. | lever (Years) |
| Lighthouse | The Winding Stair | gate to the Lantern Room | unchanged |
| Lighthouse | The Lantern Room | calm side with The Lamp Was Never Lit | unchanged |
| Lighthouse | The Keeper's Quarters (V1) | [action][action]: Heal 1 damage and 1 horror. | lever (rest) |
| Drowned Church | The Nave | *(blank)* | hub |
| Drowned Church | The Belfry | Forced – After you enter the Belfry: If your Campaign Log does not record The Thirteenth Toll, raise Dissonance by 1. | hazard, Knowledge quiets |
| Drowned Church | The Vestry | [action] Spend 1 clue: Lower Dissonance by 1. Group limit once per round. | lever (Dissonance) |
| Drowned Church | The Flooded Crypt (V1) | closed until its act | unchanged |
| Sunken Road | The Milestones | *(blank)* | hub |
| Sunken Road | The Low Bridge | *(blank)* | The Bridge Remembers covers it |
| Sunken Road | The Turning | [action] Raise Dissonance by 2: Rewind the Hourglass by 1 Hour. Group limit once per loop. | lever (Hours) |
| Fairground | The Ticket Booth (V1) | Forced – After you enter the Ticket Booth: If your Campaign Log does not record You hold the ticket, lose 1 resource. | hazard, choice quiets |
| Fairground | The Wheel | Forced – When the Hourglass advances, each investigator at the Wheel takes 1 horror. | hazard |
| Fairground | The Hall of Mirrors | [action]: You gain 1 Year (record it now; it takes effect Between Loops). Place 2 Memory on your investigator card. Group limit once per loop. | lever (Memory) |
| Almanac House | The Reading Room | *(blank)* | hub |
| Almanac House | The Press | [action] Spend 1 clue: Remove from the chaos bag 1 Static token that a card effect added until the end of a turn or round. Group limit once per round. | lever (Static) |
| Almanac House | The Sealed Study (V1) | closed until its act; the finale may begin here | unchanged |
| Finale | *(the loop's board)* | the finale plays on the locations already in play | — |

Unrevealed sides keep their flavor only, as official unrevealed sides do.

## 4. Balance check

`python3 pipeline/simulate_tempo.py --compare` models each hazard and lever,
with a party that uses them sensibly: the rewind when it is safe, the Vestry to
stay out of the Noticed band, and the Memory/Year levers once a district's work
is done. 4000 campaigns, 35% action tax, first-time play:

| players | finale unlock loop, no location text | with these locations | objectives / loop | Memory / loop from locations | Years / investigator / loop | reset loops |
|---|---|---|---|---|---|---|
| 1 | 9 (6–13), 2.4% never | 9 (6–13), 3.3% never | 0.97 → 0.95 | 0.20 | 0.09 | 0% |
| 2 | 6 (4–8) | 6 (4–8) | 1.52 → 1.52 | 0.22 | 0.04 | 0% |
| 3 | 6 (4–8) | 6 (4–8) | 1.65 → 1.69 | 0.22 | 0.03 | 0% |
| 4 | 5 (4–8) | 5 (4–8) | 1.66 → 1.73 | 0.19 | 0.02 | 0% |

**Reading:** the difficulty stays where it was tuned (a 6–8-loop campaign). The
locations add choices, not ease or pain. The Memory they add is 1–3% of a
loop's income (about 17 at three investigators). The Years are optional and
small.

Iterations the model rejected:
- An extra action to investigate the Records Office cut solo finale unlocks.
- Using the Vestry every round wasted two actions per round and slowed solo
  and two-player play. The card allows it, but the smart play is to use it
  near the Noticed band.

## 5. Playtest checklist

- **Turning:** is one rewind per loop felt? Does its Dissonance cost ever
  cause a reset?
- **Vestry:** do you spend clues here that the act needed? It should be a
  real choice.
- **Hall of Mirrors + Records Office:** is the Year-for-Memory trade taken?
  Does anyone chain them? That combo is intended but costs a lot of time.
- **Press:** does a temporary Static token ever matter enough to remove?
- **Well / Belfry / Ticket Booth:** do they soften noticeably once the entry
  is recorded?
- **Wheel:** does the horror push you off the Wheel, or just sting?
- **Quiet hubs:** does any district feel flat?
