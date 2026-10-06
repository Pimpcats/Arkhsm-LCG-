# Deckbuilding review (2026-10-06)

Designer-facing; rules text, no campaign spoilers. Scope: each investigator's
deckbuilding options and requirements (signature cards, random weakness)
against the fronts as built (PORTABLE_INVESTIGATORS.md). Method: every official
player card the investigator can legally take (class and level ranges below,
plus the cards their traits open, X1) was pulled from the local library
(tools/library/build_library.py) and searched for loops, stacking and
degenerate partners. The second pass (2026-10-06) is repeatable:
tools/library/synergy_scan.py derives each pool from the printed backs, tags
every card by mechanical feature and by the ability hook it touches, and writes
a card x investigator table (CSV and JSONL); tools/library/synergy_quant.py puts
numbers on the abilities (a stress model with stated assumptions, not the
simulation); tests/test_synergy_scan.py checks both. Nothing here is a
playtest; the "Measured" column fills in from the simulation
(docs/design/FINISHING_BALANCE.md, "Quest cards, 2026-10-06").

Pools scanned (official cards, including the ones the traits open; each pool
also holds the 10 Recollections): Elias 544 (275 at level 0), Ayako 526 (271),
Cass 804 (624), Birdie 916 (624), Seraphine 531 (271). The fan packs the SCED
menu offers (3,795 cards, 1,221-1,940 legal per investigator by class and
level) carry no rules text in the data and were not read (X9).

Status values: **Fixed** (changed in the cards or engine), **Accepted** (left
legal on purpose), **Watch** (legal; the simulation or a playtest decides),
**Rejected** (an option considered and not taken), **Change (pending)** (an
edit is proposed or made but is not in the shipped build yet; it becomes Fixed
once it is).

Corrections: the first version of this review did not scan Cass's pool and said
"no degenerate partner found"; it also missed that Seraphine's horror cost could
be soaked by an Ally. Both were found in a second scan and are recorded below.
The second pass corrected six more points in the first two versions:

1. Cass's pool is 804 official cards (624 at level 0) plus 10 Recollections,
   not 998; the 998 counted cards that have no level.
2. "Looping Seen This Hand Before" works only because the spec gave every
   signature card level 0; official signature cards have no level (X2).
3. Key of Ys does not absorb Seraphine's horror cost: direct horror cannot be
   assigned or re-assigned elsewhere (Rules Reference, Direct Damage, Direct
   Horror). It still absorbs her ordinary horror.
4. Bide Your Time is not an extra-action stacker: it costs the play action plus
   an additional action for two actions next turn, a net zero.
5. Seraphine's pool has 42 Ally-trait assets with sanity (55 assets with sanity
   of any trait), not 50.
6. Not recorded before: the cards an investigator's traits open (X1), level 0 on
   signature data (X2), the Memory economy (X3), experience-granting cards
   (X4), exile (X5), cards priced in trauma or defeat (X6) and teleports against
   district travel (X7).

## Elias Warde (Guardian, spends deck to prevent damage)

Options (unchanged): Guardian 0-5, Neutral 0-5, up to 5 Survivor 0-2. The
Survivor slot is his synergy: Survivor is the class built on the discard pile.
His ability stocks the discard pile at random (he cannot choose what leaves the
deck), so the payoffs are statistical, never a combo he assembles on purpose.
Starter list (docs/STARTER_DECKS.md): Improvised Weapon x2 and Improvised
Shield (played from the discard pile), Scrounge for Supplies x2 (returns a level
0 card).

