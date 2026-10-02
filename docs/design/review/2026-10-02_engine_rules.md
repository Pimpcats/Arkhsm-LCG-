# The Still Hour — independent post-fix verification, pass 3

**SPOILERS — designer/assistant only.**

Reviewed the current working corrections above `main` baseline `2cbd921` on
2026-10-02. Read `AGENTS.md`, `docs/ASSISTANT_WORKFLOW.md`, the required three-pass
provision in `docs/CAMPAIGN_PLAYBOOK.md`, and
`docs/design/FINISHING_CORRECTIONS.md`. Authority is the current player guide and
effective cards with override precedence. This reviewer changed no tracked
source, authored content, build output or release state. These reports and
fixtures are scratch verification evidence only.

## Result and verification evidence

All baseline findings from pass 3 are corrected within their reviewed scope.
The follow-up found several interaction errors while new purchase/signature
coverage was being implemented. They are now corrected and independently
rechecked, including the reset-during-test edge found at the initial report
save. No current functional blocker remains in this pass's reviewed scope.
Those errors were **designer engine fidelity errors**, not defects in the
authored rules or evidence that the live Control's cancellation transaction
remained broken.

Executed independent evidence:

- `.cache/finish_review/wording_fix_pass3_tests.lua`: **128 passes, zero failures**
  on both Lua 5.4 and Lua 5.2 in the final targeted run. The initially failing
  terminal-state edge was corrected and rechecked below. Tests use actual `rules`, `effects`,
  `players`, `flow`, `ai` and `finale` module factories with in-memory table
  adapters. It is an independently authored fixture, separate from
  `tests/play_engine_regressions.lua`.
- `.cache/finish_review/wording_fix_pass3_modules.lua`: **11 passes** on both Lua
  5.4 and Lua 5.2. It loads actual live modules for Prologue reset, legal transit
  distance/ties, pending Static extraction/return/consumption, duplicates and
  pending-queue save/load.
- Logs are `wording_fix_pass3_tests.log`, `wording_fix_pass3_tests52.log`,
  `wording_fix_pass3_modules54.log`, and `wording_fix_pass3_modules52.log` in this
  directory. `git diff --check` was clean when checked.
- `wording_fix_pass3_hashes.json` records SHA-256 source digests at the final
  test run. The reviewed flow digest is
  `678f6dd51fb89a6b1de48d0a5e6fd15700414982f9af83b2d76a19be7006a8d7`;
  later edits require the affected targeted checks to be rerun.
- The two other independent post-fix reports corroborate the actual Control
  callbacks and authored narrative changes. Their executed evidence is theirs;
  the third pass does not represent those fixtures as independently authored by
  this reviewer.

## Every prior finding: disposition

