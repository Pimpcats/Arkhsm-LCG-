# The Still Hour — final independent rules verification, pass 3

**SPOILERS — designer/assistant only.** Reviewed 2026-10-02 above `main` baseline
`2cbd921`, following `AGENTS.md`, `docs/ASSISTANT_WORKFLOW.md`,
`docs/CAMPAIGN_PLAYBOOK.md` section 4 and `docs/design/FINISHING_CORRECTIONS.md`.
This reviewer changed no tracked source, cards, guide, build or release state.

## Scoped signoff

**No reproduced blocker remains in the reviewed final snapshot.** The engine can
be frozen for the next calibration stage, subject to its declared policy and
approximation limits below. This is independent rules verification, not a
finding that a human group has approved the campaign or its difficulty curve.

The final follow-up specifically reviewed `players.lua`, `flow.lua`, `ai.lua`,
`tablekit.lua`, `decks.py`, and the corresponding carried purchase branch in
`engine.lua`. Expected behavior came from the current effective campaign cards
and player guide, SCED's actual printed player-card images and metadata, and
publisher-hosted images. It did not assume the root's assertions were correct:
the root fixture's initial level-2 Derringer margin-one expectation was found
wrong against its printed card and corrected.

## Executed evidence

| Independent evidence | Lua 5.4 | Lua 5.2 | Scope |
|---|---:|---:|---|
| `wording_fix_pass3_final_tests.lua` | 116 pass / 0 fail | 116 pass / 0 fail | Full own/helper skill result aggregation; shared maxima; permanent and mulligan setup; printed thresholds; timing; slots; actual encounter draws |
| `wording_fix_pass3_tests.lua`, rerun at final source | 128 pass / 0 fail | 128 pass / 0 fail | Earlier investigator, weakness, Memory, purchase/signature, advance and terminal-state interactions |
| `wording_fix_pass3_modules.lua`, rerun at final source | 11 pass | 11 pass | Actual live Prologue handoff, farthest transit/ties, pending Static extraction/return/consumption/duplicate/save-load |
| `decks.build` legality audit | 50 base/tier cells pass | Python | Five investigators × base plus nine tiers; 30 counted cards, full printed XP costs, budget bounds and permanent metadata |

The final Lua fixture has its own expected outcomes and uses production module
factories with controlled table adapters. The encounter-order section additionally
uses `tests/sced_real/tts_emu.lua` object data and **draws real emulator objects**
after rebuilding the deck. It verifies the resulting top-card identities,
original image/metadata association, stable tie order, untouched remaining
cards, preserved transform and final single-card remainder. It reports zero
emulator errors. This is stronger evidence than checking the reordered JSON
array alone; it still does not certify native TTS rendering or a desktop session.

The prior small permanent fixture was adjusted to 30 ordinary cards after the
new mulligan made its eight-card mock unsuitable. Its relevant expectation is
now five cards in hand and 25 in the draw pile. No source behavior was altered to
accommodate the test. The separate final fixture verifies rejected-card exclusion,
identity conservation, useful-weapon retention and weakness/permanent exclusions.

Files in this directory record the evidence:

- `wording_fix_pass3_final_tests54.log`, `wording_fix_pass3_final_tests52.log`.
- `wording_fix_pass3_tests54_final.log`, `wording_fix_pass3_tests52_final.log`.
- `wording_fix_pass3_modules54_final.log`, `wording_fix_pass3_modules52_final.log`.
- `wording_fix_pass3_final_decks.json` and `wording_fix_pass3_final_hashes.json`.

The source digests in the latter identify this reviewed snapshot. Later rules
edits require the affected checks to be rerun. The base/tier audit rebuilds decks
in memory from `.cache/finish_review/sced-save.json`; it does not mutate tracked
files or run a packaging build.

## Every original pass-3 finding: current disposition

The detailed original evidence remains in `wording_pass3.md` and
`wording_fix_pass3.md`. The following closes each original category at the final
snapshot and distinguishes actual campaign/module defects from engine fidelity.

