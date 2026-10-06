# Campaign design lessons (from the official campaigns)

What the official Arkham Horror LCG campaigns teach about building a campaign
that is new but still plays like Arkham. Read it before the brief
(docs/CAMPAIGN_PLAYBOOK.md, step 2). It talks about official campaigns only.

Sources: the local LCG library (`python3 tools/library/build_library.py`, then
`library/campaigns/<code>/`, `library/stats/scenario_structure.csv`, 93
scenarios from 11 campaigns) and the owner's ranking:

| Tier | Campaigns |
|---|---|
| Top | The Path to Carcosa, The Forgotten Age, The Innsmouth Conspiracy, The Feast of Hemlock Vale |
| Mid | Edge of the Earth, The Dream-Eaters, The Drowned City |
| Bottom | The Circle Undone, The Scarlet Keys, The Dunwich Legacy |

## 1. The shape every official scenario shares

**This table is the one authoritative statement of the official structure
numbers.** The new-campaign skill, `docs/CAMPAIGN_PLAYBOOK.md` and
`docs/design/OFFICIAL_COMPARISON.md` point here instead of restating them.
Source: `library/stats/scenario_structure.csv` (93 scenarios from 11
campaigns; 973 locations), rebuilt by `python3 tools/library/build_library.py`
(the library is git-ignored, so run that first in a fresh checkout). Figures
are medians with the middle half of scenarios in brackets unless a mean is
named. They are the "it still feels like Arkham" envelope. Go outside it only
on purpose, and only in one direction at a time.

| Part | Official | Note |
|---|---|---|
| Agendas | 2 (2–3) per scenario | total doom: median 17–18, typical range 14–20 (middle half 13–20) |
| Acts | about 3 (2–4) per scenario | most acts advance by story or objective, not by clues |
| Clue acts | 0 or 1 per scenario | when an act costs clues: 2–3 per investigator, never more than 5 |
| Locations | median 12, typical 9–15 | |
| Victory locations | 3 (0–5) | |
| Clues on an ordinary location | 0 (20%), 1 (50%), 2 (16%), 3+ (4%) per investigator; mean 1.05 | thoroughfares 0–1 at shroud 1–2 |
| Clues on a Victory location | 1–3 per investigator: 1 (54%), 2 (38%), 3 (6%); mean 1.48 | the richer, harder rooms |
| Clues on a location, all | 1.25 per investigator (0.95–1.45) | |
| Shroud | ordinary mostly 2–3 (mean 2.65); Victory mostly 3–4 (mean 3.1) | all locations 2.9 (2.6–3.1) |
| Encounter deck | 30 cards, typical 25–33 | |

Measurements made earlier with `tools/official_compare/compare.py` (54
scenarios, Night of the Zealot to The Innsmouth Conspiracy) differ slightly
(for example doom 18, locations 11.5, 0.9 clues per investigator per
location); they are kept in OFFICIAL_COMPARISON.md as a historical record.
Connections (2.5 per location), enemy share and stats, treachery tests and
chaos-bag changes come only from that tool, so use OFFICIAL_COMPARISON.md for
those.

Rules of thumb that follow from it:

- **Clues are a range, not a flat value.** Thoroughfares carry 0–1 clues at
  shroud 1–2, ordinary rooms 1–2 at shroud 2–3, and Victory locations 2–3 at
  shroud 3–4. The reward for the hard room is points that count at the end of
  the campaign.
- **The act deck tells the story.** About 3 acts per scenario, with at most
  one clue gate. The other acts advance on an objective: a place reached, an
  enemy defeated, an item delivered, a choice made.
- **The agenda deck is the clock.** About 17 doom over 2–3 agendas. A
  scenario that should feel like a race tightens the agendas; it does not pile
  clues onto the acts.

## 2. What the top tier does well

### The Path to Carcosa
- **One idea runs through every scenario.** The play, the yellow sign and
  doubt versus conviction: each scenario is a different angle on the same
  question. Nothing feels like filler.
- **Choices pile up into a meter.** Small choices record Doubt or Conviction,
  and that tally quietly decides later scenarios and the ending. Players feel
  the weight without being told the maths.
- **Each scenario has a signature rule:** the asylum's escape, the catacombs'
  random map, the Lost Soul possessions. Every one is still built from
  standard acts, agendas, locations and keywords.
- **Story assets and allies carry the plot forward,** and losing them hurts.

