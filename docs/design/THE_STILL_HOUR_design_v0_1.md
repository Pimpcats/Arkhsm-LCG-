# THE STILL HOUR
### A custom campaign for Arkham Horror: The Card Game (SCED / Tabletop Simulator)
**Design document v0.1 — investigators, systems, and campaign arc**

> An original cosmic-horror campaign built around one idea no published campaign uses: **the night does not end.** The town of Ambergrove is caught repeating the same span of hours. Five people remember. Everyone else does not.

---

## 0. High concept

On the night of the **Occultation** — a rare astronomical event the almanacs got wrong by exactly one hour — something that lives *outside* time tried to arrive in Ambergrove. It did not finish. The night has been repeating ever since, snagged on the moment of its almost-arrival, and each loop it gets a little closer to finishing the crossing.

The five investigators were standing too close when it first reached through. They are **unstuck**: they carry memory across the resets. Everyone else in Ambergrove lives the same hours over and over, blind. The campaign is the investigators' attempt to understand the loop, weaponize their memory of it, and end it — before the thing they call **The Latecomer** finally arrives on time.

### Design pillars
1. **Memory is progression.** You don't get stronger by winning scenarios in a line. You get stronger by *remembering*. Death is not the end of the campaign; it is the end of a loop.
2. **Foreknowledge is a currency, and using it has a cost.** Acting on what you remember builds **Dissonance** — and Dissonance is how the loop notices you.
3. **The map is the same; you are not.** Locations recur, but what you can *do* at them expands as your Knowledge Track fills. Non-linear unlocking, roguelite-flavored, inside a card game.
4. **Every system is diegetic.** No mechanic is bolted on. The clock, the memory, the paradox — they are all the loop.

---

## 1. The new systems (the heart of the design)

Five interlocking systems. Two are lightweight; three are the reason this campaign exists. Section 7 maps each to what SCED can do out of the box vs. what needs custom Lua.

### 1.1 Memory (persistent campaign currency)
- Represented by **Memory tokens** on investigator cards and a campaign-log total.
- Earned by surviving key events, solving mysteries, witnessing "anchor moments," and via certain investigator abilities.
- **Kept across loops** (across scenarios). This is the spine.
- Spent between loops (campaign interlude) as **experience — level-ups at 1 Memory per card level, plus Recollections at their listed cost** (see 1.2). *(Knowledge facts are earned by completing objectives, never purchased.)*
- Soft cap encourages spending: at the start of each loop, Memory above **10** is lost ("you can only hold so much of a night in your head").

### 1.2 Recollections (a new cross-class player-card pool)
- A shared archetype of player cards representing loop-knowledge. Any campaign investigator may include **Recollection** cards regardless of class (their deckbuilding lines grant this).
- You do not start with them. You **buy Recollections into your deck** during interludes by spending Memory. This is the campaign's equivalent of XP — but earned by remembering, not by scenario victory.
- Mechanically they reward *repetition*: "if you did X last loop," "after you fail a test you've failed before," "cancel a token you've seen this loop." Full pool in §5.

### 1.3 The Knowledge Track (non-linear unlock web)
- A campaign-log web of **facts** about Ambergrove (e.g., *The lighthouse lamp was never lit that night*, *The bell tolled thirteen times*, *The sheriff is already dead*).
- Each fact is a node you unlock by completing a specific objective in some loop. Unlocked facts **persist** and change future setups: they open locations, remove encounter cards, reveal shortcuts, or gate the finale's resolutions.
- You physically cannot finish the campaign in one loop. The track *requires* looping — but a smart run needs fewer loops.

### 1.4 Dissonance (the risk track)
- A shared campaign track (0–12) that rises when investigators **act on foreknowledge**: playing Recollections, using loop-aware abilities, skipping content you "already did."
- Dissonance drives the **chaos bag** (replaces raw difficulty scaling) and wakes **The Latecomer**:
  - **0–3** — the loop is calm. The Latecomer sleeps.
  - **4–7** — glitches. Add ↷ (Static) tokens; Echoes begin to hunt.
  - **8–11** — the loop *notices you*. The Latecomer enters play as a Hunter.
  - **12** — the night ends early. Immediate hard reset (loop failure), but you keep Memory.
