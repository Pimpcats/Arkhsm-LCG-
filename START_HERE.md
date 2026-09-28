# THE STILL HOUR — START HERE
*Drop this in the Claude Project knowledge folder first. It orients any chat in 60 seconds. Spoiler-free.*

## What this is
An **original Arkham Horror LCG campaign**, "The Still Hour," built as a module for the **SCED** Tabletop Simulator mod. A time-loop cosmic-horror campaign tuned for **3 investigators** (plays 1–4).

The owner is playing it as a **first-time player**: keep story spoilers (card effects, enemy roles, twists, solutions, endings) out of chat and out of owner-facing docs. The design documents in `docs/design/` are spoilers.

## Play it
Load `dist/saved_object_the_still_hour.json` as a Saved Object in SCED. Step by step: **`docs/LOADING.md`**. Card images load from GitHub, so the file works on any PC.

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

## Status (2026-09-27)
- ✅ Campaign content, rules wording passes, balance models, guide PDF and campaign log built; offline checks green (pytest, CardForge selftests, Lua rules suite, bundle check, scenario audit). Counts: `campaigns/still_hour/assistant/production.json`.
- ✅ Card art: the illustrations are approved and composited into the faces in `dist/`, except six still to generate (below).
- ⏳ **Pending:**
  1. a real **TTS relay run on the current head** (owner, local PowerShell; `docs/TTS_RELAY.md`);
  2. **six illustrations** via the ChatGPT art pack's "remaining" request (`docs/CHATGPT_ART_PACK.md`, `pipeline/chatgpt_art_pack.json`);
  3. the owner's **first playtest**.
- Relay passes and offline checks are not playtest approval.

## File map
**Owner docs:** `docs/LOADING.md` (load in TTS) · `docs/TTS_RELAY.md` (automated in-game test) · `docs/CHECKLIST.md` (status) · `docs/HANDOFF.md` (next session).
**Assistant/designer docs (spoilers):** `docs/ASSISTANT_WORKFLOW.md` (read first) · `docs/CAMPAIGN_PLAYBOOK.md` · `docs/BUILD_STATUS.md` · `docs/design/` (design, change orders, audits).
**State:** `campaigns/still_hour/assistant/production.json` (current counts, validation, next actions).

## How to continue
Hand the next task to **Claude Code** against `Pimpcats/Arkhsm-LCG-` @ `main`; it reads `AGENTS.md` and `docs/ASSISTANT_WORKFLOW.md` first. Next up: the relay run on the current head, the six remaining illustrations, then the first playtest.
