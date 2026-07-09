# THE STILL HOUR — Rules & Card Text Spec
### v0.2 · errata-grade wording pass · balance-tuned against in-engine simulation

This document assumes the design in `THE_STILL_HOUR_design.md`. It does three jobs:
1. **Defines the non-standard terms precisely** (§A) so card wording is unambiguous.
2. **Templates every player card** in strict Arkham timing language, each with a **wording note** flagging the interaction the wording guards against (§B–§C).
3. Records the **balance findings** from simulation and the **build handoff** (§D–§E).

> **Templating conventions used below.** Timing words are load-bearing: **When … would …** = interrupt (a window *before* the event, used for cancel/replace); **After …** = reaction (*after* the event resolves); **instead** = a replacement effect and may only appear inside a *When…would* interrupt. Triggered-ability symbols: `[action]`, `[free]`, `[reaction]`. **Forced** abilities are mandatory (never "may"). **Revelation** resolves when the card is drawn. Skill icons: `[wil][int][com][agi][wild]`.

---

## §A. Loop rules glossary (the custom timing layer)

These terms are referenced by card text. They must be defined *before* the cards, exactly like the rules reference defines "attack" before a card can say "attack."

- **Loop.** The span of play from one **reset** to the next. A single loop may span **multiple scenario nodes** (in Act I you visit 2–3 nodes per loop).
- **Reset.** Occurs when any of: the **Hourglass** reaches its final Hour; all investigators are defeated; or **Dissonance** reaches 12. On a reset, see *Carry-over* below.
- **"Limit once per loop."** The ability may be used once between resets, **even across different nodes of the same loop.** *(This is the one limit the base game does not have; it requires the mod to persist the used-flag across nodes and clear it on reset — see §E.)*
- **Memory.** A resource represented by tokens on investigator/asset cards and a shared **banked Memory** value on the campaign log. Memory on cards is added to banked Memory during the **interlude** after each node. Banked Memory is **spent as experience — level-ups at 1 Memory per card level, plus Recollections at their listed cost.** At the start of each loop, banked Memory above **18** (6 × investigators) is lost.
- **Recollection.** A player-card trait. Recollection cards are added to a deck only by spending banked Memory during an interlude (they are the campaign's XP-analog). Investigator deckbuilding lines grant Recollection access to all five.
- **Dissonance.** A shared campaign track, 0–12. Raised when investigators act on foreknowledge. Drives the chaos bag and the Appointed (design §1.4). **Start-of-loop Dissonance = the number of completed loops so far (the "scar"), to a maximum of 4.** Within a loop it only rises unless a card reduces it.
- **Hourglass.** The shared loop clock. It advances by time and by **Skip** effects, and is spent/rewound only by specific cards, always at a Dissonance cost.
- **Static** (`[static]`). A token added to the chaos bag at Dissonance 4+. Modifier **−3**; its symbol effect: *after this token is revealed, raise Dissonance by 1.* (The glitch feeds itself.)
- **Echo.** A non-Elite enemy subtype (townsfolk repeating their last moments).
- **The Appointed.** The Elite enemy aspect of the entity. It occupies an **Approach** stage (Unseen → Sensed → Emerging → Arrived), driven up by the clock and the Dissonance bands; it manifests on the board while Sensed or later. **It cannot be defeated, only Held Back** — pushed back one stage, rewinding the Hourglass. *(Full rules: `CO-002` / `encounter v0.4 §5`; supersedes this doc's original "enters play at Dissonance 8+" spawn model.)*
- **Carry-over.**
  - *Between nodes of the same loop:* board state resets (damage, in-play cards, resources) **except** Memory on cards, banked Memory, Dissonance, the Hourglass, the Knowledge Track, and all "once per loop" flags, which persist.
  - *Across a reset:* banked Memory (soft-capped), the Knowledge Track, and campaign-log flags persist; Dissonance drops to the new scar value; the Hourglass resets; "once per loop" flags clear.
- **Knowledge (fact).** Unlocked by **completing a node objective**, never purchased. *(This corrects an inconsistency in the design doc: Memory is spent as experience (level-ups + Recollections); facts are earned by play, never purchased.)*

---

## §B. The five investigators

Stat line order: `[wil / int / com / agi]`. Numbers are tuned against the simulation in §D and are provisional pending table play.

### B1 · ELIAS WARDE — "The Ninth Death" · Guardian
*Believer. Warden.* — `3 / 2 / 4 / 3` — Health **9**, Sanity **5**

**Ability (two triggered clauses):**
> `[reaction]` When another investigator at your location would take 1 or more damage that is **not** direct damage: Elias takes that damage instead, then place 1 Memory on Elias. **Limit once per round.**
>
> `[reaction]` If you are the only investigator at your location, after Elias takes 1 or more damage from an enemy: place 1 Memory on Elias. **Limit once per round.**

**⭐ Elder Sign — modifier +1:** If there are 3 or more Memory on Elias, this token is **+3** instead, and heal 1 damage from Elias.

**Deckbuilding:** Guardian cards level 0–5, Neutral 0–5, up to 5 Survivor cards level 0–2, and any number of Recollection cards. Deck size **30**.

> **Wording note.** (1) Redirect is an **interrupt** (`When…would`), the only timing where "instead" is legal; using "After" here would be unresolvable. (2) It is restricted to **another** investigator so it can't self-trigger for free Memory in true solo — that exploit is instead replaced by the explicit second clause, which requires *actually taking enemy damage* and is capped once/round. (3) "**not direct damage**" prevents redirecting effects that are balanced around being unpreventable. (4) The ability is `[reaction]`/optional, not **Forced**, because it says "may" in spirit — a Forced ability cannot be optional.

---

### B2 · DR. AYAKO SŌMA — "The Translator" · Seeker
*Scholar. Chronicler.* — `3 / 5 / 1 / 3` — Health **5**, Sanity **8**

**Ability:**
> After you succeed at an `[int]` skill test: place 1 Memory on Ayako. **Limit once per turn.**
>
> During each interlude, you may move any amount of Memory from Ayako to your banked Memory.

**⭐ Elder Sign — modifier +2:** Draw 1 card. If it is a Recollection, it costs 2 less to play this turn.

**Deckbuilding:** Seeker 0–5, Neutral 0–5, up to 5 Mystic cards 0–2, any number of Recollection cards. Deck size **30**.

> **Wording note.** "Succeed at an `[int]` test" (not "attempt") ties the trigger to the resolution step, so it can't double-fire on cancelled/redone tests. **Limit once per turn** (not per round) matters in multiplayer: it caps her to one Memory per *her* turn, preventing her from farming off other players' `[int]` tests. The interlude clause is the only route from card-Memory to banked Memory for her, keeping the soft cap meaningful.

---

### B3 · CASS LINDQVIST — "The Card Counter" · Rogue
*Criminal. Drifter.* — `2 / 3 / 3 / 5` — Health **7**, Sanity **6**

**Ability:**
> `[free]` Once per turn, spend 2 resources to **call the tide**: predict a chaos token symbol. The next time you reveal the predicted symbol during a skill test **you** perform this round, cancel that token (treat it as a 0-modifier token with no symbol effect) and place 1 Memory on Cass.

**⭐ Elder Sign — modifier +1:** Gain 1 resource for each Memory on Cass (maximum +3 resources).

**Deckbuilding:** Rogue 0–5, Neutral 0–5, up to 5 cards of any other class at **level 0**, any number of Recollection cards. Deck size **30**.

> **Wording note.** Bounded to "a skill test **you** perform" so she doesn't police the whole table's bag (a strength creep in multiplayer) and so solo/multi behave identically. "**Cancel** … treat as 0-modifier with no symbol effect" is the precise definition of cancelling a token — this blocks the reading where a cancelled Static still raises Dissonance. Cost is paid **up front** (2 resources on the call, not on the hit), so a whiffed prediction still costs her — this is what keeps the §D combo at 94%, not 100%.

---

### B4 · SERAPHINE VALE — "The Medium" · Mystic
*Sorcerer. Cursed.* — `5 / 3 / 2 / 2` — Health **6**, Sanity **8**

**Ability:**
> During your turn, you may raise Dissonance by 1 to choose one: this investigator gets +2 to a skill test she is performing; **or** take an additional action this turn; **or** ready one Spell asset you control. **Limit twice per round.**

**⭐ Elder Sign — modifier equal to current Dissonance (maximum +5):** After this skill test, reduce Dissonance by the amount this token added.

**Deckbuilding:** Mystic 0–5, Neutral 0–5, up to 5 Seeker cards 0–2, any number of Recollection cards. Deck size **30**.

> **Wording note.** "**raise Dissonance by 1**" is the cost — framed as paying into a shared track, so it's legible and can't be prevented by damage-prevention effects. **Limit twice per round** hard-caps her tempo engine; the sim shows even at max use she wakes the Appointed in 2–4 rounds, so the limit plus the self-inflicted Dissonance are the two brakes. The elder sign **reduces by the amount it added** (a self-consistent "spend the paradox" purge) and is capped +5 so it can't scale to absurdity in the late game when Dissonance floors are high.

---

### B5 · "BIRDIE" OKONKWO — "The One Who Wandered" · Survivor
*Drifter. Wayward.* — `3 / 3 / 2 / 4` — Health **6**, Sanity **7**

**Ability:**
> After you fail a skill test by 2 or more, place 1 Memory on Birdie. **Limit once per round.**
>
> `[free]` Once per scenario, remove 3 Memory from Birdie: change a skill test you just failed into a success.

**⭐ Elder Sign — modifier +1:** If you have already failed a skill test this round, this token is **+3** instead.

**Deckbuilding:** Survivor 0–5, Neutral 0–5, up to 5 cards of any class at level 0–1, any number of Recollection cards. Deck size **30**.

> **Wording note.** **Limit once per round** on the Memory gain closes the fail-farm loop (you can't repeatedly auto-fail cheap tests in one round to mint Memory); the sim already showed intentional failing is tempo-negative, this makes it airtight. The save ability triggers on a test "you **just failed**" — the fixed window after failure is determined but before its results are applied, matching the game's standard "after failure" reaction window (the `Lucky!`/`Take Heart` timing).

---

## §C. Signatures, weaknesses & the Recollection pool

### C1 · Signature assets & events (per investigator)

**THE AMBERGROVE LAMP** — *Asset. Item. Tool.* Unique. Cost 2. (Elias)
> While the Ambergrove Lamp is in play, each investigator at your location gets +1 `[agi]` while evading.
> `[action]`, exhaust, raise Dissonance by 1: Look at the top card of the encounter deck of a location connected to you. You may then move to that location.
> **Wording note.** The lamp's "look" is an `[action]` (not free) so it can't be chained with Elias's soak into a repeatable no-cost scout; the Dissonance cost is what pays for foreknowledge, consistent with pillar 2.

**"I'VE DONE THIS BEFORE"** — *Skill.* Signature. (Elias)
> Commit only to a skill test. If you have already **failed** a skill test of the same type (`[wil]`/`[int]`/`[com]`/`[agi]`) this scenario, this card provides `[wild][wild][wild]`; otherwise it provides `[wild]`.
> **Wording note.** "same **type**, this scenario" is checked at commit; because a scenario is a node, this resets between nodes even within a loop, which is intended (each node is a fresh attempt).

**THE LEXICON OF THE HOUR** — *Asset. Tome.* Unique. Cost 2. (Ayako) — starts with 0 secrets.
> After you succeed at an `[int]` test by 2 or more: place 1 secret on the Lexicon (max 5).
> `[action]`? No — `[free]`, exhaust, spend 1 secret: choose one — get +2 to an `[int]` test you are performing; **or** cancel the "when revealed" effect of a non-Elite **Static** treachery.
> **Wording note.** The `[free]` + exhaust means one use per round despite being free; "cancel the *when revealed* effect" is scoped so it can't retroactively cancel a Static token already drawn (a token and a treachery are different objects — this prevents a category error at the table).

**"IT MEANS 'WAIT'"** — *Event.* Signature. Fast. Cost 0. (Ayako)
> Play when you would be affected by a card in the **Occultation** or **The Appointed** encounter set. If you have 3 or more banked Memory, cancel that effect.
> **Wording note.** "Play when you **would be** affected" is an interrupt so the cancel is legal; gating on **banked** (not card) Memory ties her defensive tech to campaign progress and prevents a turn-one blank.

**MARKED DECK** — *Asset. Item. Illicit.* Unique. Cost 1. (Cass)
> `[free]` Exhaust: Look at the next chaos token you would reveal this round.
> `[free]` Exhaust, raise Dissonance by 1, remove 1 Memory from a card you control: Seal a non-symbol chaos token from the bag until the end of the round.
> **Wording note.** Two `[free]` exhaust abilities on one card means only **one** fires per round (shared exhaust) — this is the intended brake on the Cass engine. "non-symbol" prevents sealing away the auto-fail/elder-sign, which would warp the bag too hard.

**"SEEN THIS HAND BEFORE"** — *Event.* Signature. Fast. Cost 1. (Cass)
> Play when a chaos token is revealed during your skill test: cancel that token and gain 2 resources. If the cancelled token was a symbol token, gain 3 resources instead.
> **Wording note.** Interrupt timing ("when … revealed") required for the cancel. Costs a card + 1 resource, which is exactly why the simulated engine lands at 94%/+0.5 resources rather than becoming a free auto-win money printer.

**THE BELL OF AMBERGROVE** — *Asset. Relic.* Unique. Cost 3. (Seraphine) — 3 charges.
> `[action]`, exhaust, spend 1 charge, raise Dissonance by 1: Advance **or** rewind the Hourglass by 1 Hour.
> **Wording note.** `[action]` (not free) so clock manipulation costs a real action; pairing an `[action]` with the twice-per-round ability means she can't loop clock-rewind + extra-action into stalling forever without flooding Dissonance.

**"I REMEMBER THE ENDING"** — *Event. Spell.* Signature. Cost 2. **Limit once per loop.** (Seraphine)
> Test `[wil]` (X = current Dissonance). If you succeed: look at the top 3 cards of the Occultation deck and put them back in any order; the next time the Hourglass would advance this round, cancel that advance.
> **Wording note.** Difficulty scales with Dissonance, so it gets *harder* to see the ending the more the loop has noticed you — a self-balancing spell. **Once per loop** (not per scenario) is deliberate and is the flag §E must persist across nodes.

**LUCKY COMPASS** — *Asset. Item. Charm.* Unique. Cost 1. (Birdie)
> `[action]` Exhaust: Move to a connecting location. This move does not provoke attacks of opportunity.
> If there are 2 or more Memory on the Lucky Compass, the above action may instead move you to any revealed location you have a **Knowledge** fact about.
> **Wording note.** The upgrade is a *replacement of the destination*, not a second action, so it can't be read as granting two moves. "revealed location you have a Knowledge fact about" is checked against the campaign log.

**"I GET OUT"** — *Event.* Signature. Fast. Cost 0. **Limit once per loop.** (Birdie)
> Play when Birdie would be defeated: instead, disengage from all enemies, move to a connecting location, then heal 1 damage and 1 horror and place 1 Memory on your Lucky Compass.
> **Wording note.** Defeat-replacement is an interrupt ("would be defeated … instead"), the standard template for "cheat death" effects. **Once per loop**, not per scenario, so it can't rescue her at every node of a long loop — the loop remembers she already slipped out once.

### C2 · Signature weaknesses

**THE EIGHTH GRAVE** — *Treachery. Weakness.* (Elias)
> Revelation — Take 1 horror for each Memory on Elias (maximum 4). If there is no Memory on Elias, instead search the encounter deck and discard pile for an **Echo** and spawn it engaged with you.
> **Wording note.** Bounds horror at 4 so a Memory-flooded Elias isn't one-shot; the "no Memory" branch guarantees the weakness still bites early game when it would otherwise whiff.

**UNTRANSLATABLE** — *Treachery. Weakness.* (Ayako)
> Revelation — Take horror equal to half your banked Memory, rounded up (maximum 5).
> **Wording note.** Scales with **banked** Memory (campaign log), making it a genuine tension on her core identity (knowing more hurts more), capped at 5 so a late-campaign Ayako isn't auto-insane.

**THE HOUSE ALWAYS WINS** — *Enemy. Weakness.* Hunter. (Cass)
> Spawns at the location with the most clues (you choose if tied). While Cass has more Memory on her cards than any other investigator, The House Always Wins cannot be evaded.
> Forced — When The House Always Wins defeats an investigator: that investigator's controller loses 3 banked Memory.
> **Wording note.** The evade-lock references **on-card** Memory (an in-scenario, visible value) so it's checkable mid-fight; the defeat penalty hits **banked** Memory (the campaign resource) so the debt is paid in the currency that matters. Two different Memory pools, named explicitly to avoid ambiguity.

**THE DEBT OF HOURS** — *Treachery. Weakness.* (Seraphine)
> Revelation — If Dissonance is in the **Noticed** band: advance the Appointed's Approach by 1 stage. If in the **Glitch** band: take 2 horror. If in the **Calm** band: raise Dissonance by 1.
> **Wording note.** Every branch does *something* (no dead draw), and the branches read the current band at reveal — the escalating punishment mirrors her own risk appetite. *(CO-002: the top branch now pushes the staged Approach instead of spawning; bands replace the original 8+/4–7/0–3 absolute thresholds so it scales with player count.)*

**NOBODY BELIEVES HER** — *Treachery. Weakness.* (Birdie)
> Revelation — Until the end of the round, card abilities controlled by other investigators cannot target Birdie or her cards, and other investigators cannot take actions that would resolve effects on Birdie or her cards. If Birdie is the only investigator at her location, take 1 horror.
> **Wording note.** "cannot **target** … cannot take actions that would resolve effects on" is deliberately two-pronged to cover both targeted effects and untargeted "help" (e.g., an ally healing everyone at a location) — the loophole a single clause would leave open.

### C3 · The Recollection pool (cross-class, Memory-bought)

All have trait **Recollection.** Costs shown are the **Memory** price to add to a deck, then the resource cost to play. Upgraded variants (in brackets) cost more Memory and replace the base.

| Card | Type | Memory | Text (templated) | Key wording guard |
|---|---|---|---|---|
| **Foreknowledge** | Skill | 3 | Commit. `[wild]`. Remove 1 Memory from a card you control: this card provides `[wild][wild][wild]` instead. | "instead" = the icons don't stack; one Memory, one upgrade. |
| **Déjà Vu** | Event · Fast | 4 | Play after you resolve a card ability during your turn; raise Dissonance by 1: trigger that same ability again if able. | "if able" prevents forcing an illegal re-trigger; Dissonance cost gates the abuse. |
| **Muscle Memory** | Skill | 3 | Commit. If your campaign log shows you performed this test type during the previous loop, `[wild][wild]` and draw 1 card; otherwise `[wild]`. | Reads a **log flag**, not board state — §E must record per-loop test-type flags. |
| **Rehearsed Escape** | Event | 3 | Once per loop. Raise Dissonance by 1: automatically evade one enemy engaged with you (no test). | "no test" is explicit so it can't be boosted/failed; once-per-loop flag persists across nodes. |
| **The Long Way Round** | Event | 2 | Move up to 2 connecting locations. This move ignores attacks of opportunity and any **Skip** effects that would trigger from moving. | Names Skip explicitly to pre-empt the "does moving trigger the Hourglass" question. |
| **Borrowed Time** | Asset | 4 | Uses (3 Memory). `[free]` Exhaust, remove 1 Memory from Borrowed Time: gain 1 resource **or** get +1 to a skill test you are performing. | Uses-as-Memory keeps it self-contained; `[free]`+exhaust = once/round. |
| **This Time For Sure** | Event | 4 | Play after you fail a skill test; raise Dissonance by 1: retry that test once with a +2 bonus. | "retry that test once" bounds it to a single re-attempt; interrupt not needed (after-fail reaction). |
| **Anchor Point** | Asset · Permanent | 3 | At the start of each loop, gain 1 Memory. | Permanent + start-of-loop hook; a single fixed thing you always remember. |
| **Cassandra's Notebook** | Asset · Tome | 4 | `[reaction]` After you unlock a Knowledge fact: draw 2 cards. Limit once per loop. | Ties card draw to the progression system without becoming a per-node engine. |
| **The Hour I Learned Your Name** | Event · Spell | 5 | Deal damage to the Appointed equal to the number of Knowledge facts you have about it (see its card), then rewind the Hourglass by 1. Limit once per loop. | Damage sourced from the log; only meaningful once you've done the investigation — anti-blank. |

---

## §D. Balance findings (from in-engine simulation)

Ran a chaos-bag + economy simulation (20k–40k trials per test). Headlines:

- **Success curve is authentic:** ≈25% at delta 0, ≈56% at +1, ≈75% at +2 (calm bag). Dissonance squeezes *marginal* tests (delta 0–2 drop ~10 pts at "noticed") without touching overkill tests — the intended pressure shape.
- **Dissonance pacing is locked:** from a fresh loop, cautious play reaches the Appointed (8) in ~15 rounds (i.e., usually not within a node), greedy play in ~6 and self-destructs (12) by ~9. Late-loop scar floors compress this appropriately (floor 4 greedy: ~3 rounds).
- **Memory economy (post-fix):** ~14 banked/loop 2-handed (soft cap 15 wastes only 19% of the time), ~10 true-solo → **~2–4 Recollections/loop**. This is the XP-analog curve I wanted.
- **Combos are strong-but-bounded:** Cass's full engine → 94% on her key test + ~0.5 resource/test at a cost of cards/Dissonance/Memory. Birdie fail-farm is tempo-negative. Seraphine's engine self-limits via forced Dissonance. **No infinite loops, no ~100% trivialization.** Combos allowed, as requested.
- **Table-size caveat:** the cast is tuned for **2-handed** (your likely mode). True-solo is playable but Elias (protector) and Ayako (no combat) are visibly built for a partner. Recommend 2-handed as the default; I added Elias's second clause specifically so he still earns Memory alone.

*All numbers provisional until table play; the simulation validates the math, not the fun.*

---

## §E. What this needs from the build (and the Claude Code handoff)

Everything above is **data-first** — it drops into SCED as `Card` objects + `GMNotes` metadata and behaves, **except** the custom-timing pieces below, which need Lua. This is the natural point to hand to **Claude Code**, because it's now a defined engineering task against a real repo, not open-ended design.

**Data-only (no Lua):** all stat lines, icons, costs, traits, health/sanity, signatures/weakness links, uses/charges/secrets, permanent/Fast, deckbuilding metadata.

**Needs Lua (scoped):**
1. **Memory token** helper (reuse existing counter system) — Low.
2. **Dissonance track** object + `[static]` token that raises it on reveal + chaos-bag banding — Medium.
3. **Hourglass** shared clock with advance/rewind API — Medium.
4. **Campaign state persistence:** banked Memory (soft cap 15), Dissonance scar-on-reset, Knowledge flags, **per-loop test-type flags** (for Muscle Memory), and **"once per loop" flag persistence across nodes** — High. This is the single most important custom system; several cards above are meaningless without it.
5. **The Appointed** enemy (Dissonance-gated spawn, delay-not-defeat) — High.
6. **Location front/back toggles** driven by Knowledge facts — Medium–High.

**If you want to hand this to Claude Code**, the clean brief is: *"Fork argonui/SCED. Implement a `StillHour` campaign module: (a) a Dissonance/Memory/Hourglass state manager persisted in campaign save; (b) a `[static]` chaos token; (c) once-per-loop and per-loop-flag bookkeeping surviving node transitions; (d) the Appointed enemy behavior; (e) location fact-toggles. Cards themselves are authored as JSON with the `GMNotes` schema already in the mod."* I can write that brief out in full, plus the card JSON, whenever you're ready to move over.

---

### Open items still on me
- Full **encounter card text** (Occultation deck, Echoes, Static treacheries, the Appointed's card) — same errata-grade pass.
- The **six node objectives** + finale generator table.
- The **campaign guide** (branching narrative + resolutions + log sheet).
- Your call on **finale bleakness** and whether to lock **2-handed** as the assumed player count.