- Central tension: your memory is your only edge, and using it is the thing that gets you killed.

### 1.5 The Hourglass (shared continuous clock)
- One shared clock token advancing along a track of **Hours** (functionally a persistent agenda that spans the whole loop, not one scenario).
- Advances via time, via **Skip** treacheries, via certain actions. When it reaches the last Hour, the loop resets.
- Uniquely, it is a **resource you can touch**: a few cards/abilities let you *spend* or *rewind* the Hourglass — always at a Dissonance cost. The Mystic is built around this.

---

## 2. Campaign structure

Rather than 8 linear scenarios, THE STILL HOUR is a **prologue + an open middle of recurring "Hours" + a variable finale.** Think of the middle as a small point-crawl map you re-enter each loop, spending a limited Hourglass to visit a few nodes per pass.

### Prologue — "The First Hour" (linear, ~45 min)
You don't yet know it's a loop. A straight scenario through the Occultation. It ends, no matter what, in the **first reset** — scripted defeat that *feels* like loss but banks your first Memory and unlocks the loop framing. Teaches Memory and Dissonance gently.

### Act I — "Learning the Rules" (loops 1–3)
The Ambergrove map opens: **The Lighthouse, The Drowned Church, The Sunken Road, Town Hall, The Fairground, The Almanac House.** Each is a self-contained set-piece (mini-scenario) with its own objective and a Knowledge Track node. Each loop you get an Hourglass budget to visit **2–3** nodes. You choose the route. Cracking a node's mystery unlocks its fact permanently. Dissonance introduced as a temptation, not yet a threat.

### Act II — "The Shape of the Hour" (loops 4–6)
The Latecomer becomes aware (Dissonance-gated). Echoes hunt across nodes. New "deep" objectives appear at nodes you've already cracked (the second layer). You learn *why* the loop exists and *who* opened the door (Seraphine's thread). A **point of no return**: once enough of the Knowledge Track is lit, you may attempt the finale — or keep looping to prepare, trading Dissonance for readiness.

### Finale — "The Last Hour" (variable)
Setup is **generated from the campaign log**: which facts you know, total Memory, current Dissonance, who has died, and key choices. The finale has **multiple resolutions**, e.g.:
- **Close the door** — end the loop cleanly (requires enough Knowledge).
- **Take its place** — one investigator becomes the new anchor of the Hour (a bittersweet win; that investigator is "kept").
- **Let it in, on your terms** — a Faustian resolution unlocked only by high Memory + specific facts.
- **The loop wins** — but sufficient banked Memory seeds a hidden "you'll get it right next time" true-ending epilogue. Even total loss is not wasted.

### Chaos bag
Progresses with **Dissonance**, not a fixed difficulty ladder. A reference table maps each Dissonance band to token adjustments and to the new **↷ Static** token behavior. (Standalone difficulty presets still provided.)

### Campaign log fields
Memory (banked) · Dissonance · Recollections owned · Knowledge Track (facts flagged) · The Dead (who, which loop) · Anchor Choices · "Who Remembers What" (per-investigator flags).

---

## 3. Encounter design (sketch)

New encounter sets themed to the loop. Full card lists come after the arc is signed off; representative cards below.

- **The Latecomer** *(the boss aspect)* — Elite. Hunter. **Cannot be defeated, only delayed.** Enters play at Dissonance ≥ 8. Its fight/evade attempts don't kill it; they buy Hourglass room. Scales with Dissonance.
- **Echoes** *(townsfolk repeating their last moments)* — non-Elite enemies frozen mid-gesture; harmless until Dissonance rises, then they turn.
- **Static** *(reality glitching)* — treacheries: **Skip** (advance the Hourglass), **Rewind** (redo a bad thing you just did), **Wrong Turn** (the map shifts — swap two locations), **Familiar Stranger** (an Echo attacks the investigator with the most Memory).
- **The Occultation** *(the clock deck)* — the encounter cards that drive the Hourglass and the reset.
- **Unremembered** *(locations)* — Ambergrove nodes with a **front (this loop)** and **back (once you Know the fact)**; the fact flips the location to a more navigable version.

