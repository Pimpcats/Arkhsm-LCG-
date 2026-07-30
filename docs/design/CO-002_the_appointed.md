# THE STILL HOUR — CO-002 / P5 Spec: THE APPOINTED
### Rename the boss (Latecomer → **The Appointed**) and rebuild it as a staged, clock-driven Approach. This is the P5 build task.

Supersedes the "Latecomer" content in `encounter_v0.4 §5` and the boss references in the guide/flow/manifest. Owner-approved. Apply on branch `claude/new-session-r230bz`.

**Concept.** The Appointed is not a monster that spawns — it is an arrival the night owes. It is present as dread for most of the loop and **manifests onto the board in stages** as the clock advances and as investigators wake it. It cannot be killed; it can only be **held back** — shoved back into shadow, buying Hours.

---

## 1. The Approach (the new core mechanic)

The Appointed occupies one of four **Approach stages**, tracked in campaign state (`appointedStage`, 0–3, persists within a loop, resets to 0 on loop reset):

| Stage | Name | On the board? | Behavior |
|---|---|---|---|
| 0 | **Unseen** | No | Ambient only (Whisper cards). Most of the loop. |
| 1 | **Sensed** | Yes — a shadow marker at the location **farthest** from the investigators | Does not move or attack. **Forced** – at the end of the round, each investigator at its location takes 1 horror. |
| 2 | **Emerging** | Yes — partial figure | Gains **Hunter**; moves toward its prey. **Forced** – when it engages an investigator, that investigator takes 1 horror. |
| 3 | **Arrived** | Yes — full Elite hunter | Gains **Hunter**. **Forced** – when it attacks: 2 damage + 2 horror, then raise Dissonance by 1. |

**Prey** (all manifest stages): the investigator with the most Memory on their cards.