### The Forgotten Age
- **Exploration is a deck.** The explore action draws locations out of an
  exploration deck. It is a new verb made only from standard card types.
- **Supplies are chosen before the campaign starts** and spent across
  scenarios. Players plan, and what they forgot to bring becomes the story.
- **Consequences stick:** Poisoned stays in the deck, Yig's Fury and
  Vengeance points stay on the log. Mistakes echo for scenarios.
- **Going back pays off.** The time-travel return and the two-part Heart of
  the Elders reuse places on purpose and tell you what changed.

### The Innsmouth Conspiracy
- **Structure is the mystery.** The story is told out of order through
  recovered memories, so every scenario answers one question and raises the
  next.
- **One physical mechanic ties it together:** flood tokens raise and lower
  locations, and the tide pushes every turn.
- **Key tokens and collected memories** make objectives physical and
  readable on the table.
- **Each scenario has a different tempo:** a chase, an infiltration, a
  siege. The campaign never plays the same scenario twice.

### The Feast of Hemlock Vale
- **A clock across the whole campaign.** Days and times of day decide what
  is open and who is around; the party chooses where to spend each slot.
- **Relationships are campaign state:** residents remember how they were
  treated, and later scenes change.
- **Tight scenarios:** small encounter decks (about 14 cards per part) and
  few acts per part. Short, sharp scenes add up to a long story.
- **A place, not a corridor.** The village feels lived in because you come
  back to it at different times.

## 3. What the mid tier does well

### Edge of the Earth
- **The expedition team are assets with a fate.** Partners help in play, can
  be lost, and their survival is the campaign's scoreboard.
- **Repeated places grow:** Fatal Mirage comes back with more of itself each
  time. Coming back shows progress instead of repetition.
- **A campaign-long deck as pressure** (Tekeli-li) carries dread between
  scenarios.

### The Dream-Eaters
- **Two linked halves** (dreams and the waking world) that can be played
  separately or woven together. The structure itself is a theme.
- **Signature locations with strong art** carry each scenario's identity.

### The Drowned City
- **A changing map:** flooding reshapes the city, and Hidden, Patrol, Alert
  and Seal give enemies and places clear new behaviour as keywords.
- **Artifacts and glyphs are campaign rewards** you can see collecting.
- **Optional objectives with named achievements** reward mastery without
  making a first play miserable.

## 4. What the bottom tier does poorly (avoid)

### The Circle Undone
- **Too punishing too early.** The opening is a long and random prelude
  followed by a harsh first scenario. Its scenarios ask the most clues of any
  campaign (3.5 per investigator per clue act), with high shroud (3.05) and big
  encounter decks (about 35 cards).
- **Rules stack on rules.** Haunted, spectral realms and the late puzzles
  pile up exceptions that slow every turn.
- **Story overload.** Too many factions and named people, so players lose the
  thread of who wants what.

### The Scarlet Keys
- **The story is spread thin.** The map-and-time structure lets the party
  skip around, but many stops are standalone errands that feed little back.
- **Too much tracking:** keys, a world clock, coterie state and Concealed
  minicards, all in the log.
- **Bloated encounter decks** (about 43 cards on average). Treacheries rarely
  hit the theme twice in one game.

### The Dunwich Legacy
- **Swingy order and power.** The first two scenarios differ wildly in
  difficulty, and a bad first night snowballs.
- **Generic threats.** Many encounters are core-set monsters, and the
  signature foe is mostly an invulnerable wall. Too little that is new happens
  on the table.
- **Clue grinds late.** Long clue acts and high-shroud maps in the back half
  stretch scenarios without adding story.

## 5. Guidelines for the next campaign

1. **One question, many angles** (Carcosa, Innsmouth). Write the
   campaign's question in one line. Every scenario must reveal a new angle on
   it and end on a hook toward the next.
2. **One signature verb, made from standard parts** (Forgotten Age explore,
   Innsmouth flood, Hemlock clock). Build it from acts, agendas, locations,
   keywords and story assets, not from a new card type. If the Rules Reference
   already has a word for it, use that word.
3. **Each scenario gets its own identity:** a distinct goal shape (escape,
   hold, deliver, find, protect, choose), a distinct map, and one local rule.
   No two scenarios should share a win condition.
4. **Campaign state you can feel, kept small** (Carcosa's Doubt and
   Conviction, Hemlock's relationships, Edge of the Earth's partners).
   Choose 2–3 tallies, each changing something on the table later. Cut any log
   row that never changes play (the Scarlet Keys lesson).
