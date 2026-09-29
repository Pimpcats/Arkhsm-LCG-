# Unity test table — build plan (assistant-facing)

Superseded: the visual table is built with Godot instead (no Unity licence or
account needed); see docs/GODOT_TABLE.md. The plan below is kept for its
reasoning (AssetBundles, MoonSharp) in case a Unity table is ever wanted.

Goal: a local Tabletop-Simulator-like table, built in Unity inside the cloud
container, that loads SCED and The Still Hour, plays the campaign through the
owner's buttons, and captures screenshots for the assistant to review. The
owner never sees it: no screenshots, card names, rules or mechanics go into
chat or owner-facing docs.

## Why Unity
- TTS is a Unity game: same physics engine (PhysX), same AssetBundle format,
  so SCED's custom boards/tokens (AssetBundles on Steam's CDN) load as-is.
- TTS runs Lua on MoonSharp (C#); Unity + MoonSharp runs SCED's and our Lua
  exactly as TTS does (5.2 semantics, MoonSharp's json module and string
  extensions).

## Prerequisites (owner, one time)
1. Environment network access: Full, or allow download.unity3d.com,
   public-cdn.cloud.unity3d.com, hub.unity3d.com, packages.unity.com,
   license.unity3d.com, core.cloud.unity3d.com, api.unity.com,
   steamusercontent-a.akamaihd.net (+ any host the installer reports).
2. Environment variables UNITY_EMAIL and UNITY_PASSWORD (free Personal
   account). New session after adding them.

## Build steps
1. Install the Unity Linux editor (a 2019.4/2022 LTS close to TTS's runtime
   so AssetBundles load; verify the bundle version SCED's assets were built
   with) headless under Xvfb with Mesa llvmpipe; activate in batchmode with
   UNITY_EMAIL/UNITY_PASSWORD. Keep the install outside the repo.
2. Unity project in tools/unity_table/ (only source, no Library/): MoonSharp
   from NuGet; a C# TTS API layer ported from tests/sced_real/tts_emu.lua
   (objects/GUIDs, per-object script environments, bags/decks, Wait,
   Physics.cast via real raycasts, buttons/inputs as world-space UI, XML UI
   via uGUI, JSON, Vector/Color); save-game loader for SCED's objects/ tree
   (tests/sced_real/sced_table.py assembles it) and for
   dist/saved_object_the_still_hour.json; card meshes with face/back
   textures from the hosted card images; AssetBundle loader for SCED models.
3. Driver: run tests/sced_real/playthrough.lua and tools/tts_relay/
   ingame_runner.lua inside the Unity table (same suites as the headless
   harness and the owner's relay), capture a screenshot after every step
   (top-down + TTS default camera), write results + screenshots to a
   gitignored folder the assistant reviews.
4. pytest wrapper that skips when the Unity build is absent.

## Owner-facing output rule
Only "N passed, M failed" and plain next steps. Everything else stays with
the assistant.
