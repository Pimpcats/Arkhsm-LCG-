# THE STILL HOUR — Encounter Deck
### v0.4 · the shared campaign encounter spine + the Occultation clock + the Latecomer boss set

Written to the same errata-grade standard as `cards_v0.2`, and consistent with the 3-player constants in `aging_3p_v0.3`. This is the **reusable spine** used across every node; node-specific encounter cards ship later with the six node objectives.

> **Templating recap.** `Revelation` resolves when drawn. `Surge` = after resolving, draw another encounter card. `Peril` = resolve alone, no help from other investigators. `Hunter` = moves toward its prey each enemy phase. `Prey – X` sets targeting. Enemy line is **Fight / Health / Evade**, with **damage/horror** below. Timing words are load-bearing (`When…would` = interrupt; `After` = reaction).

---

## §0. Terms this deck relies on (glossary deltas)

- **Dissonance bands (refined for scaling).** Bands are **thirds of the reset threshold R** (R = 6 × investigators; **R = 18 at three players**), so they scale with player count and stay consistent with `v0.3`:
  - **Calm** — Dissonance 0 to R/3−1 (**0–5** at 3p)
  - **Glitch** — R/3 to 2R/3−1 (**6–11**): the chaos bag gains 1 `[static]`; Echoes wake.
  - **Noticed** — 2R/3 to R−1 (**12–17**): the bag gains a 2nd `[static]`; the Latecomer enters play.
  - **Reset** — R (**18**): the loop resets.
  - *(This refines the absolute 4-7/8-11 bands in `v0.2 §A`, which were the 1–2 player numbers. Same shape, now player-count-correct.)*
- **`[static]` token** — modifier **−3**; when revealed, raise Dissonance by 1.
- **Skip** — any instruction to **advance the Hourglass**.
- **Sleepwalking** *(new Echo keyword)* — while an enemy is Sleepwalking it does not attack, does not engage investigators, and cannot be dealt damage or taken as a target. **An Echo is Sleepwalking while Dissonance is in the Calm band.** (The town repeats its last moments, blind, until the loop glitches.)
- **The Occultation** — the loop clock deck (§1), separate from the encounter deck.

---

## §1. THE OCCULTATION — the Hour deck (the clock)

The same night, every loop, so the Occultation is a **fixed, ordered stack of nine Hour cards**, not shuffled. The **Hourglass** marker sits on the current Hour and moves as time passes and as **Skip** effects fire. When it reaches a new Hour, reveal that Hour and resolve its **"When reached"** effect. **Knowledge facts edit specific Hours** — that is how remembering the night makes it survivable.

Because it is a known sequence, players who have looped *see it coming* — which is the whole point. `Seraphine's "I Remember the Ending"` and `Ayako's Lexicon` interact with the top of this deck.

| Hour | Name | When the Hourglass reaches this Hour | Knowledge edit |
|---|---|---|---|
| **I** | First Dark | Nothing yet. The night begins. | — |
| **II** | Low Water | Each investigator draws 1 encounter card. | — |
| **III** | The Thirteenth Toll | Raise Dissonance by 1. If any investigator is at a *Church* location, raise it by 2 instead. | If you Know **"The Thirteenth Toll,"** skip the extra +1. |
| **IV** | The Road Gives Way | The location with the fewest clues becomes impassable until the next Hour (investigators there are moved to a connecting location; that move is a **Skip**). | If you Know **"The Hour Was Wrong,"** remove this Hour from the Occultation entirely. |
| **V** | The Streets Empty | Each Sleepwalking Echo in play awakens if Dissonance is in the Glitch band or higher. | — |
| **VI** | The Wrong Sky | Add 1 `[static]` token to the chaos bag until the next reset. | If you Know **"What the Almanac Hid,"** instead each investigator *removes* 1 `[static]`. |
| **VII** | The Guest Approaches | If the Latecomer is not in play, it moves 1 Hour closer (place its arrival marker; at Hour VIII it enters even below the Noticed band). | If you Know **"The Latecomer's Name,"** it enters *exhausted*. |
| **VIII** | Almost | Raise Dissonance by 2. All enemies get +1 Fight until the next reset. | — |
| **IX** | **The Appointed Hour** | The night ends. **Trigger a reset** (see campaign rules). No test, no escape — only what you carry forward. | If you Know **"The Way the Night Breaks,"** you may attempt the finale here instead of resetting. |

> **Wording note.** Every Hour effect is a **"when reached"** trigger, so advancing the Hourglass past several Hours at once (a big Skip) resolves each skipped Hour's effect in order — this is deliberate and makes Skip cards genuinely dangerous, not just a counter bump. The Knowledge edits are printed on the Hour, not on separate cards, so the clock is self-documenting once a fact is flagged on the log.

---

## §2. ENCOUNTER SET — "The Occultation" (Skip treacheries)

*These are shuffled into the encounter deck; they push the Hourglass.*

