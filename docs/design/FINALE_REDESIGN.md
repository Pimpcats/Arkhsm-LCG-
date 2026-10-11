# The Last Hour, redesigned: the Appointed across three times (design, 2026-10-11)

**SPOILERS — designer/assistant only.** Owner decisions on 2026-10-11: the Appointed can be killed, only in the
finale, as a boss fought in the Past, the Present and the Future; where it is finished decides where (when) the
investigators end up; defeating the Past and Future forms makes the Present form vulnerable; a party may stop after
one form and be **stranded** in that period (counts as a win, bittersweet, campaign over); health scales per
investigator. Goal: a full victory (home, in the Present) about **40%** in the carried-campaign simulation
(`goalsPerNight 2`), with stranded endings and failures sharing the rest.

## Why

Carried parties reached the old contest 100% of the time (2026-10-11, 30 campaigns): six deep entries made it
automatic, and capping them only moved the problem. The campaign has taught "it cannot be defeated, only held
back" for the whole run; the finale should turn that around in a fight that is hard, has a route to choose, and
uses what each campaign learned.

## Fiction (fits what is already written)

- **The Past:** the night of the first occultation, when the town voted to open the door and the hour was printed
  one late (the Vote, the brown ink, the altered hour, the name kept under seal).
- **The Present:** the looping night itself, eleven o'clock in the Square.
- **The Future:** the dawn the loop never reaches, the road the walkers walk, the deaths the keeper wrote down, the
  fare out of the night: what the loop makes of everyone who stays.
- It "was never late; you are simply early": in the finale the investigators stop being early. They step into
  the hour it was invited (Past) and the hour it means to keep (Future), and unmake it in both before it can be
  hurt where it stands (Present).

## Structure

**Setup (replaces Contest the Crossing):**
1. Place The Last Hour box. It lays out two period locations beside the board — **The First Occultation** (Past)
   and **The Morning After** (Future) — and the act **Through the Hours**. District act decks are set aside as now.
2. Set The Appointed aside and put **The Appointed, As It Is** (Present form) where it was (or where it would
   manifest). Spawn **As It Was** at The First Occultation and **As It Will Be** at The Morning After.
3. The Hourglass is set as now (Hour IX → back to V; V–VIII stays). Choices still apply at setup (spoken name,
   drowned rewind, the Press's Static, the refused ticket).

**Travel (a time cost):** at The Square, [action] Place 1 doom on the current Hour: move to The First Occultation
or The Morning After. From either, [action] Place 1 doom on the current Hour: move to The Square. Not along a
connection (no crossing doom). An investigator's period is where they stand; encounter cards resolve there.

**The three forms** (Monster, Elite; health per investigator; numbers are the starting point for tuning):

| Form | Fight / evade | Health | Attack | Rule |
|---|---|---|---|---|
| As It Was (Past) | 4 / 3 | 3 [perinv] | 1 / 1 | Cannot move. Forced – end of round: each investigator at The First Occultation takes 1 horror (the applause). |
| As It Will Be (Future) | 3 / 4 | 3 [perinv] | 2 / 0 | Cannot move. Investigators at The Morning After get −1 [agi] and −1 [com] (the Years). |
| As It Is (Present) | 5 / 4 | 4 [perinv] | 2 / 2 | Massive, hunter, prey most Memory. Cannot be damaged until As It Was and As It Will Be are both defeated. Hold Back still works on it. |

**What the campaign brings (the branching pays off):** each deep Knowledge entry can be spent once, as an
[action] at the matching period, to deal 2 damage to the form there:
- Past: The Vote That Never Ends, The Hour Was Wrong, The Appointed's Name (the first and last are always known).
- Future: Who Walks Beside You, The Keeper's Ninth Death, The Ticket-Taker's Bargain (all optional).
So a party that skipped the far districts meets a harder Future. The choices keep their finale effects; the walker's
ring Hold Back, the unspoken name's cancel and the spoken name (now: 1 damage to any form at setup) carry over.
The Uninvited stays as the hunting minion; defeating it deals 2 damage to any form.

**Endings — where you finish is when you end up:**
- **Home (Present).** Defeat As It Is (only possible after both other forms). Then the existing resolutions
  R1, R1b, R2, R3, R4 decide what the ending costs (conditions now read "the Appointed is defeated" instead of
  "contest reached"); the existing epilogue follows.
- **Stranded in the Past (new R7).** After As It Was is defeated, the investigators may end the finale there; or the
  finale ends (Hour IX, defeat, reset value) and As It Was was the last form defeated. They live out their lives in
  the old Ambergrove, decades before they were born, and know exactly what the town will vote for.
- **Stranded in the Future (new R8).** The same for As It Will Be: they wake on the morning after, years on; the
  town has emptied; the road has walkers on it no longer.
- **Not ended (R5/R6 as now).** No form defeated when the finale ends.
Stranded endings end the campaign (bittersweet wins), each with its own epilogue lines (age bracket lines reworded
for the period; investigator lines where they apply).

## Cards (new or changed)

New: The First Occultation, The Morning After (locations); As It Was, As It Will Be, As It Is (enemies); Through the
Hours (act, replacing Contest the Crossing); R7, R8 (resolution cards). Changed: R1–R4, R5/R6 wording; the Uninvited;
the finale guide chapter and epilogue; the log's Finale Record (forms defeated; where you ended up).
Art: five new illustrations (two places, three forms) through the existing pipeline.

## Control token, log and engine

- Control: Begin Finale sets up as now; the Contest counter is replaced by three toggles (Past / Future / Present
  defeated) that record the forms and announce when the Present becomes vulnerable. Damage stays on the cards.
- Log: Finale Record gains "Forms defeated" and "Ended in: Past / Present / Future".
- Engine: model the three forms, travel, the matching deep entries, the stop-early choice (stop when continuing is
  unlikely to succeed), and score full victory / stranded / not ended; tune health and travel cost to ~40% full victory.

## Order of work

1. Owner approval of this structure (spoiler-free summary).
2. Engine model + tuning runs (30 carried campaigns per arm) before card text is final.
3. Cards, art, guide chapter, log, Control; story map test extended (forms, R7, R8); full test suite; publish.