| Combo | Verdict | Status |
|---|---|---|
| His prevention plus Guardian cancel/soak (Flesh Ward, "I've had worse..." level 2 and 4, Perseverance, Idol of Xanatos, Devil's Luck, Delay the Inevitable, Armor of Ardennes, Sound Support) | His prevention resolves first (between steps 1 and 2 of dealing damage) and the rest trigger on "dealt": the stack is additive, never multiplicative, and each other piece costs a card, a charge or cards from hand. His ability only stops damage, never horror, and horror is his weak side (sanity 5); the stack cannot make him safe | Accepted |
| Short Supply (mills 10 on turn 1), Key of Ys (mills 10 on leaving play) | Self-harm: an empty deck costs 1 horror per reshuffle at sanity 5 | Accepted |
| Pushed to the Limit with a Guardian weapon he milled | Official card, official power: free fight, shuffled back, 2 copies, random fodder | Accepted |
| Respite refilling the deck he spends | Costs an action and a resource, returns level 0 events/skills only | Accepted |
| Milling weaknesses off the top (no revelation) | Same as Yaotl and Short Supply today | Accepted |
| Deck-outs: spending 3 cards a round from a 30-card deck | Stress model (0.7 damage events a round of 1-3 damage): always preventing spends 12.1 cards per 11-round loop, ends 23% of loops with an empty deck and costs about 1 reshuffle (1 horror) a loop; preventing only 2 or more damage spends 8.5 cards and 0.57 reshuffles. The simulation keeps 4 cards in the deck; whether the real policy does is the table's choice. Fallback if it measures badly: cap the ability at 2 cards, or take Versatile (+5 deck size). He is the investigator most at risk of being too weak, not too strong | Watch |
| Damage taken as a cost (Strong-Armed, Smoking Pipe, Spirit of Humanity, Blood Eclipse) | The Rules Reference lets cost damage be reassigned to an asset and still counts the cost as paid; it is silent on prevention. If prevented cost damage also counts as paid, his reaction pays one such cost a round for 1 deck card (a redraw or a heal). Blood Eclipse level 3 counts damage taken, so prevention forfeits its bonus. No loop either way (once per round) | Accepted (ruling: prevented cost damage counts as paid) |
| The Ambergrove Lamp: "you may take 1 horror to put it on the bottom" | Soakable: any of the 46 Ally-trait assets with sanity in his pool can take the horror and the cost still counts as paid (guideline 14) | Change (pending: write "take 1 direct horror") |
| Payoffs that need damage taken (Lesson Learned, Bandages, Rough, Sparrow Mask; 13 cards) | Anti-synergy: damage he prevents never reaches them | Accepted |
| Warden and Believer cards his traits open (X1): Mauser Tankgewehr M1918 (level 5), Sound Support, Cowl of Sekhmet, Memories of Another Life | Official Wardens use them; the Mauser attacks once per 2 actions (+5 combat, +3 damage and a reload), inside the Guardian norm | Accepted |

Requirements: The Ambergrove Lamp, I've Done This Before, The Eighth Grave (he
can pay deck cards to prevent its damage, so it still costs him), What the
Warden Owes.

## Dr. Ayako Soma (Seeker, translation tokens, intellect for attack/evade)

Answer to "is she a fighter-investigator hybrid": in skill, yes; in damage, not
by default. Any success with an enemy at her location tags it (once per round);
a tagged enemy can be attacked or evaded with her intellect 5, so every action
can go to investigating, fighting or evading. Combat 1 and 1 damage per hit
stay as they were.

Options (unchanged): Seeker 0-5, Neutral 0-5, up to 5 Mystic 0-2.

