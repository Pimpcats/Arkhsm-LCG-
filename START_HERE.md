# THE STILL HOUR — START HERE
*Drop this in the Claude Project knowledge folder first. It orients any chat in 60 seconds.*

## What this is
An **original Arkham Horror LCG campaign**, "The Still Hour," built as a module for the **SCED** Tabletop Simulator mod. A time-loop cosmic-horror campaign for **3 investigators** (scales 1–4).

## Run the app (one click)

Double-click in the repo folder:
- **Windows** — `Start CardForge.bat`
- **macOS** — `Start CardForge.command`
- **Linux** — `./start-cardforge.sh`

It finds Python, installs Pillow on first run, starts the studio and opens
<http://127.0.0.1:8570> in your browser. Close the window (or Ctrl-C) to stop.
Manual equivalent: `python3 cardforge/studio.py`.

## Where the code lives
- **Repo:** `github.com/Pimpcats/Arkhsm-LCG-` (public)
- **Working branch:** `claude/new-session-r230bz` ← everything is here. **`main` is just a stub README — do not read `main`.**
- Point Claude Code / any repo reader at that branch.

## The design in five lines
1. **Time loop.** You play one night; it resets; you carry what you remembered. The reset is the heartbeat.
2. **Memory = XP** (shared pool, soft cap `6 × investigators` = 18 at 3p). Buys level-ups (1/level) **and** Recollections (their `memoryCost`).
3. **Dissonance** rises when you use foreknowledge; the **Appointed** climbs a staged Approach (Unseen → Sensed → Emerging → Arrived) driven by the clock and the Dissonance bands — entering Noticed (`4 × n`, 12 at 3p) drives it to Arrived; at `6 × n` (18) the loop resets (CO-002).
4. **Knowledge Track** — facts unlocked by district objectives; they permanently edit the night. You must loop to fill it.
5. **Aging is the finale's cost.** Every loop adds Years; brackets drift body→mind; the finale's ending is gated by the party's Age. The contest target is `4 × n` (12 at 3p).

## Build status (see `REPO_BUILD_STATUS.md` for detail)
- ✅ **Design frozen** — all docs below.
- ✅ **P1–P8 all built & tested offline** (99-assertion suite + 39 in-bundle). Loadable mod at `dist/the_still_hour_mod.json`; download-box package in `dist/downloads/`.
- ✅ **CO-001 applied** (contest `4 * n`, Memory-as-XP) and **CO-002 applied** (the staged Appointed, renamed from Latecomer).
- ⏳ **Pending:** the real in-TTS load test · per-system board wiring (Appointed board callbacks, location card flips, interlude buy panel) · uploading the download-box release asset.
- 🎨 **Art:** not started. Pipeline speced (CardForge tool → ComfyUI/A1111/Krea → Strange Eons → sheets → CDN → `build_cards.py`).

## File map (this Project folder)
**Design (source of truth):** `THE_STILL_HOUR_design*` (concept) · `*_cards_v0_2` (investigators, signatures, weaknesses, Recollections — exact wording) · `*_aging_3p_v0_3` (Aging + 3p constants) · `*_encounter_v0_4` (encounter deck, Occultation, Appointed) · `*_campaign_guide_v0_5` (every scenario, finale) · `*_log_sheet` (campaign log).
**Change orders:** `CO-001_change_order` (contest 4n + Memory-as-XP — applied) · `CO-002_the_appointed` (staged Appointed — applied).
**Build briefs:** `SCED_BUILD_BRIEF` (the module) · `ART_SPEC` + `ART_PIPELINE_BRIEF` + `CARDFORGE_BRIEF` (art).
**Build state (from repo):** `REPO_BUILD_STATUS` · `REPO_INTEGRATION` (host-object wiring) · `REPO_LOADING` (how to load in TTS).
**Scaffolds:** `build_cards.py` / `stillhour_cards_spec.json` / `stillhour_starter.json` (note: repo's `pipeline/build_cards.py` is the newer authoritative version) · `build_art_manifest.py` + `art_manifest_starter.json` + `art_profiles.json` + `cardforge_stub.py` (art tooling) · `THE_STILL_HOUR_flow.html` (systems infographic).

## How to continue
Hand the next task to **Claude Code** against `Pimpcats/Arkhsm-LCG-` @ `claude/new-session-r230bz`. P1–P8 are done; next up: the **in-TTS load test** (load `dist/the_still_hour_mod.json`, click Run Tests), then the board wiring (Appointed callbacks, location card flips, interlude panel) and the art pipeline.
