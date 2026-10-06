# Arkhsm-LCG — THE STILL HOUR

An original loop-horror campaign for **Arkham Horror: The Card Game**, built as a
module for **SCED** (Super Complete Edition, Tabletop Simulator). The town of
Ambergrove repeats the same span of hours, and the investigators remember.

This repository is the **build**: card content as data, the campaign's custom
Lua for Tabletop Simulator, the pipeline that renders and packages it, and
**CardForge Studio**, the local app used to make it. The design documents live
in `docs/design/` and contain spoilers.

**To play:** load `dist/saved_object_the_still_hour.json` as a Saved Object in
SCED. See **`docs/LOADING.md`**. New here? Start with **`START_HERE.md`**.

The current finishing status and scenario difficulty results are in the
spoiler-free **[campaign handoff](docs/STILL_HOUR_HANDOFF.txt)**.

## Make a new campaign

Type `/new-campaign` with your idea in a Claude Code session on this repo; see
**`docs/NEW_CAMPAIGN.md`** (your checkpoints) and `docs/CAMPAIGN_PLAYBOOK.md`
(the process). `python3 tools/new_campaign.py <id> "<Name>"` scaffolds a
campaign that already builds; every build command takes `CAMPAIGN=<id>`.

## Layout

```
dist/                         generated; never edit by hand
  saved_object_the_still_hour.json   THE file to load in TTS (campaign box)
  cards/                      hosted card images (JPEG), referenced by commit hash
  guide/                      the typeset campaign guide PDF
  downloads/                  the same box for SCED's download mechanism (optional)
  the_still_hour_*.json       component builds the TTS relay spawns for tests
src/StillHour/                the campaign's Lua modules (bundled into the Control token)
  Constants.ttslua            thresholds scaled by investigator count
  CampaignState.ttslua        the single campaign state store + persistence
  Dissonance.ttslua           Dissonance bands and the [static] token count
  ChaosBag.ttslua             physical [static] tokens in SCED's chaos bag
  LoopFlags.ttslua            once-per-loop bookkeeping
  Hourglass.ttslua            the Hour clock
  Knowledge.ttslua            the Knowledge Track registry
  Locations.ttslua            which side of each campaign location is in play
  Appointed.ttslua            scripted behaviour for one encounter card
  Aging.ttslua                Years and age brackets
  Interlude.ttslua            the between-loops procedure and purchases
  Board.ttslua                table wiring: buttons, counters, card placement
  SCED.ttslua                 fail-safe adapter over SCED's public API
  Guide.ttslua                the Control token's "Guide: ..." menu (page numbers come from the guide PDF build)
src/tts/                      object scripts: Control entry, campaign log,
                              scenario/campaign boxes, download box
pipeline/                     specs, renderer, compiler and packagers (Python)
  publish_hosted.py           the release build: render, host images, rebuild dist/
cardforge/                    CardForge Studio (python3 cardforge/studio.py) + selftests
campaigns/                    per-campaign data (still_hour, plus hollow and demo)
tests/                        pytest suite, fake-TTS relay tests
tools/tts_relay/              automated in-game testing on the owner's PC
docs/                         loading, relay, workflow and build notes
```

## Build and test

```bash
python3 pipeline/publish_hosted.py         # the release build (see below)
python3 -m pytest -q tests                 # content, packaging, fake-TTS relay tests
python3 cardforge/selftest.py              # CardForge batch tool (seconds)
python3 cardforge/studio_selftest.py       # CardForge Studio end to end (~20-45 min)
lua5.4  pipeline/lua_smoketest.lua         # the Lua rules modules
lua5.4  pipeline/verify_bundle.lua         # the Control token in a stubbed TTS
python3 pipeline/scenario_content.py       # scenario readiness audit
python3 pipeline/simulate.py               # balance model
python3 pipeline/simulate_tempo.py         # pacing model
```

- **Release build.** `publish_hosted.py` renders every face, writes the card
  images to `dist/cards/`, commits them, and pins every image URL to that
  commit, then rebuilds all of `dist/`. The individual build scripts
  (`build_cards.py`, `bundle_mod.py`, `table_presence.py`,
  `package_download.py`) refuse to write placeholder or `file:///` image URLs
  into `dist/`; pass `--local` for a private test build that must not be
  committed.
- **Never squash- or rebase-merge a publish commit.** The hosted image URLs
  name that exact commit; rewriting it blanks every card face in TTS.
- **Selftests are sandboxed.** The CardForge selftests copy the repository to
  a temporary folder, run there, and delete the copy, so they never change
  tracked files or your generated art. The pytest suite does not write to
  tracked files either.
- Machine-specific backend settings go in `rig.local.json` (ignored by git;
  `rig.example.json` shows the shape). `rig.json` holds shared defaults only.

## Status

The campaign is content-complete and its art is complete. It passes its
offline checks (pytest suite, CardForge selftest, the Lua rules suite on Lua
5.2 and 5.4, the bundle check and the scenario audit). Current counts and
results live in `campaigns/still_hour/assistant/production.json` and the
[campaign handoff](docs/STILL_HOUR_HANDOFF.txt). Still to do before it is
released to the group:

- a real TTS relay run on the current build (`docs/TTS_RELAY.md`);
- the first playtest, and finishing the difficulty curve from real play.

Offline checks, computer-played games and relay passes are not playtest
approval. A one-page play aid for the table: `docs/QUICK_REFERENCE.md` (it
explains the campaign's systems; read it when you sit down to play).
