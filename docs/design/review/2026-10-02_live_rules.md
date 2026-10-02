# The Still Hour — independent post-fix verification, pass 1

**SPOILERS: designer/assistant only. Do not include these details in owner chat.**

Reviewed the current working tree over main `2cbd921`, 2026-10-02. Read `docs/design/FINISHING_CORRECTIONS.md` and followed the existing AGENTS/assistant-workflow spoiler requirements. This review covers live source Control, deferred Static resolution, Prologue pending Years, farthest placement, tie handling and corresponding player-guide rules. The parent is implementing other findings concurrently. No authored/runtime or tracked files were modified by this reviewer.

**Disposition: scoped live-source fixes VERIFIED.** Original defects, simultaneous-token cancellation and pending physical-token button restoration all pass the independent checks. The final player guide and integration instructions describe the token-specific procedure. This is source verification, not a built-package or real TTS/Godot playtest.

## Independent evidence

Adapted the original baseline into `.cache/finish_review/wording_fix_pass1_repro.lua`, whose assertions now expect correct behavior. It creates isolated module environments, loads the current `src/tts/control.lua`, calls its actual universal event handlers, GUI callbacks, runner API and save/load functions, and calls the actual Board destination/tie procedure with in-memory card objects. It does not use the older committed bundle. TTS objects and JSON serialization are minimal stubs; no real SCED object scripting or asynchronous game host was exercised.

Commands run from the repository root:

```text
.cache/finish_review/deps/usr/bin/lua5.4 .cache/finish_review/wording_fix_pass1_repro.lua
.cache/finish_review/deps/usr/bin/lua5.2 .cache/finish_review/wording_fix_pass1_repro.lua
.cache/finish_review/deps/usr/bin/lua5.4 pipeline/lua_smoketest.lua
```

Results:

| Evidence | Result | File |
|---|---|---|
| Expanded independent live-source fixture, Lua 5.4 | 38 passed, 0 failed | `wording_fix_pass1_repro.log` |
| Same expanded independent fixture, Lua 5.2 | 38 passed, 0 failed | `wording_fix_pass1_lua52.log` |
| Existing current module smoketest | 309 passed, 0 failed | `wording_fix_pass1_smoke.log` |

The initial simultaneous-cancellation failure and the three checks of the subsequent restoration gap now pass. The existing smoketest covers the new transit/candidate distinction but does not cover these physical token callbacks/restoration cases. The reviewer fixture deterministically flushes frame/time callbacks; it checks their outcomes, not real asynchronous object-spawn timing.

## Dispositions

### Prologue pending Years — VERIFIED

`src/StillHour/CampaignState.ttslua:518–520` clears all pending Years in the Prologue branch, while the ordinary loop reset preserves them for Age. Tested all five investigator IDs with different pending amounts through actual Control APIs. Prologue reset leaves Years and pending Years at zero; its Age stays disabled. After Begin Next Loop, the first real Age gains only the base Year. A Year awarded in a later real loop survives reset, is applied once by Age, and is cleared; a duplicate Age has no effect.

Guide `docs/design/THE_STILL_HOUR_player_guide.md:221` now explicitly says the Year encounter gives no Year in the Prologue, and its interlude Age step says Reset Loop discards Prologue pending Years. The card's ordinary real-loop behavior remains intact. This resolves baseline F1 without silently erasing real-loop awards.

### Farthest placement and lead-investigator ties — VERIFIED

`src/StillHour/Board.ttslua:653–661` computes distances on `movableLocations()` and filters only destinations to `eligibleLocations()`. `src/StillHour/Locations.ttslua:214–237` accepts candidates separately and returns the complete maximum-distance tie list. The original fixture now places at the distant revealed endpoint through unrevealed transit locations, rather than at the adjacent hub.

Also checked the minimum distance to any investigator, an exact graph tie, both destination names in the tie announcement, the lead-investigator/default-placement instruction, and retention of a player's manually selected destination through `Board.onDrop()`/board state. Physical straight-line spread no longer decides graph ties.