---

## 4. The five investigators

One per core class. Each remembers the loop for a different reason, and each has a mechanical identity that hooks into the systems above. Stat lines are `[Willpower / Intellect / Combat / Agility]`. Balance is first-pass and **needs playtesting** — numbers are deliberately conservative.

---

### 4.1 ELIAS WARDE — "The Ninth Death"  · Guardian
*Lighthouse keeper of Ambergrove. He has died in this night more times than anyone, and he keeps standing between the town and the dark.*

- **Class:** Guardian **Traits:** *Believer. Warden.*
- **Stats:** `3 / 2 / 4 / 3` **Health:** 9 **Sanity:** 5
- **Ability:** Forced — After another investigator at your location would take damage: You may take that damage instead. When you do, place 1 Memory on your investigator card.
- **⭐ Elder Sign (+1):** If you have 3+ Memory, this is +3 instead and heal 1 damage.
- **Deckbuilding:** Guardian cards (level 0–5), Neutral cards (0–5), up to 5 Survivor cards (0–2), Recollection cards (any). Deck size 30.

**Signatures**
- **The Ambergrove Lamp** — *Asset. Item. Tool.* Unique. Cost 2. A lamp that remembers the safe path. While in play, investigators at your location get +1 to evade. *Exhaust, take 1 Dissonance:* reveal the top card of the encounter deck at a connecting location before you move there (light drives the dark back — but the loop sees the light).
- **"I've Done This Before"** — *Skill.* Signature. Commit to a skill test. If you have already **failed** a test of this type this scenario, this skill is worth **+3** (else +1). *(You learn from your deaths.)*

**Weakness**
- **The Eighth Grave** — *Treachery. Weakness.* Revelation — You remember every time you did not come back. Take 1 horror for each Memory on your investigator card (max 4). If you have no Memory, instead search the encounter deck for an **Echo** and spawn it engaged with you.

---

### 4.2 DR. AYAKO SŌMA — "The Translator" · Seeker
*A linguist who came to Ambergrove chasing a dead language — and found it being spoken by the night itself. She is trying to read what the Latecomer is saying.*

- **Class:** Seeker **Traits:** *Scholar. Chronicler.*
- **Stats:** `3 / 5 / 1 / 3` **Health:** 5 **Sanity:** 8
- **Ability:** Once per turn, when you succeed at an [intellect] test: place 1 Memory on this card. (You are always taking notes.) During each campaign interlude, you may convert Memory on this card 1-for-1 into banked campaign Memory.
- **⭐ Elder Sign (+2):** Draw 1 card. If it is a **Recollection**, reduce its cost this turn by 2.
- **Deckbuilding:** Seeker (0–5), Neutral (0–5), up to 5 Mystic cards (0–2), Recollection cards (any). Deck size 30.

**Signatures**
- **The Lexicon of the Hour** — *Asset. Tome.* Unique. Cost 2. Starts with 0 **entries** (uses). After you succeed at an [intellect] test by 2+, add 1 entry (max 5). *Exhaust, spend 1 entry:* choose one — get +2 to an [intellect] test, **or** cancel a non-Elite **Static** treachery's effect (you translated it in time).
- **"It Means 'Wait'"** — *Event.* Signature. Fast. Cost 0. Play when you would be affected by a card in the **Occultation** or **The Latecomer** set. If you have 3+ Memory, cancel that effect. *(Some of it is just a request to hold on.)*

**Weakness**
- **Untranslatable** — *Treachery. Weakness.* Revelation — Some words unmake the reader. Take horror equal to half your banked Memory, rounded up (max 5). The more of the night you carry, the more it costs to look directly at it.

