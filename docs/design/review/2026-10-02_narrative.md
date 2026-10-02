# The Still Hour — independent post-fix wording verification, pass 2

**SPOILERS — designer/assistant only.**

Reviewed the working corrections above `main` baseline `2cbd921`, on 2026-10-02. Read `docs/design/FINISHING_CORRECTIONS.md`; current authority remains the player guide and `pipeline.scenario_content.load('still_hour')` with printed override precedence. This reviewer changed no authored or runtime files. The report and in-memory verification fixture are scratch evidence only.

## Result and evidence

The originally reported narrative corrections are applied coherently. The mandatory introduction now accommodates residents and the mandatory discovery list follows the actual finale prerequisites. The Almanac surface discovery now withholds the true-hour evidence instead of contradicting its act back. Repeat district passages no longer assert the flagged unsupported visits or a permanently closed Study, and duplicate Named passage instructions are explicit. No new progression blocker or invalid ending condition was found.

The two additional nonlinear-story concerns found during verification have also been corrected and independently re-read. No unresolved narrative blocker or minor remains in this pass's reviewed scope.

Executed evidence:

- `python pipeline/scenario_content.py`: **8/8 LOCKED, zero errors and zero notes**. No locking/mutation flag used.
- Reloaded effective content: **133 cards** (5 investigators, 13 assets, 3 skills, 26 treacheries, 9 events, 17 enemies, 23 locations, 14 acts, 12 stories, 9 agendas, one reference, one campaign log).
- All **14 act fronts and backs** contain rules and prose. All **9 agenda fronts** and **9 agenda prose backs** are present; Hours I–VIII contain an advance-back rule. Hour IX has no advance-back rule or doom threshold because it ends play on being reached. This is an intentional final-agenda exception, not a missing ninth transition.
- Guide contains **38 resolution fences**: Prologue 3, general loop 4, six districts × 4, finale 7. The first-applicable district ordering covers completion, partial progress, repeat play, and no progress; choices are made once and pending deep choices are read before a same-loop finale.
- `.cache/finish_review/wording_fix_pass2_check.lua`: **34 checks pass on Lua 5.4 and 34 on Lua 5.2**, against current source modules and in-memory fixtures. Covers Static preview/cancel at Dissonance 7, 15, and 23; duplicated extraction and consumption; one genuine resolution; Prologue pending-Year discard; farthest revealed destination through unrevealed transit; closed-connector exclusion; genuine distance ties; and the actual Board manifestation callback.
- `git diff --check`: clean at the point reviewed. Changes by the other implementers remain in progress; this report does not claim a final rendered package or complete simulation suite.

## Every prior finding: disposition

| Prior ID / concern | Disposition | Evidence |
|---|---|---|
| N01, obsolete full-Hour crossing summary | Fixed and verified | Guide first-loop summary now charges one doom for the first crossing along each district connection per round and identifies the Road/Lighthouse exception; exact travel rule preserved. |
| N02, surface pages printing a known true hour while denying its discovery | Fixed and verified, including alternate-route sentence | Guide resolution renamed **The Altered Hour**, blank line matches effective Almanac act back, and `scenario_manifest.json` mirrors the rename. See P2-N07 below. |
| N03, newcomer-only Prologue excludes Elias | Fixed and verified | Guide uses “You are in Ambergrove”; effective Long Pier flavor and the matching feed entry also use resident-compatible phrasing. Signature/investigator lore preserved. |
| N04, mandatory finale assumes optional discoveries | Fixed and verified | Mandatory discovery list is ledger/sky/name, all required by the actual unlock route. Newly flagged optional Lighthouse imagery in the following paragraph now uses Town Hall steps. |
| N05, repeat/placed-only passages claim unsupported visits or closed Study | Flagged passages fixed and verified | Lighthouse repeat/failure, Road repeat, Fairground repeat, and Almanac repeat now narrate the district state without the reported action/door-state assertions. Eligibility remains unchanged. |
| N06, Named add-on double-read ambiguity | Fixed and verified | General district instruction says read once, respecting local “instead of the story” instructions. Local shorter repeat variants are preserved. |
| R01, Static previews/cancellation retaining Approach/wake/reset effects | Fixed and source/module verified | ChaosBag queues pending extraction; Control resolves only explicit confirmed tokens and consumes cancellation/preview without Dissonance. Guide describes `Static waiting`, with no obsolete blanket −1 undo. Module tests pass at all three boundaries and for duplicate callbacks. Full Control/SCED release regressions remain the root verification responsibility. |
| R02, farthest manifestation omits unrevealed transit | Fixed and source/module verified | Board computes graph/occupation on all movable locations and filters candidate destinations separately. Actual callback fixture picks Lantern at distance 5; closed connector and tie list checks pass. Control announces tied names and guide leaves the final choice to the lead investigator. |
| Investigator stat/weakness asymmetry | Preserve design; calibration pending | No unsupported numerical roster rewrite. Root's all-five-investigator/party sensitivity and carried-state work must substantiate balance before approval. |
| Compass jump's specific Memory source | Preserve card rule; model implementation pending other pass | Source restriction is still on the effective card and no generic transfer rule was invented. Root/engine reviewer is verifying separate investigator/asset counters. |
| Missing card ability/model coverage | Under active implementation, not signed off here | Authored card wording still matches established concepts. Engine files are being corrected separately. This report does not turn source coverage into a playtest claim. |
| Nobody Believes Her allowing incoming Elias redirect | Implemented guard verified by source; full engine regression pending other pass | `R.hurt` now checks `not inv.round.nobodyBelieves` before redirect; other incoming effects and outgoing commits are part of the engine review. |
| Basic weakness retained across a campaign | Pending root campaign-runner verification | Existing per-game ensemble docs alone do not establish one campaign's retained weakness. Do not claim a complete carried campaign result until the new runner verifies this. |
| Century-of-nights prose | Recorded no change | `FINISHING_CORRECTIONS.md` explicitly records it as thematic prose, not a numeric rule. No invented conversion of loop count to a century. |
| Seraphine ambiguity / superseded historical numbers | Recorded no change | Current guide/cards govern. Original conjectures and obsolete one-doom, 4×n contest, old-cap/old-band numbers are not silently promoted to current rules. |

