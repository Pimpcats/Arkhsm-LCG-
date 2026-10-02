# Finishing corrections — designer only

This document contains campaign spoilers. It records the corrections authorized
by the owner on 2026-10-02, following the full-repository finishing review of
`2cbd921`. A model result is evidence about that model, not human table approval.

| Finding | Required correction | Status |
|---|---|---|
| Narrative continuity | Accommodate residents in the opening; distinguish surface from deep discoveries; remove assumed optional discoveries from mandatory passages; neutralize unvisited/repeated district resolutions; avoid duplicate Named passages | Implemented; independent narrative review passes |
| Prologue Years | Discard pending Years at the Prologue handoff, where Age is skipped | Implemented; regression and independent review pass |
| Farthest placement | Use all legal transit locations but only eligible revealed destinations; expose distance ties to the lead investigator | Implemented; regression and independent review pass |
| Static cancellation | Defer irreversible consequences until the token actually resolves; previews, returns, cancellation and duplicate callbacks must not advance the campaign | Implemented; regression and independent review pass |
| Fare cost | Place full payment before the advance effect; Parley must not provoke in the engine | Implemented; printed cost, full payment, source restriction and no-AoO checks pass |
| Timed carry objective | Arrival alone must not resolve an objective that waits for an Hourglass advance | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Damage redirection | Preserve ordinary assignment and enemy context; count owned-asset damage for the solo reaction | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Birdie defeat prevention | Heal only necessary damage/horror; end her current turn; preserve Memory source restrictions | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Weakness scope | Block incoming card effects and commits; allow the affected investigator's outgoing commits | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Skill cards | Correct commit timing, aging icons, paid success draw, helper costs and maximum copies | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Memory sources | Track investigator and asset tokens separately; discard asset tokens when the asset leaves play | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Multi-Hour cancellation | Cancel the complete advance, not just one increment | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Purchased cards and signatures | Implement missing campaign-card abilities and document AI policy separately from rules coverage | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Campaign coverage | Add missing nights, all five investigators, 1–4 player coverage and carried progression | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Difficulty evidence | Measure all ten requested played slots, including uncertainty; retune supported misses and retain nonlinear campaign structure | Measured: 70 cells / 1,319 slots; four supported costs adjusted. Exact curve and human calibration remain open |
| Economy audit | Load effective overrides; distinguish income from the carry cap; verify full-level upgrade prices and campaign earnings | Implemented; independent checks pass on Lua 5.2 and 5.4 |
| Current documentation | Mark superseded design numbers historical; refresh production status, counts and verification evidence | Updated; historical data qualified and current evidence archived |
| Release | Three independent wording passes, rendered cards/guide, Lua versions, SCED harness, Godot and pinned hosted package | Offline checks pass; 3 independent reviewers, current test suite, 200 images / 24-page guide and 3 Godot renders. Live TTS/human playtest remains open |

## Findings requiring no change

- The Prologue is already excluded from the Appointed's advance hook. The
  suspected Prologue spawn defect did not reproduce against the actual Control.
- References to a century of nights are thematic prose, not a numeric rule.
- Encounter assignment lists contain physical copies. Multiplying them again by
  the master card quantity would fabricate encounter cards and invalid metrics.
- The campaign's branching districts are not ten mandatory linear boxes. The
  owner's targets apply to played order: opening, eight nights, finale.

## Verification

Current evidence: **111 pytest tests and 155 subtests passed**, with one opt-in
render test skipped; three actual Godot scenes supplement it. Both Lua versions
pass 309 live rules checks, seven model fixtures totaling 652 checks, and the
rebuilt bundle checks. CardForge passes 20 checks. All eight boxes are locked
with zero readiness errors or warnings. The guide has 24 rendered pages and all
200 hosted images plus the guide match the immutable GitHub asset tree.

