# Location text — how it was chosen

Status: **proposed, pacing-checked, not yet playtested** (2026-09-27).
Contains rules text: this is a design document, not player-facing.

## 1. What official campaigns do

Source: the public ArkhamDB card data for the core set and the first seven
cycles (Dunwich to Innsmouth, 43 packs, 588 locations). Reproduce with
`python3 pipeline/survey_official_locations.py`.

| Revealed-side text | Share of official locations |
|---|---|
| a **Forced** effect | 44% |
| an **[action]** ability | 36% |
| deals damage or horror | 24% |
| a **restriction** ("cannot", "must") | 21% |
| a **[fast]** ability | 13% |
| **blank** | 2% (12 of 588) |

Median text length is about 30 words; 31% of locations carry Victory.

What the numbers mean in practice, from reading whole scenarios (The
Gathering, Extracurricular Activity, The House Always Wins, The Miskatonic
Museum):
- **Blanks are rare, and they cluster** at start locations, hubs and the intro
  scenario (The Gathering's Study and Hallway, Rivertown, lodge lobbies).
- **Most text is friction**: a small, flat penalty for entering, for failing
  an investigation, or for lingering (Attic: take 1 horror; Cellar: take 1
  damage; Art Gallery: lose 2 resources on a failed investigation). Friction
  shapes routes and risk more than it changes the clock.
- **Benefits are rare, costly and limited**: Student Union's
  "[action][action]: Heal 1 damage and 1 horror"; Clover Club's actions are
  "limit once per game" and tied to the scenario's story.
- **Scenario hooks**: resign, set-aside locations, story assets and act-linked
  text belong to that scenario's plot.

## 2. Rules used for The Still Hour

1. **Hubs and entry points stay blank** where the district's act, travel cost
   or Named enemy already carries the pressure (the official blanks sit at hubs
   and starts too). Every blank is a deliberate choice, listed below.
2. **Friction goes on objective and side locations**, is flat and small
   (1 damage, 1 horror, 1 Dissonance, 1 resource), and follows the district's
   theme.
3. **At most one benefit per district, costly** (two actions), and only where
   the trip is long.
4. **No new mechanics.** Only damage, horror, resources and Dissonance, which
   the Control token already tracks.
5. **Pacing must not move.** Every effect is modelled in
   `pipeline/simulate_tempo.py` (`LOCATION_PROFILES`) and the set is accepted
   only if the finale-unlock loop, objectives per loop and reset rate stay
   where they are without location text, at 1 to 4 investigators.

## 3. The locations

| District | Location | Role | Text | Why |
|---|---|---|---|---|
| Prologue | The Square | start | Each investigator begins play here. | Start location. |
| Prologue | The Long Pier | side | *(blank)* | Intro scenario, like The Gathering's Study and Hallway. |
| Prologue | The Almanac Steps | objective | Forced – After you enter the Almanac Steps: Raise Dissonance by 1. | Teaches the campaign's core pressure (being noticed) at the one place every party must go. The Prologue cannot be lost. |
| Square | The Square (hub) | hub | Each loop begins here… (travel rule) | Rules reminder. |
| Square | The Town Hall Steps | side | *(unchanged: side rule; the other side looks at the next Hour)* | Knowledge payoff. |
| Square | The Well | objective (1a) | Forced – After you enter the Well: Take 1 horror. | The body below. Like the Attic: a flat cost for going where the act needs you. |
| Square | The Records Office | objective (2a), Victory 1 | *(blank)* | Its Part II pressure is the Named enemy that raises its shroud. An extra-action cost was tried and rejected (see §4). |
| Almanac House | The Reading Room | entry hub | *(blank)* | District entry. |
| Almanac House | The Press | objective (1a) | Forced – After you fail a skill test while investigating the Press: Raise Dissonance by 1. | The press running wrong draws attention when you fumble with it. |
| Almanac House | The Sealed Study | objective (2a), Victory 1 | *(unchanged: closed until its act)* | Gate. |
| Fairground | The Ticket Booth | entry hub, Victory 1 | Forced – After you enter the Ticket Booth: Lose 1 resource. | The fare. The fastest district (one test) pays a small toll. |
| Fairground | The Wheel | objective (1a) | Forced – When the Hourglass advances, each investigator at the Wheel takes 1 horror. | The wheel turns with the night; don't linger. |
| Fairground | The Hall of Mirrors | side | Forced – After you fail a skill test while investigating the Hall of Mirrors: Take 1 horror. | You see how old you are getting (the Weathered age story is set here). |
| Drowned Church | The Nave | entry hub | *(blank)* | District entry and main clue source; the Church objective (6 clues) is already the slowest. |
| Drowned Church | The Belfry | side | Forced – After you enter the Belfry: Raise Dissonance by 1. | The thirteenth toll. |
| Drowned Church | The Vestry | objective (1a) | *(blank)* | Six clues are already the heaviest objective; no added friction. |
| Drowned Church | The Flooded Crypt | objective (2a), Victory 1 | *(unchanged: closed until its act)* | Its Named enemy is the pressure. |
| Sunken Road | The Milestones | entry hub | *(blank)* | District entry. |
| Sunken Road | The Low Bridge | objective step (1a) | Forced – After you fail a skill test while investigating the Low Bridge: Take 1 damage. | Slipping into the water that never goes down. |
| Sunken Road | The Turning | objective (1a/2a), link to the Lighthouse | *(blank)* | Its act (the Echo "Hold") already defines it. |
| Lighthouse | The Winding Stair | gate | *(unchanged: agility test to reach the Lantern Room)* | Gate. |
| Lighthouse | The Lantern Room | objective (1a) | *(unchanged)* | Knowledge payoff. |
| Lighthouse | The Keeper's Quarters | objective (2a), Victory 1 | [action][action]: Heal 1 damage and 1 horror. | The keeper's bed. The Lighthouse is two district crossings out; the Student Union's rest, at the same cost. |

Blank revealed sides: 7 of 23 (Long Pier, Records Office, Reading Room, Nave,
Vestry, Milestones, Turning). That is more than the official 2%, by choice:
this campaign's six districts each have an entry hub, and its acts already put
the pressure on specific locations.

## 4. Pacing check

`python3 pipeline/simulate_tempo.py --compare`, 4000 campaigns, 35% action tax:

| play | players | finale unlock loop, no location text | with this text | location harm per investigator per loop |
|---|---|---|---|---|
| first-time | 1 | 9 (6–12) | 9 (6–12) | 0.18 |
| first-time | 2 | 6 (4–8) | 6 (4–8) | 0.11 |
| first-time | 3 | 6 (4–8) | 6 (4–8) | 0.08 |
| first-time | 4 | 6 (4–8) | 6 (4–8) | 0.06 |

Objectives per loop and the Dissonance reset rate are unchanged at every party
size. **Rejected:** "You must spend 1 additional action to investigate the
Records Office" left the 3-player pace alone but cut solo finale unlocks by
loop 15 from 98% to 80%, because the Square's deep objective spends its clues
there.

The model counts actions, clues, travel, the Hourglass and Dissonance; it does
not play cards or enemies. It shows the text does not break the pace; only
table play shows whether it feels right.

## 5. Playtest checklist

Note these in the first loops, per location code on the review page:
- **Well / Wheel / Hall of Mirrors / Low Bridge:** does the harm ever decide a
  defeat? It should sting, not end a loop.
- **Almanac Steps / Belfry / Press:** does the Dissonance push a loop into
  Glitch noticeably earlier? One step each is the intent.
- **Ticket Booth:** is the lost resource felt, or ignored? Ignored is fine.
- **Keeper's Quarters:** is the heal ever worth two actions? If never used,
  it can go.
- **Blank hubs:** does any district feel flat? That district is where to add
  text first.
