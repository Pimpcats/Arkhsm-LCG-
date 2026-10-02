# Campaign Playbook — from idea to a playable SCED campaign

How The Still Hour was made, written so the next campaign can follow it step by
step. The assistant does the work; the owner gives a short brief, makes a few
creative calls and plays. Read `AGENTS.md` and `docs/ASSISTANT_WORKFLOW.md`
first; this playbook adds the order of work, the checks at each stage and the
lessons learned.

**How to start one (owner):** open a session on this repo and say:
> /new-campaign Theme: … Tone: … Players: … Length: … Anything I want or don't want: …

(docs/NEW_CAMPAIGN.md is the one-page version for the owner.)

**How to resume (owner):** "Continue the <name> campaign from the playbook."
The assistant finds the phase from `campaigns/<id>/assistant/production.json`.

---

## 0. Spoiler protocol (every phase)

- The owner plays first-time. Chat, progress notes, image labels and PR text
  carry **no** plot, twists, enemy roles, rules text or endings.
- Spoiler-bearing files live in the repo (design docs, card data); tell the
  owner which files are spoilers.
- Owner-facing reviews use neutral labels and put spoiler groups behind a gate
  (the review gallery does this).
- Report validation honestly: "renders fit" is not "playtested".

## 1. The pipeline is campaign-generic (done 2026-10-01)

Every build script reads the campaign from `campaigns/<id>/build.json`
(`pipeline/campaign_config.py`); choose it with `CAMPAIGN=<id>` or `--campaign
<id>`. Without either, commands build The Still Hour, the reference campaign;
its `build.json` reproduces its dist/ files and card faces byte for byte (the
refactor was checked against all 214 outputs).

| Piece | Per campaign |
|---|---|
| Names, file names, ids, specs, guide, starter slice, hosted URLs | `campaigns/<id>/build.json` |
| Card specs, print layer, overrides, scenarios, assignments | `campaigns/<id>/specs/`, `card_overrides.json`, `scenario_manifest.json`, `scenario_assignments.json` |
| Campaign log content | `campaigns/<id>/log_layout.py` (drawing and token Lua are shared) |
| Art scenes, re-shoots, prompt pack | `campaigns/<id>/art_scenes.json`, `campaign.json` (house style), `art/ART_PACK.md` |
| Control token rules | `src/tts/<id>_control.lua` (+ optional modules under `src/<lua_dir>/`) |
| Play engine rules, arithmetic models | `tools/play_engine/lua/{effects,scenarios,rules,finale}.lua`, `pipeline/simulate*.py` — written per campaign |
| Shared table scripts (loop box, download box, log) | shared; the build swaps in the campaign's names |

**Scaffold:** `python3 tools/new_campaign.py <id> "<Name>" --prefix abcd` writes
a starter campaign that already passes the content check, builds, and passes
`pipeline/verify_control.lua` on Lua 5.2 and 5.4; `tests/test_new_campaign.py`
keeps that true. It refuses a prefix another campaign uses or overlaps (card
ids, hosted image names and publish clean-up all go by prefix). Its EXAMPLE
scenario has the official components (a clue act and a take-and-deliver act
with a story asset, Resign, agenda flavor, act/agenda backs, unrevealed
location sides, location rules text) in a neutral house style.
The owner's view is `docs/NEW_CAMPAIGN.md`; the assistant's runbook is the
`/new-campaign` skill (`.claude/skills/new-campaign/SKILL.md`).

## 2. Brief and pitch (owner: 5 minutes)

0. In a fresh checkout, run `python3 tools/library/build_library.py` first. It
   rebuilds the LCG rules/card library in `library/` (ignored by version
   control: Rules Reference, FAQ, official campaigns, `library/stats/`) that
   the design lessons and the structure table come from.
1. Owner gives theme, tone, player count, length and any must/never items.
2. Assistant reads docs/design/CAMPAIGN_DESIGN_LESSONS.md (what the top and
   mid-tier official campaigns do well, what the bottom tier does poorly, and
   in its section 1 the one authoritative table of official structure
   numbers), then proposes 2–3 **non-spoiler** pitches:
   premise, the core mechanic in one sentence, how scenarios connect, target
   length. Each pitch passes that doc's pre-brief checklist. Owner picks one.
3. Record the brief in `campaigns/<id>/assistant/production.json`.

Keep asks to the owner to real creative forks. Never ask the owner to author
content, name files or maintain manifests.

## 3. Campaign skeleton (spoiler doc)

Write `campaigns/<id>/design.md` (the scaffold creates its skeleton):
- **Structure:** scenarios (or loops/districts), their order and how they link.
- **Core mechanic and currencies.** Name each resource the campaign trades in
  (Still Hour: Hours, Dissonance, Memory, Years, Static) and what each costs
  and buys.