| Finding | Classification | Final disposition |
|---|---|---|
| Canceled or previewed Static leaves irreversible band consequences | Live Control/module bug | Corrected. Pending, identified, one-shot resolution; duplicate, return and save/load regressions still pass. Full callbacks are also covered by independent passes 1 and 2. |
| Farthest placement ignores unrevealed transit | Live module bug | Corrected. All legal transit nodes, eligible revealed destinations, real lead-investigator ties; third live fixture still passes. |
| Prologue pending Years spill into first actual Age | Live state bug | Corrected. Prologue discards pending Years without scar/completed-loop awards; actual loop pending Years retained. |
| Fare is printed as an effect before unconditional advance | Authored content and engine integration | Corrected. Whole cost precedes effect; full atomic group payment and Parley no-AoO checks pass. |
| Opening, discovery claims, crossing summary, optional visits and repeated Named prose | Authored content | Corrected against the current guide, preserving nonlinear routes. No new narrative blocker in this final scoped review. |
| Timed carry resolves on arrival instead of a later advance | Engine fidelity | Corrected. Arrival/rewind/canceled skip do not deliver; actual advance does. |
| Damage redirect makes damage direct or drops enemy context | Engine fidelity | Corrected. Ordinary assignment, soak, owner Memory award, Guard Dog context and prohibited/direct exclusions pass. |
| Lone enemy-damage reaction ignores damage on owned assets | Engine fidelity | Corrected on ordinary and special attack routes; prevention and once-per-round checks pass. |
| Incoming weakness restriction is bypassed; outgoing helper commits rejected | Engine fidelity | Corrected. Incoming effects and commits barred, outgoing commits allowed; current helper/passive/healing checks pass. |
| Muscle Memory icons and draw timing | Engine fidelity | Corrected. Aging/repeated-type icons, commit-time draw and no duplicate after-test draw pass. |
| Foreknowledge cost, maximum, helper ownership and success draw | Engine fidelity | Corrected. Shared maximum; controlled source costs; paid success draw; unpaid/failure/helper variants pass. |
| Aggregate Memory pays investigator-only abilities | Engine fidelity | Corrected. Separate investigator/asset sources, source-specific costs and departing-asset loss pass. |
| Defeat prevention creates injury on unaffected track or fails to end turn | Engine fidelity | Corrected. Downward-only healing, own-turn end and controlled-asset reward pass. |
| Multi-Hour cancellation cancels only one increment | Engine fidelity | Corrected. Complete advance canceled and doom removed before iteration. |
| Automatic Hold Back bypasses ready/stage/round guards | Engine fidelity | Corrected. Guards and ring/automatic branch verified. |
| Recollection prices, investigator/signature sets, act/agenda fronts and backs | Reviewed consistency | No further authored rule change required. Current card/guide structure and ten purchase prices remain coherent; final deck audit now also covers valid upgraded counted sizes. |

## New follow-up findings and their final resolution

All defects in this table are **designer play-engine fidelity defects**, rather
than erroneous printed campaign cards or live tabletop Control defects.

| Finding or requested verification | Corrected behavior and independent evidence |
|---|---|
| Permanent XP purchase replaces a counted card, producing 29 | `decks.py` appends the permanent while preserving its ordinary card; `engine.lua` carried purchase does likewise. All 50 base/tier cells retain 30 counted cards; permanent setup excludes those cards from hand/draw pile. |
| Permanent basic weakness becomes a dead shuffled draw | SCED metadata identifies Indebted as permanent. Weakness records now preserve that flag; setup places it outside the draw pile and begins at three resources. Independent fixture passes. |
| Helper Deduction/Vicious copy or printing lost | `flow.lua` records all shared contributions on the test taker; `players.lua` sums each printing at the actual margin. Own level2 + helper level2 + helper level0 gives three additional results at margin0/1 and five at margin2/4. Actual investigate/fight paths verify the reward, owner discards and failed-test exclusion. |
| Core skill maximum omitted | Shared `P.commit` refuses a second Guts, Perception, Overpower, Manual Dexterity or Unexpected Courage across owners without discarding it. Deduction, Vicious Blow and Survival Instinct remain legal in multiple copies. Printed cards independently inspected. |
| Shotgun/Switchblade result thresholds | Shotgun damage clamps actual success margin to 1–5; Switchblade2 adds damage only at margin2. Matrix covers margins0/1/2/5/8. |
| Derringer2 grouped with margin2 threshold and missing action | Printed upgraded Derringer triggers extra damage at margin1 and action at margin3. Current fight path implements those thresholds and one action per asset per turn; same-turn repeat and next-turn reuse pass. |
| Peter2 sanity and recovery wrong | Printed health1/sanity3, both skill bonuses and controller-end-turn horror recovery now pass. Recovery no longer waits until upkeep. |
| Encyclopedia is passive or persists past the phase | Current action exhausts the asset and chooses the skill. Bonus disappears when investigation phase ends; targeted chosen-skill/other-skill checks pass. |
| Two-slot asset frees one slot or arcane capacity one | Hand2 removes both single-slot occupants, preserving other slots; two single arcane spells coexist; Arcane2 removes both. |
| Base Shrivelling inherits level3 bonus | Base printing adds no willpower; level3 adds2 and level5 adds3. Independent printed-boost matrix passes. |
| Blinding Light lacks printing-dependent damage/symbol effects | Base/level2 success damages1/2. Symbol costs one action on success or failure and level2 also inflicts one horror. Actual event-path matrix passes. Undefined `c.level` in event handler was also found and corrected to `card.level`. |
| Canceled symbols still trigger weapon/event punishment | Canceled result is returned as `Canceled`. Actual test→fight and test→event chains verify no Shrivelling horror or Blinding punishment after cancellation. |
| Survival Instinct claims disengage coverage but has no effect | Current successful evade handles the test taker, including helper commits, and excludes the primary enemy/another owner's enemies. Base disengages; level2 automatically evades other legal targets. Failed test and cannot-evade guards pass. Optional move stays unselected. |
| Encounter reorder only described, not performed | Top-three reorder and top-to-bottom move rebuild full object data while preserving cards. Stable sort, real subsequent draw order, transform, metadata, images and single-card edge pass. I Remember the Ending's former unmodeled-order caveat is superseded. |
| Opening hand has no standard mulligan | One policy mulligan now sets rejected cards and weaknesses aside until replacements, then shuffles them back. Legal-deck identity conservation, excluded replacements and no weakness resolution/resource drift pass. |