| Prior finding | Classification | Disposition and evidence |
|---|---|---|
| Static cancellation/preview retains irreversible band consequences | Live Control/module bug | Fixed. `ChaosBag.ttslua:271–331` queues identified reveals and consumes once; Control commits only actual resolution, refuses ambiguous anonymous calls and restores token buttons after load. Guide describes pending resolution. Third module fixture passes extraction/duplicate/return/save-load checks; independent passes 1 and 2 execute full boundary callbacks. Ordinary lowering still preserves Approach ratchet. |
| Farthest placement excludes unrevealed transit | Live module bug | Fixed. `Board.ttslua:650–676` builds movement graph from all legal locations and restricts destinations separately; `Locations.ttslua:215–239` returns real distance ties. Third fixture verifies unrevealed transit, missing connector and ties. Lead-investigator choice is announced, rather than silently replaced by straight-line distance. |
| Pending Prologue Years carry into first real Age | Live state bug | Fixed. `CampaignState.ttslua:520` clears the Prologue's pending counters; guide interlude explicitly explains it. Third fixture verifies both investigators clear, no scar/loop award, and real-loop pending Years are retained. |
| Fare printed as an effect then unconditional advance | Authored content plus engine integration | Fixed. `card_overrides.json:969` puts the whole group fare before the colon, with unchanged rates and scale. AI selects Parley with no AoO. `finale.lua:11–40` preflights the full payment before deductions and checks complete payment; third tests pass no partial payment/unaffordable advance and 5/10/15/20 fare at 1–4 players. |
| N01–N06 narrative/travel summary defects | Authored content | Fixed and independently re-read. Current guide is resident-compatible, charges one doom per first connection crossing per round, distinguishes the surface proof from the true hour, removes assumed optional visits/discoveries, and says Named add-ons are read once. Pass 2 documents two additional nonlinear-route prose fixes, now also present. No new narrative blocker found here. |
| V03-01 timed carry completes on arrival | Engine fidelity | Fixed. `effects.lua:496` rejects automatic advance of on-advance objectives before the carry branch. Third matrix verifies arrival waits, canceled skip does not deliver, rewind does not deliver, actual advance delivers, and ordinary untimed delivery still works. |
| V03-02 redirect changes ordinary damage to direct and loses enemy context | Engine fidelity | Fixed. `rules.lua:516–529` preserves ordinary assignment, carries originating enemy context and excludes direct/prohibited incoming effects. Third tests verify armor soak, no-soak damage, investigator Memory award, direct exclusion, weakness exclusion, and Guard Dog's enemy reaction. |
| V03-03 lone reaction ignores owned assets | Engine fidelity | Fixed. Enemy attack routes consume actual dealt damage including assets, rather than investigator-counter increase. Third tests cover fully prevented attacks, owned armor, once per round, and the separate special-enemy attack route. |
| V03-04 incoming passive permitted/outgoing commit prohibited | Engine fidelity | Fixed. Lamp and cross-owner healing respect the restriction; incoming commits are barred while outgoing commits remain available. Actual `AI.prepareTest` and healing/passive regressions pass. The reviewer did not invent a blanket prohibition on cancellation of incoming attacks/treacheries. |
| V03-05 Muscle Memory icons/draw timing | Engine fidelity | Fixed. `players.lua:355–402` applies repeat and physical-age icons and draws when committed. Third matrix covers repeated/nonrepeated willpower, combat and agility while Weathered, and verifies no duplicate after-test draw. |
| V03-05 Foreknowledge cost/draw/helper/max | Engine fidelity | Fixed. Shared commit path pays the owner's chosen controlled-card source, tracks payment, imposes one across all owners and draws only after a paid successful test. Third matrix covers unpaid/investigator-paid/asset-paid, success/failure, helper commit and cross-owner second-copy refusal. |
| V03-06 aggregate Memory pays investigator-only abilities | Engine fidelity | Fixed. `rules.lua:105–151` separates `cardMemory` from per-asset tokens and derives total. Third tests verify 2+1 cannot pay a 3-investigator-token cost, 3 can without consuming asset Memory, elder thresholds/resources use only investigator tokens, and defeat/slot replacement lose only departing asset tokens. |
| I Get Out adds injury to an unaffected track/does not end own turn | Engine fidelity; optional wording clarity | Fixed. `players.lua:519–541` clamps both injury tracks downward, ends the current investigator's remaining turn actions and places its reward on Compass. Third matrix covers damage-only/horror-only/both and an off-turn save. Optional “at least” wording was not necessary to implement healing correctly. |
| Multi-Hour cancellation cancels one increment only | Engine fidelity | Fixed. `rules.lua:192–204` cancels the complete advance before iteration and clears current-Hour doom. Third timed-carry/clock fixture verifies no Hour or delivery progress and doom removal. |
| Automatic Hold Back might bypass ready/round condition | Engine fidelity guard | Fixed and source-verified. `flow.lua:401–406` requires ready, same location, legal stage and an unused round. Automatic ring/event handling follows that guard. No numerical rewrite is required. |
| Recollection purchase-price drift / deck sizes/signatures | Reviewed consistency, no baseline change needed | Current ten Memory prices and Interlude prices remain aligned. Effective investigator deckbuilding/signature sets remain coherent. New all-five deck/purchase and carried-campaign economy checks are root responsibilities; this pass does not infer affordability from a printed price alone. |
| Act/agenda structure, nonlinear progression, terminal Hour | Reviewed consistency, no baseline change needed | Current 14 act front/back pairs and nine Hours remain coherent with the guide; Hours I–VIII advance and terminal IX ends play. Current ordinary doom schedule is 3 plus seven 2s, before crossing/skips/rewinds. Preserve nonlinear districts rather than inventing ten mandatory linear boxes. |

## Additional post-fix errors found and resolved

These are **designer engine fidelity errors**. They were reported promptly while
implementation was active; they do not imply the authored cards had those wrong
effects or that the live tabletop module executes the engine's policies.

