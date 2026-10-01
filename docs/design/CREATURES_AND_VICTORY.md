# Creatures and Victory, scenario by scenario

Spoilers: enemy names, stats and rules text. Design document, not player-facing.

## Principle
- The **shared deck** (the spine, always in play) carries the recurring cast:
  the Echoes (The Waiting Congregation, The Drowned Choir, Familiar Face, The
  Lamplighter's Echo). Echoes sleep while Dissonance is Calm, so the recurring
  cast grows teeth as the night notices you.
- **Every scenario introduces a monster of its own**, tied to its theme and to
  a campaign currency.
- **Victory is optional greed**: the monsters worth Victory can be avoided, and
  Victory locations must be cleared of clues, which costs time.

## Roster

| Scenario | New monster | Stats (fight / health / evade, damage / horror) | What it does | Victory | Recurring |
|---|---|---|---|---|---|
| Prologue | The Minute Hand (×1) | 3 / 2 / 3, 1 / 1 | Hunter, prey most clues; not an Echo, so it acts in the Calm band | — | Congregation, Choir, Familiar Face, Lamplighter's Echo; the Minute Hand recurs every loop |
| The Square (every loop) | The Band on the Steps | 3 / 3 / 3, 0 / 1 | Echo; while awake, no events at its location | — | shared cast |
| The Lighthouse | Something on the Stair | 2 / 2 / 3, 0 / 1 | Echo on the Winding Stair | — | shared cast |
| The Drowned Church | The Drowned Verger | 3 / 3 / 3, 1 / 1 | Aloof; engages whoever takes a clue at the Vestry | 1 | + a Drowned Choir; Part II: The Bell-Ringer Beneath (V2) |
| The Sunken Road | The Mile-Counter | 3 / 3 / 3, 1 / 1 | Hunter; every 3 moves it places 1 doom on the current Hour | 1 | + a Waiting Congregation |
| The Fairground | The Barker | 3 / 3 / 3, 1 / 1 | Hunter, prey most resources; costs 2 resources per attack | — | Part II: The One Who Rides Forever (V2) |
| The Almanac House | The Compositor | 3 / 4 / 2, 1 / 1 | Retaliate; failed tests beside it raise Dissonance | 1 | — |
| The Square, Part II | What Wears the Sheriff | 4 / 6 / 3, 2 / 1 | Named | 3 | — |
| Finale | The Uninvited | 3 / 4 / 2, 1 / 1 | Hunter, prey most Memory; defeating it gains contest progress | — | The Appointed |

Recurring cast (fight / health / evade): The Waiting Congregation 3 / 3 / 2,
The Drowned Choir 2 / 3 / 2, Familiar Face 3 / 3 / 3, The Lamplighter's Echo
3 / 3 / 3; Named: The Bell-Ringer Beneath 4 / 5 / 3, The One Who Rides
Forever 4 / 4 / 3.

**Official comparison (2026-10-01).** The starting encounter decks of 54
official scenarios (Night of the Zealot to The Innsmouth Conspiracy;
arkhamdb-json-data and arkham-cards-data setups): deck 34 cards (30-38),
enemies 30% (23-36%), enemy fight 2.9 / evade 2.6 / health 3.0, damage +
horror 1.9, Hunter 44% of enemy copies. The Still Hour before this pass:
enemies 29-37% of a 25-33-card deck (in range), but fight 1.9 / evade 2.0 /
health 2.4 and Hunter 20%; with the act costs it made nights
investigation-heavy. Stats were raised to the official averages (a night's
deck now 2.7-2.8 / 2.4-2.6 / 2.8-3.0) and the act costs lowered to keep the
owner's curve. Hunter stays lower by design: the Echoes sleep until Dissonance wakes
them and the Appointed hunts every night. Engine (3 investigators): about one
enemy enters play a round (0.6-1.1), about 3 encounter cards drawn a round.

## Victory map

| District | Part I | Part II |
|---|---|---|
| Square | The Records Office (V1) | What Wears the Sheriff (V3) |
| Lighthouse | The Keeper's Quarters (V1) | — |
| Drowned Church | The Drowned Verger (V1) | The Flooded Crypt (V1), The Bell-Ringer Beneath (V2) |
| Sunken Road | The Mile-Counter (V1) | — |
| Fairground | The Ticket Booth (V1) | The One Who Rides Forever (V2) |
| Almanac House | The Compositor (V1) | The Sealed Study (V1) |

Total 15 Memory per campaign (each Victory pays once). Balance numbers:
`docs/BALANCE.md`, "Victory greed".

## Art
The six new monsters have art briefs in the ChatGPT art pack (the "still to
generate" request). Until their art is imported they render without an
illustration.
