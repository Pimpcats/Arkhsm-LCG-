# Deckbuilding review (2026-10-06)

Designer-facing; rules text, no campaign spoilers. Scope: each investigator's
deckbuilding options and requirements (signature cards, random weakness)
against the Revision 2 fronts in PORTABLE_INVESTIGATORS.md. Method: every
official player card the investigator can legally take (class and level
ranges below) was pulled from the local library (tools/library/build_library.py)
and searched for loops, stacking and degenerate partners. Nothing here is
playtested; the simulation re-checks come after the engine work.

## Elias Warde (Guardian, spends deck to prevent damage)

Options (unchanged): Guardian 0-5, Neutral 0-5, up to 5 Survivor 0-2.
The Survivor slot already is his synergy: Survivor is the class built on the
discard pile. His ability stocks the discard pile at random (he cannot choose
what leaves the deck), so the payoffs are statistical, never a combo he can
assemble on purpose.

Best fits among the five Survivor slots (all level 0-2): Yaotl (discards a
card at will; his skill bonus reads the top of the discard pile), Improvised
Weapon / Impromptu Barrier / Winging It (played from the discard pile, then
shuffled back, which refunds the deck he spent), Improvised Shield (can only be
played from the discard pile), Scavenging and Hunter's Instinct (recur items
and events), Respite (shuffles discarded level 0 events/skills back).

Combos checked and verdicts:

| Combo | Verdict |
|---|---|
| His prevention plus Guardian cancel/soak (Flesh Ward, "I've had worse...", Perseverance, Idol of Xanatos) | Allowed. His ability only stops damage, never horror, and horror is his weak side (sanity 5); the stack cannot make him safe |
| Short Supply (mills 10 on turn 1), Key of Ys (mills 10 on leaving play) | Self-harm, not a power spike. An empty deck costs 1 horror per reshuffle at sanity 5. Left legal |
| Pushed to the Limit with a Guardian weapon he milled | Official card, official power: free fight, shuffled back; limit 2 copies; random fodder. Left legal |
| Respite refilling the deck he spends | Costs an action and a resource, returns level 0 events/skills only. Left legal |
| Milling weaknesses off the top (no revelation) | Same as Yaotl and Short Supply today. Accepted |
| Fortuitous Discovery with copies milled | Official, random, 3 copies at most. Accepted |

Requirements: The Ambergrove Lamp (drop the tracker clause), I've Done This
Before (unchanged), The Eighth Grave (test willpower, damage per point failed;
he can pay deck cards to prevent it, so the weakness still costs him). No
change needed beyond the portable text.

## Dr. Ayako Soma (Seeker, translation tokens, intellect for attack/evade)

Answer to "is she a fighter-investigator hybrid": in skill, yes; in damage, not
by default. Any success while an enemy is at her location tags it (once per
round); tagged enemies can be attacked or evaded with her intellect 5, so every
action can go to investigating, fighting or evading as the moment needs.
Her combat is 1 and her damage stays 1 per hit.

Options (unchanged): Seeker 0-5, Neutral 0-5, up to 5 Mystic 0-2. The Mystic
slot supplies Neutral/Mystic weapons (Knife, Kukri, Ceremonial Sickle, Enchanted
Blade, Sword Cane) and no weapon scales past +1/+2 damage at these levels. Her
Seeker class already holds intellect-fighting cards ("I've got a plan!", Caustic
Reaction, Scroll of the Pharaohs, Strange Solution at level 4), which work
without her ability, so the ability adds reach, not new peaks.

| Combo | Verdict |
|---|---|
| Her ability with Mind over Matter | Redundant, not broken: Mind over Matter covers untagged enemies for a card and an action |
| Guardian secondary (weapons) | Rejected. Intellect 5 plus Guardian weapons beats real Guardian fighters while she keeps Seeker investigation. Mystic secondary kept so damage stays the limiter |
| Tagging and evading | Strong evader (intellect 5 vs evade values 2-4); acceptable, evasion does not kill enemies |

Requirements: Lexicon of the Hour (once-per-game clause becomes once per
round; the 2-secret cost already gates it), It Means 'Wait' (first clause only),
Untranslatable (weakness: take 2 horror, then remove every translation token
from every enemy; hurts outside the campaign and bites her kit inside it).

## Cass Lindqvist (Rogue, unchanged front)

Options: Rogue 0-5, Neutral 0-5, up to 5 cards of any other class at level 0.
Her resource trigger (1 per symbol reveal, once per round) is smaller than her
cancel cost (2), so the loop is a net spend, not an engine. No degenerate
partner found in the level 0 any-class slot. Requirements: Marked Deck,
Seen This Hand Before, The House Always Wins; portable text per
PORTABLE_INVESTIGATORS.md, no further change.

## "Birdie" Okonkwo (Survivor, resolve from failures, recurs events)

Options (unchanged): Survivor 0-5, Neutral 0-5, up to 5 other-class cards at
level 0-1. Her recursion reaches any event in her discard pile, so the events
in her pool were searched for effects that are strong when repeated every round.

| Combo | Verdict |
|---|---|
| I Get Out (signature, "not defeated, heal to 1/1") recurred each round | Broken: unlimited life. Fix: the card removes itself from the game after it resolves, so the discard pile never holds it. Card-level, not an investigator ability |
| "Look what I found!" (fail by 2 or less while investigating: discover 2 clues) | Strongest legitimate combo: failing builds resolve and the event returns for 2 resolve. Capped at one recursion a round and two resolve gained a round, and it needs the failed investigation. Watch in the simulation |
| Emergency Cache (gain 3), Easy Mark (gain 2, draw 1) recurred | One recursion a round, costing an action and 2 resolve (two failures). Accepted |
| Lucky! recurred | Natural brake: a test saved by Lucky is not failed, so it gives no resolve. Accepted |
| Events that remove themselves from the game (Quantum Flux, End of the Road, Burn After Reading) | Cannot be recurred; intended |

Requirements: Lucky Compass (second ability costs 2 resources), I Get Out (above),
Nobody Believes Her (unchanged).

## Seraphine Vale (Mystic, horror for an effect, once per round)

Options (unchanged): Mystic 0-5, Neutral 0-5, up to 5 Seeker 0-2. Her ability
buys one extra action, +2 skill or a ready Spell for 1 horror a round. The
horror is sustained by Mystic and Seeker healing (Clarity of Mind, Occult
Records, Psychology Student, the Bell of Ambergrove) but every source costs an
action, a charge or a supply, so the extra action is never free. No card was
found that scales with horror on her and none that grants a free heal each
round. "Ready a Spell" is her weakest mode (few Spells exhaust); accepted.
Requirements: Bell of Ambergrove (evade with willpower, heal 1 horror, second
ability removed), I Remember the Ending (test willpower 3, scry 3 encounter
cards), The Debt of Hours (take 2 horror, place 1 doom on the current agenda).

## Open checks for after the engine work

1. Whole-campaign difficulty with the new fronts (30 campaigns Elias/Ayako/Cass,
   20 Birdie/Cass/Seraphine).
2. Experience by party (quest cards replace the old Memory reactions).
3. Targeted: Elias deck-outs per scenario; Birdie clue rate with and without
   "Look what I found!"; Ayako kill rate with Mystic-slot weapons.
