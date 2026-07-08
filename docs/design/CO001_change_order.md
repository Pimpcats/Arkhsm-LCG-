# THE STILL HOUR — Change Order CO-001 (for Claude Code)
### Two design reconciliations to apply to the SCED build. Both are owner-approved.

Context: benchmarking Memory against official Arkham XP (~5 XP/scenario/investigator, ~40–50/investigator per campaign) surfaced one economy fix, and the finale contest contradiction you flagged in `BUILD_STATUS.md` is now decided. Apply both, update tests + docs, and mark the corresponding lines in `BUILD_STATUS.md` resolved.

**Already-confirmed constants (do not change):** Memory soft cap = **18** (`6 * n`), Dissonance thresholds = **12 / 18** (`4 * n` / `6 * n`) at three players. These are correct as you have them.

---

## CHANGE 1 — Finale contest target → `4 * n`

**Decision:** the finale contest target is **`4 * investigatorCount`** (→ **12** at 3 players), not `3 * n` (9). The prose "12 at three players" was intended; `3 * n = 9` was an arithmetic slip in the guide. Nine makes the finale too easy and undercuts the "cost is age" payoff.

**Do:**
1. In `Constants.ttslua`, set the finale contest-target formula to `4 * n` (yielding 8 / 12 / 16 for 2 / 3 / 4 investigators). Locate the constant you currently derive as `3 * n`.
2. In `pipeline/lua_smoketest.lua`, update/add assertions: contest target == 12 at n=3, == 8 at n=2, == 16 at n=4.
3. In the campaign guide (§9, "The Last Hour") and anywhere else, change "contest progress equal to 3 × investigators" → "**4 × investigators (12 at three players)**." Remove the contradictory "3 ×" phrasing.
4. Mark this reconciliation **resolved** in `docs/BUILD_STATUS.md`.

---

## CHANGE 2 — Memory functions as experience (not Recollections-only)

**Decision:** Memory is a general **experience** currency. It buys **both** (a) normal higher-level card upgrades at the standard rate of **1 Memory per card level** (level 1–5, exactly like XP), **and** (b) Recollections at their listed `memoryCost`. The earlier "Memory is spent only on Recollections" wording was too narrow — it left investigators no way to level their regular decks, and it made the sink (~60–80 Memory of Recollections) far smaller than campaign income (~125 Memory), so most earned Memory had nowhere to go.

**Rationale (for validation):** with Memory = XP, total campaign spend of ~120–140 shared (≈ **42–47 per investigator**) matches the official ~40–50/investigator benchmark, and the 18/loop carryover cap remains the governor that keeps the loop structure from inflating the total.

**Do:**
1. **Spend API** — in `CampaignState.ttslua`, generalize the Memory-spend/purchase path so it can debit Memory for an arbitrary card level-up (cost = target card level in Memory), not only for Recollection purchases. Recollections keep their explicit `memoryCost`; normal cards cost `= level`. Banking, the 18 cap, and the scar logic are unchanged.
2. **Metadata** — keep `memoryCost` on the 10 Recollections. Normal player cards need no `memoryCost` field; their Memory cost is their `level`. Confirm `build_cards.py` doesn't require `memoryCost` on non-Recollection cards.
3. **Interlude (P7, when built)** — the interlude spend step must offer both options: buy Recollections (at `memoryCost`) and upgrade eligible cards (at `= level`), from the shared banked pool, respecting each investigator's deckbuilding access.
4. **Docs** — update:
   - `cards_v0.2 §1.1` and `§A` (Memory definition): "spent only on Recollections" → "**spent as experience — level-ups at 1 Memory per card level, plus Recollections at their listed cost.**"
   - Campaign guide interlude step 3 ("Spend"): same generalization.
   - `docs/BUILD_STATUS.md`: note the economy reconciliation and the benchmark target (~40–50 Memory/investigator-equivalent per campaign).
5. **Test** — add a smoketest assertion: spending Memory on a level-3 upgrade debits exactly 3 from the shared pool; spending on a Recollection debits its `memoryCost`; neither can overdraw the pool.

---

## Acceptance checklist
- [ ] `Constants.ttslua` contest target = `4 * n`; smoketest asserts 8/12/16.
- [ ] `CampaignState` spend path handles both level-ups (`= level`) and Recollections (`memoryCost`), cap/scar untouched.
- [ ] `build_cards.py` tolerant of non-Recollection cards without `memoryCost`.
- [ ] Guide §9, `cards_v0.2 §1.1/§A`, and interlude step updated; contradictory "3 ×" phrasing gone.
- [ ] `BUILD_STATUS.md` marks both reconciliations resolved.
- [ ] All existing 48 assertions still pass; new assertions added and passing.

*Unchanged and still outstanding per your report: P5 Latecomer, P6 location fact-toggles, P7 interlude UI, P8 download-box packaging.*