The guide's Appointed definition and Control instructions agree: lead investigator chooses among tied eligible destinations; the automatic placement is an overridable default. The manual drop is remembered by the existing `src/StillHour/Board.ttslua:814–818` handler. This resolves baseline F2 and its tie-choice caveat. It does not establish every manual dynamic location restriction or real SCED map arrangement, which were outside this fixture.

### Deferred Static: previews, single cancellations, ordinary resolution, callbacks and persistence — VERIFIED

`src/StillHour/ChaosBag.ttslua:268–301` queues token GUIDs and clears a returned token's pending reveal. Current `src/tts/control.lua` universal extraction handler merely records/announces a pending draw; `shApiResolveStatic` (`:829–845` at verification) explicitly consumes and commits/discards it. Tested:

- extraction at a band boundary leaves Dissonance and Approach unchanged;
- duplicate extraction queues once;
- GUID-identified cancellation and its duplicate leave campaign state unchanged;
- outside-test preview returned to the bag is inert;
- resolution applies the band/Approach change once, and duplicate commit is inert;
- a resolved token cannot requeue until it has returned and is drawn anew;
- extraction/cancellation at the reset boundary does not announce a reset; a genuine resolution does;
- pending draws survive save/load without applying effects, then resolve exactly once;
- Prologue reset clears pending Static draws;
- two simultaneous draws remain independent when cancellation identifies the correct GUID.

Guide `:146` replaces the former Dissonance undo workaround with explicit resolution after cancellation choices and inert preview/cancellation handling. Its sealed-token later-resolution instruction remains separate. This resolves the original single-token false band-entry defect (baseline F3).

### Anonymous GUI cancellation with multiple pending Static tokens — CORRECTED AND VERIFIED

The first post-fix revision had one anonymous “Static waiting” resolve/cancel button, which consumed the lexicographically first pending GUID. This differed from the physical token the player might be canceling or previewing.

**Historical failing sequence, now a passing regression:**

1. At Dissonance 7/Approach 0, draw Static A (`aaa111`) and Static B (`bbb222`). Both are pending.
2. The player cancels B using the guide's right-click alternative. The generic button instead discards A's pending entry.
3. Return canceled B to the bag. The return callback also discards B's pending entry.
4. Resolve surviving A with a left click before continuing its test. No pending entry remains, so it returns false and applies no effect.

Before the follow-up fix, final state was Dissonance 7/Approach 0 rather than 8/1. Current Control refuses both anonymous cancellation and anonymous resolution when more than one token is waiting, preserving the queue. After physically returning the canceled B, resolving the single remaining A gives the correct 8/1 state. This now passes in Lua 5.2 and 5.4.

Current Control also puts a GUID-specific Resolve/cancel button on each physical token. The actual token callbacks now verify that B's cancellation clears only B and preserves A, that B's return leaves A intact, that A resolves once, and that duplicate extraction does not duplicate buttons. The announcement, guide and final generic Control tooltip (`src/tts/control.lua:721–723`) describe these token-specific controls and the single-pending-token limit; that last tooltip correction was inspected after the passing fixtures and changes text only.

### Pending token buttons after save/load — CORRECTED AND VERIFIED

The queue round-trips correctly, and current `refreshControl()` (`src/tts/control.lua:806–820` at verification) recreates the GUID-specific buttons on every pending physical token, clearing prior buttons first. A fixture loads two pending draws into a fresh runtime with the token objects present and checks button recreation, repeated restoration without duplicates, and cancellation/resolution through the restored callbacks. All three checks pass in Lua 5.2 and 5.4. The saved GUIDs are attached to the current host's callback, so anonymous queue ordering no longer determines the canceled token.

### Guide and current card consistency — VERIFIED within scope

The current player guide consistently states deferred Static resolution, a no-Years Prologue, discarded pending Prologue counters, and graph-distance ties chosen by the lead investigator. The fare now appears before the cost/effect colon at `campaigns/still_hour/card_overrides.json:969`, preserving its amount and conversion rates. Broader authored narrative, investigator effects, engine balance and all original audit findings have other verification owners; they are not certified by this limited Control pass.