---

### 4.3 CASS LINDQVIST — "The Card Counter" · Rogue
*A gambler who was passing through and figured out the night resets three drinks before anyone else. She has been running the same hours for profit — and she's very good at it.*

- **Class:** Rogue **Traits:** *Criminal. Drifter.*
- **Stats:** `2 / 3 / 3 / 5` **Health:** 7 **Sanity:** 6
- **Ability:** Once per turn, spend 2 resources to **call the tide**: name a chaos token symbol. The next time you reveal that symbol this round, cancel its effect (resolve as +0) and place 1 Memory on this card.
- **⭐ Elder Sign (+1):** Gain 1 resource for each Memory on this card (max +3 resources).
- **Deckbuilding:** Rogue (0–5), Neutral (0–5), up to 5 cards of any other class at **level 0**, Recollection cards (any). Deck size 30.

**Signatures**
- **Marked Deck** — *Asset. Item. Illicit.* Unique. Cost 1. *Exhaust:* look at the next chaos token you would reveal this round before you commit cards. *Exhaust, take 1 Dissonance, remove 1 Memory from a card you control:* seal a non-symbol token from the bag until the end of the round (you already know how this hand plays).
- **"Seen This Hand Before"** — *Event.* Signature. Fast. Cost 1. Play when a chaos token is revealed during your skill test: cancel it and gain 2 resources. If it was a symbol token, gain 3 instead.

**Weakness**
- **The House Always Wins** — *Enemy. Weakness. Hunter.* A collector who follows the debt across every loop. Spawns at the location with the most clues. Cannot be evaded while you have the most Memory of any investigator. If it defeats you, you lose 3 banked Memory (the debt is paid in the only currency that matters).

---

### 4.4 SERAPHINE VALE — "The Medium" · Mystic
*A spiritualist who felt the Occultation coming and reached for it — and may be the reason the door is stuck open. She can touch the Hour itself, but every touch leaves a mark.*

