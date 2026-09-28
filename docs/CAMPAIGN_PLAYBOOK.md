# Campaign Playbook — from idea to a playable SCED campaign

How The Still Hour was made, written so the next campaign can follow it step by
step. The assistant does the work; the owner gives a short brief, makes a few
creative calls and plays. Read `AGENTS.md` and `docs/ASSISTANT_WORKFLOW.md`
first; this playbook adds the order of work, the checks at each stage and the
lessons learned.

**How to start one (owner):** open a session on this repo and say:
> Start a new campaign using docs/CAMPAIGN_PLAYBOOK.md. Theme: … Tone: …
> Players: … Length: … Anything I want or don't want: …

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

## 1. Before campaign #2: make the pipeline campaign-generic (one-time)

The Still Hour was built first, so parts of the pipeline name it directly.
Current state:

| Piece | State | Work for a new campaign |
|---|---|---|
| Card renderer, frames, fonts, glyphs (`pipeline/render_placeholders.py`, `cardforge/`) | generic | none |
| Card specs (`pipeline/stillhour_*_spec.json`), overrides (`campaigns/<id>/card_overrides.json`) | file names are Still Hour's | move specs under `campaigns/<id>/` and read the path from `--campaign` |
| `compile_campaign.py`, `scenario_content.py`, `assistant_bridge.py` | take `--campaign` | none |
| `build_cards.py`, `table_presence.py`, `package_download.py`, `publish_hosted.py`, `build_guide_pdf.py`, `bundle_mod.py`, `campaign_log.py` | name Still Hour files/ids | parameterize by campaign |
| Control token rules engine (`src/tts/control.lua`, `src/StillHour/*.ttslua`) | Still Hour's own mechanics (loops, Hourglass, Dissonance, Years) | a new campaign with new mechanics needs its own engine modules; reuse the board, SCED and UI helpers |
| Campaign log token layout (`pipeline/campaign_log.py`) | Still Hour's fields | new field list; the renderer and Lua are reusable (field types cb/ct/tx/dv/rv) |
| Tempo/economy simulators (`pipeline/simulate*.py`) | Still Hour's map, objectives and currencies | reuse the structure; replace the data tables and currency rules |
| Loop box, memory bags, relay (`src/tts/loop_box.lua`, `tools/tts_relay/`) | generic | point at the new package |

Do this first, as its own branch, with the Still Hour build as the regression
test: after the refactor it must rebuild byte-identical cards and pass every
test.

## 2. Brief and pitch (owner: 5 minutes)

1. Owner gives theme, tone, player count, length and any must/never items.
2. Assistant proposes 2–3 **non-spoiler** pitches: premise, the core mechanic
   in one sentence, how scenarios connect, target length. Owner picks one.
3. Record the brief in `campaigns/<id>/assistant/production.json`.

Keep asks to the owner to real creative forks. Never ask the owner to author
content, name files or maintain manifests.

## 3. Campaign skeleton (spoiler doc)

Write `docs/design/<ID>_DESIGN.md`:
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
  - "When reached" text on agendas.
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

Coverage checklist:
- agendas and acts, fronts and backs (the back resolves or continues);
- locations, both sides (unrevealed: flavor only);
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
PUBLISH_COMMIT_TRAILER="<attribution lines>" python3 pipeline/publish_hosted.py
python3 -m pytest -q tests
python3 pipeline/scenario_content.py --campaign <id>     # every scenario LOCKED, 0 errors
lua5.4 pipeline/lua_smoketest.lua && lua5.4 pipeline/verify_bundle.lua
```

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