The parent has updated `docs/INTEGRATION.md` to distinguish pending extraction from committed resolution, including duplicate/cancel handling and the multiple-token identity requirement. `Dissonance.onStaticRevealed()` remains the low-level symbol-effect implementation; its name no longer causes the integration instructions to imply automatic commit on physical extraction. Current player-guide Dissonance instructions explicitly identify the physical Resolve buttons, the anonymous single-token fallback and ambiguous-call refusal, and agree with runtime behavior.

## Release limits and next verification

No current functional blocker remains within this pass's scope. The existing report retains the failing sequence as history and a passing regression, to preserve why physical token identity matters. Source changes to the scoped files after these checks require a targeted recheck; unrelated balancing edits are owned by the parent and other independent reviewers.

The run reviewed live source against the working tree. Existing rendered faces, PDF guide, hosted assets and committed Control bundles are not automatically current. This report does not substitute for the required rebuild, rendered inspection, SCED harness, Godot run, campaign-coverage audit or statistical calibration.


## Addendum — final measured clue-cost edits, 2026-10-02

**Disposition: VERIFIED within the requested wording/feasibility scope; no remaining blocker.** Re-exported the current effective cards into `wording_final_balance_context.json` and independently loaded the compiler/print layers with `scenario_content.load('still_hour')`. Only reviewer cache files were written.

- **Why Thirteen?**: metadata and its printed acquisition payment both require **3 clues per investigator** (`campaigns/still_hour/card_overrides.json:876–877,883`). Only the activator must be at the Vestry; the explicitly unrestricted group may contribute from anywhere. Delivery still waits for the completed Hourglass advance, and the reverse still removes the correct asset and applies the recorded surface fact (`:882,884–888`).
- **The Hour Was Wrong**: metadata and printed acquisition payment both require **3 clues per investigator** (`:892–893,899`). Here the contributing group is explicitly restricted to investigators at the Crypt. Its opening/spawn, delivery destination and reverse remain coherent (`:893,898,900–903`).
- **Who Walks Beside You**: metadata is **4 per investigator**, and **both** printed payment routes require **4 per investigator** (`:918,924–926`). Stand Firm requires a ready Echo and returns all spent clues to the Turning on failure; the alternative is the reaction to the successful evade. The reverse's recorded fact and lasting fight adjustment remain unchanged (`:923`).

The wording follows the publisher's Rules Reference: payment precedes the effect colon; a defined group may share the cost; prerequisites/full payment apply before initiation; discovered clues belong to investigators and are portable. The action and reaction retain their distinct trigger windows. See printed pages 3, 6, 7 and 22 of the [official Rules Reference](https://cdn.svc.asmodee.net/production-fantasyflightgames/uploads/2026/09/ahc60_rules_reference_eng-compressed.pdf). The renderer prints a dash for take-and-deliver and `no_threshold` acts (`pipeline/render_placeholders.py:2330–2338`), so these amounts do not become an independent generic act-advance route.

Clue-supply feasibility, using district clues alone and counting the two Church payments sequentially:

| Investigators | Church before Crypt opens | Church total after opening | Surface payment | Remaining for deep payment | Deep payment | Road total / deep payment |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 6 | 3 | 3 | 3 | 4 / 4 |
| 2 | 8 | 12 | 6 | 6 | 6 | 8 / 8 |
| 3 | 12 | 18 | 9 | 9 | 9 | 12 / 12 |
| 4 | 16 | 24 | 12 | 12 | 12 | 16 / 16 |

Source values are Nave 2, Belfry 1, Vestry 1 and Crypt 2 per investigator (`card_overrides.json:376–377,407–409,428–430,448–450`); Road 1, 1, 2 (`:480–481,503–504,527–528`). Road's surface objective discovers rather than spends clues, including the solo 2/1/1 clause (`:908`), so its entire local supply remains available for the deep payment. Contributors must bring their carried clues to the restricted location. These exact local totals leave no buffer for spending/loss elsewhere; the always-present Square provides additional portable supply. This establishes arithmetic feasibility, not a promise of success within the clock or a balance verdict on the paired trials.