## Effective card, manifest, and feed consistency

### Fare cost

Effective `sthr-act-bargain.text` puts the full party fare before the colon and advancement, specifies investigators at Ticket Booth, allows clues/Memory from their own cards/resources at 3:1, scales **5 per investigator**, and restricts the acting investigator to the same location. At 1/2/3/4 players, the required fare is 5/10/15/20 units. The back records its deep entry and completes the Fairground deck; there is no altered reward or new purchase mechanic. `no_threshold` suppresses a misleading ordinary clue-advance interpretation. The manifest points to this effective card and `needs.clues = "card"`, with the correct location and source model. Actual Parley/AOO and affordability behavior is under the independent engine pass.

### Other acts and agendas

Read both effective faces, including the carry objectives, Belfry advance-timed objective, Knowledge changes, Part II gates, Study opening/name unlock, contest sources/threshold/end conditions, and each Hour's transition to the next. The effective current doom schedule remains 3 for Hour I, 2 for Hours II–VIII, and no threshold for Hour IX. The surface/deep act transitions, Knowledge reward rules, and finale choice menu agree with the current guide. No current back directs players to a deleted district or obsolete finale outcome.

### Feed status

`scenario_content_feed.json` begins with an explicit **SUPERSEDED / do not re-apply** note. It deliberately retains historical acts, former one-doom Hours, and the earlier contest/unlock rules; runtime loading and ordinary rendering/compilation use the current override layer, not this archive. The newly synchronized Long Pier line matches its effective current flavor, but that isolated correction does not make the old feed an authoritative release feed.

Therefore the historical feed is **not byte-for-byte current**, by design, and must not be cited as current balance/rules evidence. `pipeline/scenario_content.py --apply-feed` remains a potentially destructive historical reimport; do not invoke it during release. Root may add an explicit guard or regenerate a current feed, but this review does not apply the obsolete feed or report its obsolete values as new play defects.

## New localized findings sent promptly to root

### P2-N07 — legal prior Church discovery denied by the Almanac surface ending

The Almanac Resolution 2 paragraph previously ended “You do not yet know what it was before.” The Church's deep objective has no prerequisite requiring Almanac surface first, so players may already know the true hour when completing this act. A nonlinear route can legally play Church first, then this discovery.

**Fixed and independently re-read:** the paragraph now ends “The changed proof cannot tell you what was there before.” This describes the document's limit instead of denying an already-recorded party fact. No extra branch flag or imposed district order was added. Verified after root's authored update; no further correction needed.

### P2-N08 — mandatory aging/finale imagery assumes optional locations

Weathered originally placed the investigator at Hall of Mirrors; Elder claimed repeated Lighthouse climbs, and a following mandatory finale paragraph did the same. Reported immediately. **Already fixed and re-read:** Weathered uses a darkened shopfront; Elder and the finale use Town Hall steps. No further change required.

## Scope of approval

This is an independent authored-content and specific integration verification. It does not establish final render fit, all engine ability/weakness rules, all purchased-card policy coverage, full ten-slot difficulty calibration, human playtest approval, or actual desktop TTS execution. Pending work is recorded in the root finishing document and the other independent passes.

## 2026-10-02 — final balance wording addendum

Independently reloaded current effective content with `pipeline.scenario_content.load('still_hour')` and re-read both faces of the three final retuned acts against the current player guide and manifest. This is a source-content check while the root rebuilds the final artwork and package.