Earlier follow-up errors concerning canceled-advance doom, elder healing,
Marked Deck/Compass cost sources, seal release, per-complete-advance recharge,
Seraphine options/repeated boost, Notebook repeated Knowledge reward, paid
Dissonance history, Bell repeat legality and the terminal Static reset are still
corrected. Their 128-check fixture was rerun against the final source. Compass's
recomputed repeated destination remains source-reviewed, with its exact repeated
movement branch not independently executed; that limitation is unchanged.

## Printed-card authority

Actual SCED printed images and their source metadata were cached for inspection
in `card_rule_images/`; `index.json` identifies the XP printings. Inspected
prints include Peter2, Encyclopedia2, base/level3/level5 Shrivelling,
Blinding Light2, Deduction2, Vicious Blow2, all five core
max-one skills and base Survival Instinct. Publisher-hosted images independently
confirm the counterintuitive upgraded Derringer threshold and Survival Instinct2:

- https://images-cdn.fantasyflightgames.com/filer_public/10/7e/107eb49c-dbf0-4959-aaef-9879786b1879/ahc15_card_41-derringer.png
- https://images-cdn.fantasyflightgames.com/filer_public/15/e2/15e2bb2c-9109-4d8d-95c4-8156dbb9a8a0/ahc06_card_survival-instinct.png

## Limits for calibration and release claims

The declaration in `P.APPROX` remains relevant. The policy does not select every
printed option: for example Chicago Typewriter extra-action boosts, Survival
Instinct's optional movement and Magnifying Glass's optional return. Old Book
of Lore, certain basic weaknesses and selected signature cancellation policy
remain approximated or restricted. Encyclopedia policy currently chooses its
controller's intellect; this pass certifies its implemented chosen-skill timing,
not an exhaustive optimizer over every printed recipient/repeat/stacking choice.
The carried purchase path's permanent change was source-reviewed; this pass did
not independently execute the complete carried-campaign purchase sequence.

A legal budget tier is representative, not evidence its purchases were actually
earned. Actual carried progression, all player counts, statistical difficulty
confidence intervals, final renders, Godot/native desktop execution and hosted
release-package verification remain the root's separate responsibilities. The
pass approves the reviewed engine snapshot for calibration with those explicit
limits; it does not replace the requested scenario-by-scenario balance report.


## Final timing addendum — complete-advance objective window

**WITHDRAWN as Rules Reference certification.** The implementation-only checks below used an incorrect expectation for optional clue-spending objectives. The official-timing correction at the end of this report supersedes this section.

Root's calibration pilot identified a remaining engine timing omission: the
Prologue could reach Hour VIII with eligible investigators/clues, then draw
Mythos encounters before offering its non-action objective. A subsequent skip
to IX could therefore select the lower resolution despite an objective window
that should have existed. This is an engine fidelity fix; authored rules are
unchanged. This reviewer did not independently reproduce the root's reported
9/25 pilot rate and does not use it as a difficulty estimate.

Current `rules.lua:264–268` checks non-action objectives after the complete
advance and `FX.afterAdvance`, while play is still active. It does not check
between increments of a multi-Hour advance. `flow.lua` accepts a missing
`actOrder` as an empty order for isolated callers.

**Independent standalone evidence:** `objective_window_pass3.lua`, provided as
its own file for durable copying, passes **40 checks / zero failures on Lua 5.4
and Lua 5.2**. It loads actual production `rules`, `effects`, `players` and `flow`
modules and executes the real First Hour `canAdvance`, clue-payment and
`advanceAct` paths. Actual `endLoop` sentinel termination is handled by the
fixture, rather than replacing terminal rules with a nonthrowing stub.

The fixture verifies:

- At each player count 1–4, a doom advance from VII to VIII completes the
  eligible Prologue objective before any actual Mythos encounter draw and pays
  exactly one clue per investigator.
- Insufficient clues, clues held elsewhere and a closed objective location do
  not manufacture success. Normal draws remain available when the objective is
  unmet.
- A complete two-Hour skip ending at VIII resolves both Hours, then its
  after-advance effects, then one objective window. It preserves per-Hour
  healing.
- A complete skip passing through VIII to IX offers no intermediate objective
  window; IX terminates before objective payment. Direct IX arrival behaves
  likewise.
- Whole-advance cancellation opens no Hour/after/objective windows, clears doom
  and supplies no healing/payment. Canceling only the reached Hour's text
  retains the completed-advance objective window.
- Reset during the reached Hour and termination during `afterAdvance` prevent
  objective payment. Eligibility is evaluated after forced after-effects.