| Interaction found | Current disposition / independent evidence |
|---|---|
| Canceled advance did not clear current-Hour doom | Corrected; entire canceled skip/doom regression passes. |
| Additional lasting elder horror heal was dropped | Corrected; actual damage heal gives the additional heal, and no damage healed gives no extra horror heal. |
| Marked Deck's chosen-number option accepted only investigator Memory | Corrected; controlled-asset Memory payment and paid-cost tally pass. |
| Lucky Compass paid asset Memory did not count toward loop-power Years | Corrected; specific asset deduction and `spent` tally pass. |
| Separate special-enemy attack route omitted the lone reaction | Corrected; attack absorbed by owned armor still awards its reaction. |
| Another owner's First Aid/Medical Texts could heal prohibited recipient | Corrected; other-owner heal is barred, own heal allowed. |
| Automatic evade bypassed cannot-be-evaded signature condition | Corrected; Rehearsed Escape and Cat selection honor the condition. Direct event regression preserves the engaged enemy. |
| Sealed token remained after slot replacement or actual elimination | Corrected; both release the token. Elimination still preserves the campaign's Memory-banking exception. |
| One multi-Hour advance recharged Stolen Minute once per Hour | Corrected; recharge moved to complete-advance hook. One skip gives one charge, later advance gives another, cancellation gives none, cap remains three. |
| Seraphine choices/ring branch were absent from new claimed coverage | Source-present now. Extra-action/ready-Spell tests and second-use Memory/limit pass; ring route uses guarded automatic Hold Back. |
| Seraphine's repeated skill bonus discarded returned extra +2 | Corrected; actual prepareTest supplies +4 and tallies both ability payments plus Doorway's payment. Lexicon repeat also supplies +4 and pays two secrets. |
| Unlimited Notebook Knowledge reaction had no owned-ability repeat hook | Corrected; own-turn repeated Knowledge reward independently gives four draws, four resources before event cost and two asset Memory. |
| Generic paid Dissonance costs were absent from most-recent-turn history | Corrected; costInv history is marked only during its own investigation turn. Third encounter tests verify +2 penalty for own-turn cost and +1 for an off-turn cost. |
| Bell repeat used a target already disengaged by first success | Corrected; failed evasion may repeat while still engaged, successful evasion cannot repeat against that now-illegal target. Both matrix cases pass. |
| Compass repeat reused the first destination | Source corrected; descriptor recomputes a legal next destination and Knowledge restriction. This exact repeated movement branch was source-reviewed, not separately executed in the final fixture. |

## Final terminal-state correction — resolved and verified

### F3-R01 — resolved reset-boundary Static continued its skill test

Guide Campaign Rules explicitly says the loop ends at once at the reset value,
even during a skill test or finale. `flow.lua:79–113` commits an uncanceled
Static, but determines success, offers failure-prevention/retry and invokes
`P.afterTest` before/after finally checking reset. The latter can award a
success/failure Memory token after the loop ended.

**Independent reproduction:** Ayako, Dissonance 23, intellect 3 versus difficulty
0, no commits, an uncanceled Static. The adapter applies the actual +1 on token
resolution. The first reviewed revision returned success and awarded investigator Memory even
though the loop ended. Expected: end and return tokens immediately, with no
successful action/retry/reaction reward. The fixture's canceled Almanac variant
passes: at the same boundary cancellation leaves Dissonance 23, redraws and
continues the legal test normally. Both Lua versions reproduced that failure
before the fix.

**Corrected and independently verified:** the reveal path now returns the seal
before a potentially terminal raise, checks reset immediately after uncanceled
Static resolution, returns tokens and exits without success, retry or after-test
reward. Both Lua versions pass the resolved and canceled boundary variants.
This is separate from the correctly fixed live pending-token transaction.

## Limits and retained approximations

The current engine implements far more purchases/signatures than the baseline,
but implementation and AI policy are different evidence. The root must retain
explicit limitations for printed options not selected by the policy and any
effects still omitted. The encounter-deck reorder in I Remember the Ending is
still explicitly not modeled in its handler at this review point. It Means
'Wait' remains explicitly partial in `P.APPROX`; base-game player cards also
retain approximations. Removing a stale label is appropriate only when replaced
by accurate current coverage, not by an assertion that every printed choice has
been played.

This pass certifies no final render fit, Godot/desktop execution, full human
playtest approval or ten-slot statistical difficulty curve. Root's new carried
campaign runner, retained basic weakness, budget and all-player/investigator
coverage require their own end-to-end evidence. A narrow source read of the new
runner confirmed it retains each investigator's original basic weakness and
actual campaign/deck progression; no additional direct guide contradiction was
found in that limited check. Source changes after the final
targeted run require the relevant fixture to be rerun, not a blanket repetition
of unrelated checks.
