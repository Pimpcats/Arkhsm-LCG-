# Portable investigators (built 2026-10-06)

Designer-facing; contains rules text. Status: **built on the branch, not
published.** Rule (CAMPAIGN_DESIGN_LESSONS.md, guidelines 13-15): an
investigator, their signature cards and their weaknesses use only core-game
concepts (resources, cards, clues, damage, horror, doom, skill values, chaos
tokens) and tokens named on their own cards. No Memory, Dissonance, Hourglass,
Hours, loops, Recollections or Campaign Log. They then work in any campaign.
The campaign flavour is on one **personal quest card** per investigator,
unlocked in this campaign only.

Owner direction applied: keep Cass; Seraphine once per round; no once-per-game
abilities on an investigator; every ability and elder sign unique against the
official investigators (checked against library/cards/player/*/investigators.md)
and independent of card level (deckbuilding stays level 0-5); Elias leans on
the Survivor discard cards; Ayako can investigate or fight on any turn; Birdie
kept.

## Investigator fronts (as printed)

- **Elias Warde (Guardian).** [reaction] When damage would be dealt to you or another investigator at your location: Discard up to 3 cards from the top of your deck. Prevent 1 of that damage for each card discarded. (Limit once per round.) Elder: +1. You may discard the top 2 cards of your deck. If you do, this token is +3 instead and heal 1 damage from an investigator at your location.
- **Dr. Ayako Sōma (Seeker).** [reaction] After you succeed at a skill test while an enemy is at your location: Place 1 translation token on an enemy at your location. (Limit once per round.) While attacking or evading an enemy that has 1 or more translation tokens, you may use your [int] in place of your [com] or [agi]. Elder: +2. Place 1 translation token on an enemy at your location. If there is none, draw 1 card.
- **Cass Lindqvist (Rogue).** [free] Spend 2 resources: Name a symbol token other than [autofail]. The next time you reveal that symbol during a skill test this round, cancel it. (Limit once per round.) [reaction] After you reveal a symbol token during a skill test: Gain 1 resource. (Limit once per round.) Elder: +1. Gain 2 resources.
- **"Birdie" Okonkwo (Survivor).** [reaction] After you fail a skill test: Place 1 resolve on "Birdie". (Limit twice per round.) [free] During your turn, remove 2 resolve from "Birdie": Return an event from your discard pile to your hand. (Limit once per round.) Elder: +1. If you have failed a skill test this round, this token is +3 instead.
- **Seraphine Vale (Mystic).** [free] During your turn, take 1 direct horror: Choose one – +2 skill value for this test; gain 1 additional action; or ready a Spell asset you control. (Limit once per round.) Elder: +2. You may take 1 direct horror. If you do, ready a Spell asset you control.

Uniqueness against the official investigators, by ability:

| Ability | Closest official | Why it is distinct | Status |
|---|---|---|---|
| Elias, deck discarded to prevent damage | Survivors who may be assigned damage meant for allies or others | No official investigator spends deck cards to prevent damage; his prevents, theirs reassigns | Built |
| Ayako, translation tokens and [int] for attack/evade | Survivor that seals bless/curse on an evaded enemy; Mind over Matter (a card) | Her own tokens, placed by successes, and a stat swap no investigator has | Built |
| Birdie, resolve from failures to return events | Seeker/Mystic play of Spell/Insight from discard; Survivor skill recursion for horror | Failure currency; any event; returned to hand, not played | Built |
| Birdie elder, +3 after a failure this round | none found | unique | Built |
| Seraphine, direct horror for one of three effects | Agnes Baker (horror triggers); Rogues that spend resources for an extra action | Horror is the price, the buyer picks the effect | Built |
| Seraphine elder, take 1 direct horror to ready a Spell | none found | unique (the first draft's "+X for horror on you" was Agnes Baker's elder sign) | Built |

## Signature cards and weaknesses (as printed)

| Card | Text (changes from the first campaign build) | Status |
|---|---|---|
| Ambergrove Lamp | the Dissonance clause is gone; +1 [agi] to evade, the look-and-move action stays | Built |
| I've Done This Before | "during this game" | Built |
| The Eighth Grave (weakness) | Revelation: test [wil] (3); for each point you fail by (maximum 3), take 1 damage | Built |
| Lexicon of the Hour | its cancel clause is once per round (its 2-secret cost already gates it) | Built |
| It Means 'Wait' | first clause only (cancel a treachery, take 1 horror) | Built |
| Untranslatable (weakness) | Revelation: take 2 horror; remove each translation token from each enemy | Built |
| Marked Deck | second ability costs 2 resources (limit once per game, a game is one scenario) | Built |
| The House Always Wins | cannot be evaded while Cass has more resources than each other investigator; after its attack deals damage, that investigator discards 2 resources | Built |
| Bell of Ambergrove | 4 charges; evade with willpower and heal 1 horror; the second ability moved to the quest back | Built |
| I Remember the Ending | test [wil] (3); look at the top 3 encounter cards, bottom 1, rest on top in any order (max once per game) | Built |
| The Debt of Hours (weakness) | Revelation: take 2 horror and place 1 doom on the current agenda | Built |
| Lucky Compass | second ability: spend 2 resources, move to any revealed location with no enemy | Built |
| I Get Out | "Remove I Get Out from the game" replaces "max once per game", so Birdie's recursion can never return it (it would be unlimited life) | Built |
| Nobody Believes Her, Seen This Hand Before | unchanged | Built |

## Personal quest cards (this campaign only)

Each investigator has two cards, both Permanent (no slot, not counted toward
deck size): a **quest card**, listed in the deckbuilding requirements on the
investigator's back, and its **bonded unlocked card**, taken from the Player
Cards bag when the quest is met (the swap is the official bonded pattern, as
with the Resolute cards). The tally is kept on the investigator card's **Quest**
button, mirrored on the Campaign Log's panel (counter and "met" box) and in the
Control token's state. A reset never clears it. Until the swap, none of the
unlocked clauses apply.

| Investigator | Quest card | Goal (tally across the campaign) | Unlocked card | What it carries |
|---|---|---|---|---|
| Elias | What the Warden Owes | prevent 4 damage with his ability | What the Warden Remembers | 1 Memory when dealt damage or when his ability prevents damage (three times per game); the Lamp's move may raise Dissonance by 1 so it places no doom |
| Ayako | The Unfinished Translation | first translation token on 8 different enemies | The Translation, Finished | 1 Memory on an [int] success (twice per game); Recollections drawn by her elder sign cost 2 less; It Means 'Wait' also reaches Hour text and The Appointed's attack |
| Cass | A Marked Run of Cards | cancel 3 symbol tokens with her own ability or cards | The Table Remembers | 1 Memory per symbol reveal (twice per game); Marked Deck may pay Dissonance and Memory instead of 2 resources |
| Birdie | Somewhere to Be | spend 8 resolve | She Knows the Road | 1 Memory when she fails by 2 or more (three times per game); Lucky Compass may remove 1 Memory instead of spending 2 resources; I Get Out places 1 Memory on the Compass |
| Seraphine | The Medium's Price | use her ability 8 times | The Price, Remembered | 1 Memory when dealt horror (twice per game); Dissonance may pay for her ability; the Bell may advance or rewind the Hourglass |

The goals are set by the whole-campaign measurements in
docs/design/FINISHING_BALANCE.md (section "Quest cards, 2026-10-06"): each is met
around the second or third night, which keeps experience inside 35-45. They live
in one place (`Constants.QUEST` in src/StillHour/Constants.ttslua) and on the
quest card text; change both together.
The Lighthouse act's own text still heals 1 horror with Elias's elder sign once
"The Keeper's Ninth Death" is recorded; that text is on the scenario card, not
on a quest card.

## Art

Ten quest-card faces are briefed in pipeline/art_manifest.json (scene prompts,
no characters) and render with placeholder art until the art is generated and
registered. No image tool was available when they were built.
