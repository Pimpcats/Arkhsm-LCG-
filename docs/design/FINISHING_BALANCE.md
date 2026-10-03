# Finishing balance evidence — 2026-10-02

**Designer reference; contains spoilers. This is an offline validated candidate for human playtesting.**

The requested 80/80/70/70/60/60/50/50/40/40 curve is a design target. The current model does not certify it or a monotone difficulty increase. Structural and rules corrections are complete within the reviewed scope; calibration remains open where the measured results differ.

## Method and validity

The final run contains **70 cells and 1,319 played slots**: 1,000 main scenario trials, 120 party/player-count probes and 199 slots from 20 carried campaigns. All expected cells completed. There were zero engine errors, Lua errors, table notes or missing encounter draws; no failed trial was removed from a denominator. Every final cell used one unchanged fingerprinted input snapshot.

Standard difficulty, the real SCED save/table on a Lua emulator, and legal role-based starter/upgraded decks are used. The main party is Elias/Ayako/Cass. Nights average five routes equally, 20 trials each; opening and conditional finale each have 100 trials. Success means all required objective acts completed, or the finale contest reached. Optional Road work on a Lighthouse route is not required for a win.

Seeds and every raw trial are preserved. Lua pairs/next ordering is unspecified: equal-score moves, equal-length paths and similar legal ties can differ between fresh processes despite equal PRNG seeds. Same numeric seeds in proposal screens therefore do **not** guarantee identical draws or coupled paths. These are directional screens, not a controlled causal estimate. Wilson intervals summarize sampled model outcomes, not human win probabilities or calibration approval. Primary references: [Lua 5.2 next](https://www.lua.org/manual/5.2/manual.html#pdf-next) and [Lua 5.4 next](https://www.lua.org/manual/5.4/manual.html#pdf-next). The independent tie-policy probe is in `review-evidence.tar.gz`.

## Difficulty by played slot

| Played slot | Target | Model wins / trials | Model rate | Approx. 95% interval | Difference |
|---|---:|---:|---:|---:|---:|
| 1: Prologue | 80% | 83/100 | 83% | 74%–89% | +3 points |
| 2: Night 1 | 80% | 71/100 | 71% | 61%–79% | -9 points |
| 3: Night 2 | 70% | 82/100 | 82% | 73%–88% | +12 points |
| 4: Night 3 | 70% | 69/100 | 69% | 59%–77% | -1 points |
| 5: Night 4 | 60% | 60/100 | 60% | 50%–69% | +0 points |
| 6: Night 5 | 60% | 62/100 | 62% | 52%–71% | +2 points |
| 7: Night 6 | 50% | 56/100 | 56% | 46%–65% | +6 points |
| 8: Night 7 | 50% | 50/100 | 50% | 40%–60% | +0 points |
| 9: Night 8 | 40% | 42/100 | 42% | 33%–52% | +2 points |
| 10: Finale | 40% | 50/100 | 50% | 40%–60% | +10 points |

The finale row is conditional on an already unlocked, prepared state. Its legacy preset has six completed loops and 10 recorded Years; it is not a literal continuation after eight tested nights. The campaign itself is nonlinear, with repeatable districts. The ten rows refer to played order, not ten mandatory scenario boxes.

## Route differences

| Night | Church | Road | Lighthouse | Fairground | Almanac | Target |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 75% | 80% | 45% | 75% | 80% | 80% |
| 2 | 85% | 95% | 65% | 80% | 85% | 70% |
| 3 | 65% | 60% | 60% | 75% | 85% | 70% |
| 4 | 75% | 60% | 45% | 80% | 40% | 60% |
| 5 | 70% | 80% | 60% | 70% | 30% | 60% |
| 6 | 55% | 50% | 50% | 75% | 50% | 50% |
| 7 | 50% | 40% | 40% | 70% | 50% | 50% |
| 8 | 40% | 35% | 60% | 45% | 30% | 40% |

Each route cell has only 20 trials and a much wider uncertainty interval than the pooled row. Actual objective counts, travel, clue access and enemies differ by route. An equal-route average can conceal a route outlier.

## Supported adjustments and rejected proposal

| Printed cost | Previous | Candidate | Corrected same-seed screen | Disposition |
|---|---:|---:|---|---|
| Prologue clue payment | 1 per investigator | 2 per investigator | 37/40 at 1; 33/40 at 2; 29/40 at 3 | Apply 2; retain Hour gate and reverse |
| Church surface carry | 4 per investigator | 3 per investigator | Nights 1/2/3: 45/55/40% to 65/65/70%, 20 each | Apply 3 |
| Church deep carry | 2 per investigator | 3 per investigator | Night 6: 85% to 70%, 20 each | Apply 3 |
| Road deep payment | 3 per investigator | 4 per investigator | Night 6: 95% to 55%, 20 each | Apply 4 to both payment paths |
| Three-player finale contest | 6 | 7 | 21/40 at 6; 4/40 at 7 | Reject 7; retain 5/6/7 by player count |

These 400 proposal trials use the corrected player windows and encounter-draw adapter. Their archived inputs predate the opening image pin and finale accounting/classification follow-up. The district screens do not play the opening or finale; the finale proposal measures contest reach, which the later aftermath/classification fix does not change. They support bounded choices and do not close the remaining difficulty residuals. Earlier measurements with illegal early clue spending or missing encounters are withdrawn.

## XP and campaign progression

| Played slot | Mean XP income per investigator in preset trials |
|---|---:|
| Prologue | 3.88 |
| Night 1 | 5.28 |
| Night 2 | 5.49 |
| Night 3 | 5.28 |
| Night 4 | 7.48 |
| Night 5 | 7.22 |
| Night 6 | 7.31 |
| Night 7 | 7.67 |
| Night 8 | 7.57 |

Income is the change in banked Memory before purchases, including Knowledge/Victory and banked generated Memory. It is not unspent carry. Finale ordinary banking and resolution Years are intentionally not simulated, so no comparable final-income row is fabricated.

Fixed exhaustively collectible sources total 41 + 1/n XP per investigator: opening 2 plus a shared successful-objective bonus, six surface entries at 1, six deep entries at 3, Victory locations totaling 5 and Victory enemies totaling 10. Generated Memory is additional and variable. The bank cap is 10 × investigators after spending. This fixed-source ceiling is not guaranteed campaign earnings.

Prepared decks are conditional budgets: ordinary XP tiers 2/4/8/12/16/20/24/28 for nights 1–8, plus selected Recollections. The Night-1 three-player preparation spends 13 group Memory on ordinary upgrades/Recollections and retains 2: 15 total group wealth. It may exceed a particular opening trial’s actual earnings. Prepared cells do not claim those purchases were financed by previous trials.

The separate carried runs start from legal level-0 decks and preserve actual earnings, full printed-level purchase costs, Recollections, after-spending cap, Knowledge, Years, and each original basic weakness. All progression conservation checks passed. They played **199 slots across 20 campaigns**; 19 reached all ten slots. Three reached the first age-out: one at slot 9 and two at slot 10. There were 7 genuinely unlocked finale attempts and 4 contest wins.

| Carried campaign quantity, per investigator | Mean | Range |
|---|---:|---:|
| Earned banked Memory | 47.43 | 38.00–56.33 |
| Paid purchases | 30.38 | 28.67–33.00 |
| Lost to carry cap | 3.87 | 0.00–10.67 |

The carried policy rotates Church/Fairground/Almanac/Road/Lighthouse, stops after at most ten played slots or the first investigator ages out, and does not simulate replacement investigators. It never injects an unearned finale unlock. Later reached slots select surviving campaigns; these are not independent full-length human campaigns and do not establish a finale rate among all campaign starts.

## All five investigators and 1–4 players

| Party | Opening | Deep Church | Conditional finale |
|---|---:|---:|---:|
| Cass | 3/5 | 5/5 | 0/5 |
| Birdie | 4/5 | 3/5 | 1/5 |
| Elias, Ayako | 3/5 | 4/5 | 3/5 |
| Elias, Birdie | 3/5 | 2/5 | 4/5 |
| Ayako, Cass, Seraphine | 5/5 | 4/5 | 2/5 |
| Elias, Ayako, Birdie | 5/5 | 5/5 | 4/5 |
| Elias, Ayako, Cass, Seraphine | 5/5 | 3/5 | 1/5 |
| Elias, Cass, Seraphine, Birdie | 5/5 | 1/5 | 1/5 |

These are only five trials per party/scenario: useful coverage probes, too small to approve investigator parity. Every investigator’s abilities, signatures, weaknesses and all Recollections also have source-level rules checks; legal card coverage is separate from the AI choosing every useful ability.

## Whole-campaign calibration (2026-10-02, evening)

Designer-facing; contains spoilers. Supersedes the preset-night table above for tuning decisions.

**What changed in the method.** The single-night presets always had two goals (the Square's act plus a district's act), but a carried campaign finishes the Square's acts by about the fifth night, after which a night had one goal and won 90–100%. Official scenarios have about three acts however a party gets there, so the carried runs now give every night two goals: the Square's current act while it has one, then two districts' acts (`goalsPerNight` what-if in `tools/play_engine/lua/engine.lua`). The guide tells players to plan on about two acts a night.

**Values chosen** (all official range, 2–3 per investigator; walk 3, 1, 1): The Hour Was Wrong 2, What the Almanac Hid 3, Who Walks Beside You 3, the Ticket-Taker's fare 3, Why Thirteen? 3; The Appointed's Name while the Approach is Emerging or Arrived (the Arrived-only window left it near 40%).

**Result** (20 carried campaigns, Elias/Ayako/Cass, 3 players, same seeds as the earlier arms; win = every goal of the night done): Prologue 90, Night 1 75, Night 2 75, Night 3 25, Night 4 55, Night 5 20, Night 6 90, Night 7 40, Night 8 81. Against 80/80/70/70/60/60/50/50/40 the mean is 59% against 60%. Single slots swing ±25 points at n=20 and depend on which districts the fixed route draws, so treat the per-night shape as noise and the mean and the Part I / Part II levels (58% / 58% against 73% / 52%) as the signal. Nights 8+ and the last slots often have fewer than two acts left. Earlier arms on the same seeds: one district a night, 90–100% on Nights 2–7 (too easy); two districts plus the Square, 0% (too hard); two goals with the previous costs, mean 38% (too hard).

**Player cards.** Stolen Minute, The Lexicon of the Hour, Anchor Point, The Long Way Round, Rehearsed Escape, the Bell, I Remember the Ending, the Ambergrove Lamp and both unusual weaknesses were trimmed or limited toward official strength; each investigator's Memory reaction is limited to once per round and three times per loop. Ayako and Birdie gained 1 health to reach the official 14 total. Experience per investigator over a full campaign, 6 carried campaigns each: Elias/Ayako/Cass 43 (41–45), Birdie/Cass/Seraphine 40 (38–41), Elias/Birdie/Seraphine 36 (30–42), Elias/Ayako 49 (40–56).

**Still open.** n=20 per cell is a screen, not certification. The finale on the final cards (40 games, prepared state): 32% (13 wins) against 40%, was 50% before the player-card trims. The other player counts were not re-measured on the final cards. Human playtests decide the rest.

## Remaining calibration

The candidate can proceed to live relay and human playtesting. The target curve remains open: repeat route outliers with actual carried decks, test the transition between early nights and upgraded decks, and test endings with real group choices. Choose further encounter/tempo adjustments from that evidence rather than forcing an integer finale threshold that overshoots. Do not mark human playtest approval or exact target percentages complete.

## Evidence

The correction ledger links the three independent reviews. `verification/2026-10-02/` contains `balance-summary.json`, 70 full-cell raw results and seeds in `release-results.tar.gz`, the exact owned inputs in `release-inputs.tar.gz`, and 400 proposal trials plus matching earlier inputs in `proposal-results.tar.gz` / `paired-inputs.tar.gz`. The README records reproduction and exclusions. Godot renders and card/PDF proofs establish packaging/rendering, not TTS physics or human balance.

## Experience by party (2026-10-03)

Whole carried campaigns, three investigators, 20 campaigns per party, Memory banked per investigator (mean, range): Elias/Ayako/Cass 39.0 (32.7–44.3); Birdie/Cass/Seraphine 40.1 (34.0–46.3); Elias/Birdie/Seraphine 38.8 (32.0–50.7); Ayako/Elias/Seraphine 42.6 (35.7–47.0); Ayako/Birdie/Cass 40.1 (33.0–48.7). The spread between parties is 3.8, inside the official 35–45 band. Before the change the Elias/Birdie/Seraphine party earned 36. Each investigator's own Memory reaction now has no per-round limit and a per-loop cap (twice for Ayako and Cass, three times for the others); Elias gains Memory whenever he is dealt damage, Seraphine whenever Dissonance is raised in the investigation phase, and her elder sign is capped at +3.