5. **Consequences echo, but never lock you out** (Forgotten Age Poisoned,
   Edge of the Earth partners). A bad scenario costs something real, and the
   next scenario is still winnable (the Dunwich lesson).
6. **Coming back has to show change** (Forgotten Age, Edge of the Earth,
   Hemlock). If a place returns, it returns with something new: a part opened,
   a person changed, a clue moved.
7. **Stay inside the shape in section 1,** especially for clues. Make the
   race through the agenda's doom, not through act clue costs. Victory
   locations are the richer, harder rooms.
8. **Encounter decks of about 25–33 cards,** themed so the same threat shows
   up twice in a game. About half the treacheries should be skill tests. Use
   one or two new keywords at most (the Drowned City lesson).
9. **Ramp the difficulty and teach first.** The first scenario teaches the
   signature verb with a forgiving clock. Pressure ramps up, and the finale is
   the hardest (the Circle Undone lesson). Target win rates by scenario come
   from the owner's curve (the default is in the `/new-campaign` skill, step 4;
   The Still Hour's measured curve is in docs/design/PLAYTEST_SIM.md).
10. **Readable rules on every card.** Official templating, with the Rules
    Reference and errata in `library/rules/` as the authority. Check
    `python3 tools/library/search.py "<phrase>"` before inventing wording.
11. **Story assets carry the plot,** and each has a clear cause and effect: a
    reason the story put it there, a cost to carry it, and a payoff
    (Carcosa).
12. **Optional mastery goals** (Drowned City achievements, Victory
    locations): reward thorough play without punishing a first play.
13. **Investigators must work outside the campaign** (every official
    campaign). New investigators fit the campaign's theme, but their
    abilities, elder signs, signature cards and weaknesses use only
    core-game concepts and tokens named on their own cards (a translation
    token, resolve), so they are playable in any campaign. Nothing on an
    investigator front or a signature card may name the campaign's trackers
    (Dissonance, an hourglass, banked Memory, the Campaign Log), not even as a
    harmless bonus. The campaign hooks move to a **personal quest card**: one
    Permanent card per investigator (a requirement printed on the back, no
    slot, not counted toward deck size) with a quest to be met by playing the
    investigator's own style and a tally kept on the Campaign Log across the
    whole campaign. Meeting it swaps the card for its bonded unlocked card,
    which carries the Memory income and every clause that touches the
    trackers. Test: strike every campaign reference from the investigator
    front, every signature card and every weakness. Each ability and elder
    sign must still do something useful and each weakness must still hurt.
    The Still Hour's first audit (2026-10-03) found two investigators that
    failed (Seraphine's cost and elder sign ran on Dissonance; Ayako's Memory
    had no use of its own) and two weaknesses that went dead (Untranslatable,
    The Debt of Hours).
14. **Price an ability in something nobody can soak.** A cost of "take 1
    horror" may be reassigned to an Ally and still counts as paid (Rules
    Reference, Dealing Damage/Horror), and most pools hold dozens of Allies
    with sanity. Write "take 1 direct horror", as official investigators who
    pay horror do. Check every damage or horror cost, and every prevention,
    the same way.
15. **Review every investigator's whole pool for loops before the build.**
    Pull every card the deckbuilding options allow (class and level ranges
    from the card library), search them for recursion, prevention stacking,
    deck and discard engines, token control and extra actions, and write down
    each risk with a status (fixed, accepted, watch) in
    docs/design/DECKBUILDING_REVIEW.md. The Still Hour's review found one
    broken loop (a recurrable "you are not defeated" card: it now removes
    itself from the game), one unpaid cost (the ally soak above) and four
    combinations to watch in the simulation. Recursion and prevention are the
    usual culprits; anything that returns a card from the discard pile needs
    a once-per-round limit or a currency the investigator cannot farm.

## 6. Pre-brief checklist

- [ ] The campaign's question in one line, and each scenario's angle on it
- [ ] The signature verb and the standard parts it is built from
- [ ] A table of each scenario's goal shape and local rule, with no two alike
- [ ] 2–3 campaign tallies, each with where it changes play
- [ ] Per-scenario numbers inside section 1 (or a written reason to differ)
- [ ] Encounter sets themed per scenario, 25–33 cards, about half skill tests
- [ ] A difficulty ramp with the first scenario as the tutorial
- [ ] Every new term checked against the Rules Reference in `library/rules/`
- [ ] Portability test passed for every investigator and signature card (guideline 13)
