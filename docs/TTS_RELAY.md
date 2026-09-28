# TTS relay: automated in-game testing on the owner's PC

The build is made in a cloud session that cannot reach the owner's computer.
The relay closes that gap using GitHub as the go-between:

```
cloud session ──push build──▶ GitHub branch ──relay pulls──▶ owner's PC
                                                              │  TTS External Editor API
                                                              ▼  (localhost 39999 / 39998)
cloud session ◀──reads── tts-results branch ◀──relay pushes── Tabletop Simulator
```

## Owner: start it (Windows, local PowerShell)

1. Open Tabletop Simulator and load a game (the SCED Arkham mod).
2. In **local PowerShell** on the same PC, run:

   ```powershell
   irm https://raw.githubusercontent.com/Pimpcats/Arkhsm-LCG-/main/tools/tts_relay/start-relay.ps1 | iex
   ```

   Or double-click `Start TTS Relay.bat` in the repo folder.
3. Leave both open. Turn off PC sleep. Keep TTS visible for screenshots.

Needs Git and Python 3.8+ (both already used by CardForge). The first results
push may open a GitHub sign-in window once. Close Atom or the VS Code TTS
extension first because they use the same port (39998).

## What a run does

For each new commit on the watched branch:

1. Pulls it into `%USERPROFILE%\StillHourRelay\repo` (a private clone; the
   owner's own checkout is never touched).
2. Reads `tools/tts_relay/job.json`, then sends the listed `dist/` objects and
   `tools/tts_relay/ingame_runner.lua` into TTS ("Execute Lua Code").
3. The runner checks the build in the live game and reports each result back.
   It checks spawning, SCED card metadata, hosted image URLs, the control
   token's rules tests, save/reload, the board wiring (touchable counters and
   their persistence; `[static]` tokens entering/leaving SCED's chaos bag and a
   drawn one raising Dissonance; two test location cards flipping and
   un-sealing; the scripted encounter card's buttons and placement; Aging on
   an investigator card and its SCED skill tracker;
   the state riding in the campaign log through a simulated SCED export), and
   dealing a card. With the table payload (`dist/the_still_hour_table.json`) it
   also presses the campaign box's Place, checks the minicards / campaign guide /
   campaign log it lays out (log clicks, save+reload, page turn, sync from the
   campaign state), screenshots the log, and presses Recall. Best run on a fresh
   SCED table: other locations/minicards already on the table take part in
   "farthest" and "prey". It also moves the
   camera over each object so the relay can screenshot the TTS window.
4. Commits `runs/<time>_<commit>/{results.json,log.txt,screenshots/}` plus
   `latest.json` to the `tts-results` branch and pushes it.

The relay watches `main` (the working branch) by default. If a watched branch
no longer exists (merged and deleted), the relay and its launcher fall back to
`main`. Card images and the guide are hosted at the commit that holds them
(`pipeline/publish_hosted.py`), so deleting a branch never blanks the faces in
TTS, as long as that commit survives the merge: **never squash- or
rebase-merge a publish commit**.

Only objects tagged `StillHourRelay` (the ones the relay spawned) are ever
removed. Only Lua from the watched commit is sent to TTS. The relay never runs
repository code on the PC itself.

## Assistant: reading results

```bash
git fetch origin tts-results
git show origin/tts-results:latest.json
git show origin/tts-results:runs/<run>/log.txt
```

The `verdict` is `pass`, `fail`, `incomplete` (the runner never reported
`done`, usually because of a Lua error) or `relay_error` (bad job file). A pass
here means the scripted checks passed in real TTS. It is not a playtest.

## Changing what gets tested

Edit `tools/tts_relay/job.json` (payload files, timeout) or
`tools/tts_relay/ingame_runner.lua` (add a `step(...)`), then push. The next run
uses them automatically.

## Offline test of the relay itself

`tests/test_tts_relay.py` drives the real relay against a fake TTS
(`tests/tts_fake/`), once on a vanilla table and once on a minimal SCED stand-in
(`tests/tts_fake/sced/`, built by `sced_fixture.py`: SCED's Global chaos-bag
functions, the GUID reference handler and the Mythos objects its APIs use). The fake speaks the same socket protocol and runs the
runner and the bundled control token under Lua 5.2 with a mocked TTS API. It
uses a local bare repo in place of GitHub.

```bash
python3 -m pytest -q tests/test_tts_relay.py      # needs lua5.2
```

## Headless SCED harness (no Tabletop Simulator needed)

`tests/sced_real/` plays the campaign on a stand-in for Tabletop Simulator,
so integration bugs show up before a relay run. It boots SCED's real table
(Global and every scripted object, with SCED's own scripts), spawns
`dist/saved_object_the_still_hour.json` the way the owner does, and then plays
Campaign Setup, the Prologue, a loop, an interlude, Part II and the start of
the finale using only what the owner touches: the Control token's buttons,
each box's Place, the campaign log's boxes and page menu, and moving cards by
hand. Along the way it checks SCED's real chaos bag after each difficulty
button and Dissonance change, where every box lays its cards (SCED's agenda,
act, encounter and scenario-card spots, inside the play area, no overlaps,
nothing dropped on or into SCED's own objects), deck sizes, that Clear Board
takes exactly what the boxes laid out (and the tokens on those cards) and
leaves SCED's table alone, the log-to-Control link, and a full save and
reload. Any Lua error, from the campaign or from SCED reacting to it, fails the
step. It also runs this relay's own in-game suite (`ingame_runner.lua`) on the
same emulated table, so both environments share one suite.

```bash
python3 -m pytest -q tests/test_sced_real.py      # lua5.2 and lua5.4
python3 tests/sced_real/run.py                    # readable PASS/FAIL list
python3 tests/sced_real/run.py --fake             # without SCED (stand-in)
```

SCED is pinned at commit `0e12534` (argonui/SCED). The harness uses, in order:
`$SCED_DIR`, a local clone at `/home/user/argonui/sced`,
or a copy it fetches into the git-ignored `.cache/sced/`. Without any of them
the real-SCED tests are skipped (set `SCED_REAL=0` to skip them on purpose);
the stand-in tests (the minimal SCED fixture above, laid out where SCED keeps
its objects) always run.

What it can NOT catch: anything visual (rendering, card faces, image loading,
the PDF), TTS physics and snapping beyond "lands on the highest thing under
it" (bounds are approximate), XML UI (tracked, never drawn), timing that
depends on real frame rates or downloads, and differences between the pinned
SCED and the SCED version installed on the owner's PC. A pass is not a
playtest and does not replace a relay run in real TTS.
