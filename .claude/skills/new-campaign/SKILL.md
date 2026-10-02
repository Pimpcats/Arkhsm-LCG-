---
name: new-campaign
description: Make (or continue) an original Arkham Horror LCG campaign for SCED/Tabletop Simulator the way The Still Hour was made, from the owner's idea to a tested, published saved object. Use when the owner says /new-campaign, asks to start a new campaign or campaign idea, or to continue/resume a campaign other than The Still Hour.
---

# New campaign runbook

The owner gives an idea and plays the result as a first-time player. You do all
production work. This runbook is the order of work; the detail behind each step
is in `docs/CAMPAIGN_PLAYBOOK.md` (read it first, with `AGENTS.md` and
`docs/ASSISTANT_WORKFLOW.md`). The owner's one-page view is `docs/NEW_CAMPAIGN.md`.

## Always

- **Spoilers:** nothing about plot, enemies' roles, twists, solutions, endings or
  rules text in chat, progress notes, image labels, commit/PR summaries. Report
  with numbers, scenario numbers and plain next steps. Spoiler files live in the
  repo; say which files are spoilers.
- **Owner style:** concise but complete; say which machine/shell a step runs on
  (usually: nothing on the owner's PC except Tabletop Simulator); give the best
  solution directly, no reversals; never tell the owner when to stop; never claim
  to be watching something you are not; report validation honestly
  (computer-played games and tests are not a playtest).
- **Ask only real creative forks** (pitch, curve, art direction). Never ask the
  owner to author content, name files or maintain manifests.
- **Git:** work on the session's designated branch; commit and push as you go;
  never force-push or rewrite history; fast-forward `main` only after a validated
  publish; no PR unless asked.
- **State:** keep `campaigns/<id>/assistant/production.json` current (stage,
  next actions, validation evidence) and resume from it, not from memory.
- Every build command takes the campaign from `CAMPAIGN=<id>` (or `--campaign <id>`).
  Without it, commands build The Still Hour, which is the reference campaign.

## Continue

`/new-campaign continue <name>`: find `campaigns/<id>/`, read
`assistant/production.json` and the design doc, inspect the current branch, and
carry on from the recorded stage. Report the stage in one line, then work.

## Start: the phases

0. **Library.** In a fresh checkout run `python3 tools/library/build_library.py`
   first: it rebuilds the LCG rules/card library in `library/` (ignored by
   version control: Rules Reference, FAQ, official campaigns and
   `library/stats/`), which the design lessons and the structure table use.
1. **Brief** (owner, 2 min). Theme, tone, players (default 3), length (default 8
   scenarios), must/never. Record in production.json.
2. **Pitch.** Read `docs/design/CAMPAIGN_DESIGN_LESSONS.md` first (what the
   official campaigns do well and badly; its section 1 is the one authoritative
   table of official structure numbers: use it, do not restate other figures). Then
   write 2–3 spoiler-free pitches: premise, the core mechanic in one sentence, how
   scenarios connect, length. Each passes that doc's pre-brief checklist. The
   owner picks (AskUserQuestion).
3. **Scaffold.**
   `python3 tools/new_campaign.py <id> "<Name>" --prefix <4 letters>`
   (a prefix another campaign uses, or that overlaps one, is refused)
   writes `campaigns/<id>/` (build.json, neutral house art style, an EXAMPLE
   scenario in the official shape: a clue act, a take-and-deliver act with a
   story asset, Resign, agenda flavor, act/agenda backs, unrevealed location
   sides, location rules text; log layout, guide and design skeletons,
   production tracker) and
   `src/tts/<id>_control.lua` (a working Control token). Check it builds before
   changing anything (step 9 commands). Replace every EXAMPLE as you go.
4. **Design** (`campaigns/<id>/design.md`, spoilers): structure, core mechanic and
   currencies, story graph (2+ resolutions per scenario, choices that echo into the
   finale, several endings), campaign log (hidden-until-earned names), chaos-bag
   changes (story results add/remove [cultist]/[tablet]/[elderthing]; Elder Sign
   and Auto-fail almost never), XP plan (Victory per investigator + resolution
   bonuses, 35–50 per investigator per campaign), difficulty and player-count
   scaling. Confirm the win-rate curve with the owner (default: early scenarios
   80%, then 70 / 60 / 50, finale 40% at 3 players; never above 80%).
5. **Content.** Cards in `campaigns/<id>/specs/` (cards_spec, encounter_spec,
   print_text), scenarios in `scenario_manifest.json` + `scenario_assignments.json`
   (docs/design/SCENARIO_SCHEMA.md), guide in `campaigns/<id>/guide.md` (official
   order, "Do not read until" gates, ```resolution fences), log in
   `log_layout.py`. Campaign rules for the Control token go in
   `src/tts/<id>_control.lua` (or modules under `src/<lua_dir>/` listed in
   build.json `lua_modules`); reuse The Still Hour's `src/StillHour/SCED.ttslua`,
   `ChaosBag.ttslua` and `Board.ttslua` patterns for SCED wiring.
6. **Wording passes.** Three independent sub-agent passes (Rules Reference audit,
   fix, verify + contradiction hunt across cards, guide and Control). Apply every
   finding or record why not.
7. **Official comparison.** Compare against the structure table in
   `docs/design/CAMPAIGN_DESIGN_LESSONS.md` section 1 (doom, acts and clue acts,
   location clues and shroud, locations, encounter deck size). For what that
   table does not cover, `python3 tools/official_compare/compare.py` gives the
   tool-only baselines (docs/design/OFFICIAL_COMPARISON.md shows how):
   connections (2.5 per location), enemies (~30%, fight/evade/health
   ~2.9/2.6/3.0, 1–3 elites), treacheries (~half "test or suffer", ~a third
   linger), chaos-bag changes over the campaign, XP. Tell the owner which gaps
   are missing and which are deliberate (numbers only); fix the missing ones.
8. **Balance.** Arithmetic models first (pipeline/simulate*.py are The Still
   Hour's; adapt the data tables). Then the play engine (`tools/play_engine`,
   docs/design/PLAYTEST_SIM.md): its TTS emulator, SCED table, AI, decks and XP
   tiers are reusable; the campaign's rules live in `lua/effects.lua`,
   `scenarios.lua`, `rules.lua` and `finale.lua` and must be written for the new
   campaign (budget real time for this). Calibrate with several levers (enemy
   stats, treachery mix, act costs, doom), not clue costs alone. Measure every
   scenario of each curve pair, later scenarios with that point's XP decks, the
   finale at 1–4 players (an integer goal moves 25–50 points; take the closest
   per count). Make the engine's AI work the hub/opening objective first (it
   moved win rates 17–27 points). Report every rate with an uncertainty
   interval, and judge difficulty on carried full-campaign runs, not only
   single-scenario presets. Publish before a final verification run; never
   publish while engine runs are going (the engine lays out the table from
   dist/). More: `docs/CAMPAIGN_PLAYBOOK.md` "Lessons".
9. **Build and test** (cloud checkout):
   ```bash
   export CAMPAIGN=<id>
   python3 pipeline/render_set_icons.py               # encounter-set symbols (build.json set_icon_shapes)
   python3 pipeline/scenario_content.py --lock        # every scenario LOCKED, 0 errors
   python3 pipeline/render_placeholders.py            # card faces (official frames)
   python3 pipeline/build_cards.py --local && python3 pipeline/bundle_mod.py --local
   python3 pipeline/compile_campaign.py               # the campaign box
   python3 pipeline/table_presence.py --local && python3 pipeline/package_download.py --local
                                                      # local package: dist/saved_object_<slug>.json
   lua5.4 pipeline/verify_control.lua dist/<slug>_bundle.lua runCampaignTests
   lua5.2 pipeline/verify_control.lua dist/<slug>_bundle.lua runCampaignTests
   python3 -m pytest -q tests                          # about 7 minutes
   ```
   TTS runs Lua 5.2-era code, so check both Lua versions. The suite tests The
   Still Hour (pinned by `tests/conftest.py` whatever `CAMPAIGN` says), the kit
   (`test_new_campaign.py`) and, read-only, the selected campaign's scenario
   audit (`test_selected_campaign.py`); it must pass with `CAMPAIGN=<id>`
   exported. `--local` builds are private checks: never commit them; step 11
   rebuilds `dist/` with hosted images.
   Look at every changed card face (contact sheets): text vs clue circles, enemy
   text vs the circle edge, numerals in their circles.
10. **Art track** (separate; owner's pace). Scenes in `campaigns/<id>/art_scenes.json`;
    `python3 pipeline/build_art_manifest.py`, then `python3 pipeline/chatgpt_art_pack.py`
    writes `campaigns/<id>/art/ART_PACK.md` (one request per ChatGPT chat, house
    style included). The owner saves images by number; `python3 pipeline/import_art.py
    --dir <folder>` imports them. Neutral-label reviews; flag visually revealing
    art first; art approval is not playtest approval.
11. **Publish.**
    `CAMPAIGN=<id> PUBLISH_COMMIT_TRAILER="<attribution lines>" python3 pipeline/publish_hosted.py`
    (commits the hosted images, rebuilds dist/), run the tests again, commit dist,
    push, fast-forward `main`. The Still Hour must still rebuild unchanged.
12. **Report** to the owner: results by scenario number (numbers only), what was
    validated and how, and the loading step: copy
    `dist/saved_object_<slug>.json` into
    `Documents\My Games\Tabletop Simulator\Saves\Saved Objects\` (their PC,
    Windows File Explorer), docs/LOADING.md.

## Done means

Every scenario LOCKED with 0 content errors; all tests and the Control check
pass; the curve met within a few points per pair (residuals reported); official
comparison gaps fixed or recorded as deliberate; guide PDF, log and saved object
published on `main`; production.json says what was validated. Then
`docs/CAMPAIGN_PLAYBOOK.md`'s "Lessons" gets anything new.
