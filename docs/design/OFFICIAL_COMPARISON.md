# The Still Hour against the official campaigns

Design document (spoilers). The owner's checklist for "the correct flow":
agenda pacing (doom), act pacing (clues), locations (count, connections,
clues against the act), enemy spawns including elites, encounter cards,
chaos-bag changes over a campaign, and XP gain.

Official figures: `tools/official_compare/compare.py` (downloads SCED's own
TTS campaign files, arkhamdb-json-data and arkham-cards-data into
`.cache/official/`; nothing vendored). 54 scenarios, Night of the Zealot to
The Innsmouth Conspiracy; the newer campaigns are missing from
arkhamdb-json-data, so their stats are left out. Medians, with the middle
half of scenarios in brackets. The Still Hour: a night at three
investigators (the Square plus one district unless noted), measured
2026-10-01.

| area | official | The Still Hour (before this pass) | verdict / change |
|---|---|---|---|
| Agenda: total doom | 18 (14-20) over 3 agendas (about 6 each) | 17 over 8 Hours (2 each); 10.5-13 rounds a night | matches in total and length; the Hourglass's small steps are the campaign's clock (kept) |
| Act: clues asked | 2.5 per investigator per clue act, 3 per scenario (0-5) | 9-10 per investigator (Part I), 6-8 (Part II) | about 3x; **rescaled to official** (third pass, below) |
| Location clues | 0.9 per investigator per location (0.7-1.2), 10 per scenario (7-15) | 2.3 per location, 16-21 a night | about 2.5x; **rescaled to official ranges** (third pass, below) |
| Locations | 11.5 (9-14) | 7-8 with one district, 11-14 with two or three | in range on a typical night |
| Connections per location | 2.5 (1.6-3.5) | 1.7-1.9 (district leaves are dead ends) | low end of the official range (kept) |
| Enemies | 30% of a 30-card deck (25-33); fight 2.9 / evade 2.6 / health 3.0 per enemy copy; 2 elites (1-3) | 29-37% of 25-33 cards; fight 1.9 / evade 2.0 / health 2.4; elites 1-2 a night (the Appointed, a Named enemy in Part II) | **stats raised** to 2.7-2.8 / 2.4-2.6 / 2.8-3.0 (CREATURES_AND_VICTORY.md) |
| Encounter cards | 52% call for a skill test (40-60%); 37% stay in play | 1 of 23 distinct cards had a test (7% of copies); none stayed in play; mostly automatic horror | **10 rewritten** as "Test X (3). If you fail, ..."; Rising Water attaches until the Hourglass advances (about half of a night's treachery copies now test) |
| Chaos bag | Standard about 16 tokens; over a campaign, story results add or remove a symbol token (add: Elder Thing 66, Tablet 64, Cultist 53, Skull 12, Auto-fail 1; remove: Tablet 73, Elder Thing 73, Cultist 65, Skull 4, Elder Sign 1, across 12 campaigns) | Standard 17 tokens; nothing changed over a campaign (only the temporary [static] tokens) | **added**: Part II +1 [tablet]; the first Torn loop +1 [cultist]; the first age-out +1 [elderthing]; The Hour Was Wrong -1 [elderthing], Who Walks Beside You -1 [cultist], The Appointed's Name -1 [tablet] |
| XP | about 4-6 per scenario, 35-50 per campaign; Victory pays each investigator | engine: about 2.7 Memory per investigator a Part I night, 4 a Part II night, about 30 a campaign (part of it spent on Recollections); Victory paid the group once; surface entries 0, deep 2; cap 6 per investigator | **raised**: Victory pays each investigator, surface entries 1 and deep entries 3 per investigator, cap 10 per investigator; engine: about 5.6 a Part II night |

## How the Still Hour side is measured

- Encounter deck, enemy share and stats: `scenario_assignments.json`
  encounter lists with the campaign card data (Square box plus the district
  box; Part II adds the Appointed's Whispers).
- Connections: the location GMNotes in `dist/saved_object_the_still_hour.json`
  (same icon/connection format as SCED's official files), with the same
  degree count as the tool.
- Treachery tests and lingering effects: the same text patterns as the tool.
- XP: play-engine games (`memory_bank_end - memory_bank_start` per
  investigator), plus `pipeline/simulate_tempo.py --memory`.

## Implementation

- Chaos-bag changes: `src/tts/control.lua` (`bagChanges`, `bagFor`,
  `refreshBag`) derives them from the campaign state (Part II, Knowledge, the
  `torn` mark set by Reset Loop, Years at 18) and refills SCED's bag with the
  chosen difficulty plus the changes; `tests/sced_real/playthrough.lua`
  checks Part II (+[tablet]) and The Hour Was Wrong (-[elderthing]).
- Treacheries: `tools/play_engine/lua/effects.lua` resolves the new tests.
- XP: `Knowledge.MEMORY_PER_INVESTIGATOR`, `Constants.forCount().memoryCap`,
  `shApiClaimVictory` (X per investigator).

## Card components (second pass, 2026-10-01)

The owner's follow-up: everything an official scenario prints, front and
back. Official figures: SCED's TTS files and arkhamdb-json-data, Night of the
Zealot to The Innsmouth Conspiracy (same sources as above).

| component | official | The Still Hour before | change |
|---|---|---|---|
| Agenda front flavor | 100% of agendas | 0 of 9 Hours | **added** to all nine Hours |
| Location rules text | 98% | 83% (4 blank) | **every location** has text |
| Location Forced effects | 44% | 22% (5 of 23) | **39%** (9 of 23): the Nave, the Milestones, the Low Bridge, the Flooded Crypt added |
| Location [reaction] | 4% | 0 | the Reading Room (1 of 23) |
| Unrevealed-side text | 18% | 0 | **17%** (4 of 23): Closed rules moved to the Flooded Crypt's and the Sealed Study's unrevealed sides (where official Closed locations print them), the Belfry, the Winding Stair |
| Acts with a clue threshold | 36% | 86% (12 of 14) | **50%** (7 of 14); five acts became take-and-deliver objectives (an [action] spends the clues to take control of a set-aside story asset; the act advances when its controller reaches another location; the clue circle prints a dash) |
| Story assets | median 1 per scenario | 0 | **5**: Keeper's Logbook, Parish Register, Drowned Page, Town Ledger, Bound Almanac (each with an ability tied to its district's threat, a Forced drop on elimination and an [action] to pick it up; the illustration is the act's) |
| Resign | median 1 per scenario | none | **[action]: Resign** on the hub Square (not in the finale or the Prologue); a loop ending for when everyone resigned or was defeated |
| Encounter-set symbol and number | every scenario card | none | **13 set symbols** (drawn in code, `pipeline/render_set_icons.py`) printed in each frame's set slot, with "n/total" in the footer (`pipeline/encounter_sets.py`); shown in the guide's district setup and appendix |
| Act / agenda backs | story and rules on every b side | present on all | story assets' acts add "Remove X from the game." |

The play engine encodes every new effect (COVERAGE in
`tools/play_engine/lua/effects.lua`): the location Forced effects and
reaction, the Belfry's unrevealed Forced, taking, carrying, dropping on
defeat and delivering a story asset, and the assets' skill bonuses. The
party never resigns (it cannot win a loop that way).

## Clue scale and the night's goal (third pass, 2026-10-01)

The owner's follow-up: act clue costs and location clues to official, and
locations as a range like official (Victory locations richer and harder).
Official figures: 973 locations and 93 scenarios from 11 campaigns
(`library/stats/scenario_structure.csv`, built by
`tools/library/build_library.py`).

| part | official | The Still Hour before | now |
|---|---|---|---|
| Ordinary location clues (per investigator) | 0 (20%), 1 (50%), 2 (16%), 3+ (4%); mean 1.05 | 2-3 everywhere | 0-2, mean 1.2 (a thoroughfare at 0, most at 1, the richer rooms at 2) |
| Victory location clues | 1 (54%), 2 (38%), 3 (6%); mean 1.48 | 2-3 | 1-2, mean 1.8 |
| Ordinary shroud | mostly 2-3, mean 2.65 | 2-4 | 1-4, mean 2.2 (the hub and roads at 1) |
| Victory shroud | mostly 3-4, mean 3.1 | 3-4 | 3-4, mean 3.4 |
| Acts per scenario | 3 (2-4) | 1 district act a night | the night's goal is two acts: the district's and the Square's current act (with the agenda's Hours, the official shape) |
| Clue cost per clue act | 2-3 per investigator (max 5) | 4-9 | 2-3 (take-and-deliver acts spend 2 to take the story asset) |
| Location clues a night (per investigator) | 10 (7-15) | 14-19 | 9-11 (the Square plus one district) |

Measured with the play engine (`tools/play_engine/report.py`: a night counts
as won only when every act of its goal is done) against the owner's curve:
docs/design/PLAYTEST_SIM.md.
