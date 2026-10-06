# THE STILL HOUR — START HERE
*Drop this in the Claude Project knowledge folder first. It orients any chat in 60 seconds. Spoiler-free.*

## What this is
An **original Arkham Horror LCG campaign**, "The Still Hour," built as a module for the **SCED** Tabletop Simulator mod. A time-loop cosmic-horror campaign tuned for **3 investigators** (plays 1–4).

The owner is playing it as a **first-time player**: keep story spoilers (card effects, enemy roles, twists, solutions, endings) out of chat and out of owner-facing docs. The design documents in `docs/design/` are spoilers.

## Play it
Load `dist/saved_object_the_still_hour.json` as a Saved Object in SCED. Step by step: **`docs/LOADING.md`**. Card images load from GitHub, so the file works on any PC.

Deck building: **`docs/STARTER_DECKS.md`** has an optional, legal 30-card starting deck for each of the five investigators (suggestions only; the guide carries the same lists as an appendix).

If Place stops Tabletop Simulator: **`docs/PLACE_TEST.md`** (a small Saved Object that finds out why; five buttons, then the last 60 lines of `Player.log`).

At the table: **`docs/QUICK_REFERENCE.md`** is a one-page play aid (round structure and the campaign's own terms, each pointing to the guide section). It explains how the campaign's systems work, so read it when you sit down to play, not before.

## Run the app (one click)

Double-click in the repo folder:
- **Windows** — `Start CardForge.bat`
- **macOS** — `Start CardForge.command`
- **Linux** — `./start-cardforge.sh`

It finds Python, installs Pillow on first run, starts CardForge Studio and opens
<http://127.0.0.1:8570> in your browser. Close the window (or Ctrl-C) to stop.
Manual equivalent: `python3 cardforge/studio.py`. Local image backends are
optional; their machine-specific settings live in `rig.local.json`.

## Where the code lives
- **Repo:** `github.com/Pimpcats/Arkhsm-LCG-` (public)
- **Working branch:** `main`. It is current: all earlier branches were folded into it (2026-09-22) and later work is merged there.
- Point Claude Code / any repo reader at `main`. GitHub access is not access to the owner's running desktop app or Tabletop Simulator.

## The systems in brief (what the player guide teaches)
- **Time loop.** You play one night; it resets; you keep what you remembered.
- **Memory** is the campaign's experience: it buys upgrades between loops.
- **Dissonance** tracks how hard you lean on what you know.
- **Knowledge** — facts you earn that change later nights.
- **Aging** — living the same night again has a cost.

## Status (2026-10-02)
- ✅ Campaign content, rules wording passes, guide PDF and campaign log built; offline checks pass (pytest suite, CardForge selftest, Lua rules suite on Lua 5.2 and 5.4, bundle check, scenario audit). Current counts and results: `campaigns/still_hour/assistant/production.json`; summary: `docs/STILL_HOUR_HANDOFF.txt`.
- ✅ Card art: complete. Every illustration is approved and composited into the faces in `dist/`.
- ✅ Campaign log: names you have not earned yet stay hidden until you tick them (already built in).
- ⏳ **Pending:**
  1. a real **TTS relay run on the current build** (owner, local PowerShell; `docs/TTS_RELAY.md`);
  2. the owner's **first playtest**;
  3. finishing the difficulty curve from real play (the computer-played results do not yet match every target).
- Relay passes, computer-played games and offline checks are not playtest approval.

## File map
**Owner docs:** `docs/LOADING.md` (load in TTS) · `docs/PLACE_TEST.md` (if Place stops TTS) · `docs/QUICK_REFERENCE.md` (play aid; read at the table) · `docs/STARTER_DECKS.md` (optional ready-made 30-card starting decks for all five investigators) · `docs/TTS_RELAY.md` (automated in-game test) · `docs/CHECKLIST.md` (status) · `docs/HANDOFF.md` (next session).
**Assistant/designer docs (spoilers, do not read as a player):** `docs/ASSISTANT_WORKFLOW.md` (read first) · `docs/CAMPAIGN_PLAYBOOK.md` · `docs/BUILD_STATUS.md` · `docs/BALANCE.md` · `docs/ART_HANDOFF.md` · `docs/design/` (design, change orders, audits, the campaign guide source).
**State:** `campaigns/still_hour/assistant/production.json` (current counts, validation, next actions).

## How to continue
Hand the next task to **Claude Code** against `Pimpcats/Arkhsm-LCG-` @ `main`; it reads `AGENTS.md` and `docs/ASSISTANT_WORKFLOW.md` first. Next up: the relay run on the current build, then the first playtest.