[FINISHING_BALANCE.md](FINISHING_BALANCE.md) records 70 complete cells and
1,319 played slots with zero engine/Lua/table-note/missing-draw failures, plus
400 scoped proposal trials. Exact inputs and raw trials are archived in
[verification/2026-10-02](verification/2026-10-02/README.txt). The curve remains
open: Night 1 is 71% versus 80%, Night 2 is 82% versus 70%, and the conditional
finale is 50% versus 40%. These model residuals are not human approval.
Historical early-paid-advance or missed-encounter runs are withdrawn.

## Additional faults found while verifying the fixes

- Standard opening mulligans were absent. Rejected cards and opening weaknesses
  are now set aside until replacement draws, then shuffled back; identity and
  counted deck size are conserved.
- Permanent purchases wrongly replaced counted deck cards. All five
  investigators now have 30 counted cards in each base and budget tier.
  Indebted remains outside the deck and applies its starting resource penalty.
- Two-hand and two-arcane assets used one slot. Installing an asset now makes
  sufficient space and resolves leaving assets normally.
- Upgraded printed cards were incompletely encoded. Corrected Deduction,
  Vicious Blow, Fearless, Opportunist, Lucky!, .41 Derringer, Beat Cop,
  Shrivelling, Peter Sylvestre, Encyclopedia, talents and Blinding Light;
  shared skill-card limits also apply across helpers. The final independent
  review compares these effects with publisher card images.
- Encounter preview and reorder effects changed only logical order. They now
  replace the actual SCED deck order and preserve card identity and image data.
- Final primary-source review found that the preliminary model spent clues
  outside a legal player window after a doom advance and during clue discovery.
  The earlier timing signoff and preliminary balance measurements are withdrawn.
  Optional payments now use the Rules Reference's actual player windows,
  including both pre-reveal skill-test windows inside encounters. Mandatory
  delivery and explicit after-evade/after-advance reactions retain their printed
  timing. Final evidence is rerun against this corrected implementation.
- The model incorrectly applied an ordinary reset/interlude after a finale.
  Finale trials now stop at the measured contest/eligible ending. Their
  epilogue and choice payments remain guide procedures, explicitly outside
  the model, and are not replaced with ordinary loop aging or banking.
  Eligibility now retains investigators who participated and were later
  defeated, and includes their recorded plus pending Years. Ninety independent
  follow-up checks cover classification and accounting across every finale
  outcome, ordinary interludes and all opening outcomes.
- SCED can stack a drawn encounter card into an existing pile at the draw
  spot. The model searched only single cards and could miss a draw or reuse
  an old weakness. It now distinguishes destination GUIDs, extracts only the
  newly drawn card from a Deck, and handles a moved last single card. Release
  measurement refuses any trial with a missing encounter draw.
- Re-importing the superseded content feed could erase current corrections.
  Import now refuses that historical feed before making any mutation.
- Paired what-if runs could overwrite configuration files. Filenames now
  include a configuration digest; proposals use cardOverrides for printed
  costs. Evidence records input hashes and rejects changed inputs, incomplete
  trials and rules or SCED errors.

## Measurement limits identified at handoff

Seeds control the PRNG inputs but do not fix equal legal choices made in Lua
table traversal order. The independent reviewer reproduced different legal
move/BFS path choices with identical PRNG values in both Lua versions. Proposal
screens retain the same seed families, but are not guaranteed identical paired
draws or controlled causal comparisons. Raw trials, exact input hashes and the
tie-policy probe are preserved. This is not a rules-legality defect; it limits
the precision and replay claims of the balance model. The Lua
[5.2](https://www.lua.org/manual/5.2/manual.html#pdf-next) and
[5.4](https://www.lua.org/manual/5.4/manual.html#pdf-next) manuals describe
unspecified traversal order.

Independent reviews: [live rules](review/2026-10-02_live_rules.md),
[narrative](review/2026-10-02_narrative.md),
[engine](review/2026-10-02_engine_rules.md), and
[final engine follow-up](review/2026-10-02_final_engine_rules.md).
Reports remain scoped to the source they reviewed. Durable Lua fixtures execute
current source; results are in `verification/2026-10-02/rules-checks.txt`.
Declared simulation policies and approximations remain in `P.APPROX`; a card
being implemented does not mean the AI selects every legal use.
