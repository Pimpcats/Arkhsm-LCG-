# Audit pass 5 — release readiness (SPOILERS, assistant/designer only)

Head audited: e5e5070 on claude/loving-bohr-n7ixl4 (2026-09-27). Four
independent read-only audits: card rules/grammar, guide vs Control code,
scenario setup consistency, release packaging. Plus the tempo and Memory
checks below. Nothing here is applied yet; the owner approves the fix pass.

## Automated results at e5e5070
- pytest 68 passed (149 subtests); tts_relay tests 9 passed
- scenario_content 8/8 LOCKED, 0 errors; compile_campaign 144 cards, 11 objects
- lua_smoketest 194/194 (5.4 and 5.2); verify_bundle OK
- cardforge selftest 20/20; studio_selftest 248 passed, 5 failed (Apply/rebuild
  section expects file:/// and placeholder URLs; at least one is stale since the
  card now has art; confirm and update the test)
- A git-archive rebuild reproduces committed card JPGs byte-for-byte; all 194
  hosted URLs pin commit 9322ff9 and resolve.

## Balance findings (tempo + Memory)
- Loop length is ~5 rounds at 3p (~6 solo, ~4 at 4p). Objectives per loop at
  3p: 0 = 3%, 1 = 40%, 2 = 49%, 3 = 8%. Loop-level race is fair; single
  districts are too loose: square_surface leaves 6.7 Hours, fairground_surface
  6.6, square_deep / almanac_surface ~5. Sim models no defeats and 0% resets.
- Memory income: simulate.py's 17/loop at 3p is an ASSUMED constant. Actual
  sources: investigator once-per-round reactions (Ayako ~4/loop, Elias ~2-3,
  Birdie ~2-3, Cass ~1-2, Seraphine 0), Prologue 2/inv (+1), Victory 15 total,
  Hall of Mirrors +2 (costs a Year), Familiar Face +1, Elder +1/loop. No loop or
  district resolution pays Memory. Campaign total ~25/inv vs official ~35-45,
  heavily party-dependent; solo Seraphine earns almost none (finale needs
  4 banked per investigator for R5).
- Proposed: district objective pays banked Memory (+1/inv surface, +2/inv
  deep); give Seraphine a once-per-round Memory trigger tied to raising
  Dissonance; tighten the easy objectives so a single district leaves ~2-4
  Hours; derive the Memory income model from card sources; re-run all sims.

## Cards (rules/grammar)
Major
- Lantern Room calm side vs Crowd Turns / Eighth Grave: no "cannot", so
  precedence is undefined. Decide which wins and state it on the cards.
- Who Walks Beside You: needs an awake Echo at the Turning; nothing spawns there
  and a lit lamp keeps Road Echoes asleep. Add a forced spawn when it becomes
  current (Waiting Congregation at the Turning, awake while this act is current).
- Fairground: The Bargain (deep) is a single Parley action at the Ticket Booth;
  Wheel Turns (surface) is one agi(3) test. Far cheaper than all other acts.
  Proposed Parley cost: spend 1 [perinv] clues.
- No player asset/event has skill icons (only the 3 skills have wild). Give
  signature assets 1 icon of the investigator's best skill, Recollection events
  1 wild; Anchor Point stays blank.
- Town Hall Steps kinder side ("look at the next Hour") does nothing: Hours are
  fixed order. Replace with a real effect.
- elderSign data field differs from printed [elder] text on Ayako, Seraphine,
  Cass; copy the printed lines into the field.
Minor
- Eighth Grave parenthetical placement; "Memory on Elias" wording.
- Familiar Face spawn tie-breaker; House Always Wins banked Memory floor at 0;
  its statline still DRAFT.
- Keeper's Quarters heal has no limit (add Limit once per round).
- This Time For Sure: token return and static side effect; Muscle Memory
  conditional draw; It Means 'Wait' clause split.
- Define "loop" = the Prologue during the Prologue.
- Curly apostrophe in The Appointed's Approach name; Appointed's Whisper traits.
- Waiting Congregation / Drowned Choir printed quantity 2 vs 3 in play.
- Flipped Lantern Room / Town Hall Steps sides have no clue value; unify
  "calm side" vs "other side".
- Last Hour objective omits two contest sources; guide Control note on "pushes
  back without rewinding" contradicts the card.
- Borrowed Time and Cassandra's Notebook weak for their Memory price.
Open questions: Hold Back uncapped per round (multiple investigators, exhausted
Appointed); loop length shrinks with player count while clue needs scale;
Bargain and Vote have no lasting town effect; surface vs deep act wording on
who may contribute clues.

