# Late objectives: every night has something to do (design, 2026-10-12)

**SPOILERS — designer/assistant only.** Owner decision 2026-10-12 ("There should always be something to do"; chose
"prep objectives + safety"): each district gains a third act, a late objective that prepares for the finale, and once
every one is done the next loop is the finale.

## Why

Whole-campaign simulation (27 carried campaigns, 2026-10-11): 18 of 27 parties had recorded all 14 Knowledge entries
by the end of Night 7, so Night 8 had no objective (scored 19%; 56% where a goal was left). At the table that is an
empty loop: nothing to find, only Years to pay.

## The rule

- Each district's act deck is now three acts: 1a (surface), 2a (deep, Part II), **3a (late, Part II)**. Act 2a's back
  advances to act 3a. Place makes act 3a current when the district's deep entry is recorded; when its late record is
  in the log the act deck is removed (its objectives are complete).
- Completing act 3a records a **late record** (log page 2, "Before the Last Hour"). Late records pay no banked Memory
  (experience stays in the official 35–45 band); their reward is in the finale.
- **In The Last Hour's setup**, each late record of a Past district (The Square, The Drowned Church, The Almanac
  House) places 1 damage on As It Was; each of a Future district (The Lighthouse, The Sunken Road, The Fairground)
  places 1 damage on As It Will Be, never more than half a form's health (so at most 1 at one investigator, 2 at two). Same periods as the deep entries spent in the finale.
- **The night will not wait (safety):** when the log records all six late records, the next loop is the finale:
  after Loop Setup, begin the finale at once (Control: Begin Finale), wherever the investigators are.
- So a loop always has an objective: a surface, deep or late act is left somewhere (late acts have no requirement
  beyond their own deep entry), or the finale begins.

## The six acts

| District | Act 3a | Objective (2 [perinv] clues) | Record | Period |
|---|---|---|---|---|
| Lighthouse | Keep the Light | lamp lit; group spend at The Lantern Room | The Light Is Kept | Future |
| Drowned Church | Toll the True Hour | Hour VI or later; group spend at The Belfry | The True Hour Tolled | Past |
| Sunken Road | The Last Milestone | group spend at The Milestones | The Road Has an End | Future |
| Square | Call the Roll | [action] at The Town Hall Steps, test [wil]/[int] (3); fail: clues to the location | Every Name Was Read | Past |
| Fairground | Stop the Wheel | [action] at The Wheel, 1 [perinv] only, test [com]/[agi] (3); fail: clues to the location | The Wheel Stands Still | Future |
| Almanac House | Set the Hour Right | [action] at The Press, +1 doom on the current Hour | The Hour Is Set Right | Past |

Each uses an objective shape the table and the engine already run (lamp, minimum Hour, plain group spend, [action]
test with failed clues, doom cost).

## District resolutions

Resolution 3's condition now reads "you completed neither <1a> nor <2a> this loop, and your log records at least one
of this district's entries", and a new **Resolution 4** (you completed <3a> this loop) is read *in addition* to the
first resolution that applies. NR is unchanged.

## Balance

The finale gets up to 3 damage on each period form before the fight; the finale is re-tuned to keep full victory near
40% (see FINALE_REDESIGN.md, "Late objectives" rows).

## Measurements (carried campaigns, 3 investigators, `goalsPerNight 2`, seeds 5000/6000/7000 × 9)

| build | Night 7 | Night 8 | finale home | stranded | not ended / unavailable | deep entries at finale | late records | Memory / inv. |
|---|---|---|---|---|---|---|---|---|
| before late objectives (boss finale tuned) | 63% | 19% (18 of 27 nights had no goal) | 41% | 22% | 37% / 0 | mostly 6 | – | 44.3 |
| late objectives, planner treats all pending alike | 78% | 59% | 22% | 33% | 33% / 11% | mostly 4–5 | 2–5 | 39.5 |

The second row's planner spent nights on late objectives while deep ones were still open, so parties reached the
finale with fewer deep entries (2 damage each, and the Name and the Vote open the finale): three campaigns never
opened it. A table would finish the deep objectives first; the planner now does (surface and deep before late).
No campaign recorded all six late records, so the forced finale did not fire.
