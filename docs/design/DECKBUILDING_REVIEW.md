# Deckbuilding review (2026-10-06)

Designer-facing; rules text, no campaign spoilers. Scope: each investigator's
deckbuilding options and requirements (signature cards, random weakness)
against the fronts as built (PORTABLE_INVESTIGATORS.md). Method: every official
player card the investigator can legally take (class and level ranges below)
was pulled from the local library (tools/library/build_library.py) and searched
for loops, stacking and degenerate partners. Nothing here is a playtest; the
"Measured" column fills in from the simulation (docs/design/FINISHING_BALANCE.md,
"Quest cards, 2026-10-06").

Status values: **Fixed** (changed in the cards or engine), **Accepted** (left
legal on purpose), **Watch** (legal; the simulation or a playtest decides),
**Rejected** (an option considered and not taken).

Corrections: the first version of this review did not scan Cass's pool and said
"no degenerate partner found"; it also missed that Seraphine's horror cost could
be soaked by an Ally. Both were found in a second scan and are recorded below.

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
| His prevention plus Guardian cancel/soak (Flesh Ward, "I've had worse...", Perseverance, Idol of Xanatos) | His ability only stops damage, never horror, and horror is his weak side (sanity 5); the stack cannot make him safe | Accepted |
| Short Supply (mills 10 on turn 1), Key of Ys (mills 10 on leaving play) | Self-harm: an empty deck costs 1 horror per reshuffle at sanity 5 | Accepted |
| Pushed to the Limit with a Guardian weapon he milled | Official card, official power: free fight, shuffled back, 2 copies, random fodder | Accepted |
| Respite refilling the deck he spends | Costs an action and a resource, returns level 0 events/skills only | Accepted |
| Milling weaknesses off the top (no revelation) | Same as Yaotl and Short Supply today | Accepted |
| Deck-outs: spending 3 cards a round from a 30-card deck | The simulation keeps 4 cards in the deck; whether the real policy does is the table's choice | Watch |

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
| Kill rate with Mystic-slot weapons (Knife, Kukri, Enchanted Blade) | Needs the simulation | Watch |

Requirements: Lexicon of the Hour (cancel clause once per round), It Means
'Wait' (first clause only), Untranslatable (2 horror, then every translation
token is removed), The Unfinished Translation.

## Cass Lindqvist (Rogue, resources from symbols)

Options: Rogue 0-5, Neutral 0-5, up to 5 cards of any other class at level 0
(998 cards scanned).

| Risk | Detail | Status |
|---|---|---|
| Trigger wording | "After you reveal a symbol token" also fired on reveals outside tests (Voice of Ra, Henry Wan, Astral Travel, 21 or Bust) | Fixed: "during a skill test" |
| Token-control stacking | Her cancel, Marked Deck's seal, Seen This Hand Before, Olive McBride (reveal 3, keep 2), Heavy Furs, Defiance, Analysis and Skeptic could steer almost every test; Marked Deck's choose-a-number stays once per game (a scenario), which keeps it from every round | Watch (fallback: only tokens of 0 or lower) |
| Olive McBride with her elder sign | Two resolved tokens could both be the elder sign (2 resources each) | Accepted (about 1 in 16 per token) |
| Looping Seen This Hand Before | Scrounge for Supplies / Hunter's Instinct (Survivor level 0, legal in her any-class slot) return it; it costs 1, gains 1-2 | Accepted (net about +1 resource an action plus a cancel) |
| The House Always Wins feeds on a resource engine | It cannot be evaded while she holds the most resources, and discards 2 resources when it damages someone | Accepted (self-balancing) |

Requirements: Marked Deck, Seen This Hand Before, The House Always Wins, A Marked
Run of Cards.

## "Birdie" Okonkwo (Survivor, resolve from failures, recurs events)

Options (unchanged): Survivor 0-5, Neutral 0-5, up to 5 other-class cards at
level 0-1. Her recursion reaches any event in her discard pile, so the events in
her pool were searched for effects that are strong when repeated every round.

| Combo | Verdict | Status |
|---|---|---|
| I Get Out (signature, "not defeated, heal to 1/1") recurred each round | Broken: unlimited life | Fixed: the card removes itself from the game after it resolves, so the discard pile never holds it |
| "Look what I found!" (fail by 2 or less while investigating: discover 2 clues) | Strongest legitimate combo: failing builds resolve and the event returns for 2 resolve; capped at one recursion a round, two resolve gained a round, and it needs a failed investigation | Watch (not in the simulation's deck; a playtest decides) |
| Emergency Cache (gain 3), Easy Mark (gain 2, draw 1) recurred | One recursion a round, costing an action and 2 resolve (two failures) | Accepted |
| Lucky! recurred | Natural brake: a test saved by Lucky is not failed, so it gives no resolve | Accepted |
| Events that remove themselves from the game (Quantum Flux, End of the Road, Burn After Reading) | Cannot be recurred; intended | Accepted |

Requirements: Lucky Compass (second ability costs 2 resources), I Get Out (above),
Nobody Believes Her (unchanged), Somewhere to Be.

## Seraphine Vale (Mystic, horror for an effect, once per round)

Options (unchanged): Mystic 0-5, Neutral 0-5, up to 5 Seeker 0-2.

| Risk | Detail | Status |
|---|---|---|
| Her horror cost can be soaked by an Ally | The Rules Reference says horror taken as a cost may be reassigned to an asset and still counts as paid; 50 Allies in her pool have sanity | Fixed: "direct horror" in the ability and the elder sign |
| Jim Culver (Mystic ally) | After she takes horror: draw 1 card (level 4: and 1 resource). With the direct cost she gets an extra action or +2, a card and a resource each round for 1 horror | Watch (not broken: sanity 8, healing costs actions) |
| Key of Ys (Neutral level 5) | Horror placed on her goes onto the Key instead (+1 to each skill per horror) | Accepted (4 sanity: it breaks at 4 horror and mills 10 cards) |
| Extra-action stackers (Bide Your Time, Ace of Rods, Astral Mirror, Press Pass, Captivating Performance) | Stack with her one extra action a round | Accepted (nothing loops) |
| Horror healing (Clarity of Mind, Occult Records, Psychology Student, the Bell) | Every source costs an action, a charge or a supply | Accepted |
| "Ready a Spell" mode | Few Spells exhaust | Accepted (weakest mode) |

Requirements: The Bell of Ambergrove (4 charges), I Remember the Ending,
The Debt of Hours, The Medium's Price.

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
