# The Still Hour — story, resolutions and reading-load review (2026-10-07)

**SPOILERS — designer/assistant only. Do not quote in owner chat, status summaries or PR text.**

Scope: the player guide (`docs/design/THE_STILL_HOUR_player_guide.md`), the effective card text
(`pipeline.scenario_content.load('still_hour')`: acts, Hours, stories, resolutions, story assets, locations,
enemies), the campaign log choice table (`pipeline/campaign_log.py`) and the play-engine Prologue run.
Read in full, not sampled. This is a content review; it is not a playtest and says nothing about how the
campaign feels in Tabletop Simulator.

## 1. The story as written

**Premise.** Ambergrove is gathered for an occultation the town's almanac promised for midnight. It happens
at eleven, the night folds, and the investigators wake in the Square at eleven o'clock with everyone else
unaware. Each play-through ("loop") costs them Years.

**The answer the six districts assemble.** The town once voted, unanimously, to open a door so that Ambergrove
would never be forgotten. The cost was to be settled at an appointed hour. Someone changed the hour in the
printing ("one late"), in brown ink, so the debt was never collected and the night never closed. Something
the town invited (the Appointed, "the guest") is climbing the hill toward the Square; it was never late, the
town is simply early, every time. The loop is held in place by anchors: people consumed by repeating it
(the hooded walkers on the Sunken Road, worn smooth; the Lighthouse keeper, who has died eight times trying
to leave by his own light and left a ninth line ruled and waiting). The investigators are being turned into
the next ones (Resolution 6 shows new faces under the hoods).

| District | What it contributes to the answer |
|---|---|
| Square | The sheriff has been dead since ten; something wears him and the town. The Records Office holds the minutes of the vote (deep act): the cost, the "one late" amendment, and where the name is kept. |
| Almanac House | The proof pulled before the type was changed (surface); the Sealed Study and the Appointed's name (deep, needs Almanac surface + the Vote). |
| Drowned Church | The bell tolled thirteen; the register has the thirteenth stroke added in a different ink (surface); the page showing the true hour (deep). |
| Sunken Road | The walkers are earlier loopers; the ring is an anchor's ring, worn thin (deep). |
| Lighthouse | The keeper's eight deaths and the ninth line (deep); the lamp, which "remembers being lit" (surface). |
| Fairground | The Wheel shows the whole town at once (surface); the ticket-taker's fare, the one way out that is paid for (deep). |

**Beats.**
1. Prologue: one night, learn the clock. The act is gated to Hour VIII; the cheaper reward needs the group at
   the Almanac Steps late. Cannot be lost; "What You Saw" gives the first choice (warn the town / tell no one).
2. Part I (loops 1–3, or three surface entries): learn the town; each surface act answers "what is wrong
   with this place". Torn / Taken / Closed at the Hour loop stories escalate the cost of failing.
3. Part II (The Shape of the Hour): the second acts open, Named enemies enter, the Whispers join the deck.
   Each deep act records a Knowledge entry and forces a two-way choice with a standing consequence.
4. The way opens (The Way the Night Breaks = the Name + the Vote + the Almanac's surface entry; two districts
   minimum). Before the finale, the cost is stated in the open and the 4-Memory-per-investigator safety net.
5. Finale: contest the crossing. Six deep entries, Hold Back successes and the Uninvited are the sources.
6. Resolutions 1, 1b, 2, 3, 4 (contest reached; each cost is paid in Years or in a person) or 5 / 6
   (contest not reached; try again or the campaign ends). Epilogue by age bracket, plus Seraphine's thread.

**Choices and where they return.** Every choice returns in the finale; all but two also echo in another
district's entry text:

| Choice | Finale effect | Echo elsewhere |
|---|---|---|
| Town warned / kept the night | R2 (2 Years instead of 3); R1b (3 per investigator) | Square, Fairground |
| Signed the ninth line / left blank | R1 eligibility; R3 ending line | Road |
| True page to the Press / drowned heard | Fewer Static / rewind Hourglass | Almanac / (Church only) |
| Ring carried / kept | One free Hold Back / R1 costs 1 Year not 3 | (Road only) / Lighthouse |
| Vote torn out / still stands | R4 walk-away / R2 availability | Square, Fairground |
| Ticket held / refused | R1b / Lost Hour cancel | Road, Fairground |
| Name spoken / unspoken | +1 contest / cancel one Hour advance | Church |

## 2. Findings and dispositions