| Combo | Verdict | Status |
|---|---|---|
| Guardian secondary (weapons) | Intellect 5 plus Guardian weapons beats real Guardian fighters while she keeps Seeker investigation | Rejected (Mystic kept, so damage stays the limiter) |
| Her ability with Mind over Matter | Redundant, not broken: it covers untagged enemies for a card and an action | Accepted |
| "I've got a plan!" and Caustic Reaction (up to about 4 damage an action) | Any Seeker can already do this without her ability | Accepted |
| Evading with intellect 5 | A strong evader; evading does not kill enemies | Accepted |
| Kill rate with Mystic-slot weapons (Knife, Kukri, Enchanted Blade) | Needs the simulation. Note that the +combat bonuses on these do not apply to her intellect attacks (next row) | Watch |
| "You may use your [int] in place of your [com] or [agi]" (the Sword Cane template) | Rules Reference and FAQ (Mind over Matter, Sharpshooter): the test uses intellect, so only intellect bonuses apply and only intellect or wild icons can be committed; Knife, Kukri, Enchanted Blade and Spirit Athame add nothing. The other reading (a combat test with an intellect value) would stack them and is the only strong reading. Tagged intellect 5 succeeds as often as a Guardian's combat 4 plus a +1 weapon (70.6 / 41.2 / 23.5% at difficulty 3 / 4 / 5) but deals 1 damage | Watch (add "(it is an [int] test)" or record the ruling) |
| Doom-fed cards (Abyssal Tome, Ceremonial Sickle, Hallowed Chalice; 15 cards put doom on themselves) | Doom on any card counts toward the Hour and clears when the Hour changes, so they speed the clock; Abyssal Tome (+1 skill and +1 damage per doom, up to 3) is her best damage source | Watch |
| Lexicon secrets with margin tools (Inquisitive, Steady-Handed) | "Succeed by 2 or more" earns a secret and spending one gives +2 intellect, which tends to earn it back: about +2 intellect a round, bounded by the exhaust | Accepted |
| Transmogrify (evade with intellect, attach "Massive. Cannot move", 1 clue each time she evades it) | 1 clue a round per attached enemy for an action, the same as investigating | Accepted |
| Researched and Untranslated cards (30 Researched at levels 3-4, 10 Untranslated or Unidentified at levels 0-1) | They need Campaign Log records from other campaigns that this campaign's log does not have: 30 of her 84 level 3-4 cards are dead unless a table writes the record by hand | Change (pending: the guide says they cannot be used) |
| Scholar cards her traits open (X1): Library Pass, Archibald MacVeigh, Inquisitive | Official; Archibald lets Lexicon secrets pay for Insight events, bounded by 4 secrets | Accepted |

Requirements: Lexicon of the Hour (cancel clause once per round), It Means
'Wait' (first clause only), Untranslatable (2 horror, then every translation
token is removed), The Unfinished Translation.

## Cass Lindqvist (Rogue, resources from symbols)