- **Story graph:** every scenario has at least 2 resolutions (up to 4–5).
  Choices are recorded and **echo** later, including in the climax. Every
  branch builds toward one finale with several endings.
- **Campaign log:** what is recorded (Knowledge, choices, Victory,
  per-investigator state), and which names stay hidden until earned.
- **Difficulty and player-count scaling** as explicit rules.

Use official campaigns as structure references, not as material to copy.

## 4. Rules text (the campaign rules and every card)

- Write in Rules Reference templating. Checklist:
  - en dash after bold labels ("Forced –", "Revelation –", "Objective –");
  - named actions as "[action]: Name.";
  - "Limit once per …" (each investigator) vs "Group limit …";
    "Max once per …" for events;
  - costs before the colon ("[action] Spend 2 clues: …"), and "As an
    additional cost to play X, …";
  - spend-clue objectives ("investigators at X may, as a group, spend N
    clues to advance");
  - an agenda's on-arrival effect as Forced templating ("Forced – When …:"),
    never a home-made label such as "When reached:".
- Every term the campaign invents is defined once in the guide's rules
  section, and cards use it the same way everywhere.
- **Three wording passes**, each by an independent reviewer (a sub-agent):
  1. audit against the Rules Reference;
  2. fix;
  3. verify the fixes and hunt contradictions between cards, guide and
     Control-token behaviour.

  Apply every finding or record why not.

## 5. Card design, by type — reference first, then design, then test

For each card type:
1. **Look at official patterns first.** `pipeline/survey_official_locations.py`
   shows the method (public ArkhamDB data): count what the text does, how long
   it is and where the exceptions sit. Adapt the script for other types.
2. **Design a system, not one-offs.** Cards of a type share a job. Still Hour's
   locations each carry a lever paid in a campaign currency or a hazard that a
   Knowledge entry quiets (`docs/design/LOCATION_DESIGN.md`).
3. **Place effects where they add something:** no duplicate pressure where the
   encounter deck already punishes, and quiet hubs.
4. **Test it (section 6)** before it goes on a card.

Coverage checklist (component rates in brackets, NotZ–TIC; see
`docs/design/OFFICIAL_COMPARISON.md`; structure numbers such as clues, shroud,
doom and deck size are in `docs/design/CAMPAIGN_DESIGN_LESSONS.md` section 1):
- agendas: flavor and rules on the front (100%), story and rules on the back;
- acts: fronts and backs (the back resolves or continues); vary the
  objectives — about a third ask for a clue threshold, the rest are
  take-and-deliver story assets, tests, enemies, sequences (manifest act
  `carry`: {asset, take_at, deliver_to}; the audit checks it);
- story assets (median 1 per scenario), set aside in their box;
- locations, both sides: rules text on nearly all (98%), Forced on about 40%,
  a rare [reaction], text on about a fifth of unrevealed sides (Closed rules
  go there, `unrevealed_text`);
- a Resign ability somewhere on most scenarios' maps;
- an encounter-set symbol and number on every scenario card: pick a shape per
  set in build.json `set_icon_shapes`, map boxes in `encounter_symbols`, run
  `python3 pipeline/render_set_icons.py`;
- enemies, treacheries, story and resolution cards;
- scenario reference card (Easy/Standard and Hard/Expert sides);
- player cards, signature weaknesses;
- investigators: front, back with deckbuilding and a spoiler-free background
  story, and minicards.

## 6. Balance (simulate before the table)

- Model each effect in the simulators as a profile (`LOCATION_PROFILES` in
  `pipeline/simulate_tempo.py`), with a **sensible-player policy**. A greedy
  policy understates optional levers.
- Compare against a no-effect baseline at 1–4 players and first-time and
  planned play.
- **Acceptance:**
  - campaign length on target (Still Hour: 6–8 loops, first-time 3-player
    finale unlock around loop 6);
  - no player count slowed noticeably;
  - no extra loops ending on the fail state;
  - XP-analog within the official 40–50 per investigator per campaign;
  - optional costs (Years) small.
- Record rejected designs and why (for example, the Records Office extra
  action slowed solo play).
- Check that the model covers the fail states (Dissonance reset) and scales
  with player count. Still Hour's first model did neither.
- Say plainly that a simulator checks the arithmetic of the pace, not play.
- Then calibrate on the play engine (`tools/play_engine`, docs/design/PLAYTEST_SIM.md)
  against the owner's win-rate curve **by night** (Still Hour: Prologue and
  night 1 80%, nights 2–3 70%, 4–5 60%, 6–7 50%, night 8 and the finale
  40% at three investigators). Later nights must play from that night's
  state (scar, Years, banked Memory) **with upgraded XP decks**; measure every
  night of each pair, not one per pair, since the state can move a night by
  10–25 points. Report to the owner by night, not by scenario variant.