The guide defers objective payments to the act fronts and correctly governs opening/Part II setup (`docs/design/THE_STILL_HOUR_player_guide.md:139–141,345–352,419,462`). The current audit's three amounts agree (`docs/design/CURRENT_CAMPAIGN_AUDIT.md:45–48`). Church manifest payments read effective card metadata rather than stale numbers (`scenario_manifest.json:850–881`).

**Additional readiness gap found and corrected during this check:** the Road deep manifest originally described only its test, so an impossible counterfactual cost of 400 still passed the objective checker. The parent added `needs.clues = "card"`, its three portable district sources and current Stand Firm terminology (`scenario_manifest.json:1045–1052`). Rechecked: the actual costs pass for 1–4 investigators, while the 400-per-investigator counterfactual now fails at all four counts. This was a coverage gap, not an actual cost infeasibility.

Independent evidence: **26/26** cache assertions pass (`wording_final_balance_checks.json`, with input SHA-256 hashes); the read-only full scenario audit reports **all eight boxes, zero errors and zero notes**. Existing source/host/render/package limits above remain applicable. Historical feed/design amounts are superseded, and the feed's import refusal prevents reintroducing them. No authored mechanics beyond the parent's requested cost edits were changed by this reviewer.


## Addendum — opening cost, 2026-10-02

**Scoped signoff: VERIFIED; no authored wording or feasibility blocker.** The effective Prologue act now has metadata/clue circle **2 per investigator**, and its plural printed group payment is also **2 per investigator** (`campaigns/still_hour/card_overrides.json:832–833,839`). The ordinary Objective adds the location and Hour VIII conditions to that single payment; it does not charge twice. Its reverse still directs **R1** (`:838`), and the front still sends an earlier Hour IX ending to R2. The guide's setup, ending conditions and R1 condition/reward remain consistent (`docs/design/THE_STILL_HOUR_player_guide.md:211–229`). The manifest reads the effective card threshold, lists all three portable clue sources and uses advancement as R1's condition (`scenario_manifest.json:582–591,628–632`). The current audit records the new 2-per-investigator cost (`docs/design/CURRENT_CAMPAIGN_AUDIT.md:43`).

| Investigators | All Prologue clues | Almanac Steps clues | Payment | Total surplus |
|---|---:|---:|---:|---:|
| 1 | 4 | 2 | 2 | 2 |
| 2 | 8 | 4 | 4 | 4 |
| 3 | 12 | 6 | 6 | 6 |
| 4 | 16 | 8 | 8 | 8 |

All location clues scale per investigator (`card_overrides.json:186–189,207–208,226–228`). The payment location alone has the required supply; previously discovered clues may also be brought there. Only investigators at that location contribute. This is source/arithmetic feasibility, not certification of the reported win-rate target.

Independent evidence: **19/19** effective-card/manifest/supply checks pass (`wording_prologue_cost_checks.json`, with input hashes). All 1–4 objective audits pass, and all eight full scenario audits still report zero errors/notes. A counterfactual 5-per-investigator opening cost correctly fails at all four counts. The three earlier changes remain **3/3/4**.

A minimal cache fixture, `wording_prologue_cost.lua`, loads the current production effects factory and effective override data: **24/24 checks pass on each of Lua 5.2 and 5.4**. `FX.actNeed` reads the printed metadata; `FX.canAdvance` rejects pre-Hour-VIII, one-clue-short, remote-contributor and closed-location cases, and accepts the full co-located 2n payment (`tools/play_engine/lua/effects.lua:382–384,422–428,513,528–535`). This probe does not replace the broader legal-window timing fixture. I reported its former 1-clue assumptions in `tests/play_engine_objective_windows.lua` to the parent for rebasing; rendered fronts, hosted assets and package repinning remain the parent's release checks. This reviewer changed only cache files.