Options: Rogue 0-5, Neutral 0-5, up to 5 cards of any other class at level 0
(804 official cards scanned, 624 at level 0; Jenny Barnes's option).

| Risk | Detail | Status |
|---|---|---|
| Trigger wording | "After you reveal a symbol token" also fired on reveals outside tests (Voice of Ra, Henry Wan, Astral Travel, 21 or Bust) | Fixed: "during a skill test" |
| Token-control stacking | Her cancel, Marked Deck's seal, Seen This Hand Before, Olive McBride (reveal 3, keep 2), Premonition, Heavy Furs, Uncanny Specimen, Contingency, Defiance, Analysis and Skeptic could steer almost every test; Marked Deck's choose-a-number stays once per game (a scenario), which keeps it from every round. Each piece is paid in resources or cards; her cancel names a symbol blind (it shows in 17-31% of 3-test rounds) unless Marked Deck or Premonition shows the next token, and 41% of reveals are symbol tokens (the guide counts every non-number token). Jacqueline Fine cancels 2 tokens a round for free | Watch (fallback: only tokens of 0 or lower) |
| Olive McBride with her elder sign | Two resolved tokens could both be the elder sign (2 resources each) | Accepted (about 1 in 16 per token) |
| Looping Seen This Hand Before | Scrounge for Supplies / Hunter's Instinct (Survivor level 0, legal in her any-class slot) can return it only while the spec gives signature cards level 0 (official ones have none, X2); it costs 1, gains 1-2, and every return costs an action | Change (pending: drop `level` from signature, quest and unlocked cards, X2); otherwise accepted (net about +1 resource an action plus a cancel) |
| The House Always Wins feeds on a resource engine | It cannot be evaded while she holds the most resources, and discards 2 resources when it damages someone | Accepted (self-balancing) |
| The House Always Wins when she plays alone | "More resources than each other investigator" is vacuously true with no other investigator, so it can never be evaded in solo play; every hit still discards 2 resources | Watch (if unintended: "while another investigator is in the game and...") |
| Resource sinks that reward hoarding: The Black Fan (level 3 exceptional, 10 / 15 / 20 resources), Name Your Price (Criminal-gated, cost 20), Double Down (Criminal-gated, 3 resources for 6 wild icons) | Her income is about 2.15 resources a round (upkeep 1, reaction 0.80, elder sign 0.35) against Jenny Barnes's 2.0 plus her elder sign: the same ceiling as Jenny decks | Accepted |
| Symbol-dig cards (Katarina Sojka, Dark Prophecy, Sacrificial Doll) | They force symbols that are mostly bad; her reaction pays once a round; net negative | Accepted |
| Criminal and Drifter cards her traits open (X1): Name Your Price, Double Down, Nose to the Grindstone, True Awakening, Bound for the Horizon | Official; none multiplies her reaction (once a round) or her cancel | Accepted |
| Memory engines legal for her: Adaptable (Rogue level 1), Versatile, Anchor Point, Cassandra's Notebook | See X3 | Watch |

Requirements: Marked Deck, Seen This Hand Before, The House Always Wins, A Marked
Run of Cards.

## "Birdie" Okonkwo (Survivor, resolve from failures, recurs events)

Options (unchanged): Survivor 0-5, Neutral 0-5, up to 5 other-class cards at
level 0-1 (916 official cards scanned, 624 at level 0, 344 of them events). Her
recursion reaches any event in her discard pile, so the events in her pool were
searched for effects that are strong when repeated every round: 229 events have
a value that repeats, 74 of those are Fast, and 17 cannot be recurred.

| Combo | Verdict | Status |
|---|---|---|
| I Get Out (signature, "not defeated, heal to 1/1") recurred each round | Broken: unlimited life | Fixed: the card removes itself from the game after it resolves, so the discard pile never holds it |
| "Look what I found!" (fail by 2 or less while investigating: discover 2 clues) | Strongest legitimate combo: failing builds resolve and the event returns for 2 resolve; capped at one recursion a round, two resolve gained a round, and it needs a failed investigation | Watch (not in the simulation's deck; a playtest decides) |
| Emergency Cache (gain 3), Easy Mark (gain 2, draw 1) recurred | One recursion a round, costing an action and 2 resolve (two failures) | Accepted |
| Lucky! recurred | Natural brake: a test saved by Lucky is not failed, so it gives no resolve | Accepted |
| Events that remove themselves from the game (Quantum Flux, End of the Road, Burn After Reading, Lifeline) | Cannot be recurred; intended (17 cards) | Accepted |
| Free Fast events as targets: Cheat the System (cost 0, 1 resource per class you control, 3-5), Swift Reflexes (taboo: limit twice a round), Working a Hunch, Hand-Eye Coordination (taboo: level 0-3 Tool or Weapon only), Galvanize, Narrow Escape, Knowledge is Power | Upper bound 0.63 returns a round at 45% failure and 3 tests (0.44-0.79 at 30-60%); the simulation measured 1.4-2.0 returns a night and carries none of these cards. Stress values: Cheat the System +1.9 to +3.2 resources a round against Jenny Barnes's +1.0; Swift Reflexes +0.63 actions a round against Stella Clark's 0.83 and Skids O'Toole's 1.0 | Watch (fallbacks: price 3 resolve, 0.42 returns a round; or limit her other-class slot to level 0 like Cass's, which removes 112 cards including Cheat the System, Galvanize and Hand-Eye Coordination) |
| True Awakening (Drifter-gated, cost 0, an action: 2 of draw 2, discover 1 clue, heal 1 damage, heal 1 horror) | The best value per resource of any target she can take: +1.26 cards and +0.63 clue a round at the upper bound | Watch (as above) |
| Failure-negating cards (Lucky!, Eucatastrophe (taboo: removed from the game after use), Beloved, Three Aces, Steady-Handed; 8 cards) | They reduce her resolve income: anti-synergy, not an exploit | Accepted |
| On Your Own (Survivor level 3 exceptional) | Her first Survivor event each round costs 2 less, so Look what I found!, Lucky! and Dumb Luck become free once a round | Accepted |
| Lucky Compass's second ability and the official teleports in her pool (Astral Travel, Join the Caravan, Ethereal Slip) | See X7 | Watch |
| Quest wording | The quest says "Spend 8 resolve" and her ability says "remove 2 resolve"; the same in play | Change (pending: write "spend 2 resolve" in the ability) |
| Exile cards (16 in her pool: Devil's Luck, Guiding Spirit...) | See X5 | Change (pending) |
| Drifter cards her traits open (X1): True Awakening, Bound for the Horizon, Nose to the Grindstone | Official; True Awakening is the target above | Watch |

Requirements: Lucky Compass (second ability costs 2 resources), I Get Out (above),
Nobody Believes Her (unchanged), Somewhere to Be.

## Seraphine Vale (Mystic, horror for an effect, once per round)

Options (unchanged): Mystic 0-5, Neutral 0-5, up to 5 Seeker 0-2.

| Risk | Detail | Status |
|---|---|---|
| Her horror cost can be soaked by an Ally | The Rules Reference says horror taken as a cost may be reassigned to an asset and still counts as paid; 42 Ally-trait assets in her pool have sanity (55 assets with sanity of any trait) | Fixed: "direct horror" in the ability and the elder sign |
| Jim Culver (Mystic ally) | After she takes horror: draw 1 card (level 4: and 1 resource). With the direct cost she gets an extra action or +2, a card and a resource each round for 1 horror | Watch (not broken: sanity 8, healing costs actions) |
| Key of Ys (Neutral level 5) | Ordinary horror placed on her goes onto the Key instead (+1 to each skill per horror). It does not absorb her direct-horror cost: direct horror cannot be re-assigned (Rules Reference), which the first version of this row got wrong | Accepted (4 sanity: it breaks at 4 horror and mills 10 cards) |
| Extra-action stackers (Press Pass, Sign Magick, Blur, Astral Mirror (asset plays only), Captivating Performance, Ace of Rods, Stolen Minute, Time Warp, Spiritual Echo (taboo: Fast, once a round), Knowledge is Power) | Stack with her one extra action a round; each has a condition or a limit and 6-7 actions in a turn needs four or more pieces. Bide Your Time is a net zero. Time Warp also undoes any horror paid inside the undone action | Accepted (nothing loops) |
| Horror healing (Clarity of Mind, Hallowed Chalice, Occult Records, Psychology Student, Meditative Trance, the Bell; 38 cards touch horror) | Every source costs an action, a card, a charge or a supply; none repeats for free | Accepted |
| "Ready a Spell" mode | Only 6 Spell assets have an exhaust cost (Scrying...) | Accepted (weakest mode) |
| Her price against her pool | Stress model (0.35 chance a round of 1-2 other horror; an Hour heals 1 horror about every second round): defeated by horror in an 11-round loop 17 / 55 / 95% at 0.4 / 0.7 / 1.0 uses a round with only the Hour heal, 1 / 9 / 28% with 0.5 more horror healed a round, about 0 / 0 / 0.3% with 1 more. Isabelle Barnes pays the same price once a round at sanity 9 | Watch |
| Sorcerer and Cursed cards her traits open (X1): Sacred Oath (3 versions), Storm Ruler, Blood of K'n-yan, Forbidden Sutra, Captivating Performance, Dimensional Vortex, Memories of Another Life | Official Sorcerer and Cursed investigators (Marie Lambeau, Jim Culver) use them; Forbidden Sutra's horror is not direct, so an Ally can take it | Accepted |
| Doom-on-card cards (21, the most of any pool) | As for Ayako: they speed the clock | Watch |

Requirements: The Bell of Ambergrove (4 charges), I Remember the Ending,
The Debt of Hours, The Medium's Price.

## All five investigators (second pass)

Official investigators spend the same budget: skills plus health plus sanity is
26 for 42 of 66 official investigators (range 12-28), and for all five of ours.
Cass has health plus sanity 13, below every official Rogue (14-15), paid for by
skills 13, the official maximum. Deck size 30 and one random basic weakness match
the officials.

| Risk | Detail | Status |
|---|---|---|
| X1: the traits on a front open "X deck only" cards | A card printed "Sorcerer deck only" is legal for an investigator with that trait (27 official cards, 25 pool rows). Elias (Believer, Warden): Cowl of Sekhmet, Mauser Tankgewehr M1918, Memories of Another Life, Sound Support. Ayako (Scholar, Chronicler): Archibald MacVeigh, Inquisitive, Library Pass (levels 1 and 5). Cass (Criminal, Drifter): Bound for the Horizon, Double Down, Name Your Price, Nose to the Grindstone, True Awakening. Birdie (Drifter, Wayward): Bound for the Horizon, Nose to the Grindstone, True Awakening. Seraphine (Sorcerer, Cursed): Blood of K'n-yan, Captivating Performance, Dimensional Vortex, Forbidden Sutra, Memories of Another Life, Sacred Oath (3 versions), Storm Ruler. Official investigators with the same traits use them (Warden: Daniela Reyes, Nathaniel Cho, Tommy Muldoon; Sorcerer: Marie Lambeau; Cursed: Jim Culver; Scholar: Kohaku Narukami; Criminal: Skids O'Toole; Drifter: Jenny Barnes). The trait lines are therefore deckbuilding data (PORTABLE_INVESTIGATORS.md) | Accepted (change a trait line if a gate is unwanted) |
| X2: signature, quest and unlocked cards carried level 0 in the spec | 20 cards (10 signature, 5 quest, 5 unlocked). Official signature cards carry no level: SCED's metadata has no `level` for Roland's .38 Special or Daisy's Tote Bag, and the FAQ says a signature card is not a level 0 card. With level 0, effects that fetch level 0 cards (Scrounge for Supplies, Hunter's Instinct, Respite, Do-or-Die, Pushed to the Limit, Jumpsuit, Memories of Another Life, Versatile's "one other level 0 card", Adaptable) could reach an investigator's own signature and quest cards. The Recollections stay level 0: they are level 0 cards bought with Memory | Change (pending): `level` is removed from the 20 cards in pipeline/stillhour_cards_spec.json (the renderer prints a card with no level exactly like level 0, checked on all 20 faces byte for byte; GMNotes lose only the key; tests/test_content_lints.py requires it); it reaches the shipped build with the next build of dist/ |
| X3: the Memory economy | Simulation: 37-41 Memory per investigator per campaign against the official 35-45 band. Unmeasured movers: Adaptable (Cass, Birdie: two free level 0 swaps a game, worth more here than in an official campaign because every loop is a game and a campaign has 10-20 of them), Versatile (+5 deck size and one off-class level 0 card; all five), Anchor Point (returns 1 Memory a loop for a price of 4) and Cassandra's Notebook (returns 1 Memory per first-time Knowledge entry for a price of 3), the discount cards (Down the Rabbit Hole, Arcane Research, Shrewd Analysis) and Deja Vu (Birdie). The unlocked quest cards pay Memory up to 3 a game for Elias and Birdie and 2 for the others, and the cap is always reached | Watch (run a measured campaign with these cards; decide whether 3 against 2 is intended) |
| X4: cards that gain or refer to experience (Ascetic "gain 10 experience", In the Thick of It, The Great Work, Charon's Obol, Let God sort them out, Pelt Shipment, Spiritual Healing, The Raven Quill) | The guide says investigators never earn experience but not that these do nothing. Read as Memory, Ascetic is a 10-Memory windfall and Charon's Obol repays itself in one loop | Change (pending: a guide line: they do nothing here) |
| X5: exile (16 cards in Elias's pool, 16 in Birdie's, 3 in Cass's, 2 each in Ayako's and Seraphine's) | The Rules Reference says an exiled card must be bought again with experience; the guide never mentions exile, so Devil's Luck (cancel up to 10) would return every loop | Change (pending: a guide line: bought again between loops at its Memory cost) |
| X6: cards priced in trauma or defeat (I'll see you in hell!, Ghastly Revelation, Ultimate Sacrifice, The Great Work) | There is no trauma, and defeat costs the rest of the loop and a Year, so near a loop's end these are cheap | Change (pending: a guide line: defeat as normal, trauma does nothing) |
| X7: teleports against district travel (Astral Travel, Join the Caravan, Ethereal Slip level 2, Cheat Death, Fang of Tyr'thrha, Lucky Compass) | The guide says a move that is not along a connection costs no time, so each of these skips the crossing doom. Elusive does not count (the current taboo list makes it a move to a connecting location); Esoteric Atlas moves several connections at once, and whether that is a crossing is for the guide's wording to say | Watch (decide the intent; if unwanted, extend the crossing rule to any cross-district move) |
| X8: the taboo list (the guide mandates the current list, 010 of 2026-02-21) | It already tames Swift Reflexes, Spiritual Echo, Eucatastrophe, Hand-Eye Coordination, Elusive (now a move to a connecting location) and Key of Ys. Forbidden: Double or Nothing (Cass, Birdie) and The Necronomicon (Ayako). Counterspell now cancels any non-auto-fail symbol, including the campaign's own symbol token, as the guide intends | Accepted |
| X9: fan packs | 3,795 cards from 30 packs; the data holds images only, so none could be read | Watch (choose which packs to allow, or read the images) |

Stress model (tools/library/synergy_quant.py; Standard bag, 3 tests a round,
an 11-round loop; an upper bound, not a prediction):

| Interaction | Result | Official comparator | Status |
|---|---|---|---|
| Cass's resource income | 2.15 a round (upkeep 1, reaction 0.80, elder sign 0.35) | Jenny Barnes 2.0 plus her elder sign | Accepted |
| Cass's named cancel and Marked Deck | A blind named symbol shows in 17-31% of rounds; Marked Deck shows a symbol 41% of the time; the cancel costs 2 | Jacqueline Fine: 2 free cancels a round | Accepted |
| Birdie's returns | 0.44 / 0.63 / 0.79 a round at 30 / 45 / 60% failure; Cheat the System +1.9 to +3.2 resources a round | Stella Clark 0.83 actions; Andre Patel 0.73; Jenny Barnes +1.0 | Watch |
| Elias's prevention | 12.1 cards a loop if he always prevents, 8.5 if only for 2 or more damage | First Aid: a supply and an action per damage | Watch |
| Ayako's tagged intellect 5 | A tag 0.94 of rounds; success equals a Guardian's combat 4 plus a +1 weapon | Guardian fighters | Accepted |
| Seraphine's price | Defeated by horror in a loop 17 / 55 / 95% at 0.4 / 0.7 / 1.0 uses a round with only the Hour heal | Isabelle Barnes | Watch |

## Measured after the build (simulation, FINISHING_BALANCE.md "Quest cards, 2026-10-06")

| Item | Result | Status |
|---|---|---|
| Elias deck-outs | 0.4-0.7 reshuffles (1 horror each) per played night, 0.4 before the redesign | Accepted |
| Elias's prevention | about 2 damage a night; he is defeated in about a quarter of nights (a third before) | Accepted |
| Ayako's tagging | about 5.5 tokens a night; her kill rate is not measured (the simulation's decks have no Mystic-slot weapons) | Watch |
| Birdie's recursion | an event returns 1.4-2.0 times a night; "Look what I found!" is not in the simulation's decks | Watch |
| Seraphine's horror cost | defeated in about a third of nights, the same as before the redesign | Watch |
| Cass's token control | not measured | Watch |

Everything marked Watch needs a human playtest or a simulation deck that carries the card.