## Control token / guide vs code
Major
- Reset Loop has no guard; the guide invites a second click (Prologue end and
  Between Loops "if you have not already"). Second click adds a completed loop,
  raises the scar, can open Part II early and overwrites lastLoopEndDissonance.
  Fix: loopEnded flag set in reset(), cleared in beginNextLoop().
- "Ended in danger" Year uses the investigator count at Age time; changing
  Investigators after an age-out mid-interlude changes the threshold. Store
  lastLoopEndedInDanger at reset.
- Departed (aged-out) investigators keep receiving Elder/Ancient start Memory
  and it gets banked. Restrict to investigators in play under 18 Years.
- Run Tests restores the snapshot only at the end; an error mid-run leaves test
  data as the live campaign. pcall + restore, or move to a context menu.
Minor
- Hour VI cancelled by It Means 'Wait' still sets the once-per-loop flag; no undo
  for the Almanac bag reduction (right-click static cannot undo it).
- Changing Investigators mid-loop does not clamp or check reset/band entry.
- Hour IX broadcast in the finale says "you may attempt the finale".
- Age button works after the Prologue (guide says skip step 1).
- Log token ticks Part II from surface>=3 or loops>=3 mid-loop; use st.partTwo.
- Sealed Study opens on facts alone even if act 2a never became current.
- LoopFlags.muscleMemoryUpgraded reads the previous loop; unused; fix or delete.
- Hunt pathing ignores unrevealed locations.
- Interlude Memory button tooltip says "Bank on-card Memory" (it is +/-1).
- Knowledge.actIIOpen() status print ignores the Loop 3 route.
- Guide: line 24 reads as once per round overall (rule is per connection);
  "Every Hour has a doom threshold of 1" (Hour IX has none); log sheet Part II
  omits "or after Loop 3"; Sync Board / Status / Knowledge / Run Tests buttons
  undocumented.
- Test gaps: band/scar at 1/2/4p, double Reset Loop, count change before Age,
  departed Memory, difficulty buttons, Victory claim, interlude purchase, Hour VI
  in the in-engine runStillHourTests.

## Scenario setup
Major
- Guide never lists encounter set contents/quantities (only the manifest does).
  Add an Encounter Sets table per box.
- Deck is oversized and treachery-heavy: Square core 28 (7 enemies / 21
  treacheries); a typical loop 33-36 cards, treacheries 74-79%. All Prologue and
  Square-core enemies are Echoes, so Calm has no active enemy. Proposed: cut
  Wrong Turn, Stutter, Dead Air, Loop Notices You to 1 copy (core 24) and add a
  non-Echo monster to the spine or the Prologue.
- Six new enemies publish with blank art windows (owner's ChatGPT request).
Minor
- Prologue endings omit the First Hour advancing (R1). Lighthouse reachable only
  via the Road: say so in its Place entry. "Kept as anchor" vs log label "in the
  finale". Log fields never mentioned in the guide (Current Part, Recollections
  owned, Spent this interlude, Those Who Left, finale record). First Dark / Last
  Hour / R1-R6 cards never referenced by the guide. Table layout vs ASCII map
  adjacency. Lighthouse has effectively no active enemy after lighting.
  connections_patch.json is stale and unused.

## Release packaging
Blockers
- Branch not on main (27 ahead, fast-forwardable). Hosted URLs pin 9322ff9,
  reachable only from this branch: never squash/rebase-merge. The relay and
  START_HERE point at main (Sep 24 build).
- Current head never run in real TTS (last relay 89/89 on 5bb290d).
Major
- Six blank-art cards; House Always Wins DRAFT; relay runner gaps (difficulty,
  Victory, purchase, Hour VI); owner docs stale.
Minor
- Guide PDF bytes differ across environments (text identical).
- art_urls.json is gitignored: standalone build_cards/bundle_mod/table_presence
  write file:/// URLs (BUILD_STATUS tells readers to run them). Selftests also
  rewrite tracked files (campaign.json, scenario_assignments.json, dist/) while
  running and restore at the end; never commit mid-run.
- rig.json tracked with the owner's Windows user path; 0-byte `export` file;
  orphan dist/cards/sthr-campaign-log.jpg; 30 MB third-party .seext plugin in a
  public repo (confirm redistribution); download box cannot work as built
  (Saved Object is the load path).
- Two Square locations have no back image (confirm intended).
- Stale docs: README, START_HERE, CHECKLIST, BUILD_STATUS, HANDOFF,
  production.json (counts, branch, pending items).