**LOST HOUR** — Treachery. ×3
> Revelation — **Skip:** advance the Hourglass by 1 Hour. If the Hourglass is at Hour VI or later, advance it by **2** instead.
> **Wording note.** Late-loop acceleration ("VI or later") makes the back half of a node tighten on its own, so players feel the night closing without a separate escalation card. Resolving each skipped Hour (per §1) is what gives this teeth.

**SLIPPAGE** — Treachery. Surge. ×2
> Revelation — Add 1 `[static]` token to the chaos bag until the end of the round. Then, because Surge, draw another encounter card.
> **Wording note.** "until the end of the round" bounds the extra `[static]` so it doesn't permanently bloat the bag; Surge keeps the tempo cost real without stacking a lasting effect.

---

## §3. ENCOUNTER SET — "Echoes of Ambergrove" (Echo enemies)

*Townsfolk frozen mid-gesture. `Sleepwalking` while Dissonance is Calm; they wake when the loop glitches.*

**THE WAITING CONGREGATION** — Enemy. Echo. Humanoid. ×2
> **Fight 2 · Health 2 · Evade 2** — damage 1 / horror 1
> Sleepwalking. While Dissonance is in the Glitch band or higher, this enemy gains **Hunter**.
> **Prey** – the investigator with the most Memory on their cards.
> **Wording note.** The wake condition and Hunter are gated on the same band, so it can't attack while Sleepwalking (Sleepwalking already forbids attacking) — belt-and-suspenders against the "does a woken-this-phase Echo act" edge case. Prey ties the town's attention to whoever is carrying the most of the night.

**THE DROWNED CHOIR** — Enemy. Echo. Monster. ×2
> **Fight 1 · Health 3 · Evade 1** — damage 0 / horror 2
> Sleepwalking. Aloof. **Forced** – When the Drowned Choir awakens (leaves Sleepwalking): each investigator at its location takes 1 horror.
> **Wording note.** Horror-focused, low fight — a sanity pressure enemy. The awaken trigger fires exactly once (leaving Sleepwalking is a one-time state change), so it can't re-bleed horror every round the band fluctuates.

**FAMILIAR FACE** — Enemy. Echo. Humanoid. ×1
> **Fight 3 · Health 2 · Evade 3** — damage 1 / horror 1
> Sleepwalking. **Spawn** – engaged with the investigator with the most Memory. **Forced** – When Familiar Face is defeated: that investigator places 1 Memory on their investigator card. (You will remember this face too.)
> **Wording note.** Double-edged, on theme: killing someone you recognize costs you a memory of them. The defeat trigger grants **on-card** Memory (not banked), matching the "The House Always Wins" precedent so the two Memory pools never blur.

**THE LAMPLIGHTER'S ECHO** — Enemy. Echo. Humanoid. ×1
> **Fight 2 · Health 3 · Evade 2** — damage 1 / horror 1
> Sleepwalking. While the **Ambergrove Lamp** is in play, this enemy loses Sleepwalking and gains **Retaliate** (the light wakes him first).
> **Wording note.** A pointed interaction with Elias's signature — light both helps the party and stirs this one Echo early. Scoped to the specific asset by name to avoid unintended interactions with any future "light" cards.

---

## §4. ENCOUNTER SET — "Static" (reality-glitch treacheries)

**WRONG TURN** — Treachery. ×2
> Revelation — The map is not where you left it. Each investigator moves to a connecting location of the lead investigator's choice. This move is **not** a Skip and does not provoke attacks of opportunity.
> **Wording note.** Explicitly "not a Skip" so it doesn't accidentally advance the Hourglass (movement and Skip are different things here); "not … attacks of opportunity" because the investigators aren't choosing to move.

**REWIND** — Treachery. Peril. ×2
> Revelation — The loop stutters backward. Return the most recent clue you discovered this round to its location (you lose it). If you have discovered no clues this round, instead take 2 horror.
> **Wording note.** Peril (resolve alone) stops the table from shuffling the loss onto whoever it hurts least. The "no clues this round" branch guarantees the card is never a blank.

**DEAD AIR** — Treachery. ×2
> Revelation — Add 1 `[static]` token to the chaos bag until the end of your next turn. Until then, `[static]` tokens are treated as **−4** instead of −3.
> **Wording note.** A short, sharp bag-worsening window rather than a permanent add; the temporary −4 override is duration-bounded so it can't be stacked into a broken modifier.

**THE LOOP NOTICES YOU** — Treachery. ×2
> Revelation — Raise Dissonance by 1. If you have played a **Recollection** or triggered a foreknowledge ability this round, raise it by 2 instead.
> **Wording note.** The only deck card that directly punishes *using your advantage this round* — the mythos-side echo of pillar 2. Bounded to "this round" so it reads a clear, checkable window.

---

## §5. ENCOUNTER SET — "The Latecomer" (boss)

*Seeded aside, not shuffled. Enters play when Dissonance reaches the Noticed band (12 at 3p) or when Hour VIII forces it (§1).*