| # | Finding | Severity | Disposition |
|---|---|---|---|
| S1 | **The Prologue objective had dropped to 5/40 in the play engine** (R1 reached; 34/40 at the 2026-10-03 and 2026-10-06 builds). Bisected to commit 35c9065: the delayed clue sweeps (1.5, 5, 12 s) after Clear Board/Recall cover the same spots the next Place fills, so a loop started straight after Clear Board lost its locations' clues. In Tabletop Simulator this would show as locations with no clues right after Clear Board then Place. | High | **Fixed** (delayed sweeps skip tokens under a card; `place_state` N-9). Engine back to 34/40. Full suite 304 passed. |
| S2 | "Walkers keep their ring" has a standing rule (exhaust the Sunken Road's Echoes after the lamp is lit) that exists only in the Lighthouse entry; the log's standing-rule list (read at Loop Setup step 9) did not carry it. | Low | **Fixed** (`STANDING[("ring","b")]`; log page 3 re-rendered). |
| S3 | Fairground: the "You hold the ticket" line says "the barker's eyes slide past you"; the barker is an enemy, the ticket-taker is the figure who made the offer. | Low | **Fixed** (ticket-taker). |
| S4 | "Every choice echoes somewhere else in Ambergrove": the ring-carried and drowned-heard options echo only inside their own district. | Low | Open. Optional one-line echoes (e.g. in the Lighthouse and the Almanac House). Writing, not a defect in play. |
| S5 | A woman in a green shawl is set up in the Prologue and the Square and never explained. | Low | Open, a creative call. Either pay it off in the epilogue or leave it as an unexplained recurring figure. |
| S6 | The brown-ink hand that changed the hour is never named. The Almanac and Ayako's line (a note in her own hand: "wait") imply the investigators did it in an earlier loop. | Info | Intentional ambiguity; consistent. |
| S7 | A party that finishes only the minimum route (Square + Almanac House) reads "Before the finale" (anchor imagery) without having met the walkers or the keeper. The anchor idea is then introduced by Resolution 1 itself. | Low | Acceptable; note only. |
| S8 | The printed collector number comes from the encounter-set table (2/8 for the Lighthouse's second act). `stillhour_scenario_spec.json` carries a stale "2/9" for it that is never printed. | None | No change. |
| S9 | The guide says Prologue "about eight rounds or more". The engine runs 8–12 rounds (median 10). | None | Matches. |

Not found: a resolution whose condition cannot be met; a choice with no downstream use; an act whose back
contradicts a district resolution; a district resolution that names a record the act does not write; a
card/guide mismatch in the six finale resolution cards (they are short forms of the guide text).

## 3. Reading load (words; ~150 words a minute read aloud)

| Part | Words | Of which story |
|---|---|---|
| How to Use + New Rules (read aloud before the Prologue) | 1,683 | 0 |
| Campaign Setup + Map | 735 | 0 |
| Prologue (+ What You Saw) | 1,065 | ~400 |
| Loop Setup (every loop) | 1,254 | 195 (+530 loop resolutions) |
| Between Loops (every loop) | 1,163 | 316 |
| Each district entry (first time in a loop) | 32–44, up to 140–180 with log variants | all |
| Each district's resolutions (read one, plus add-ons) | 49–280 | all |
| Each district's act cards (front, back) | 315–425 | 122–160 |
| The nine Hours (back flavour) | 291 | all |
| The Last Hour | 2,652 | 540 (+940 resolutions) |
| Campaign Rules (reference, not read through) | 5,372 | 0 |

A typical loop reads about 450–650 words of story (loop ending, one resolution per placed district, interlude)
plus roughly 300 more as the Hours and acts turn, against about 1,400 words of procedure (Loop Setup and
Between Loops). The story is light; the repeated administration is what is heavy.

## 4. Triple check (2026-10-10): continuity, flow and wording

Three independent full reads of the guide, every card's effective text, the log and the Control token's
tooltips and chat: story continuity (9 should-fix, 17 nits), flow and dead ends (7 story-level, 16 nits) and
wording/rules consistency (1 blocker, 19 should-fix, 44 nits). Each finding was checked against the source
before it was applied. Reports: `scratchpad/review/{continuity,flow,wording}.md` in the session (not committed).

**Dead ends: none.** Every Knowledge entry, choice option and log record now has a reader downstream.
The four records that were written but never read now are: You Are Unstuck (starts Part I), Prologue ended
(the second Taken interlude reads it), Closed at the Hour (an epilogue line) and the blank ninth line (a
Sunken Road echo). Every act back says what leaves play; every set-aside card has a release; the finale's
"not reached" endings point to R5/R6 on the cards.

Fixed (summary; the diff is the record):

- **Rules/cards:** the Approach card and Appointed tooltip no longer name The Debt of Hours (it does not
  advance the Approach); act-2a backs remove their story asset and Named enemy, and finale setup removes
  any act-2a enemy; R5 marks the loop as its ending would (Torn/Taken/Closed), matching the Control token;
  Who Walks Beside You takes an Echo in play if none is at The Turning; Hour IV prints its Hour Was Wrong
  exception; The drowned heard the true hour gains a standing rule (first Thirteen each loop canceled) on
  the log and in the engine; Begin Finale applies the Press's 1-fewer-Static itself; the Elder/Ancient start
  Memory step restored to Loop Setup; Sync from campaign's coverage described page by page.
- **Story:** the keeper's deaths no longer happen "by its own light"; the surface proof's struck hour cannot
  be read; the occultation completes "at the almanac's hour, an hour after it began"; Seraphine's
  "before Ambergrove" weeks; the ninth line "is not its to write"; R1's anchor does not come back down
  (moved to the right branch); the Ancient epilogue no longer implies a century outside; the Prologue intro
  no longer assumes the investigators arrived that night, with an Elias add-on; Elias's name in the ledger;
  the Shape of the Hour no longer says the guest only now stops waiting; Wheel streets "still"; "the first
  occultation" kept for the original night only; Fairground R3 after the Bargain; an R4 holder line; the
  green-shawl line only when someone leaves; Cass, Ayako and The Page That Wasn't lines.
- **Wording:** loop vs night in rules/tooltips; Act slot and set-aside pile; "reset value" everywhere;
  Hour IX messages; tooltips for Back, Place, Recall, Years, Quest, Status, Knowledge, Bank; duplicated
  rules removed (three-investigator note, Prologue Years, Walk It Backward parenthesis).

Left as is (deliberate): the brown-ink hand stays unnamed (S6 above); "kneeling congregation" vs The
Waiting Congregation (different words in play); Cassandra's Notebook name; the printed collector number
(S8); the campaign box's description text; a fifth log panel (a replacement takes the replaced
investigator's panel).