- Compare the structure with the official campaigns before calibrating:
  doom, acts and clue acts, location clues and shroud, locations and deck
  size against the table in `docs/design/CAMPAIGN_DESIGN_LESSONS.md` section 1
  (the only place those numbers are stated); connections, enemy share and
  stats (elites included), treacheries with a skill test or a lingering
  effect, chaos-bag changes over the campaign (mostly Cultist / Tablet /
  Elder Thing; Elder Sign and Auto-fail almost never) and XP with
  `tools/official_compare/compare.py` (Still Hour:
  docs/design/OFFICIAL_COMPARISON.md). Report which gaps are missing and
  which are deliberate, and fix the missing ones first.
- Calibrate with several levers, not clue costs alone: tuning only the acts
  left The Still Hour with official-strength flow but weak enemies,
  automatic treacheries and acts three times the official size.
- Check every player count where a target is an integer (the finale's
  contest goal): one step can move the win rate 25–50 points, so choose the
  goal closest to the target per count and report the residual.

## 7. Guide and log

- The guide follows an official campaign guide's order:
  1. how to use;
  2. campaign rules;
  3. setup;
  4. map;
  5. the scenarios, each with intro, setup and resolutions (spoiler-gated
     "do not read until");
  6. between-scenario steps;
  7. finale and epilogue;
  8. difficulty/player count.
- It builds to PDF with `pipeline/build_guide_pdf.py` (```resolution fences).
- The log token and printed sheets mirror each other. Hidden rows reveal their
  name when ticked (field type `rv`).

## 8. Art

Follow `docs/ASSISTANT_WORKFLOW.md`:
- Aim for a painterly, period, restrained look.
- Use character reference images for continuity.
- Keep art free of lettering.
- Register art through the bridge.
- Show neutral-label reviews, and flag any visually revealing art before
  showing it.

## 9. Build, render and check fit

```bash
export CAMPAIGN=<id>
python3 pipeline/render_set_icons.py                    # the encounter-set symbols
python3 pipeline/scenario_content.py --lock             # every scenario LOCKED, 0 errors
python3 pipeline/render_placeholders.py                 # card faces
# local package for checking (private; never commit a --local build):
python3 pipeline/build_cards.py --local && python3 pipeline/bundle_mod.py --local
python3 pipeline/compile_campaign.py
python3 pipeline/table_presence.py --local && python3 pipeline/package_download.py --local
lua5.4 pipeline/verify_control.lua dist/<slug>_bundle.lua runCampaignTests
lua5.2 pipeline/verify_control.lua dist/<slug>_bundle.lua runCampaignTests
python3 -m pytest -q tests                              # about 7 minutes
# release (commits the hosted images, rebuilds dist/ with hosted URLs):
PUBLISH_COMMIT_TRAILER="<attribution lines>" python3 pipeline/publish_hosted.py
# The Still Hour only: lua5.4 pipeline/lua_smoketest.lua && lua5.4 pipeline/verify_bundle.lua (and lua5.2)
```

The suite tests The Still Hour, whatever `CAMPAIGN` is exported:
`tests/conftest.py` pins it. `tests/test_new_campaign.py` checks the kit in a
throwaway copy, and `tests/test_selected_campaign.py` runs the exported
campaign's scenario audit read-only. Publishing a campaign removes only its
own earlier images from `dist/cards/` (by prefix), never another campaign's;
`tests/test_publish_hosted.py` keeps that true.

Then **look** at every changed card (contact sheets). The automatic overflow
check misses text that runs under frame art. Known trouble spots:
- act text vs the clue circle;
- enemy text vs the circle edge;
- event text vs the lower corners;
- skill text vs the left border;
- investigator backs vs the portrait cartridge;
- doom and clue numerals vs their circles.

## 10. Package and in-game test

- The package is SCED-native:
  - memory-bag boxes;
  - replayable loop boxes where scenarios repeat;
  - a Control token for campaign bookkeeping;
  - a log token and a saved object the owner spawns (`docs/LOADING.md`).
- In-game verification: the owner runs the TTS relay from **local PowerShell
  on their PC** with Tabletop Simulator open. Results come back on the
  `tts-results` branch. The assistant cannot see the owner's desktop.

## 11. Owner review

- Publish the review gallery: every item coded (A-01…), per-item notes,
  **Copy feedback**, spoiler groups gated.
- The owner sends feedback by code; the assistant fixes, re-renders and
  republishes to the same link.

## 12. Playtest and tune

- Each design doc ends with a playtest checklist: what to watch per card
  or location.
- After a session, the owner sends what happened. The assistant tunes the
  named constants and card numbers, re-runs the simulators, and records
  errata in the design doc.

## 13. Release

- Work on the session branch. Merge to `main` only with the owner's go-ahead.
- Tag the release; `dist/saved_object_<id>.json` is the deliverable.

---

## Lessons from The Still Hour

- Never add card text "to fill space". Check official patterns, give the
  text a job in the campaign's system, and test it.
- Models must include the fail states and player-count scaling. Otherwise
  solo balance numbers are fiction.
- Wording drifts: run the three passes after any bulk text change, not once.
- Look at renders. Most fit problems were invisible to the automatic check.
- Hidden-until-earned log names protect a first-time owner; keep reveal
  fields in the log from the start.
- Relay test fixtures must respect the rules they test (for example, closed
  locations).
- Keep spoilers out of chat even when summarizing your own work.
- Never squash- or rebase-merge a publish commit. `publish_hosted.py` pins
  every hosted image URL to the commit that holds the images; rewriting that
  commit blanks every face in TTS. Use a normal merge or fast-forward.
- Tests must never write to the checkout. The CardForge selftests run in a
  temporary copy (`cardforge/sandbox.py`); a snapshot-and-restore scheme left
  tracked files rewritten mid-run and could wipe local art and backends.
  Check `git status --porcelain` is identical before and after every suite.
- Build scripts must fail loudly rather than write a broken release: without
  hosted URLs they refuse to put placeholder or `file:///` images into `dist/`
  (`--local` for private test builds).
- Keep machine-specific settings out of tracked files (`rig.local.json`, not
  `rig.json`) from the first commit. Untracking a file that is already
  tracked deletes it on the next pull elsewhere; keep it tracked with neutral
  defaults and have the app write an ignored override file.
- A test that waits on a background job must check the job's outcome, not
  just that the worker went idle, and must not let its own output be
  captured by the app's log redirection.

- The play engine lays out the table from `dist/`'s Saved Object (deck
  contents and counts) while card values come from the campaign data. Publish
  before a final verification run, and never publish while engine runs are
  in progress: runs that start before the new `dist/` play the old decks.