- Rewind, nonpositive advances and calls during already-ended play open no new
  objective window. A missing `actOrder` remains harmless.

Affected existing independent fixtures were rerun against this new source:
**116 final-scope checks plus 128 prior-interaction checks, zero failures on each
Lua version.** The live-module files are unchanged by this engine-only timing
fix. Logs and results are `objective_window_pass3_results.json` and the
`*_window_54.log` / `*_window_52.log` files in this directory.
`objective_window_pass3_hashes.json` supersedes the earlier final hashes for
this latest engine snapshot.

**Prior timing signoff withdrawn:** this section did not establish legal player-window timing. Calibration using its early paid-advance hook must be rerun after the correction below.


## Limited balance-cost addendum — final adopted adjustments

**Signoff:** the three adopted cost changes load consistently into effective
card text/metadata and the production engine at every player count. No blocker
remains in this limited pass. The original 144-check fixture still passes after
the final carry hardening; two added edge checks bring it to **146 passes / zero
failures on each of Lua 5.4 and Lua 5.2**.

Standalone durable fixture: `balance_costs_pass3.lua`. It reads the current
`campaigns/still_hour/card_overrides.json` directly and loads production rules,
effects, players, flow, finale and AI modules. A separate Python check used
`tools.play_engine.cards.load_cards()` to verify the actual effective merge,
rather than assuming raw overrides or a stale calibration export governed.
Movement targeting is held constant for the cost probes, while production
`AI.choose` and its objective-affordability gates execute unchanged.

| Effective cost | 1 investigator | 2 | 3 | 4 |
|---|---:|---:|---:|---:|
| Why Thirteen? | 3 | 6 | 9 | 12 |
| The Hour Was Wrong | 3 | 6 | 9 | 12 |
| Who Walks Beside You, either action or reaction | 4 | 8 | 12 | 16 |

Compared with the baseline override text, only the intended `4→3`, `2→3` and
`3→4` payment numbers change. Both Road payment lines match its metadata; all
three backs remain identical. Part-II text, pickup/delivery places, group payer
scopes, readiness/Echo requirement, failure return and timed-advance wording are
retained. Existing declaration for Opportunist now accurately describes base
success-by-three and upgraded success-by-one behavior.

The Lua fixture executes exact/one-short affordability for both Church assets
at counts 1–4. Production AI selects a one-action pickup only with sufficient
eligible clues. It also verifies that if a clue disappears after selection, the
selected action rejects without spending or granting the asset. Surface
contributions may come from the whole active party; deep contributions must be
at the Crypt. The actual Road action and evade-reaction paths both charge the
new 4-per-investigator total, refuse partial payment, and preserve legal evasion
when the optional reaction is unaffordable. Failed Stand Firm places the exact
new payment on The Turning. Non-Echo/wrong-place evades do not trigger the act.

This pass found and closed an existing carry-action fidelity gap: direct
`R.takeStory` previously granted an asset after partial payment even though AI
preflight ordinarily protected it. The final function now preflights actor,
carry act, current ownership, actual pickup/drop location and sufficient
eligible clues before deductions. Invalid calls return false without mutation;
valid calls enforce exact payment. Closed location, eliminated actor, existing
holder, wrong dropped location and missing dropped GUID regressions pass.
An already occupied impassable location still permits the ability, since
impassability restricts movement. AI additionally respects the explicitly
reported one-story sequential policy. That restriction remains a model policy,
not a new printed campaign rule.

Surface delivery still waits at the Belfry for an actual completed Hourglass
advance. Arrival, rewind and a canceled skip do not deliver; a real advance
does. The deep asset still delivers immediately on arrival at the Vestry.
These use the unchanged production carry/advance objective paths.

### Independent clue feasibility

Effective location quantities give **5 clues per investigator in the hub,
6 in the Church and 4 on the Road**. Before opening the Crypt the Church has 4
per investigator, enough for its surface cost3; the Crypt adds2, supplying the
remaining deep cost3 after the surface cost is spent. The Church's two costs
therefore total6 per investigator against6 district clues, with the hub's5
additional clues available along the route. Hub plus Church totals
11/22/33/44 clues at counts1–4. Hub plus Road totals9/18/27/36, versus the Road
payment4/8/12/16. The Road's surface sequence discovers clues without spending
or consuming them: solo discovers2+1+1, multiplayer3+1+1, feasible within its
actual location quantities and portable toward its deep payment. Optional clue
abilities can reduce these pools; this is mathematical feasibility, not a
claim that every route is easy or that every game collects all clues.

`balance_costs_pass3_data.json` records these comparisons and budgets. A synthetic
carried two-slot validator probe additionally passes with the final slot lacking
purchase/spending fields, preserved bank/weakness/Knowledge and a finale attempt
recorded in `metrics.finale_began`; its result is
`balance_costs_pass3_validator.json`. This checks the reporting repair, not a
carried-game success rate.