| Effective act | Final clue cost per investigator | Printed paths and continuity |
|---|---:|---|
| `sthr-act-whythirteen` / Why Thirteen? | 3 | Metadata and purchase action agree; the Vestry-to-Belfry carry and subsequent Hourglass-advance objective remain intact. |
| `sthr-act-hourwaswrong` / The Hour Was Wrong | 3 | Metadata and Crypt payment agree; Part II, opening/spawn, Crypt-to-Vestry carry and back consequences remain intact. |
| `sthr-act-walksbeside` / Who Walks Beside You | 4 | Metadata, Stand Firm action and post-evade reaction agree; failed Stand Firm returns exactly the clues spent. |

For each act, `back_text`, front flavor and back flavor are byte-for-byte unchanged from the reviewed baseline. The new numbers produce no grammar error or contradiction between either face and the guide's corresponding discovery, repeat/failure passage, choice or finale consequence. The guide has no hardcoded competing cost for these acts. The Church manifest already derives both costs from the card and retains the correct take/deliver locations. Clues remain portable: the new Church surface/deep total is 6 per investigator, matching its four locations' total; the Road has 4 per investigator on its three locations, and its surface objective discovers rather than spends clues. The always-present Square remains an additional source. No identity, Knowledge entry, XP award, prerequisite or finale-unlock route changed. Optional district order, repeated loops and multiple endings remain available.

Two localized, pre-existing manifest descriptions were reported promptly to the root for correction. They are not introduced by the three numeric edits:

- `scenario_manifest.json:1046` described the road deep test as “evade or Hold an awakened Echo.” Its authoritative effective card calls the test **Stand Firm**, requires a **ready** Echo, and also permits the paid post-evade reaction. Use those terms; `needs.clues = "card"` may explicitly describe the card-driven cost.
- `scenario_manifest.json:1608` said the finale contest was `4 x investigators`, contradicting that same manifest's structured current thresholds and the player guide. Replace the obsolete setup-note number with a reference to the effective act's threshold, or the current party-size thresholds.

These are metadata consistency findings, not proposed rule or story changes. Their final disposition will be appended after the root updates the manifest.

Fresh verification: all eight scenarios are `LOCKED`, with zero readiness errors or notes; `git diff --check` is clean. The previously noted historical-feed import risk is now corrected by the explicit superseded-feed guard at `pipeline/scenario_content.py:665–668`, before mutation; the feed itself remains deliberately historical. No new narrative or grammatical blocker was found in the retuned cards or guide. This addendum does not claim final rendered fit, human playtest approval or engine/balance verification beyond this stated scope.

### 2026-10-02 — manifest findings closed

Independently re-read the root's final manifest corrections. Both localized findings are **fixed and verified**:

- The Road deep act now declares `needs.clues = "card"`, lists The Milestones, The Low Bridge and The Turning as clue sources, and describes the effective Stand Firm/evade alternatives using the ready-Echo terminology. Its card-driven cost, act identity and location agree with the effective override. The effective card continues to govern the exact trigger and test requirements.
- The finale setup note now refers to the effective Contest the Crossing threshold and gives 5 solo, 6 with two or three investigators, and 7 with four. Those values agree with the same manifest's structured contest fields and the current guide.

No authored story or guide change was needed. Re-ran readiness after these changes: all eight scenarios remain `LOCKED` with zero errors or notes; `git diff --check` remains clean. **No wording, narrative or manifest-consistency blocker remains in this independent pass.** The scope limits above remain in force.

### 2026-10-02 — Prologue cost correction verified

Independently reloaded `sthr-act-firsthour` after the final supported opening retune. The effective clue circle is **2 per investigator** (`clues = 2`, `clues_per_investigator = true`), and the objective's plural group-payment sentence also requires **2 [perinv] clues** from investigators at The Almanac Steps. Its Hour VIII gate and Hour IX failure boundary are unchanged. The back still directs Resolution 1; its back text, front flavor and back flavor are byte-for-byte unchanged from the reviewed baseline.

The Prologue manifest already uses `needs.clues = "card"` and the correct three clue-source locations. Effective Prologue locations and manifest agree on 1/1/2 clues per investigator, giving 4 per investigator in total; The Almanac Steps itself has the 2 per investigator now required. The current guide introduces the same act and routes its successful advance, deadline/reset and defeat outcomes to the same three resolutions. It contains no conflicting fixed clue requirement. Every outcome still begins Part I, with the established difference in opening Memory reward, so the tutorial's continuation and all later nonlinear branches are preserved. No XP, act identity, story or ending was changed by this cost correction.

Fresh readiness remains eight `LOCKED` scenarios, zero errors or notes, and a clean `git diff --check`. **No source, guide, narrative or manifest-coherence blocker was found.** The root's paired numerical trials are separate balance evidence; this wording check does not independently certify those results, unachieved later targets, artwork fit or human playtesting.
