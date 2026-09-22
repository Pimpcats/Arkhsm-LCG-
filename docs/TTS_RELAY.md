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
   irm https://raw.githubusercontent.com/Pimpcats/Arkhsm-LCG-/claude/campaign-art-tts-testing-w2yabf/tools/tts_relay/start-relay.ps1 | iex
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
   un-sealing; the Appointed card manifesting at the farthest location, Hold
   Back, returning when put in a bag, hunting), and dealing a card. Best run on
   a fresh SCED table: other locations/minicards already on the table take part
   in "farthest" and "prey". It also moves the
   camera over each object so the relay can screenshot the TTS window.
4. Commits `runs/<time>_<commit>/{results.json,log.txt,screenshots/}` plus
   `latest.json` to the `tts-results` branch and pushes it.

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