Affected existing fixtures were rerun at the exact final snapshot: **128 prior,
116 final-scope and40 objective-window checks, zero failures on each Lua
version**. Logs are `balance_costs_pass3_54.log`, `balance_costs_pass3_52.log` and
`*_balance_54.log` / `*_balance_52.log`; summaries are
`balance_costs_pass3_reruns.json`. `balance_costs_pass3_hashes.json` records the
final source/data digest set. No source changed between capture and recheck.
The cached engine card export was intentionally baseline until calibration
preparation; this reviewer did not overwrite it. The fresh effective export and
pinned rebuilt physical package must govern the final jobs, as the root plans.

The root's paired pilot figures motivated these limited choices. This reviewer
has not independently reproduced those pilot rates and grants no human balance
approval or statistical difficulty-target certification. The original release
and calibration limits remain in force.


## Critical Rules Reference timing correction — independent recheck

**Release blocker confirmed; previous objective-window signoff withdrawn.**
The generic `R.advance → R.checkObjectives` hook offers optional paid-clue
advancement inside Mythos framework step 1.3, before encounter draws in 1.4.
That is not a general player window. The earlier 40-check fixture confirmed
its implementation against an incorrect expected timing rule. It must not be
used as evidence of campaign balance or rules fidelity. The reported jump in
Prologue success after adding this hook requires fresh calibration once the
timing is corrected. The reviewer has not independently reproduced either
pilot rate.

