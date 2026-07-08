# THE STILL HOUR — Aging, 3-Player Tuning & Finale
### v0.3 · adds the Aging system (the finale's cost), re-tunes for a 3-investigator group, and makes the finale age-gated

Supersedes the finale sketch in the design doc and updates the tuning constants in `cards_v0.2`. Everything else in those docs stands.

---

## §1. THE COST IS AGE — the Aging system

The price of living the same night hundreds of times is **years.** Aging is a persistent, per-investigator campaign mechanic that runs the whole campaign and *is* the finale's cost. How much you age depends on how you played — defeats, how hard the loop noticed you, and how much you leaned on its power.

### 1.1 Years (the counter)
- New campaign-log field per investigator: **Years**, starting at **0**.
- Updated at each **interlude** (after every reset). Years gained that loop:

> **Years this loop = 1** *(the night always takes something)*
> **+1** if this investigator was **defeated** during the loop.
> **+1** if the loop ended with **Dissonance at the danger threshold or higher** (the loop closed its hand on you).
> **+1** if this investigator personally **leaned on the loop** this loop — raised Dissonance 3+ times, **or** spent 4+ Memory on loop-power effects (Recollections, foreknowledge abilities).

Simulated outcomes: a **clean** loop ages you **+1**, a **typical** loop **+2**, a **rough/reckless** loop **+4**. Over a campaign this spreads the party across brackets by playstyle — exactly the "depending on how they did" you asked for.