**THE LATECOMER** — Enemy. **Elite.** Hunter. Monster. ×1
> **Fight 4 · Health — · Evade —** — damage 2 / horror 2
> **Prey** – the investigator with the most Memory. Hunter.
> The Latecomer cannot be attacked, cannot be evaded, and **cannot be defeated.**
> `[action]` **Hold Back:** Test `[wil]` **or** `[com]` (4). If you succeed, exhaust the Latecomer and rewind the Hourglass by 1 Hour.
> **Forced** – When the Latecomer attacks: after it resolves, raise Dissonance by 1.
> **Forced** – When the Latecomer would be defeated or leave play by any effect: instead, it does not.
> **Wording note.** Health/Evade are "—" and the two "cannot" lines plus the defeat-replacement close every removal vector (damage, evade-to-disengage, "discard an enemy" tech, defeat triggers) — this is what makes "only delayed" airtight rather than a flavor line. **Hold Back** is a normal `[action]` (so it costs an action and can fail), gives the two most on-theme stats a use, and turns "combat" against it into buying time on the clock. It attacks for 2/2 *and* feeds Dissonance, so ignoring it spirals you toward reset — the intended relentless-clock pressure.

**THE CROSSING** — Treachery. ×1
> Revelation — If the Latecomer is not in play, put it into play at the location farthest from the investigators (it is arriving). If it is already in play, it readies and moves toward its prey. Then raise Dissonance by 1.
> **Wording note.** Doubles as the arrival trigger *and* an in-play accelerant, so one card covers both states without a dead draw.

**THE LATECOMER'S WHISPER** — Treachery. Peril. ×2
> Revelation — It knows your name now. Take 1 horror. If the Latecomer is in play, take 2 horror instead and raise Dissonance by 1.
> **Wording note.** Scales cleanly with whether the boss is out; Peril prevents spreading the horror. Kept low pre-arrival so the card isn't oppressive when drawn early.

---

## §6. ENCOUNTER SET — "The Weight of Years" (aging-linked treacheries)

*The encounter-side of the Aging system — the night literally takes years.*

**A YEAR IN A NIGHT** — Treachery. Peril. ×2
> Revelation — Test `[wil]` (3). For each point you fail by, take 1 horror. If you **fail**, the night takes a year: increase your **Years** by 1 (apply any bracket change at the next interlude).
> **Wording note.** The only encounter card that injects the finale's currency directly. Gated behind a *failed* test (so it's earned, not automatic) and bracket changes apply at the interlude (never mid-scenario), so a stat drop can't retroactively invalidate a test already in progress — an important errata guard given aging changes base skill values.

**WHAT YOU'VE FORGOTTEN** — Treachery. ×2
> Revelation — Remove 2 Memory from among your cards (your choice which). For each Memory you cannot remove, take 1 horror instead.
> **Wording note.** A Memory sink that pressures the Memory-rich and still bites the Memory-poor (via horror). "among your cards" scopes it to on-card Memory, never banked — the campaign progress is safe, only the in-scenario fuel is at risk.

**OLD BONES** — Treachery. Peril. ×1
> Revelation — If you are **Elder** or **Ancient**, take 2 damage. Otherwise take 1 damage. If you have no `[com]` and `[agi]` icons left to commit and are Elder or Ancient, take 1 additional horror (your body remembers what your mind won't).
> **Wording note.** Ties physical frailty to age brackets so aging has a downside the deck can exploit — without ever being a pure death sentence for young investigators.

---

## §7. Building the encounter deck

- **Shared spine (every node):** all of §2, §3, §4, and §6 — **26 cards**. This is the reusable core.
- **Boss set (§5):** set aside; the Latecomer/Crossing enter via Dissonance or Hour VIII. The Whispers shuffle in only from Act II onward.
- **The Occultation (§1):** never shuffled — it is the clock, arranged in order I→IX at setup and edited by Knowledge facts.
- **Node-specific sets:** each of the six Ambergrove nodes adds its own small set (2–4 cards) on top of the spine — those ship with the node objectives.
- **Static token count** in the bag is set by the Dissonance band automatically (§0); cards in §2/§4 add *temporary* extras on top.

---

## §8. Pressure check (simulated)

Ran the shared pool through the same method as the player-card tuning:

- **Hourglass** advances **~1.5 Hours/round** at three players (deck Skips ~0.45 + baseline clock 1.0) → a 9-Hour loop runs **~6 rounds**. Good node length.
- **Dissonance from the deck alone** climbs **~0.8/round** → it would take **~14 rounds** to reach the Latecomer on its own, longer than a node. So the mythos deck is **secondary** pressure; **your foreknowledge use is the primary driver** of Dissonance — exactly the intended "your choices wake the loop, not the dice."
- Horror-weighted (Drowned Choir, Whisper, Rewind's fail branch) vs. damage-light: the deck leans on **sanity and the clock**, which suits a cast with generally healthy sanity and lower health — pressure lands where the party is thinner.

*Provisional until table play; validates pacing, not drama.*

---

### Still on me
1. **Six node-specific encounter sets** (2–4 cards each) + the node objectives and their Knowledge facts.
2. The **finale generator table** (Knowledge × Dissonance × Age → resolution).
3. The **campaign guide** + printable **campaign-log sheet**.
4. On request: the **Claude Code brief + starter card JSON** to begin the SCED build in parallel.