Primary source inspected: [FFG Arkham Horror: The Card Game Rules Reference](https://images-cdn.fantasyflightgames.com/filer_public/c4/b0/c4b0d66c-d79e-411b-bdb5-b5d8c457d4bc/ahc01_rules_reference_web.pdf),
printed pp3,22–26. The actual p23 timing chart was visually inspected.

- Page3 treats ordinary spending of clues to advance an act as a free triggered player ability. Objective instructions can change prerequisites.
- Free triggered abilities use player windows. The p23 chart places no such window between the doom threshold check1.3 and encounter draws1.4; the next general Mythos window follows those draws.
- Page26 supplies two player windows before token revelation in a skill test. A test during encounter resolution can therefore supply a legal window earlier than completion of all encounter draws.
- Reaction triggers use their specified condition; automatic mandatory objectives do not become optional free abilities merely because no action is charged.

The First Hour's effective text (`card_overrides.json:830–840`) requires Hour
VIII or later and says eligible investigators may spend clues. It contains no
When, After, Forced, anytime exception, or other instruction changing that
ordinary timing. Its Hour eligibility condition does not authorize spending
during a framework event. The Sheriff Is Already Dead and The Appointed's
Name likewise retain normal player-window timing for their optional payments.

By contrast, holder-at-delivery objectives for Bound Almanac, Drowned Page,
Town Ledger and Keeper's Logbook have already paid for pickup and then
mandatorily advance when their condition is met. Why Thirteen? specifically
advances after the Hourglass advances when its holder is at the Belfry. Those
automatic deliveries keep their printed timing. Who Walks Beside You's
after-evade reaction is a separately printed reaction with its own cost and
trigger; it remains legal at that reaction point.

At the rechecked source, `rules.lua:263–266` runs `FX.afterAdvance` then the
unqualified objective check. `flow.lua:206–220` does not distinguish paid
optional objectives from automatic deliveries. `flow.lua:662–674` invokes
doom advancement before all encounter draws. The same generic check inside
`R.discover` (`flow.lua:183`) can also pay during an investigate result before
the complete action and its remaining consequences resolve. Turn-loop
boundary checks at `flow.lua:701,710` are legal player-window placements.

Recommended correction: classify automatic and triggered deliveries separately
from optional paid advances. Calls during complete advancement and discovery
can check automatic conditions; paid advances require explicit legal windows.
A post-encounter Mythos window is required. If pre-token skill-test windows are
not modeled for objective payment, disclose that approximation rather than
authoring an unprinted anytime exception. Cancellation, terminal IX, reset and
multi-Hour atomicity remain required, but none creates a new player window.

This correction supersedes the prior early-objective timing claims and the
40-check fixture's rules-certification claim. Cost, affordability, card text,
carry preflight and no-cost delivery findings remain valid independently.


## Corrected official-timing verification — final independent pass

**The paid-objective timing blocker is corrected.** The previous pre-encounter
40-check expectation remains withdrawn. The replacement repository fixture
`tests/play_engine_objective_windows.lua` explicitly documents that withdrawal
and is based on the primary Rules Reference cited above. It is standalone and
reads effective overrides, loading production rules, effects, players, flow
and finale. A durable standalone copy is
`objective_windows_rr_pass3.lua` in this report's directory.

| Independent fixture | Lua5.4 | Lua5.2 |
|---|---:|---:|
| Corrected RR objective windows | 87 pass /0 fail | 87 pass /0 fail |
| Effective costs, AI paths and pickup preflight | 146 pass /0 fail | 146 pass /0 fail |
| Final investigator, upgraded-card and deck scope | 116 pass /0 fail | 116 pass /0 fail |
| Prior campaign/investigator interactions | 128 pass /0 fail | 128 pass /0 fail |

`R.checkObjectives(allowPaid)` now defaults to automatic-only. Only an explicit
`R.playerWindow` calls it with payment permission. Generic complete-advance and
discovery calls therefore retain mandatory delivery checks without granting
optional paid advancement. The explicit parameter also prevents permission
from leaking into nested consequences of another paid ability.

The replacement independently verifies:

- At counts1–4, doom reachesVIII before encounters; each non-test encounter is
  drawn before payment at the general Mythos window. An already eligible act
  cannot advance at Mythos beginning to bypass an encounter reachingIX.
- An encounter test supplies actualST.1 andST.2 windows. Payment can occur
  before subsequent investigators draw, before committing atST.1 or after
  committing but before token revelation atST.2. Ineligible tests continue
  normally through both windows and the entire revelation.
- Defaults, declined payment, one-short cost, remote contributors and closed
  locations cannot spend illegally. Nested discovery inside another paid
  ability cannot inherit payment permission.
- Actual investigate, Deduction's two-clue result, committed-card discard and
  Milan's resource effect all complete before the following paid act ability.
- Complete, canceled, text-canceled, multi-Hour, terminal, reset, rewound,
  nonpositive and already-ended advances retain their required behavior; none
  creates an extra free window.
- Mandatory already-paid carry delivery bypasses optionalAI preferences. The
  Register's delivery still waits for the complete printed after-advance
  trigger, including a multi-Hour skip; cancellation does not deliver.
- Actual evasion preserves the paid Road reaction at its printed trigger,
  with full affordability and no invented post-test free window.
- Phase order follows the visually inspectedRRp23 chart: a turn begins before
  its first player window; no window follows turn-end consequences; all
  Hunter movement completes before its player window; engaged attacks are
  grouped by investigator, with no window between that investigator's
  individual enemies; Upkeep has a post-reset/pre-ready window and its next
  window follows all draws and mandatory round-end consequences.

The standalone146-check cost fixture is now copied unchanged to
`tests/play_engine_balance_costs.lua`, as authorized. For that timing verification, this reviewer changed
only the two owned test files and this review, never production rules. The
root owns their Python test-suite integration. Results, logs and the exact
source/card/test SHA256 set are in
`objective_windows_rr_pass3_results.json`; source did not change during either
verification batch.

**Corrected scoped signoff:** no further paid-objective timing, cost, carry
preflight or reviewed investigator/deck blocker was found in this snapshot.
Calibration must use this corrected model and fresh effective export. This
signoff is neither human playtest approval nor certification of difficulty
percentages. Newly observed missing encounter draws are a separate calibration
validity issue under review and are not covered by a zero-error claim.


## Encounter draw identity and calibration validity — independent follow-up

**The newly observed missing-draw blocker is corrected in the scoped adapter
verification.** Prior affected games are invalid calibration evidence. The
root reports stopping all earlier release/paired/pytest processes and retaining
no old batch as final. Fresh calibration must use the new adapter and validity
gate; the reviewer has not independently reproduced the entire new rate suite.

The pre-fix diagnostic log `encounter-probe5.log` demonstrates a genuine defect:
seed721401 misses at simulated times107.05 and120.35 with17 and14 cards in
encounter discard, respectively. A Deck with GUIDfda95e is physically at the
Green draw target in both cases. This is not an exhausted legal encounter pool.
The prior adapter polled only Card objects; its fallback could alternatively
return a preexisting weakness as the new encounter. Both behaviors invalidate
a game even when its engine-error and Lua-error lists are empty.

The corrected production `T.drawEncounter` records all Card and Deck child GUIDs
already at the destination before clicking. Its polling detects a moved
existing source Card or the newly arrived child of a destination Deck. It
extracts that child by GUID while preserving preexisting cards. There is no
old-Card fallback. Three simulated seconds cover SCED's0.55-second reshuffle
redraw delay.

Independent new repository fixture: `tests/play_engine_encounter_draws.lua`,
provided to the root for Python parametrization. Standalone durable copy:
`encounter_draws_pass3.lua`. It runs actual production tablekit against actual
emulator Card/Deck data, button dispatch, timers, merges, extraction, source
remainder transformation and encounter discard. The small test button
reproduces SCED's draw placement/merge and delayed reshuffle; the adapter's
polling, object identification and extraction run unchanged. This is bounded
adapter testing, not a live tabletop playtest or independent reproduction of
the entireSCED save.

**31 checks pass, zero fail, on both Lua5.4 and5.2.** They cover:

- The preexisting last source Card moves to the destination and is recognized
  without requiring a new global object identity.
- An encounter merges with a preexisting weakness Card or Deck and is extracted
  correctly; all preexisting GUIDs, card metadata and artwork remain.
- A two-card encounter source becomes one existing Card; both sequential draws
  preserve identity and actually reach discard without duplication.
- A delayed reshuffle draw is found within the polling window, with the
  remaining source cards conserved and the reshuffle correctly reported.
- No arrival returnsnil even with an old Card or old Deck at the destination;
  those identities and the undrawn source remain intact. The Card case waits
  for the timeout rather than falsely succeeding immediately.

The existing actual encounter reorder fixture additionally retains its
**27 passes on each Lua version** after this adapter change. Five independent
Python probes confirm `run.invalid_game` accepts a clean record and rejects
missing draws, table notes, Lua errors or engine errors individually. The
finishing validator calls that same validity predicate. No invalid record may
contribute to a reported rate; rerun affected seed cells rather than dropping
failed trials to retain a favorable sample.

Results, logs and exact source/test SHA256 values are recorded in
`encounter_draws_pass3_results.json`. Production adapter, runner and validator
bytes did not change during this verification. This follow-up adds one owned
test file and updates this review, with no production edits by the reviewer.

**Final scoped disposition:** the independently reviewed timing and draw
adapter corrections have no remaining blocker in these probes. The root's
fresh complete calibration and full repository checks govern release evidence.
The broader model-policy limitations and absence of human playtest approval
still apply.


## Final opening cost2 verification — current effective release data

**The owned RR timing fixture is rebased to the final opening cost of2 clues
per investigator.** Earlier87-check cost1 evidence is retained as historical
timing verification; this93-check snapshot governs the current opening rule.
The fixture reads the effective cost from current override JSON and uses it
for investigator starting clues, complete payment, test-window eligibility,
nested consequences, investigator attack batches and Upkeep consequences.
Its separate synthetic auxiliary ability explicitly retains a1-clue cost,
while its nested production opening objective uses the actual2-clue cost.

`tests/play_engine_objective_windows.lua` now passes **93 checks, zero failures
on each of Lua5.4 and5.2**. Both costs and printed plural wording are checked
against current release data. At counts1–4, the actual full costs are
**2,4,6,8 clues**, and a group exactly one clue short is rejected without
payment or other mutation. Existing legal-window, no-cost delivery, reaction,
complete investigate/Deduction/Milan, cancellation, terminal and phase-order
regressions all pass with their eligibility probes made sufficient for the
new cost.

An independent Python comparison uses production
`tools.play_engine.cards.load_cards()` to verify the effective merged card,
rather than relying on a calibration export. Its cost, per-investigator flag
and printed text agree with the current override. Relative to the baseline
opening card, only the intended1→2 payment and singular→plural clue wording
change; Hour eligibility, IX condition and back rules/flavor remain unchanged.
This reviewer did not change or rebuild campaign/card/guide production files.

Durable current standalone fixture: `objective_windows_rr_pass3.lua`. Latest
results, both logs, the effective-card comparison and exact source/data/test
SHA256 values are in `opening_cost2_pass3_results.json`. Source and data bytes
did not change during these checks. The source-rule hashes also match the
previous corrected timing snapshot; the draw adapter matches its later
independently verified repair.

**Current scoped signoff:** no new timing, affordability or printed-cost
blocker was found after this authorized final balance adjustment. The root's
40-trial paired figures motivate the design choice; this reviewer has not
independently reproduced those rates and grants no human balance approval or
statistical difficulty-target certification. The rejected contest proposal
does not enter this verification or require a finale rules change. Final
calibration must use the rebuilt package and fresh effective export with this
current card data.


## Final model endpoint and ending eligibility — current independent signoff

**The final narrow accounting change and two classification defects discovered
during its review are now independently verified.** This section supersedes
earlier classification observations; it does not certify human play balance.
The reviewed current source is pinned by SHA256 in
`finale_accounting_pass3_results.json`. No production source was edited by this
reviewer, and none of the scoped source/data bytes changed during the checks.

### Findings and dispositions

- **Finale participation:** the old classifier filtered only undefeated
  investigators, contradicting the player guide at622 and662. Current
  `finale.lua:130–131` captures active participant IDs when the finale begins.
  `finale.lua:235–240` uses that record even after later defeat. Someone
  already defeated before the finale is excluded; a repeated begin cannot
  replace the original participant record. **Fixed and regression covered.**
- **Pending Years:** the old classifier trusted the current stat bracket,
  omitting Years pending despite guide622. Current `finale.lua:247–252` uses
  recorded plus pending Years with the Ancient threshold15. Recorded Years
  take precedence over a stale bracket; bracket fallback applies only when
  the field is absent in legacy isolated fixtures. Classification neither
  ages the stat line nor consumes pending Years. **Fixed and regression covered.**
- **Unsimulated aftermath:** `engine.lua:435–447` guards ordinary Reset Loop,
  opening/closing interlude, aging and on-card banking behind non-finale.
  Finale output at452 explicitly says to resolve the ending and epilogue in
  the guide; `players.lua:56` declares both outside model scope. Every finale
  classification R1,1b,2,3,4,5,6 leaves the ordinary interlude unapplied.
  **Declared stopping boundary verified; no completed epilogue claim.**

### Permanent independent evidence

`tests/play_engine_final_independent.lua` now passes **206 checks, zero failures
on each of Lua5.4 and5.2**. This adds90 checks to its prior116; both complete
logs and exact source/test hashes are in `finale_accounting_pass3_results.json`.
The durable standalone copy is `wording_fix_pass3_final_tests.lua`.

The added eligibility probes call the actual production begin/resolution
functions and cover later defeat, exclusion of pre-finale defeat, repeated
begin, Years14+0 versus14+1 and10+4 versus10+5, cached-bracket disagreement,
pending Years acquired during the finale before defeat, and the legacy
no-recorded-Years fallback. The priority policy R3>R1b>R2>R1>R4 selects one
guide-eligible ending; the fixture checks it does not confuse the conditions.

The accounting probes capture the **actual private `engine.finish` closure**
from a zero-job engine bootstrap with test-only `debug.getlocal`. Every rules
module remains production code; only the table API is mocked. No copy of the
finish implementation is tested. The mock records calls and supplies state
changes and return values to detect unwanted reset/age/bank mutation. Across
all seven classifications, banked and on-card Memory, recorded and pending
Years and loop count stay at their measured endpoint; reported aging is empty,
reported on-card banking is0, and aftermath is explicitly unsimulated.

Victory is legitimately claimed **before** ending classification
(`engine.lua:403–417`, guide622). A separate probe starts one Memory below
the failed-contest bank threshold and confirms a cleared Victory1 location
raises the bank before choosing R5, without enabling any ordinary aftermath.
This is not a claim that every state field is immutable after the last action.

The ordinary-loop probe confirms Reset Loop→open interlude→Age each
investigator with the correct defeat flag→bank the actual API return→close.
All three Prologue outcomes retain their Memory reward, Unstuck recording,
reset and banking without ordinary reset aging. These are bounded API/order
checks; actual SCED Control behavior and game-rate evidence remain separately
validated by the root run.

### Interpretation limits

The guide's R5 retry ordinarily goes through Between Loops, while other
endings have individual consequences and epilogues. This model deliberately
stops before those consequences for every finale classification and labels
that boundary. Its returned campaign state is an endpoint snapshot, not a
fully resolved ending or playable retry state. The classifier chooses one
eligible resolution and does not enumerate all player choices. Signer-specific
R1 availability is not recorded by the current policy; when Keeper deep
Knowledge is present the policy selects valid R3. This limitation is within
the declared unmodeled ending-choice scope, and must not be presented as
complete ending/epilogue simulation.

**Final scoped signoff:** no remaining blocker in the reviewed accounting,
participation or pending-Year classification paths. Fresh release evidence
must pin this corrected source and must not mix earlier classification
snapshots or any missing-draw trials into current calibration. This review
does not replace the full repository suite, final calibration, or human
playtest approval.


## Seed replay consistency — brief read-only assessment

**A numeric seed does not currently guarantee a reproducible complete game
across fresh Lua processes.** `engine.lua:238–239` seeds the emulator PRNG and
`math.random`, but the current policy uses unspecified table enumeration for
legal tie choices: `ai.lua:194–200` keeps the first equal-score adjacent move;
`rules.lua:458–464` keeps the first BFS predecessor for an equal-length path;
`ai.lua:401–406` similarly resolves equal-safety improvements by encounter
order. The official Lua5.2 and5.4 reference manuals document `next` ordering
as unspecified, with `pairs` using `next`; `math.randomseed` controls the
pseudorandom number sequence rather than table enumeration. Primary references:
https://www.lua.org/manual/5.2/manual.html#pdf-next
https://www.lua.org/manual/5.2/manual.html#pdf-pairs
https://www.lua.org/manual/5.2/manual.html#pdf-math.randomseed
https://www.lua.org/manual/5.4/manual.html#pdf-next
https://www.lua.org/manual/5.4/manual.html#pdf-pairs
https://www.lua.org/manual/5.4/manual.html#pdf-math.randomseed

The standalone `.cache/finish_review/seed_tie_policy_pass3.lua` probe calls
actual production `AI.chooseMove` and `R.route` on an identical legal diamond
graph with the same numeric seed. **12 fresh processes for each Lua version
produce two different default move/path outcomes**, despite identical first
two `math.random` values within each runtime. A controlled `__pairs` probe
then reverses only the two equal neighbors and selects the corresponding
other legal move and predecessor, still at distance2. Exact outputs and
source hashes are saved in `seed_tie_policy_pass3_results.json`; source did
not change. This is actual bounded order dependence, not a copied algorithm.

Different legal tie decisions may alter travel, crossings, subsequent actions
and the number and order of RNG draws. No illegality appears in these probes.
This demonstrates a genuine replay limitation but **does not trace the root's
full-game rate differences to a particular decision**. Treat same numeric
seeds as matched seed labels, not guaranteed identical draws or fully coupled
paired trials. Disclose tie-policy/replay variability when comparing sampled
rates; do not infer the effect of a classification-only patch from unrelated
non-finale rate differences. No model source modification is made or demanded
while final validation runs. The permanent final regression count remains
**206 passing checks on each Lua version**.