### What advances the Approach (it only ever ratchets **up**, via events — never recomputed continuously)
The stage rises to the highest triggered by any of these, whichever is furthest:
- **The clock (Hourglass):** reaching **Hour V** → at least *Sensed*; **Hour VII** → at least *Emerging*; **Hour VIII** → *Arrived*.
- **Dissonance band:** entering **Glitch** → at least *Sensed*; entering **Noticed** (= `appointedThreshold` = 4 × investigators) → *Arrived*.
- **Cards:** The Crossing (and Seraphine's *The Debt of Hours* at high Dissonance) push it a stage.

So **time brings it inevitably; recklessness brings it early.** You can watch it climb the clock toward you.

### Holding it back (the only counterplay)
> `[action]` **Hold Back:** Test `[willpower]` **or** `[combat]` (4). If you succeed: push the Appointed back **one** Approach stage and **rewind the Hourglass by 1 Hour**.

Rewinding the Hour lowers the clock-driven floor so it doesn't immediately re-advance — Hold Back buys a real window until the next Hour tick or Dissonance band change. It cannot go below **Unseen**. When the stage drops to 0, remove it from the board; when it rises to ≥1 and it isn't on the board, place it at the farthest location.

> **Why this can't be abused to stall forever:** Hold Back costs an action and can fail (~diff 4), it does nothing to stop Dissonance climbing toward the reset at 18, and while you Hold Back you aren't gathering clues. The clock still wins eventually — you're only choosing *when*.

---

## 2. Card text (errata-grade)

**THE APPOINTED** — *Enemy. Elite. Monster.* Unique.
> **Fight 4 · Health — · Evade —** — damage 2 / horror 2 *(Arrived)*
> **Prey** – the investigator with the most Memory. The Appointed cannot be attacked, cannot be evaded, and **cannot be defeated.**
> It occupies an **Approach** stage (Unseen → Sensed → Emerging → Arrived) and manifests at the location farthest from the investigators while Sensed or later. Its Approach advances per the campaign rules (clock, Dissonance, and card effects) and never rises above Arrived.
> `[action]` **Hold Back:** Test `[willpower]` or `[combat]` (4). If you succeed, push the Appointed back one Approach stage and rewind the Hourglass by 1 Hour.
> **While Sensed:** it does not move or attack. **Forced** – At the end of the round, each investigator at its location takes 1 horror.
> **While Emerging:** it gains **Hunter** and moves toward its prey. **Forced** – When it engages an investigator: that investigator takes 1 horror.
> **While Arrived:** it gains **Hunter**. **Forced** – When it attacks: it deals 2 damage and 2 horror, then raise Dissonance by 1.
> **Forced** – When the Appointed would be defeated or leave play by any effect: instead, it does not.
> *Wording note:* the three "cannot" clauses plus the defeat-replacement close every removal vector; behavior is gated by stage so a Sensed/Emerging figure can't attack as if Arrived; Hold Back is an `[action]` (costs a turn, can fail) at any manifest stage.

**THE APPOINTED'S WHISPER** — *Treachery. Peril.* ×2 *(rename of "The Latecomer's Whisper")*
> Revelation — It knows your name now. Take 1 horror. If the Appointed is **Emerging or Arrived**, take 2 horror instead and raise Dissonance by 1.

**THE CROSSING** — *Treachery.* ×1 *(reframed)*
> Revelation — Advance the Appointed's Approach by 1 stage (to a minimum of Sensed). Then raise Dissonance by 1.

*(The former "put the Latecomer into play" is now "advance the Approach" — same net effect, but it fits the staged model and never double-spawns.)*

---

## 3. Rename map (Latecomer → Appointed)

**Code (`src/StillHour/`):**
- `Constants.ttslua`: `latecomerThreshold` → `appointedThreshold` (value unchanged, `4 * n`; it now drives the *Arrived* stage and equals the Noticed-band start).
- `CampaignState.ttslua`: rename `latecomerInPlay` / `isLatecomerInPlay` / `setLatecomerInPlay` / `latecomerShouldArrive` → `appointed*` equivalents; **add** `appointedStage` (0–3) with `getAppointedStage()`, `advanceAppointed(driverStage)` (ratchets up, clamps ≤3), `pushBackAppointed()` (−1, clamp ≥0), persisted in serialize/deserialize, **reset to 0 in `reset()`**.
- New module `src/StillHour/Appointed.ttslua`: board manifest/remove by stage, the Hold Back action, and the stage-gated Forced effects.

**Docs:** `encounter_v0.4 §5` (retitle the set "The Appointed", replace the three cards with §2 above) · `campaign_guide §9` and its glossary · `START_HERE.md` · `THE_STILL_HOUR_flow.html` (legend + finale line) · art manifest `enemy-latecomer` → `enemy-appointed` · `ART_SPEC.md` (the Latecomer bullet → The Appointed).

---

## 4. Build tasks (P5) with acceptance tests

1. **State** — add `appointedStage` to `CampaignState` (persist; `reset()` sets it to 0). *Accept:* stage survives serialize/deserialize and node travel; a reset zeroes it.
2. **Advancement hooks** — from `Hourglass.ttslua` (on reaching a new Hour) and `Dissonance.ttslua` (on entering a new band), call `advanceAppointed(driverStage)`. *Accept:* reaching Hour V→stage ≥1, VII→≥2, VIII→3; entering Glitch→≥1, Noticed→3; stage only ratchets up.
3. **The enemy** — `Appointed.ttslua`: manifest at the farthest location when stage ≥1, remove at 0; stage-gated Forced effects; Prey = most Memory; the `[action]` Hold Back (test Wil/Com 4 → `pushBackAppointed()` + rewind Hourglass 1). *Accept:* no effect defeats/removes it; Hold Back drops exactly one stage and rewinds one Hour; a Sensed figure deals no attack damage; an Arrived one attacks 2/2 + raises Dissonance.
4. **Cards** — regenerate The Appointed / Whisper / Crossing from §2 via the card pipeline.
5. **Smoketest** — add assertions for stage ratcheting, Hold-Back pushback + Hour rewind, clamps [0,3], reset→0, undefeatable. *Accept:* all pass alongside the existing 48.

---

*Everything else (P6 location toggles, P7 interlude UI, P8 download-box, in-TTS load test) is unchanged and still outstanding. This spec replaces the boss design only.*