- Lua: `{ table.unpack and table.unpack(t) or unpack(t) }` keeps only the
  first value (an and/or expression returns one). It made the engine's
  enemies attack one at a time; copy lists with a loop.
- Audit components against official cards, not just numbers: The Still
  Hour first shipped with no agenda flavor, no set symbols, no story assets,
  no resign and nearly all clue-threshold acts (fixed in the parity pass).
- Objective feasibility checks must count every clue source really in play
  (the hub is always placed and clues are portable), or they flag costs the
  engine meets.
- The play-engine AI must work the hub/opening objective first. Letting it
  wander to the districts first moved measured win rates by 17–27 points.
- Test every Lua path on both Lua 5.2 and 5.4 (rules suite, Control check,
  engine fixtures). Table code that works on one can fail on the other.
- Wait until a chaos token has resolved (cancellation and redraw choices
  done) before applying an irreversible effect such as a campaign-state
  change; a token that is later canceled must leave no trace.
- Encounter assignment lists (`scenario_assignments.json`) are physical
  copies: each id appears once per copy. Never multiply them by a quantity
  again when counting a deck.
- The engine uses the standard opening mulligan (redraw any cards once;
  weaknesses set aside and replaced). Other policies skew early tempo.
- Measure with uncertainty intervals: report each win rate with its
  approximate 95% interval and the trial count, and treat differences inside
  the interval as noise.
- When a measurement is superseded, mark the old table historical at its
  top (with a link to the current source) instead of leaving two sets of
  numbers that look current.
- Measure difficulty with carried full-campaign runs (each scenario played
  from the state, decks and XP the earlier ones produced), not only with
  single-scenario presets. Single-night presets hid that later nights had
  only one objective each.

## Definition of done (per campaign)

- [ ] Every scenario has 2+ resolutions; choices echo into the finale.
- [ ] Every card type covered (section 5), both sides where they exist.
- [ ] Three wording passes applied; guide, cards and Control token agree.
- [ ] Simulators: acceptance criteria met; rejected designs recorded.
- [ ] Renders checked by eye; `scenario_content` all LOCKED, 0 errors; tests
      green.
- [ ] Package spawns; relay run in real TTS passes (owner, local PowerShell).
- [ ] Review gallery published; owner feedback applied.
- [ ] Owner playtest done; errata recorded.