- **Class:** Mystic **Traits:** *Sorcerer. Cursed.*
- **Stats:** `5 / 3 / 2 / 2` **Health:** 6 **Sanity:** 8
- **Ability:** During your turn, you may take **1 Dissonance** to choose one: get +2 to a skill test you are performing, gain an additional action this turn, or ready one Spell asset you control. (Limit twice per round.)
- **⭐ Elder Sign (+X):** X = current **Dissonance**. Then set Dissonance to **3** (you spend the paradox all at once — and reset the loop's patience with you).
- **Deckbuilding:** Mystic (0–5), Neutral (0–5), up to 5 Seeker cards (0–2), Recollection cards (any). Deck size 30.

**Signatures**
- **The Bell of Ambergrove** — *Asset. Relic.* Unique. Cost 3. Starts with 3 **charges**. *Exhaust, spend 1 charge, take 1 Dissonance:* advance **or** rewind the Hourglass by 1 Hour. *(The bell marks the Hour. It can also un-mark it.)*
- **"I Remember the Ending"** — *Event. Spell.* Signature. Cost 2. Once per loop. Test [willpower] (X = current Dissonance). If you succeed: look at the top 3 cards of the Occultation deck; you may cancel the next Hourglass advance. *(You have seen how this night ends. Not this time.)*

**Weakness**
- **The Debt of Hours** — *Treachery. Weakness.* Revelation — Paradox comes due. If Dissonance is 8+, put the **Latecomer** into play (or, if already in play, it gets +2 fight and moves toward you). If Dissonance is 4–7, take 2 horror. If 0–3, take 1 Dissonance — you cannot stop reaching for it.

---

### 4.5 "BIRDIE" OKONKWO — "The One Who Wandered" · Survivor
*A young drifter who slipped into Ambergrove the wrong night and shouldn't remember a thing — but she does. Nobody in town believes a stranger. She's used to that.*

- **Class:** Survivor **Traits:** *Drifter. Wayward.*
- **Stats:** `3 / 3 / 2 / 4` **Health:** 6 **Sanity:** 7
- **Ability:** After you fail a skill test by 2 or more, place 1 Memory on this card. Once per scenario, remove 3 Memory from this card to change a skill test you just failed into a success.
- **⭐ Elder Sign (+1):** If you have already failed a skill test this round, this is +3 instead.
- **Deckbuilding:** Survivor (0–5), Neutral (0–5), up to 5 cards of any class at level 0–1, Recollection cards (any). Deck size 30.

**Signatures**
- **Lucky Compass** — *Asset. Item. Charm.* Unique. Cost 1. The needle always points at the way out. *Exhaust:* move to a connecting location; this move ignores attacks of opportunity. If you have 2+ Memory, you may instead move to any revealed location you have a **Knowledge** fact about.
- **"I Get Out"** — *Event.* Signature. Fast. Cost 0. Play when you would be defeated: instead, disengage from all enemies, move to a connecting location, and heal 1 damage and 1 horror. Place 1 Memory on your Lucky Compass. (Usable once per loop.)

**Weakness**
- **Nobody Believes Her** — *Treachery. Weakness.* Revelation — You try to warn them; they look right through you. Until the end of the round, other investigators cannot trigger abilities on **your** assets or take actions to help you (no "ally" effects target you). If you are alone at your location, take 1 horror.

---

## 5. New player cards — the Recollection pool

Cross-class. Bought with Memory during interludes (a Memory→card economy replacing XP). First-pass list; costs/levels tune in playtest. All have the **Recollection** trait.

| Card | Type | Cost | Effect (first pass) |
|---|---|---|---|
| **Foreknowledge** | Skill | — | Commit. +1. Remove 1 Memory from a card you control: +2 more. |
| **Déjà Vu** | Event (Fast) | 1 | Repeat the "when revealed"/reaction window of the last card you resolved this turn. Take 1 Dissonance. |
| **Muscle Memory** | Skill | — | Commit. If you performed this same test type last loop (log flag), it's +2 and draw 1 card. |
| **Rehearsed Escape** | Event | 0 | Evade an enemy without a test (you've done this exact evade before). Once per loop. Take 1 Dissonance. |
| **The Long Way Round** | Event | 1 | Move up to 2 locations; ignore attacks of opportunity and Skip effects. |
| **Borrowed Time** | Asset | 2 | Uses (3 Memory). Exhaust, remove 1 Memory: gain 1 resource **or** +1 to a test. |
| **This Time For Sure** | Event | 2 | After you fail a test: retry it once with +2. Take 1 Dissonance. |
| **Anchor Point** | Asset (permanent) | — | At the start of each loop, gain 1 Memory. Bought once; represents a fixed thing you always remember. |
| **Cassandra's Notebook** | Asset. Tome | 2 | Once per turn, when you unlock a Knowledge fact, draw 2 cards. |
| **The Hour I Learned Your Name** | Event (Spell) | 3 | Deal X damage to the Latecomer where X = facts you Know about it; delays it a full Hour. |

Each has a leveled/upgraded variant purchasable at higher Memory cost, mirroring standard 0→3→5 XP curves.

---

## 6. Sample scenario node (so the middle act is concrete)

**"THE DROWNED CHURCH" — an Ambergrove Hour**
- **Setup:** 4 locations (Nave, Belfry, Flooded Crypt, Vestry). The Belfry holds the **Bell** (ties to Seraphine). The Occultation deck seeds 2 **Skip** and 1 **Rewind**.
- **Objective (loop-1 layer):** Discover why the bell tolled thirteen times. Gather 6 clues → read the register → unlock Knowledge fact **"The Thirteenth Toll."**
- **Deep objective (unlocks after you Know "The Thirteenth Toll"):** The crypt opens. Recover the **Almanac page** → unlock **"The Hour Was Wrong."** This fact removes 1 Skip from the Occultation deck campaign-wide (you stop losing time here).
- **Reward:** +2 Memory; Seraphine may attach the **Bell of Ambergrove** benefit even if her signature is elsewhere this loop.
- **Dissonance interaction:** at 4+, three **Echoes** (drowned congregation) begin as Hunters.

Five more nodes (Lighthouse, Sunken Road, Town Hall, Fairground, Almanac House) follow this two-layer template. That's the whole open middle.

---

## 7. Build & scripting scope map (ties to your SCED file)

From cracking open `Arkham SCE 4.8.0.json`: the engine is data-driven — cards behave off their `GMNotes` metadata, and content ships as JSON pulled by download-box placeholders. So here's what's **free** (metadata only) vs. what needs **custom Lua** when we build.

| System | SCED reality | Effort |
|---|---|---|
| All investigator/signature/weakness/Recollection cards | Standard `Card` objects + `GMNotes` (schema confirmed: `id`, `class`, `type`, `traits`, `cost`, `level`, `*Icons`, `health`/`sanity`, `signatures`, `weakness`, `elderSignEffect`, `uses`, `permanent`…). **Data only.** | Low |
| Standard effects (uses, charges, heal, evade, seal, resources) | Engine already spawns/tracks these from metadata. | Low |
| Memory tokens on cards | Reuse the generic token/counter system already in the mod. | Low |
| **Dissonance track** | New shared counter object + a small Lua module; the mod already draws custom counters, so pattern exists. | Medium |
| **Chaos-bag by Dissonance** | Global Lua already manipulates the chaos bag (bless/curse manager confirmed). Hook Dissonance bands to bag edits. | Medium |
| **The Hourglass (persistent clock)** | New shared token + Lua; behaves like a campaign-spanning agenda counter. | Medium |
| **Memory persistence across scenarios** | SCED has campaign save/log + import/export. Store Memory/Dissonance/Knowledge in campaign state. | Medium |
| **Knowledge Track unlocks flipping location fronts/backs** | Location cards support unique backs already; Lua toggles which face/objective is active per fact flag. | Medium–High |
| **The Latecomer** (Dissonance-gated spawn, undefeatable-only-delayed) | Custom enemy Lua + spawn hooks. | High |
| **Recollection "did you do X last loop" checks** | Needs the campaign log to record per-loop flags; Lua reads them at commit time. | High |
| Distribution | Package as SCED-downloads JSON behind a download-box placeholder (mechanism confirmed in the file: `placeholderDownload` → GitHub release). | Low–Medium |

Nothing here is blocked by the engine. The three genuinely custom pieces are **the Latecomer, the loop-flag bookkeeping, and the Knowledge Track toggles** — all scriptable, all scoped above.

---

## 8. Open design questions (for you)

1. **Tone of the finale — how bleak?** Do you want a clean "you can win" ending as the default, or should the true ending always cost something (an investigator kept behind as the new anchor)?
2. **Party size assumption.** Design the Hourglass budget around 2-player (your usual?) or scale for 1–4?
3. **Recollection economy vs. real XP.** Full replacement of XP with Memory (bold, cohesive), or a hybrid where scenarios still grant some XP and Memory is *additional*?
4. **How punishing should Dissonance be?** Is "using your one advantage gets you killed" the intended vibe, or a gentler risk?
5. **Setting texture.** Inland fog-town (as written) vs. a snowbound valley vs. a coastal town — I kept it inland to avoid overlap with the official *Drowned City* box in your file. Preference?

---

### Next steps once this is signed off
1. Lock the five stat lines + abilities in playtest-ready form.
2. Write the full card text for all signatures, weaknesses, and the Recollection pool.
3. Build the six Ambergrove nodes to full card lists + the finale generator table.
4. Draft the campaign guide (branching narrative + resolutions + campaign-log sheet).
5. Then hand to the build pipeline: Strange Eons frames → art (your SD rig) → `GMNotes` metadata → SCED objects → download-box package.

*Balance note: every number in this document is a first pass written to be conservative and internally consistent, not a playtested value. Treat abilities as directionally locked and numbers as provisional.*