### 1.2 Age brackets (the drift)
Checked at each interlude and applied as a **lookup by current bracket** (moving up a bracket *replaces* the lower bracket's effects — nothing stacks arbitrarily). The theme is **body for mind**: the longer you live the night, the more you become mind and memory, and the less you are your body.

| Bracket | Years | Effect |
|---|---|---|
| **Prime** | 0–4 | No change. |
| **Weathered** | 5–9 | −1 to one **physical** skill (`[com]` or `[agi]`, chosen once on entry and recorded); +1 to one **mental** skill (`[wil]` or `[int]`, chosen once on entry). |
| **Elder** | 10–14 | The Weathered drift, **and** +1 more to your chosen mental skill, −1 maximum health, and you begin each loop with 1 Memory on your investigator card. |
| **Ancient** | 15+ | The Elder drift, **and** −1 maximum sanity. You unlock the **"Take Its Place"** finale resolution (see §3). If your Years reach **18**, at the next interlude you **age out**: your investigator has lived too many nights and is removed from the campaign. |

**Rules notes (errata-grade):**
- Skill values have a **floor of 1** — aging never takes a stat below 1.
- Maximum health/sanity reductions reduce current health/sanity to the new maximum if it exceeds it, but the *reduction itself* never defeats an investigator (the numbers here never bring a maximum to 0).
- The physical/mental skills chosen at **Weathered** are **locked** and reused at Elder/Ancient — you don't re-pick as you age.
- Aging pushes each investigator toward their mental identity: Ayako (`[int]` 5) sharpens into a `[int]` 6–7 savant as she frays physically; Elias the protector trades his already-modest `[com]` for wisdom, leaning fully into soak/Lamp (his kit doesn't need combat). This is intended characterization, not a penalty spiral — every bracket grants as well as takes, and Ancient unlocks the campaign's most powerful ending.

### 1.3 Why this isn't a death spiral
Aging gives mental stats, a Memory perk (Elder), and the keystone finale option (Ancient). An aged party is *differently* capable, not merely weaker — and **clean play ages you slowly**, so the party controls the pace. The tension is: the Knowledge you need to end the loop only accrues by looping, and looping ages you. **You cannot end the Still Hour young.** Someone pays in years.

---

## §2. 3-PLAYER RE-TUNE (locked to your group)

The cast is now tuned for **3 investigators** as the assumed baseline. Two constants change; everything else holds. Both derive from clean scaling rules so a 1/2/4-player table still works.

### 2.1 Memory soft cap → **18** (rule: **6 × investigators**)
Simulation: a 3-player shared pool banks **~17 Memory/loop** (5–95th: 14–20). Testing caps: 15 wastes 82% of the time (far too low), **18 wastes 21%** (bites occasionally, forces spending — correct), 20 wastes 2% (too loose). So **soft cap = 6 × investigator count** → **18 at three players**. This supports **~1.4 Recollections per player per loop** against a shared demand of ~24 Memory/loop — a healthy, slightly tight XP-analog for three decks.

### 2.2 Dissonance thresholds → Latecomer **12**, reset **18** (rules: **4× and 6× investigators**)
A shared Dissonance track with three actors climbs three times as fast. At the old 8/12 thresholds, a greedy 3-player group wakes the Latecomer in ~4 rounds and resets in ~5.6 — they could never use the loop's power. Scaling to **12 / 18** restores the target window:

- **Cautious 3p:** ~13 rounds to the Latecomer (survives a normal node comfortably).
- **Greedy 3p:** ~5.5 rounds to the Latecomer, ~8 to a reset (flirting with danger mid-to-late node; reckless play still self-destructs).

Rules: **Latecomer threshold = 4 × investigators; reset = 6 × investigators** (3p → 12/18; 2p → 8/12; 1p → 6/9 recommended for solo, a touch looser than the pure 4×/6× to keep true-solo playable).

### 2.3 Two derived constants
- **Scar floor** (start-of-loop Dissonance): = completed loops so far, capped at **6** for a 3-player game (⅓ of the reset threshold), so late loops open near — but not inside — the danger band.
- **Hourglass length**: budget the loop clock so three investigators still feel time pressure. Target **~9 Hours per loop**, enough for the group to attempt **2–3 nodes** before the reset. (Final value set in node playtesting.)

---

## §3. THE FINALE — age-gated resolutions

"The Last Hour" reads three things off the campaign log — **collective Knowledge**, **Dissonance**, and the party's **Age profile** — and offers different resolutions. The finale can be *attempted* once enough of the Knowledge Track is lit (target: after ~loop 4); the party may keep looping to prepare, trading years for readiness.

The available endings by the party's age profile:

- **Mostly Prime / Weathered** — *"Vigorous, unready."* You have the bodies to fight through but likely lack the deep Knowledge. Endings lean toward **Break Through** (force an escape — everyone survives, but the loop is only *paused*, a bittersweet "did we really end it?" epilogue) or a costly **Seal by Force**.
- **Elder-heavy party** — *"Wise and still standing."* The balanced center. Full access to **Close the Door** (end the loop cleanly) if Knowledge is sufficient — the "good" ending, purchased with the years everyone spent to get here.
- **An Ancient present** — unlocks **Take Its Place**: one Ancient investigator becomes the loop's new anchor. The loop ends for everyone else; that investigator is *kept* — decades older, the new keeper of a night that no longer repeats. The keystone bittersweet ending, only reachable by someone who paid the maximum price.
- **Aged-out investigators** — an investigator who aged out before the finale is honored in the resolution text but cannot perform the final act; their years bought the others' Knowledge.
- **The loop wins** (Dissonance-driven failure at the finale) — but sufficient **banked Memory** still triggers the hidden **"Next Time"** epilogue: you wake at the first Hour knowing you're closer. Even total loss is seeded forward.

**Design intent:** there is no single "correct" age. A young party and an Ancient party are both *winnable*, but they win *different endings*. The group's play across the whole campaign — how clean, how greedy, how many defeats — writes which finale they're allowed to reach. That is the cost being age.

---

## §4. Downstream effects on the card spec

- **Anchor Point** (Recollection) stacks with the **Elder** start-of-loop Memory — an intended, mild synergy (an old investigator who *also* fixed an anchor remembers most). Not degenerate: caps at the soft cap anyway.
- No player card references player count directly, so the 3p re-tune touches only the two campaign constants (§2), not any card text. Good — the wording pass in `cards_v0.2` stands unchanged.
- **"once per loop"** limits gain weight at 3p (three actors, longer loops) — reinforces that §E's cross-node flag persistence is the critical build item.
- Aging modifies **base skill values**, so it interacts cleanly with all committed-icon and modifier effects (it changes the number the delta is computed from; nothing in the wording breaks).

---

## §5. Updated balance verdict

- **3-player economy:** ~17 Memory/loop, soft cap 18 → ~1.4 Recollections/player/loop. Tight and healthy.
- **3-player Dissonance:** thresholds 12/18 reproduce the intended window (cautious survives a node; greedy flirts with the Latecomer mid-late; recklessness resets). Locked.
- **Aging pacing:** clean +1/loop, typical +2, reckless +4 → a ~6–8-loop campaign lands clean players around Weathered and typical players around Elder at the finale, with Ancient/age-out reserved for the reckless or for overtime. The bracket spread is wide enough to make the finale gate meaningful without forcing a single path.
- Still provisional until table play; the sim validates pacing and economy, not the drama.

---

### Remaining open items (all on me)
1. **Campaign length** — I've assumed **~6–8 loops**, finale openable after ~loop 4. If your group wants shorter/longer, I re-space the Age brackets and the Knowledge Track to match. (Only thing I'd still like your read on.)
2. Full **encounter card text** — the Occultation deck, Echoes, Static treacheries, and the **Latecomer**'s card, to the same errata-grade standard.
3. The **six node objectives** + the finale generator table (Knowledge × Dissonance × Age → resolution).
4. The **campaign guide** + a printable **campaign-log sheet** (Years, brackets, Memory, Dissonance, Knowledge, the dead).
5. On request: the full **Claude Code brief** + starter **card JSON** to begin the SCED build.
